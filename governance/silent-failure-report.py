#!/usr/bin/env python3
"""Read-only report of silent-failure findings in tracked portfolio Python files.

Only immediate child Git repositories of --projects-root are examined. Findings
never make this dry run fail; incomplete enumeration or scanning exits with 2.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path


def load_scanner():
    path = Path(__file__).parent / "validators" / "silent-failure-check.py"
    name = "portfolio_silent_failure_scanner"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load silent-failure scanner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    source = path.read_bytes()
    # Import only this fixed sibling module, from the exact bytes being hashed.
    exec(compile(source, str(path), "exec"), module.__dict__)  # noqa: S102
    module._REPORT_SOURCE_SHA256 = hashlib.sha256(source).hexdigest()
    return module


def git_output(repo, *args):
    # Respect each repository rather than inherited Git worktree/index overrides.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    result = subprocess.run(
        ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repo), *args],
        env=env, check=True, capture_output=True, timeout=30,
    )
    return result.stdout


def read_head(repo):
    """Return the commit SHA, or None for a verified unborn branch."""
    try:
        return git_output(repo, "rev-parse", "--verify", "--quiet", "HEAD^{commit}").decode("ascii").strip()
    except subprocess.CalledProcessError as head_error:
        if head_error.returncode != 1:
            raise
        # Quiet rev-parse also fails for damaged refs. An unborn branch must be
        # symbolic and its target ref must be absent, rather than invalid.
        branch = os.fsdecode(git_output(repo, "symbolic-ref", "--quiet", "HEAD")).strip()
        try:
            git_output(repo, "show-ref", "--verify", "--quiet", branch)
        except subprocess.CalledProcessError as ref_error:  # governance: allow-silent SF002: absent branch ref is reported as unborn HEAD with a warning
            if ref_error.returncode == 1:
                return None
            raise
        raise


def add_error(report, project, path, category, error):
    # Exception messages (including SyntaxError and git stderr) may contain source
    # or local configuration. Report the failure type, never that raw content.
    report["errors"].append({
        "project": project, "path": path, "category": category,
        "message": type(error).__name__,
    })


def safe_tracked_path(repo, relative):
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or ".." in parts:
        raise ValueError("Tracked path is outside repository")
    candidate = repo
    for part in parts:
        candidate = candidate / part
        if stat.S_ISLNK(candidate.lstat().st_mode):
            raise ValueError("Tracked path contains a symlink")
    if not stat.S_ISREG(candidate.lstat().st_mode):
        raise ValueError("Tracked path is not a regular file")
    if not candidate.resolve().is_relative_to(repo.resolve()):
        raise ValueError("Tracked path resolves outside repository")
    return candidate


def build_report(projects_root, scanner=None):
    report = {
        "schema_version": 1,
        "mode": "dry-run",
        "scanner_sha256": None,
        "snapshot": "Current tracked working-tree files, including staged files before the first commit; HEAD and tracked dirty state recorded before scanning. A null HEAD with head_state=unborn means no commit exists. Concurrent edits are not locked.",
        "projects": [], "findings": [], "errors": [], "warnings": [],
    }
    root = Path(projects_root).expanduser()
    try:
        if not root.is_dir():
            raise NotADirectoryError("Invalid projects root")
        children = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError as error:
        add_error(report, None, None, "projects-root", error)
        return finish_report(report)

    if scanner is None:
        try:
            scanner = load_scanner()
        except (OSError, SyntaxError, UnicodeError, ImportError) as error:
            add_error(report, None, None, "scanner-load", error)
            return finish_report(report)
    report["scanner_sha256"] = getattr(scanner, "_REPORT_SOURCE_SHA256", None)

    for repo in children:
        try:
            if not stat.S_ISDIR(repo.lstat().st_mode):
                continue
            marker = repo / ".git"
            try:
                marker.lstat()
            except FileNotFoundError:
                continue
        except OSError as error:
            add_error(report, repo.name, None, "repository-discovery", error)
            continue
        project = {
            "name": repo.name, "head": None, "head_state": None, "tracked_dirty": None,
            "tracked_python_files": 0, "scanned_python_files": 0,
        }
        report["projects"].append(project)
        try:
            project["head"] = read_head(repo)
            project["head_state"] = "unborn" if project["head"] is None else "committed"
            if project["head_state"] == "unborn":
                report["warnings"].append({
                    "project": repo.name,
                    "message": "Repository has no commits; scanning the current tracked working-tree files with no committed snapshot",
                })
            project["tracked_dirty"] = bool(git_output(repo, "status", "--porcelain=v1", "-z", "--untracked-files=no"))
            raw_paths = git_output(repo, "ls-files", "-z", "--", "*.py")
            paths = sorted({os.fsdecode(path) for path in raw_paths.split(b"\0") if path})
        except (OSError, subprocess.SubprocessError, UnicodeError) as error:
            add_error(report, repo.name, None, "git", error)
            continue
        project["tracked_python_files"] = len(paths)
        if not paths:
            report["warnings"].append({"project": repo.name, "message": "Repository has zero tracked Python files"})
        for relative in paths:
            display_path = f"{repo.name}/{relative}"
            try:
                candidate = safe_tracked_path(repo, relative)
            except (OSError, ValueError) as error:
                add_error(report, repo.name, display_path, "unsafe-path", error)
                continue
            try:
                findings = scanner.scan_file(candidate)
                converted = [{
                    "path": display_path, "line": item["line"],
                    "column": item["column"], "rule": item["rule"],
                    "message": item["message"],
                } for item in findings]
            except (OSError, SyntaxError, UnicodeError, ValueError, TypeError, KeyError) as error:
                add_error(report, repo.name, display_path, "scan", error)
                continue
            report["findings"].extend(converted)
            project["scanned_python_files"] += 1
    if not report["projects"]:
        add_error(report, None, None, "repositories", FileNotFoundError("No child repositories"))
    return finish_report(report)


def finish_report(report):
    report["findings"].sort(key=lambda item: (item["path"], item["line"], item["column"], item["rule"]))
    report["summary"] = {
        "projects": len(report["projects"]),
        "tracked_python_files": sum(project["tracked_python_files"] for project in report["projects"]),
        "scanned_python_files": sum(project["scanned_python_files"] for project in report["projects"]),
        "findings": len(report["findings"]),
        "errors": len(report["errors"]), "warnings": len(report["warnings"]),
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-root", required=True, type=Path)
    parser.add_argument("--json", action="store_true", help="Print the complete structured report")
    args = parser.parse_args(argv)
    report = build_report(args.projects_root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(f"Dry run: {summary['projects']} projects, {summary['scanned_python_files']} Python files, "
              f"{summary['findings']} findings, {summary['errors']} errors")
        for finding in report["findings"]:
            print(f"{finding['path']}:{finding['line']}:{finding['column']}: {finding['rule']} {finding['message']}")
        for warning in report["warnings"]:
            print(f"Warning: {warning['project']}: {warning['message']}", file=sys.stderr)
        for error in report["errors"]:
            print(f"Error: {error['path'] or error['project'] or 'portfolio'}: {error['category']} ({error['message']})", file=sys.stderr)
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

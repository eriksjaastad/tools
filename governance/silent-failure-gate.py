#!/usr/bin/env python3
"""Block on silent-failure findings in one repository's tracked Python files.

    uv run governance/silent-failure-gate.py [--repo PATH]

Scans every tracked .py/.pyi file's working-tree content, as in a CI checkout
(scripts/local-checks.sh runs it on every push). Exit 1 for findings, 2 for
scan or enumeration errors, unsafe paths, or no Python files at all. It is not
a staged-index pre-commit check; governance-check.sh runs
silent-failure-check.py --staged for that.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tokenize


def load_reporter():
    path = Path(__file__).with_name("silent-failure-report.py")
    spec = importlib.util.spec_from_file_location("silent_failure_gate_reporter", path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load repository scan helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_repository(repo):
    result = {"findings": [], "errors": [], "scanned_python_files": 0}
    try:
        reporter = load_reporter()
        scanner = reporter.load_scanner()
        root = Path(os.fsdecode(reporter.git_output(repo, "rev-parse", "--show-toplevel")).removesuffix("\n"))
        paths = reporter.git_output(root, "ls-files", "-z").split(b"\0")
    except (OSError, ValueError, ImportError, SyntaxError, UnicodeError, subprocess.SubprocessError) as error:
        result["errors"].append({"path": ".", "error": type(error).__name__})
        return result
    for relative in sorted(set(os.fsdecode(path) for path in paths if path)):
        if Path(relative).suffix.lower() not in {".py", ".pyi"}:
            continue
        try:
            path = reporter.safe_tracked_path(root, relative)
            findings = scanner.scan_file(path)
            for finding in findings:
                finding["path"] = relative
            result["findings"].extend(findings)
            result["scanned_python_files"] += 1
        except (OSError, ValueError, UnicodeError, SyntaxError, tokenize.TokenError) as error:
            result["errors"].append({"path": relative, "error": type(error).__name__})
    if result["scanned_python_files"] == 0:
        result["errors"].append({"path": ".", "error": "NoPythonFilesScanned"})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="Repository to scan; defaults to current directory")
    args = parser.parse_args(argv)
    result = check_repository(args.repo)
    print(json.dumps(result, sort_keys=True))
    if result["errors"]:
        return 2
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())

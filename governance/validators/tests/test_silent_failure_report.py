"""Portfolio dry-run tests use temporary repositories and no external services."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPORT_SCRIPT = Path(__file__).resolve().parents[2] / "silent-failure-report.py"
SWALLOWED = "try:\n    work()\nexcept Exception:\n    pass\n"


@pytest.fixture
def reporter():
    spec = importlib.util.spec_from_file_location("silent_failure_report_test", REPORT_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({
        "GIT_AUTHOR_NAME": "Offline Test", "GIT_COMMITTER_NAME": "Offline Test",
        "GIT_AUTHOR_EMAIL": "offline@example.invalid", "GIT_COMMITTER_EMAIL": "offline@example.invalid",
    })
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
        env=env, text=True, capture_output=True, check=True, timeout=15,
    ).stdout.strip()


def make_repo(root, name="project", files=None):
    repo = root / name
    repo.mkdir(parents=True)
    git(repo, "init", "--quiet")
    for relative, source in (files or {"app.py": "answer = 42\n"}).items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    git(repo, "add", "--", ".")
    git(repo, "commit", "--quiet", "-m", "Offline fixture")
    return repo


def run_report(root, expected_code=0):
    try:
        result = subprocess.run(
            [sys.executable, str(REPORT_SCRIPT), "--projects-root", str(root), "--json"],
            text=True, capture_output=True, check=True, timeout=30,
        )
    except subprocess.CalledProcessError as error:
        assert error.returncode == expected_code, error.stderr
        return json.loads(error.stdout)
    assert expected_code == 0, "Dry run unexpectedly succeeded"
    return json.loads(result.stdout)


def test_clean_report_records_head_and_scans_current_tracked_files(tmp_path, reporter):
    repo = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    first = reporter.build_report(tmp_path)
    assert first["summary"] == {
        "projects": 1, "tracked_python_files": 1, "scanned_python_files": 1,
        "findings": 0, "errors": 0, "warnings": 0,
    }
    assert first["projects"][0]["head"] == head
    scanner_path = REPORT_SCRIPT.parent / "validators" / "silent-failure-check.py"
    assert first["scanner_sha256"] == hashlib.sha256(scanner_path.read_bytes()).hexdigest()
    assert first["projects"][0]["tracked_dirty"] is False
    (repo / "app.py").write_text(SWALLOWED)
    changed = reporter.build_report(tmp_path)
    assert changed["projects"][0]["tracked_dirty"] is True
    assert changed["projects"][0]["head"] == head
    assert len(changed["findings"]) == 1


def test_findings_are_nonblocking_and_do_not_include_source(tmp_path):
    make_repo(tmp_path, files={"app.py": SWALLOWED + "sentinel_source_should_not_be_reported = 42\n"})
    report = run_report(tmp_path)
    assert report["mode"] == "dry-run"
    assert report["summary"]["findings"] == 1
    assert report["findings"][0]["path"] == "project/app.py"
    assert "sentinel_source_should_not_be_reported" not in json.dumps(report)


def test_invalid_python_is_an_error_without_source_contents(tmp_path):
    make_repo(tmp_path, files={"broken.py": "sentinel_private_source = (\n"})
    report = run_report(tmp_path, expected_code=2)
    assert report["errors"] == [{
        "project": "project", "path": "project/broken.py", "category": "scan", "message": "SyntaxError",
    }]
    assert "sentinel_private_source" not in json.dumps(report)


def test_missing_tracked_file_fails_visibly(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "app.py").unlink()
    report = run_report(tmp_path, expected_code=2)
    assert report["summary"]["errors"] == 1
    assert report["errors"][0]["message"] == "FileNotFoundError"
    assert report["summary"]["scanned_python_files"] == 0


def test_unreadable_file_is_an_explicit_error(tmp_path, reporter):
    make_repo(tmp_path)

    def unreadable(path):
        raise PermissionError("sentinel-private-detail")

    report = reporter.build_report(tmp_path, scanner=SimpleNamespace(scan_file=unreadable))
    assert report["errors"][0]["message"] == "PermissionError"
    assert "sentinel-private-detail" not in json.dumps(report)


def test_spaces_and_zero_python_warning_have_deterministic_order(tmp_path):
    make_repo(tmp_path, "z project", {"file with spaces.py": SWALLOWED, "a.py": SWALLOWED})
    make_repo(tmp_path, "a project", {"README.md": "No Python here\n"})
    report = run_report(tmp_path)
    assert [project["name"] for project in report["projects"]] == ["a project", "z project"]
    assert [item["path"] for item in report["findings"]] == ["z project/a.py", "z project/file with spaces.py"]
    assert report["warnings"] == [{"project": "a project", "message": "Repository has zero tracked Python files"}]
    assert run_report(tmp_path) == report


@pytest.mark.parametrize("root_kind", ["empty", "missing", "file"])
def test_invalid_root_or_zero_repositories_exit_nonzero(tmp_path, root_kind):
    root = tmp_path / "root"
    if root_kind == "empty":
        root.mkdir()
    elif root_kind == "file":
        root.write_text("not a directory")
    report = run_report(root, expected_code=2)
    assert report["summary"]["projects"] == 0
    assert report["summary"]["errors"] == 1


def test_git_failure_is_recorded_and_other_projects_still_scan(tmp_path):
    invalid = tmp_path / "broken"
    (invalid / ".git").mkdir(parents=True)
    make_repo(tmp_path, "valid")
    report = run_report(tmp_path, expected_code=2)
    assert report["errors"][0]["category"] == "git"
    assert report["errors"][0]["project"] == "broken"
    assert report["summary"]["scanned_python_files"] == 1


@pytest.mark.parametrize("staged_python", [False, True])
def test_unborn_repository_is_scanned_with_explicit_snapshot_warning(tmp_path, staged_python):
    repo = tmp_path / "unborn"
    repo.mkdir()
    git(repo, "init", "--quiet")
    if staged_python:
        (repo / "staged.py").write_text(SWALLOWED)
        git(repo, "add", "--", "staged.py")
    report = run_report(tmp_path)
    assert report["projects"][0]["head"] is None
    assert report["projects"][0]["head_state"] == "unborn"
    assert report["projects"][0]["tracked_dirty"] is staged_python
    assert report["summary"]["scanned_python_files"] == int(staged_python)
    assert report["summary"]["findings"] == int(staged_python)
    assert report["errors"] == []
    assert "no committed snapshot" in report["warnings"][0]["message"]
    if not staged_python:
        assert "zero tracked Python" in report["warnings"][1]["message"]


def test_corrupt_branch_is_not_misreported_as_unborn(tmp_path):
    repo = make_repo(tmp_path)
    branch = git(repo, "symbolic-ref", "HEAD")
    (repo / ".git" / branch).write_text("f" * 40 + "\n")
    report = run_report(tmp_path, expected_code=2)
    assert report["errors"][0]["category"] == "git"
    assert report["projects"][0]["head_state"] is None
    assert report["warnings"] == []


def test_unreadable_repository_discovery_is_an_explicit_error(tmp_path, reporter, monkeypatch):
    repo = make_repo(tmp_path)
    original_lstat = Path.lstat

    def unreadable(path):
        if path == repo:
            raise PermissionError("sentinel-private-detail")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", unreadable)
    report = reporter.build_report(tmp_path)
    assert report["errors"][0] == {
        "project": "project", "path": None, "category": "repository-discovery", "message": "PermissionError",
    }
    assert "sentinel-private-detail" not in json.dumps(report)


def test_unreadable_root_enumeration_is_an_explicit_error(tmp_path, reporter, monkeypatch):
    def unreadable(path):
        raise PermissionError("sentinel-private-detail")

    monkeypatch.setattr(Path, "iterdir", unreadable)
    report = reporter.build_report(tmp_path)
    assert report["errors"] == [{
        "project": None, "path": None, "category": "projects-root", "message": "PermissionError",
    }]


def test_only_tracked_python_in_immediate_repos_is_read(tmp_path, reporter):
    root = tmp_path / "portfolio"
    repo = make_repo(root, files={"app.py": "answer = 42\n", ".gitignore": "ignored.py\n", "notes.txt": "not Python"})
    (repo / "untracked.py").write_text("invalid untracked Python !")
    (repo / "ignored.py").write_text("invalid ignored Python !")
    (repo / ".env").write_text("sentinel_private_environment")
    external = make_repo(tmp_path, "external", {"private.py": SWALLOWED})
    (root / "linked-repo").symlink_to(external, target_is_directory=True)
    make_repo(root / "container", "nested", {"nested.py": SWALLOWED})
    scanned = []

    def record_path(path):
        scanned.append(path)
        return []

    report = reporter.build_report(root, scanner=SimpleNamespace(scan_file=record_path))
    assert scanned == [repo / "app.py"]
    assert report["summary"]["projects"] == 1
    assert report["errors"] == []


@pytest.mark.parametrize("directory_link", [False, True])
def test_tracked_symlink_cannot_read_outside_repo(tmp_path, reporter, directory_link):
    root = tmp_path / "portfolio"
    repo = make_repo(root, files={"package/app.py": "answer = 42\n"})
    external = tmp_path / "external"
    external.mkdir()
    (external / "app.py").write_text("sentinel_private_source")
    if directory_link:
        (repo / "package").rename(tmp_path / "original-package")
        (repo / "package").symlink_to(external, target_is_directory=True)
    else:
        (repo / "package" / "app.py").unlink()
        (repo / "package" / "app.py").symlink_to(external / "app.py")

    def should_not_read(path):
        pytest.fail("Scanner followed an unsafe tracked symlink")

    report = reporter.build_report(root, scanner=SimpleNamespace(scan_file=should_not_read))
    assert report["errors"][0]["category"] == "unsafe-path"
    assert report["summary"]["scanned_python_files"] == 0


@pytest.mark.parametrize("replacement", ["fifo", "directory"])
def test_nonregular_tracked_files_are_rejected_without_reading(tmp_path, reporter, replacement):
    repo = make_repo(tmp_path)
    source = repo / "app.py"
    source.unlink()
    if replacement == "fifo":
        os.mkfifo(source)
    else:
        source.mkdir()

    def should_not_read(path):
        pytest.fail("Scanner attempted to open a nonregular tracked file")

    report = reporter.build_report(tmp_path, scanner=SimpleNamespace(scan_file=should_not_read))
    assert report["errors"][0]["category"] == "unsafe-path"
    assert report["summary"]["scanned_python_files"] == 0
    # Exercise the real CLI too: opening the FIFO would block past this timeout.
    try:
        subprocess.run(
            [sys.executable, str(REPORT_SCRIPT), "--projects-root", str(tmp_path), "--json"],
            text=True, capture_output=True, check=True, timeout=5,
        )
    except subprocess.CalledProcessError as error:
        assert error.returncode == 2
        assert json.loads(error.stdout)["errors"][0]["category"] == "unsafe-path"
    else:
        pytest.fail("CLI unexpectedly accepted a nonregular tracked file")


def test_git_worktree_marker_file_is_discovered(tmp_path):
    repo = make_repo(tmp_path, "source")
    worktree = tmp_path / "linked worktree"
    git(repo, "worktree", "add", "--detach", str(worktree), "HEAD")
    assert (worktree / ".git").is_file()
    report = run_report(tmp_path)
    assert report["summary"]["projects"] == 2
    assert report["summary"]["scanned_python_files"] == 2


def test_git_runner_uses_bounded_readonly_subprocess(tmp_path, reporter, monkeypatch):
    observed = {}

    def run(command, **kwargs):
        observed.update({"command": command, **kwargs})
        return SimpleNamespace(stdout=b"tracked.py\0")

    monkeypatch.setenv("GIT_WORK_TREE", "unrelated")
    monkeypatch.setattr(reporter.subprocess, "run", run)
    assert reporter.git_output(tmp_path, "ls-files", "-z", "--", "*.py") == b"tracked.py\0"
    assert observed["check"] is True
    assert observed["capture_output"] is True
    assert observed["timeout"] == 30
    assert "--no-optional-locks" in observed["command"]
    assert "GIT_WORK_TREE" not in observed["env"]

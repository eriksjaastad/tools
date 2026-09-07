"""Exercise the actual blocking process and automatic Git trigger offline."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest


GATE = Path(__file__).resolve().parents[2] / "silent-failure-gate.py"


@pytest.fixture
def repository(tmp_path):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_AUTHOR_NAME": "Offline", "GIT_AUTHOR_EMAIL": "offline@example.invalid",
                "GIT_COMMITTER_NAME": "Offline", "GIT_COMMITTER_EMAIL": "offline@example.invalid"})
    subprocess.run(["git", "init", "-q", str(tmp_path)], env=env, check=True, capture_output=True, timeout=10)
    return tmp_path, env


def git(repo, *args, succeeds=True):
    path, env = repo
    try:
        return subprocess.run(["git", "-C", str(path), *args], env=env, check=True,
                              capture_output=True, text=True, timeout=15)
    except subprocess.CalledProcessError as error:
        if succeeds:
            raise
        return error  # Tests assert the expected failure code and diagnostics.


def scan(repo):
    path, env = repo
    try:
        return subprocess.run([sys.executable, str(GATE), "--repo", str(path)], env=env,
                              check=True, capture_output=True, text=True, timeout=15)
    except subprocess.CalledProcessError as error:
        return error  # Failure is the subject of assertions, not a successful scan.


def test_automatic_hook_blocks_logged_empty_results_then_accepts_fix(repository):
    path, _ = repository
    hook = path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, str(GATE)]) + "\n")
    hook.chmod(0o700)
    source = path / "search.py"
    source.write_text("def search():\n    try:\n        query()\n    except Exception:\n        warn()\n        return []\n")
    git(repository, "add", "search.py")
    blocked = git(repository, "commit", "-m", "offline fixture", succeeds=False)
    assert blocked.returncode != 0
    assert "SF002" in blocked.stdout + blocked.stderr
    source.write_text("def search():\n    return query()\n")
    git(repository, "add", "search.py")
    git(repository, "commit", "-m", "offline corrected fixture")
    assert json.loads(scan(repository).stdout)["scanned_python_files"] == 1


@pytest.mark.parametrize("damage", ["missing", "syntax", "symlink", "directory"])
def test_unscannable_tracked_file_fails_closed(repository, damage):
    path, _ = repository
    source = path / "module.py"
    source.write_text("x = 1\n")
    git(repository, "add", "module.py")
    source.unlink()
    if damage == "syntax":
        source.write_text("sensitive_source = (\n")
    elif damage == "symlink":
        target = path / "target.txt"
        target.write_text("x = 1\n")
        source.symlink_to(target)
    elif damage == "directory":
        source.mkdir()
    result = scan(repository)
    assert result.returncode == 2
    assert json.loads(result.stdout)["errors"]
    assert "sensitive_source" not in result.stdout + result.stderr


def test_untracked_python_is_not_scanned_and_zero_coverage_is_error(repository):
    path, _ = repository
    (path / "untracked.py").write_text("x = 1\n")
    result = scan(repository)
    assert result.returncode == 2
    assert json.loads(result.stdout)["errors"] == [{"path": ".", "error": "NoPythonFilesScanned"}]


def test_paths_with_spaces_and_non_python_files(repository):
    path, _ = repository
    (path / "a space.py").write_text("def query():\n    return []\n")
    (path / "notes.md").write_text("not Python ((\n")
    git(repository, "add", "a space.py", "notes.md")
    result = scan(repository)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"errors": [], "findings": [], "scanned_python_files": 1}

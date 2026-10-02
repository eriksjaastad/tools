"""Pre-push governance backstop (#7841), driven through a real `git push`.

Each test pushes to a local bare remote through a pre-push hook that runs
push-range-check.py. Commits are made with no commit hooks installed, which is
exactly the situation the backstop exists for: a cherry-pick, a rebase replay
or `--no-verify` put commits on the branch that pre-commit never saw.

Bad content is assembled at runtime so this file does not trip the
repository's own pre-commit gate.
"""
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest


DRIVER = Path(__file__).resolve().parents[2] / "push-range-check.py"

SILENT = ("def collect():\n    try:\n        query()\n    except Exception:\n"
          "        logger.warning('failed')\n        return []\n")
DELETE = 'from pathlib import Path\nPath("valuable").unlink()\n'
ABSOLUTE = 'DATA = "' + "/" + 'Users/fixture/data.csv"\n'
SECRET = 'TOKEN = "' + "ghp_" + "a" * 36 + '"\n'


@pytest.fixture
def repo(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
    remote, root, hooks = tmp_path / "remote.git", tmp_path / "work", tmp_path / "hooks"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], env=env, check=True, timeout=10)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], env=env, check=True, timeout=10)
    hooks.mkdir()
    hook = hooks / "pre-push"
    hook.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(DRIVER))} "$@"\n')
    hook.chmod(0o755)
    state = (root, env, remote)
    git(state, "config", "core.hooksPath", str(hooks))
    git(state, "remote", "add", "origin", str(remote))
    return state


def git(repo, *args):
    root, env, _ = repo
    return subprocess.run(["git", *args], cwd=root, env=env, check=True,
                          capture_output=True, text=True, timeout=30).stdout


def commit(repo, name, text, message="change"):
    path = repo[0] / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD").strip()


def push(repo, *args):
    root, env, _ = repo
    return subprocess.run(["git", "push", "-q", "origin", *args], cwd=root, env=env,
                          capture_output=True, text=True, timeout=120)


def remote_tip(repo, branch="main"):
    _, env, remote = repo
    result = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "--verify", "--quiet",
                             f"refs/heads/{branch}"], env=env, capture_output=True, text=True, timeout=10)
    return result.stdout.strip() or None


def test_clean_push_passes_and_a_zero_commit_push_checks_nothing(repo):
    commit(repo, "m.py", "VALUE = 1\n")
    first = push(repo, "main")
    assert first.returncode == 0, first.stderr
    assert "1 commit(s)" in first.stderr
    again = push(repo, "main")
    assert again.returncode == 0, again.stderr
    assert "commit(s)" not in again.stderr


def test_cherry_picked_silent_failure_is_refused(repo):
    base = commit(repo, "m.py", "VALUE = 1\n")
    assert push(repo, "main").returncode == 0
    git(repo, "checkout", "-qb", "side")
    commit(repo, "handler.py", SILENT, "silent handler")
    git(repo, "checkout", "-q", "main")
    git(repo, "cherry-pick", "side")
    result = push(repo, "main")
    assert result.returncode != 0
    assert "SF002" in result.stderr and "silent handler" in result.stderr
    assert remote_tip(repo) == base


def test_every_commit_is_checked_not_just_the_net_range(repo):
    commit(repo, "config.py", SECRET, "add token")
    commit(repo, "config.py", "TOKEN = None\n", "remove token")
    result = push(repo, "main")
    assert result.returncode != 0
    assert "add token" in result.stderr and "remove token" not in result.stderr
    assert "1 of 2 commit(s)" in result.stderr


def test_committed_blob_is_checked_not_the_worktree(repo):
    commit(repo, "paths.py", ABSOLUTE, "hardcoded path")
    (repo[0] / "paths.py").write_text("DATA = None\n")
    result = push(repo, "main")
    assert result.returncode != 0
    assert "absolute-path-check.py" in result.stderr


def test_root_commit_is_checked_against_the_empty_tree(repo):
    commit(repo, "cleanup.py", DELETE, "root with deletion")
    result = push(repo, "main")
    assert result.returncode != 0
    assert "DS001" in result.stderr


def test_new_branch_checks_only_commits_no_remote_has(repo):
    # Legacy history already on the remote (pushed past the gate) is not
    # re-litigated: a new branch is based on what remote-tracking refs contain.
    commit(repo, "legacy.py", ABSOLUTE + SILENT, "legacy")
    assert push(repo, "--no-verify", "main").returncode == 0
    git(repo, "fetch", "-q", "origin")
    git(repo, "checkout", "-qb", "feature")
    commit(repo, "other.py", "VALUE = 2\n", "clean feature work")
    clean = push(repo, "feature")
    assert clean.returncode == 0, clean.stderr
    assert "1 commit(s)" in clean.stderr
    commit(repo, "more.py", DELETE, "feature deletion")
    blocked = push(repo, "feature")
    assert blocked.returncode != 0
    assert "DS001" in blocked.stderr and "1 of 1 commit(s)" in blocked.stderr


def test_merge_is_judged_only_on_what_it_introduces(repo):
    commit(repo, "base.py", "VALUE = 1\n", "base")
    assert push(repo, "main").returncode == 0
    git(repo, "checkout", "-qb", "feature")
    commit(repo, "feature.py", "FEATURE = 1\n", "feature work")
    git(repo, "checkout", "-q", "main")
    commit(repo, "incoming.py", ABSOLUTE + SILENT + DELETE, "someone else's legacy code")
    assert push(repo, "--no-verify", "main").returncode == 0
    git(repo, "fetch", "-q", "origin")
    git(repo, "checkout", "-q", "feature")
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "main")
    clean = push(repo, "feature")
    assert clean.returncode == 0, clean.stderr
    assert "2 commit(s)" in clean.stderr  # feature work + the merge

    git(repo, "checkout", "-qb", "evil", "feature~1")
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "main")
    (repo[0] / "resolved.py").write_text(SILENT)
    git(repo, "add", "resolved.py")
    git(repo, "commit", "-qm", "evil merge")
    evil = push(repo, "evil")
    assert evil.returncode != 0
    assert "evil merge" in evil.stderr and "SF002" in evil.stderr
    assert "incoming.py" not in evil.stderr


def test_branch_deletion_and_tag_of_published_commit_pass(repo):
    commit(repo, "m.py", "VALUE = 1\n")
    git(repo, "checkout", "-qb", "topic")
    assert push(repo, "main", "topic").returncode == 0
    git(repo, "tag", "-a", "v1", "-m", "release")
    tag = push(repo, "v1")
    assert tag.returncode == 0 and "commit(s)" not in tag.stderr
    deletion = push(repo, "--delete", "topic")
    assert deletion.returncode == 0 and "commit(s)" not in deletion.stderr


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="Platform lacks symlinks")
def test_symlink_has_no_content_to_check(repo):
    # A symlinked .py stays a DS000 error in source-deletion-check, as it is at
    # pre-commit; this covers the whole-file validators, which skip symlinks.
    os.symlink("/" + "Users/fixture/target.cfg", repo[0] / "link.cfg")
    git(repo, "add", "link.cfg")
    git(repo, "commit", "-qm", "symlink")
    result = push(repo, "main")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("line", [
    "refs/heads/main abc refs/heads/main",
    "not a ref line",
    "refs/heads/main " + "1" * 40 + " refs/heads/main " + "0" * 40,
])
def test_unreadable_hook_input_blocks(repo, line):
    root, env, _ = repo
    result = subprocess.run([sys.executable, str(DRIVER)], input=line + "\n", cwd=root, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert "unable to list the pushed commits" in result.stderr

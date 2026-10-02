"""Pre-push governance backstop (#7841), driven through a real `git push`.

Each test pushes to a local bare remote through a pre-push hook that runs
push-range-check.py. Commits are made with no commit hooks installed, which is
exactly the situation the backstop exists for: a cherry-pick, a rebase replay
or `--no-verify` put commits on the branch that pre-commit never saw.

Bad content is assembled at runtime so this file does not trip the
repository's own pre-commit gate.
"""
import importlib.util
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


# Review round 1 on ffbdc91: case-colliding paths, and the enumeration edges.

def load_driver():
    spec = importlib.util.spec_from_file_location("push_range_check", DRIVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blob(repo, text):
    root, env, _ = repo
    return subprocess.run(["git", "hash-object", "-w", "--stdin"], input=text, cwd=root, env=env,
                          check=True, capture_output=True, text=True, timeout=10).stdout.strip()


def test_case_colliding_paths_are_each_scanned(repo):
    # Built with plumbing: a case-insensitive worktree cannot stage both names.
    for name, text in (("A.py", SECRET), ("a.py", "VALUE = 1\n")):
        git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob(repo, text)},{name}")
    git(repo, "commit", "-qm", "colliding names")
    result = push(repo, "main")
    assert result.returncode != 0
    assert "A.py" in result.stderr and "secrets-scanner.py" in result.stderr


def test_layers_separate_names_that_collide_on_disk():
    driver = load_driver()
    files = {name: ("100644", name) for name in ("A.py", "a.py", "B", "b/c.py", "d/e.py", "café.py", "café.py")}
    files["link.py"] = ("120000", "link")
    placed = driver.layers(files)
    for left in ("A.py", "B", "café.py"):
        right = {"A.py": "a.py", "B": "b/c.py", "café.py": "café.py"}[left]
        assert not any(left in layer and right in layer for layer in placed)
    assert sorted(name for layer in placed for name in layer) == sorted(set(files) - {"link.py"})
    assert len(placed) == 2


def test_force_push_checks_only_the_rewritten_commits(repo):
    commit(repo, "m.py", "VALUE = 1\n", "base")
    commit(repo, "n.py", "VALUE = 2\n", "tip")
    assert push(repo, "main").returncode == 0
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    commit(repo, "n.py", DELETE, "rewritten tip")
    blocked = push(repo, "--force", "main")
    assert blocked.returncode != 0 and "1 of 1 commit(s)" in blocked.stderr
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    commit(repo, "n.py", "VALUE = 3\n", "clean rewrite")
    clean = push(repo, "--force", "main")
    assert clean.returncode == 0, clean.stderr
    assert "1 commit(s)" in clean.stderr


def test_one_commit_pushed_to_two_refs_is_checked_once(repo):
    commit(repo, "m.py", ABSOLUTE, "shared bad commit")
    result = push(repo, "main", "main:refs/heads/copy")
    assert result.returncode != 0
    assert "1 of 1 commit(s)" in result.stderr
    assert remote_tip(repo) is None and remote_tip(repo, "copy") is None


def test_annotated_tag_of_unpublished_commit_is_checked(repo):
    commit(repo, "m.py", "VALUE = 1\n", "published")
    assert push(repo, "main").returncode == 0
    git(repo, "checkout", "-q", "--detach")
    commit(repo, "m.py", ABSOLUTE, "tagged only")
    git(repo, "tag", "-a", "v2", "-m", "release")
    result = push(repo, "v2")
    assert result.returncode != 0 and "tagged only" in result.stderr


def test_tag_of_a_blob_publishes_no_commits(repo):
    commit(repo, "m.py", "VALUE = 1\n")
    assert push(repo, "main").returncode == 0
    git(repo, "tag", "loose", blob(repo, SECRET))
    result = push(repo, "loose")
    assert result.returncode == 0 and "commit(s)" not in result.stderr


def test_validator_timeout_fails_closed(tmp_path, monkeypatch):
    driver = load_driver()
    (tmp_path / "slow.py").write_text("import time\ntime.sleep(30)\n")
    monkeypatch.setattr(driver, "VALIDATORS_DIR", tmp_path)
    monkeypatch.setattr(driver, "VALIDATOR_TIMEOUT", 0.5)
    code, output = driver.run_validator("slow.py", [], None)
    assert code == 124 and "timed out" in output


# Codex review on 428f5a7: the installer must install the backstop, and a Git
# failure while looking up the old remote tip must not narrow the range.

INSTALL = DRIVER.parent / "install-hooks.sh"
UNINSTALL = DRIVER.parent / "uninstall-hooks.sh"


def installer_repo(tmp_path):
    root, remote, home = tmp_path / "work", tmp_path / "remote.git", tmp_path / "home"
    uv = home / ".local/bin/uv"
    uv.parent.mkdir(parents=True)
    uv.write_text('#!/bin/sh\n[ "$1 $2" = "run --no-project" ] || { echo "unexpected uv: $*" >&2; exit 97; }\n'
                  'shift 2\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
    uv.chmod(0o700)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(HOME=str(home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], env=env, check=True, timeout=10)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], env=env, check=True, timeout=10)
    state = (root, env, remote)
    git(state, "remote", "add", "origin", str(remote))
    return state


def run_script(repo, script):
    root, env, _ = repo
    return subprocess.run(["bash", str(script), str(root)], env=env, capture_output=True,
                          text=True, timeout=30)


def test_installer_adds_a_working_pre_push_backstop(tmp_path):
    repo = installer_repo(tmp_path)
    installed = run_script(repo, INSTALL)
    assert installed.returncode == 0, installed.stderr
    hook = repo[0] / ".git/hooks/pre-push"
    assert os.access(hook, os.X_OK)
    git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    (repo[0] / "handler.py").write_text(SILENT)
    git(repo, "add", "handler.py")
    git(repo, "commit", "-q", "--no-verify", "-m", "skipped pre-commit")
    result = push(repo, "main")
    assert result.returncode != 0 and "SF002" in result.stderr
    assert remote_tip(repo) is None
    assert run_script(repo, INSTALL).returncode == 0  # reinstall over its own hook


def test_installer_and_uninstaller_leave_a_foreign_pre_push_alone(tmp_path):
    repo = installer_repo(tmp_path)
    hooks = repo[0] / ".git/hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\necho project hook\n")
    refused = run_script(repo, INSTALL)
    assert refused.returncode == 1 and "not a governance hook" in refused.stderr
    assert not (hooks / "pre-commit").exists()
    assert (hooks / "pre-push").read_text() == "#!/bin/sh\necho project hook\n"
    kept = run_script(repo, UNINSTALL)
    assert kept.returncode == 1 and "pre-push hook exists but doesn't appear" in kept.stdout
    assert (hooks / "pre-push").exists()


def test_git_failure_looking_up_the_old_tip_fails_closed(tmp_path, monkeypatch):
    driver = load_driver()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.delenv("GIT_DIR", raising=False)
    with pytest.raises(subprocess.CalledProcessError):
        driver.known_locally("1" * 40)


# Codex review on f9b56bb: with core.hooksPath set, .git/hooks is dead, so the
# installer must not report an install that does nothing.

def test_installer_with_hooks_path_writes_nothing_and_reports_the_active_hooks(tmp_path):
    repo = installer_repo(tmp_path)
    active = tmp_path / "active-hooks"
    active.mkdir()
    (active / "pre-commit").write_text('#!/bin/sh\nexec bash "$HOME/tools/governance-check.sh"\n')
    git(repo, "config", "core.hooksPath", str(active))
    missing = run_script(repo, INSTALL)
    assert missing.returncode == 1
    assert "pre-push does not run push-range-check.py" in missing.stderr
    assert "runs governance-check.sh" in missing.stdout
    assert not (repo[0] / ".git/hooks/pre-commit").exists()
    assert not (repo[0] / ".git/hooks/pre-push").exists()
    (active / "pre-push").write_text('#!/bin/sh\nexec uv run --no-project "$HOME/tools/push-range-check.py" "$@"\n')
    git(repo, "config", "core.hooksPath", "../active-hooks")  # relative to the worktree root
    both = run_script(repo, INSTALL)
    assert both.returncode == 0, both.stderr
    assert not (repo[0] / ".git/hooks/pre-push").exists()

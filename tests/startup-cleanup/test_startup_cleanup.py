"""Synthetic integration tests for startup-cleanup/startup_cleanup.py.

Every test runs against throwaway git repositories under tmp_path and uses a
fake Trash backend, so no real project worktree, credential, or production
path is ever touched.
"""

import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "startup-cleanup" / "startup_cleanup.py"


def load_module():
    spec = importlib.util.spec_from_file_location("startup_cleanup", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sc(monkeypatch):
    module = load_module()
    # Synthetic repo behavior should be independent of host lsof availability.
    monkeypatch.setattr(module, "_active_cwds", lambda timeout: (set(), ""))
    return module


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc


def make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-qm", "init")
    git(repo, "remote", "add", "origin", "https://github.com/test-owner/test-repo.git")
    git(repo, "update-ref", "refs/remotes/origin/main", "main")
    return repo


def refresh_origin(repo: Path) -> None:
    git(repo, "update-ref", "refs/remotes/origin/main", "main")


def make_task_branch(repo: Path, branch: str, filename: str) -> None:
    """Create a task branch with one commit and merge it into main."""
    git(repo, "checkout", "-q", "-b", branch)
    (repo / filename).write_text(f"work {branch}\n")
    git(repo, "add", filename)
    git(repo, "commit", "-qm", f"work {branch}")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--ff-only", branch)
    refresh_origin(repo)


def make_task_worktree(repo: Path, branch: str, worktree: Path) -> Path:
    """Create a linked worktree on a new task branch with one commit."""
    git(repo, "worktree", "add", "-q", "-b", branch, str(worktree))
    (worktree / "work.txt").write_text(f"work {branch}\n")
    git(worktree, "add", "work.txt")
    git(worktree, "commit", "-qm", f"work {branch}")
    return worktree


def merge_branch(repo: Path, branch: str) -> None:
    git(repo, "merge", "-q", "--ff-only", branch)
    refresh_origin(repo)


def branch_names(repo: Path) -> list[str]:
    proc = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def track_task_branch(repo: Path, branch: str) -> None:
    """Give a local task branch the normal origin/task tracking configuration."""
    git(repo, "config", f"branch.{branch}.remote", "origin")
    git(repo, "config", f"branch.{branch}.merge", f"refs/heads/{branch}")
    git(repo, "update-ref", f"refs/remotes/origin/{branch}", branch)


class FakeTrash:
    """Recoverable trash stand-in: moves paths into a per-test trash dir."""

    def __init__(self, dest: Path):
        self.dest = dest
        self.dest.mkdir(parents=True, exist_ok=True)
        self.calls: list[str] = []

    def __call__(self, path):
        path = Path(path).resolve()
        self.calls.append(str(path))
        target = self.dest / f"{len(self.calls)}-{path.name}"
        shutil.move(str(path), str(target))
        return not path.exists(), "fake trash moved path"


def make_fake_gh(tmp_path: Path) -> Path:
    """Executable gh stand-in honoring --head <branch> against an env list."""
    script = tmp_path / "bin" / "gh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] != ['pr', 'list']:\n"
        "    sys.exit(2)\n"
        "head = args[args.index('--head') + 1]\n"
        "branches = json.loads(os.environ.get('FAKE_GH_OPEN_BRANCHES', '[]'))\n"
        "if head in branches:\n"
        "    print(json.dumps([{'number': 5, 'title': 'open pr', 'url': 'https://example.invalid/5'}]))\n"
        "else:\n"
        "    print('[]')\n"
    )
    script.chmod(0o755)
    return script


def reasons_for(report: dict, target: str) -> list[str]:
    for refused in report["refused"]:
        if refused["target"] == target:
            return refused["reasons"]
    return []


# --- safe deletion ---------------------------------------------------------


def test_removes_merged_clean_worktree_and_branch_outside_claude_dir(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "isolated-task-worktree"
    make_task_worktree(repo, "task/123-isolated", wt)
    merge_branch(repo, "task/123-isolated")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")
    trash = FakeTrash(tmp_path / "trash")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=trash,
    )

    assert report["ok"] is True
    removed_worktrees = [r for r in report["removed"] if r["type"] == "worktree"]
    assert len(removed_worktrees) == 1
    removal = removed_worktrees[0]
    assert removal["target"] == str(wt)
    assert removal["branch"] == "task/123-isolated"
    assert removal["branch_deleted"] is True
    assert report["summary"]["branches_deleted"] == 1
    assert not wt.exists()
    assert "task/123-isolated" not in branch_names(repo)
    assert any("worktree" in call or "wt" in call for call in trash.calls)

    # Reruns are idempotent.
    report2 = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=trash,
    )
    assert report2["removed"] == []
    assert report2["summary"]["refusals"] == 0


def test_removes_merged_clean_worktree_with_tracking_upstream(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    branch = "task/124-tracked-worktree"
    wt = tmp_path / "tracked-task-worktree"
    make_task_worktree(repo, branch, wt)
    merge_branch(repo, branch)
    track_task_branch(repo, branch)
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo, gh_bin=str(make_fake_gh(tmp_path)), trash_fn=FakeTrash(tmp_path / "trash")
    )
    assert report["ok"] is True
    assert any(item["branch"] == branch and item["branch_deleted"] for item in report["removed"])
    assert not wt.exists()
    assert branch not in branch_names(repo)


def test_preserves_clean_merged_worktree_used_by_another_session(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "active-other-worktree"
    make_task_worktree(repo, "task/124-active", wt)
    merge_branch(repo, "task/124-active")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")
    trash = FakeTrash(tmp_path / "trash")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=trash,
        active_cwds_fn=lambda timeout: ({wt / "nested"}, ""),
    )

    assert wt.exists()
    assert "task/124-active" in branch_names(repo)
    assert trash.calls == []
    assert any("active process" in reason for reason in reasons_for(report, str(wt)))


def test_preserves_worktree_when_session_inspection_fails(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "unverified-worktree"
    make_task_worktree(repo, "task/125-unverified", wt)
    merge_branch(repo, "task/125-unverified")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")
    trash = FakeTrash(tmp_path / "trash")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=trash,
        active_cwds_fn=lambda timeout: (None, "lsof unavailable"),
    )

    assert wt.exists()
    assert "task/125-unverified" in branch_names(repo)
    assert trash.calls == []
    assert "lsof unavailable" in reasons_for(report, str(wt))


def test_lsof_cwd_inventory_detects_nested_active_directory(tmp_path, monkeypatch):
    module = load_module()
    wt = tmp_path / "worktree"
    nested = wt / "src"
    nested.mkdir(parents=True)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/lsof")
    monkeypatch.setattr(
        module, "_run",
        lambda args, cwd, timeout: subprocess.CompletedProcess(
            args, 0, stdout=f"p123\nfcwd\nn{nested}\n", stderr=""
        ),
    )

    active, error = module._active_cwds(3)
    assert error == ""
    assert module._has_active_cwd(wt, active)


def test_hook_uses_payload_cwd_before_stale_provider_environment(sc, tmp_path, monkeypatch):
    current = tmp_path / "current"
    stale = tmp_path / "stale"
    current.mkdir()
    stale.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(stale))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"cwd": str(current)})))

    assert sc._resolve_project_dir(None) == current
    for provider in ("claude", "codex"):
        config = json.loads(sc._hook_command(provider))
        assert config["matcher"] == "^startup$"
        command = config["hooks"][0]["command"]
        assert '"$HOME/projects/_tools/startup-cleanup/startup_cleanup.py"' in command


def test_deletes_standalone_merged_task_branch(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    make_task_branch(repo, "task/456-standalone", "standalone.txt")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    deleted = [r for r in report["removed"] if r["type"] == "branch"]
    assert len(deleted) == 1
    assert deleted[0]["target"] == "task/456-standalone"
    assert deleted[0]["branch_deleted"] is True
    assert "task/456-standalone" not in branch_names(repo)


def test_dry_run_removes_nothing(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "dry-wt"
    make_task_worktree(repo, "task/789-dry", wt)
    merge_branch(repo, "task/789-dry")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        dry_run=True,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["dry_run"] is True
    assert wt.exists()
    assert "task/789-dry" in branch_names(repo)
    assert report["removed"] == []
    assert report["summary"]["worktrees_removed"] == 0
    assert report["summary"]["branches_deleted"] == 0
    assert report["summary"]["worktrees_planned"] == 1
    assert report["summary"]["branches_planned"] == 1
    assert all(r.get("note", "").startswith("dry-run") for r in report["planned"])


# --- refusal cases ---------------------------------------------------------


def test_refuses_untracked_dirty_worktree(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "dirty-wt"
    make_task_worktree(repo, "task/100-dirty", wt)
    merge_branch(repo, "task/100-dirty")
    (wt / "stray.txt").write_text("untracked\n")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    reasons = reasons_for(report, str(wt))
    assert any("dirty" in reason for reason in reasons)
    assert wt.exists()
    assert "task/100-dirty" in branch_names(repo)


def test_refuses_tracked_modification(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "tracked-wt"
    make_task_worktree(repo, "task/101-tracked", wt)
    merge_branch(repo, "task/101-tracked")
    (wt / "base.txt").write_text("modified\n")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    assert any("dirty" in reason for reason in reasons_for(report, str(wt)))


def test_refuses_meaningful_ignored_artifacts(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "ignored-wt"
    make_task_worktree(repo, "task/102-ignored", wt)
    (wt / ".gitignore").write_text("*.log\n")
    git(wt, "add", ".gitignore")
    git(wt, "commit", "-qm", "add gitignore")
    merge_branch(repo, "task/102-ignored")
    (wt / "debug.log").write_text("ignored artifact\n")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    reasons = reasons_for(report, str(wt))
    assert any("ignored" in reason for reason in reasons)
    assert wt.exists()


def test_refuses_unmerged_worktree_and_branch(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "unmerged-wt"
    make_task_worktree(repo, "task/103-unmerged", wt)
    # Do NOT merge into main; branch stays ahead.
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    assert any("not merged" in reason for reason in reasons_for(report, str(wt)))
    assert any("not merged" in reason for reason in reasons_for(report, "task/103-unmerged"))
    assert wt.exists()
    assert "task/103-unmerged" in branch_names(repo)


def test_refuses_open_pr(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "pr-wt"
    make_task_worktree(repo, "task/104-pr", wt)
    merge_branch(repo, "task/104-pr")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", json.dumps(["task/104-pr"]))

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    assert any("open PR" in reason for reason in reasons_for(report, str(wt)))
    assert wt.exists()


def test_refuses_gh_unavailable(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "no-gh-wt"
    make_task_worktree(repo, "task/105-nogh", wt)
    merge_branch(repo, "task/105-nogh")
    monkeypatch.setattr(sc, "_resolve_gh_bin", lambda: None)

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=None,
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    reasons = reasons_for(report, str(wt))
    assert any("GitHub CLI unavailable" in reason for reason in reasons)
    assert wt.exists()


def test_refuses_locked_worktree(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "locked-wt"
    make_task_worktree(repo, "task/106-locked", wt)
    merge_branch(repo, "task/106-locked")
    git(repo, "worktree", "lock", str(wt))
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    reasons = reasons_for(report, str(wt))
    assert any("locked" in reason for reason in reasons)
    assert wt.exists()


def test_refuses_active_session_worktree(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "active-wt"
    make_task_worktree(repo, "task/107-active", wt)
    merge_branch(repo, "task/107-active")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    # The check runs from inside the candidate worktree (the agent started there).
    report = sc.run_startup_cleanup(
        wt,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    reasons = reasons_for(report, str(wt))
    assert any("active session" in reason for reason in reasons)
    assert wt.exists()
    assert "task/107-active" in branch_names(repo)


def test_refuses_main_not_fresh(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "stale-main-wt"
    make_task_worktree(repo, "task/108-stale", wt)
    merge_branch(repo, "task/108-stale")
    # main moved past origin/main -> not fresh -> cleanup disabled entirely.
    (repo / "later.txt").write_text("later\n")
    git(repo, "add", "later.txt")
    git(repo, "commit", "-qm", "later commit")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["main_fresh"] is False
    assert report["removed"] == []
    assert report["summary"]["reason"] == "main not fresh"
    assert wt.exists()
    assert "task/108-stale" in branch_names(repo)


def test_fresh_main_after_refusal_can_clean_on_next_startup(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "fresh-later"
    make_task_worktree(repo, "task/108-fresh-later", wt)
    merge_branch(repo, "task/108-fresh-later")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD~1")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")
    gh = str(make_fake_gh(tmp_path))
    trash = FakeTrash(tmp_path / "trash")

    first = sc.run_startup_cleanup(repo, min_interval_seconds=3600,
                                   gh_bin=gh, trash_fn=trash)
    assert first["summary"]["reason"] == "main not fresh"
    refresh_origin(repo)
    second = sc.run_startup_cleanup(repo, min_interval_seconds=3600,
                                    gh_bin=gh, trash_fn=trash)
    assert second["throttled"] is False
    assert not wt.exists()


def test_deletes_merged_standalone_branch_from_older_task_checkout(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    active = tmp_path / "active-task"
    git(repo, "worktree", "add", "-q", "-b", "task/109-active", str(active))
    make_task_branch(repo, "task/109-merged", "merged.txt")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        active, gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )
    assert "task/109-merged" not in branch_names(repo)
    assert any(item["branch"] == "task/109-merged" for item in report["removed"])
    assert active.exists()


def test_branch_delete_refuses_new_worktree_checkout(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    branch = "task/110-race-checkout"
    make_task_branch(repo, branch, "race.txt")
    original = sc._git_ok
    new_wt = tmp_path / "new-active-worktree"

    def with_race(path, args, timeout):
        if args[-3:] == ["branch", "-d", branch]:
            git(repo, "worktree", "add", "-q", str(new_wt), branch)
        return original(path, args, timeout)

    monkeypatch.setattr(sc, "_git_ok", with_race)
    ok, reason = sc._delete_branch(repo, branch, "main", 3)
    assert not ok
    assert "used by worktree" in reason
    assert branch in branch_names(repo)
    assert new_wt.exists()


def test_branch_delete_refuses_new_unmerged_tip(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    branch = "task/111-race-tip"
    make_task_branch(repo, branch, "race.txt")
    original = sc._git_ok

    def with_race(path, args, timeout):
        if args[-3:] == ["branch", "-d", branch]:
            tree = git(repo, "rev-parse", f"{branch}^{{tree}}").stdout.strip()
            parent = git(repo, "rev-parse", branch).stdout.strip()
            new_tip = git(repo, "commit-tree", tree, "-p", parent, "-m", "new work").stdout.strip()
            git(repo, "update-ref", f"refs/heads/{branch}", new_tip)
        return original(path, args, timeout)

    monkeypatch.setattr(sc, "_git_ok", with_race)
    ok, reason = sc._delete_branch(repo, branch, "main", 3)
    assert not ok
    assert "not fully merged" in reason
    assert branch in branch_names(repo)


def test_deletes_merged_branch_with_tracking_upstream(sc, tmp_path):
    repo = make_repo(tmp_path)
    branch = "task/112-tracked-merged"
    make_task_branch(repo, branch, "merged.txt")
    track_task_branch(repo, branch)

    ok, reason = sc._delete_branch(repo, branch, "main", 3)
    assert ok, reason
    assert branch not in branch_names(repo)


def test_branch_delete_refuses_new_tip_even_if_upstream_advances(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    branch = "task/113-tracked-race"
    make_task_branch(repo, branch, "merged.txt")
    track_task_branch(repo, branch)
    original = sc._git_ok

    def with_race(path, args, timeout):
        if args[-3:] == ["branch", "-d", branch]:
            tree = git(repo, "rev-parse", f"{branch}^{{tree}}").stdout.strip()
            parent = git(repo, "rev-parse", branch).stdout.strip()
            new_tip = git(repo, "commit-tree", tree, "-p", parent, "-m", "new work").stdout.strip()
            git(repo, "update-ref", f"refs/heads/{branch}", new_tip)
            git(repo, "update-ref", f"refs/remotes/origin/{branch}", new_tip)
        return original(path, args, timeout)

    monkeypatch.setattr(sc, "_git_ok", with_race)
    ok, reason = sc._delete_branch(repo, branch, "main", 3)
    assert not ok
    assert "not fully merged" in reason
    assert branch in branch_names(repo)
    assert git(repo, "config", "--get", f"branch.{branch}.remote").stdout.strip() == "origin"
    assert git(repo, "config", "--get", f"branch.{branch}.merge").stdout.strip() == f"refs/heads/{branch}"


def test_branch_delete_uses_main_when_primary_checkout_switches(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    branch = "task/114-primary-switch"
    make_task_branch(repo, branch, "merged.txt")
    track_task_branch(repo, branch)
    original = sc._git_ok

    def with_race(path, args, timeout):
        if args[-3:] == ["branch", "-d", branch]:
            git(repo, "checkout", "-q", "-b", "another-branch", branch)
            tree = git(repo, "rev-parse", f"{branch}^{{tree}}").stdout.strip()
            parent = git(repo, "rev-parse", branch).stdout.strip()
            new_tip = git(repo, "commit-tree", tree, "-p", parent, "-m", "new work").stdout.strip()
            git(repo, "update-ref", f"refs/heads/{branch}", new_tip)
            git(repo, "update-ref", f"refs/heads/another-branch", new_tip)
            git(repo, "update-ref", f"refs/remotes/origin/{branch}", new_tip)
        return original(path, args, timeout)

    monkeypatch.setattr(sc, "_git_ok", with_race)
    ok, reason = sc._delete_branch(repo, branch, "main", 3)
    assert not ok
    assert "not fully merged" in reason
    assert branch in branch_names(repo)


def test_branch_delete_refuses_ambiguous_tracking_configuration(sc, tmp_path):
    repo = make_repo(tmp_path)
    branch = "task/115-ambiguous-tracking"
    make_task_branch(repo, branch, "merged.txt")
    track_task_branch(repo, branch)
    git(repo, "config", "--add", f"branch.{branch}.merge", "refs/heads/another-task")

    ok, reason = sc._delete_branch(repo, branch, "main", 3)
    assert not ok
    assert "ambiguous upstream" in reason
    assert branch in branch_names(repo)


def test_refuses_when_no_origin_main(sc, tmp_path):
    repo = make_repo(tmp_path)
    wt = tmp_path / "no-origin-wt"
    make_task_worktree(repo, "task/109-noorigin", wt)
    merge_branch(repo, "task/109-noorigin")
    git(repo, "update-ref", "-d", "refs/remotes/origin/main")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin="/nonexistent-gh",
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["main_fresh"] is False
    assert report["removed"] == []
    assert wt.exists()


def test_refuses_ambiguous_provenance(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "feature-wt"
    make_task_worktree(repo, "feature/not-a-task", wt)
    merge_branch(repo, "feature/not-a-task")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    reasons = reasons_for(report, str(wt))
    assert any("does not match task branch convention" in reason for reason in reasons)
    assert wt.exists()
    assert "feature/not-a-task" in branch_names(repo)


def test_refuses_detached_worktree(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    detached = tmp_path / "detached-wt"
    # A worktree checked out at a commit (not a branch) has no branch provenance.
    git(repo, "worktree", "add", "-q", str(detached), "HEAD")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    reasons = reasons_for(report, str(detached))
    assert any("detached" in reason for reason in reasons)
    assert detached.exists()


def test_branch_checked_out_in_refused_worktree_is_preserved(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    wt = tmp_path / "dirty-parent-wt"
    make_task_worktree(repo, "task/111-parent", wt)
    merge_branch(repo, "task/111-parent")
    (wt / "stray.txt").write_text("untracked\n")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    reasons = reasons_for(report, "task/111-parent")
    assert any("checked out in another worktree" in reason for reason in reasons)
    assert "task/111-parent" in branch_names(repo)


# --- scope / boundedness ---------------------------------------------------


def test_cross_project_cleanup_touches_only_target_repo(sc, tmp_path, monkeypatch):
    repo_a = make_repo(tmp_path, "repo-a")
    repo_b = make_repo(tmp_path, "repo-b")
    wt_a = tmp_path / "repo-a-wt"
    wt_b = tmp_path / "repo-b-wt"
    make_task_worktree(repo_a, "task/200-a", wt_a)
    merge_branch(repo_a, "task/200-a")
    make_task_worktree(repo_b, "task/201-b", wt_b)
    merge_branch(repo_b, "task/201-b")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")
    gh = str(make_fake_gh(tmp_path))

    report = sc.run_startup_cleanup(
        repo_a,
        min_interval_seconds=0,
        gh_bin=gh,
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert len(report["removed"]) == 1
    assert not wt_a.exists()
    assert wt_b.exists()
    assert "task/201-b" in branch_names(repo_b)


def test_worktree_cap_refuses_cleanup(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    make_task_worktree(repo, "task/300-a", tmp_path / "cap-a")
    merge_branch(repo, "task/300-a")
    make_task_worktree(repo, "task/301-b", tmp_path / "cap-b")
    merge_branch(repo, "task/301-b")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")

    report = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=0,
        max_worktrees=2,  # primary + 2 linked worktrees = 3 > 2
        gh_bin=str(make_fake_gh(tmp_path)),
        trash_fn=FakeTrash(tmp_path / "trash"),
    )

    assert report["removed"] == []
    assert report["summary"]["reason"] == "worktree cap exceeded"
    assert (tmp_path / "cap-a").exists()
    assert (tmp_path / "cap-b").exists()


def test_throttle_skips_second_run(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    make_task_branch(repo, "task/400-throttle", "throttle.txt")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")
    gh = str(make_fake_gh(tmp_path))
    trash = FakeTrash(tmp_path / "trash")

    first = sc.run_startup_cleanup(
        repo, min_interval_seconds=3600, gh_bin=gh, trash_fn=trash
    )
    assert first["throttled"] is False
    assert "task/400-throttle" not in branch_names(repo)

    second = sc.run_startup_cleanup(
        repo, min_interval_seconds=3600, gh_bin=gh, trash_fn=trash
    )
    assert second["throttled"] is True
    assert second["removed"] == []


def test_force_bypasses_throttle(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    make_task_branch(repo, "task/401-force", "force.txt")
    monkeypatch.setenv("FAKE_GH_OPEN_BRANCHES", "[]")
    gh = str(make_fake_gh(tmp_path))

    first = sc.run_startup_cleanup(
        repo, min_interval_seconds=3600, gh_bin=gh, trash_fn=FakeTrash(tmp_path / "trash")
    )
    assert first["throttled"] is False

    forced = sc.run_startup_cleanup(
        repo,
        min_interval_seconds=3600,
        force=True,
        gh_bin=gh,
        trash_fn=FakeTrash(tmp_path / "trash"),
    )
    assert forced["throttled"] is False
    assert forced["removed"] == []


def test_not_a_repo_reports_error(sc, tmp_path):
    report = sc.run_startup_cleanup(tmp_path, min_interval_seconds=0)
    assert report["ok"] is False
    assert "not a git repository" in report["error"]


def test_invalid_explicit_project_never_falls_back_or_consumes_stdin(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.chdir(repo)
    prompt = io.StringIO("user prompt stays available")
    monkeypatch.setattr(sys, "stdin", prompt)
    with pytest.raises(sc.StartupCleanupError, match="explicit project directory"):
        sc._resolve_project_dir(str(tmp_path / "missing"))
    assert prompt.tell() == 0
    assert sc._resolve_project_dir(str(repo)) == repo
    assert prompt.tell() == 0


def test_cli_returns_failure_for_nonrepository(sc, tmp_path):
    result = subprocess.run(
        [sys.executable, str(TOOL), "--project-dir", str(tmp_path), "--dry-run"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_total_budget_refuses_slow_pr_lookup(sc, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    make_task_branch(repo, "task/555-budget", "budget.txt")
    gh = tmp_path / "slow-gha"
    gh.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(10)\nprint('[]')\n")
    gh.chmod(0o755)

    report = sc.run_startup_cleanup(
        repo, gh_bin=str(gh), max_duration_seconds=1,
        active_cwds_fn=lambda timeout: (set(), ""),
    )
    assert "task/555-budget" in branch_names(repo)
    assert report["duration_ms"] < 2500

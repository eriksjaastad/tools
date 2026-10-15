#!/usr/bin/env python3
"""Per-project startup cleanup for merged local task worktrees and branches.

    cleanup="$HOME/projects/_tools/startup-cleanup/startup_cleanup.py"
    python3 "$cleanup" --human
    python3 "$cleanup" --human --dry-run
    python3 "$cleanup" --project-dir ~/projects/ai-memory

The first cleans up and prints a readable report, the second lists what a real
run would try to remove (removing nothing), the third cleans up another
project and prints JSON.

The shared startup check owned by _tools, run by a Claude Code and a Codex
SessionStart hook (--print-claude-hook-config / --print-codex-hook-config
print the entries). Cleanup after a merge does not depend on a session-end
event: the next startup in that project can remove the merged task worktree
and branch. It works on one Git repository: the one containing the folder it
is given or started in. Inherited ``GIT_DIR``, ``GIT_WORK_TREE`` and Git's
other repository-local variables are ignored.

Safety
------
Only task branches (``task/<number>[-<slug>]``) and their linked worktrees are
ever removed, and only when every check passes: local main matches
``origin/<main>`` (there is no fetch, so pull main first), the branch is merged
into main, the worktree has no tracked, untracked or ignored changes, it is
unlocked, no visible process has its working directory in it
(``lsof``), and ``gha`` shows no open PR for the branch. A worktree is trashed only after its branch's deletion checks pass.
A task branch or linked worktree that fails a check, or cannot be verified,
is kept, and the report says why.

Directories go to the Trash (the ``trash`` CLI, then Finder, then
``send2trash``), never ``rm`` or ``git clean``. Branches are deleted with
``git branch -d``, which re-checks the merge. Remote branches are never
touched. To undo, put the directories back from the Trash; the branch's
commits are on main, so ``git branch task/1234-example 0123abc``, with its
name from the report and its tip found in main's history, recreates it.

The run is bounded by ``--max-duration``, a timeout on every external call,
and ``--max-worktrees``/``--max-branches`` caps above which nothing is
removed.

The exit code is 1 when the run's report (schema
``tools.startup-cleanup.v1``) has ``ok: false`` and 0 when it has ``ok: true``.

Hook mode (``--hook``) is for SessionStart, which also fires in folders that
are not repositories. The folder must come from ``--project-dir`` or the stdin
JSON ``cwd``. When Git answers with exactly its not-a-repository message and
no ``.git`` marker is found in the folder or above it, the run reports
``applicable: false`` and exits 0; any other Git error still fails. A direct
run outside a repository is an error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = "tools.startup-cleanup.v1"
MAIN_BRANCH_CANDIDATES = ("main", "master", "trunk")
TASK_BRANCH_RE = re.compile(r"^task/[0-9]+(-.+)?$")
DEFAULT_MIN_INTERVAL_SECONDS = 0
DEFAULT_MAX_WORKTREES = 40
DEFAULT_MAX_BRANCHES = 100
DEFAULT_GIT_TIMEOUT = 3
DEFAULT_GH_TIMEOUT = 5
DEFAULT_TRASH_TIMEOUT = 5
DEFAULT_MAX_DURATION_SECONDS = 35
THROTTLE_STAMP_NAME = "startup-cleanup-last-run"
# Git's exact untranslated message when discovery finds no repository.
NOT_A_REPOSITORY_DIAGNOSTIC = "fatal: not a git repository (or any of the parent directories): .git"
# Git's own list of repository-local variables (`git rev-parse --local-env-vars`,
# what Git's hook scripts unset), kept literal so clearing them costs no probe.
GIT_REPOSITORY_ENV = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT", "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
    "GIT_SHALLOW_FILE", "GIT_COMMON_DIR",
)
_RUN_DEADLINE: float | None = None


class StartupCleanupError(Exception):
    """Internal failure that prevents the check from running at all."""


@dataclass
class Worktree:
    path: str
    head: str = ""
    branch: str | None = None
    locked: bool = False
    prunable: bool = False


@dataclass
class Refusal:
    type: str  # "worktree" | "branch"
    target: str
    branch: str | None
    reasons: list[str] = field(default_factory=list)


@dataclass
class Removal:
    type: str  # "worktree" | "branch"
    target: str
    branch: str | None
    trashed: list[str] = field(default_factory=list)
    branch_deleted: bool = False
    note: str = ""


def _run(
    args: list[str], cwd: Path, timeout: int, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    """Run a subprocess with a mandatory timeout and captured output.

    Raises subprocess.TimeoutExpired / OSError; callers translate those into
    refusal reasons so a failure never silently looks like success.
    """
    if _RUN_DEADLINE is not None:
        remaining = _RUN_DEADLINE - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(args, 0)
        timeout = min(timeout, remaining)
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _git(repo: Path, args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return _run(["git"] + args, cwd=repo, timeout=timeout)


def _git_ok(repo: Path, args: list[str], timeout: int) -> tuple[bool, str, str]:
    """Run git; return (ok, stdout, stderr). Timeout/OSError -> (False, "", msg)."""
    try:
        proc = _git(repo, args, timeout)
    except subprocess.TimeoutExpired:
        return False, "", f"timed out after {timeout}s"
    except OSError as exc:
        return False, "", f"git failed to start: {exc}"
    return proc.returncode == 0, proc.stdout, proc.stderr


def _resolve_repo(project_dir: Path) -> Path:
    ok, out, err = _git_ok(project_dir, ["rev-parse", "--show-toplevel"], DEFAULT_GIT_TIMEOUT)
    if not ok:
        raise StartupCleanupError(f"not a git repository ({project_dir}): {err.strip() or 'rev-parse failed'}")
    return Path(out.strip()).resolve()


def _resolve_hook_repo(project_dir: Path) -> Path | None:
    """Resolve the repository for hook mode; None means no repository applies.

    One ``rev-parse --show-toplevel`` probe, run under ``LC_ALL=C`` so its
    diagnostic is untranslated, decides the outcome; no later probe can turn
    an unexpected first failure into a skip. The folder counts as outside Git
    only when that probe exits 128 with exactly Git's not-a-repository
    diagnostic, GIT_DIR does not bypass discovery, and neither the folder nor
    any ancestor holds a ``.git`` entry that Git could have rejected as
    corrupt. Exit 128 alone is not enough: Git also uses it for real errors
    such as a malformed configuration file. Every other outcome, including a
    timeout, a Git that cannot start, a bare repository, or an unreadable
    ancestor, raises StartupCleanupError.
    """
    prefix = f"cannot determine the git repository for {project_dir}"
    env = {key: value for key, value in os.environ.items() if key != "LANGUAGE"}
    env["LC_ALL"] = "C"
    args = ["git", "rev-parse", "--show-toplevel"]
    try:
        proc = _run(args, project_dir, DEFAULT_GIT_TIMEOUT, env=env)
    except subprocess.TimeoutExpired as exc:
        raise StartupCleanupError(f"{prefix}: git rev-parse --show-toplevel timed out") from exc
    except OSError as exc:
        raise StartupCleanupError(f"{prefix}: git failed to start: {exc}") from exc
    if proc.returncode == 0:
        return Path(proc.stdout.strip()).resolve()
    if proc.returncode != 128 or proc.stderr.strip() != NOT_A_REPOSITORY_DIAGNOSTIC:
        detail = proc.stderr.strip() or "no diagnostic"
        raise StartupCleanupError(
            f"{prefix}: git rev-parse --show-toplevel exited {proc.returncode}: {detail}"
        )
    if os.environ.get("GIT_DIR"):
        raise StartupCleanupError(f"{prefix}: GIT_DIR is set, so Git did not search for a repository")
    for directory in (project_dir, *project_dir.parents):
        marker = directory / ".git"
        try:
            os.lstat(marker)
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError as exc:
            raise StartupCleanupError(f"{prefix}: cannot inspect {marker}: {exc}") from exc
        raise StartupCleanupError(f"{prefix}: Git rejected the repository marker {marker}")
    return None


def _resolve_main_branch(repo: Path) -> str | None:
    for name in MAIN_BRANCH_CANDIDATES:
        ok, _, _ = _git_ok(repo, ["rev-parse", "--verify", f"refs/heads/{name}"], DEFAULT_GIT_TIMEOUT)
        if ok:
            return name
    return None


def _main_fresh(repo: Path, main: str) -> tuple[bool, str]:
    """Local freshness check: refs/heads/<main> must equal refs/remotes/origin/<main>."""
    ok, local, err = _git_ok(repo, ["rev-parse", "--verify", f"refs/heads/{main}"], DEFAULT_GIT_TIMEOUT)
    if not ok:
        return False, f"cannot resolve local {main}: {err.strip()}"
    ok, origin, err = _git_ok(repo, ["rev-parse", "--verify", f"refs/remotes/origin/{main}"], DEFAULT_GIT_TIMEOUT)
    if not ok:
        return False, f"cannot resolve origin/{main}: {err.strip() or 'no origin ref'}"
    if local.strip() != origin.strip():
        return False, f"local {main} ({local.strip()[:12]}) != origin/{main} ({origin.strip()[:12]})"
    return True, ""


def _list_worktrees(repo: Path) -> list[Worktree]:
    ok, out, err = _git_ok(repo, ["worktree", "list", "--porcelain"], DEFAULT_GIT_TIMEOUT)
    if not ok:
        raise StartupCleanupError(f"git worktree list failed: {err.strip()}")
    worktrees: list[Worktree] = []
    current: Worktree | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            current = Worktree(path=line[len("worktree "):])
            worktrees.append(current)
        elif current is None:
            continue
        elif line.startswith("HEAD "):
            current.head = line[len("HEAD "):]
        elif line.startswith("branch refs/heads/"):
            current.branch = line[len("branch refs/heads/"):]
        elif line == "locked" or line.startswith("locked "):
            current.locked = True
        elif line.startswith("prunable "):
            current.prunable = True
    return worktrees


def _worktree_status(wt: Path, timeout: int) -> tuple[list[str], list[str]]:
    """Return (dirty_paths, ignored_paths) for a worktree directory.

    dirty_paths includes tracked modifications and untracked files.
    ignored_paths is the ``!!`` entries from ``status --ignored`` — any
    ignored artifact is treated as meaningful and blocks automatic cleanup.
    A failure to inspect the status is reported as a non-empty dirty list
    with a synthetic reason so the caller refuses (fail closed).
    """
    # --untracked-files=normal overrides a repository's status.showUntrackedFiles=no,
    # which would otherwise hide untracked (and ignored) files from both checks.
    ok, out, err = _git_ok(wt, ["status", "--porcelain", "--untracked-files=normal"], timeout)
    if not ok:
        return [f"<status unavailable: {err.strip() or 'git status failed'}>"], []
    dirty: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = _porcelain_path(line)
        if path:
            dirty.append(path)

    ok, out, err = _git_ok(wt, ["status", "--porcelain", "--ignored", "--untracked-files=normal"], timeout)
    if not ok:
        return dirty, [f"<ignored status unavailable: {err.strip() or 'git status failed'}>"]
    ignored: list[str] = []
    for line in out.splitlines():
        if line.startswith("!!"):
            path = _porcelain_path(line)
            if path:
                ignored.append(path)
    return dirty, ignored


def _porcelain_path(line: str) -> str:
    """Extract the path from a porcelain v1 status line (handles renames)."""
    path_part = line[3:].strip()
    if " -> " in path_part:
        path_part = path_part.split(" -> ", 1)[1]
    return path_part.strip().strip('"')


def _branch_merged(repo: Path, main: str, branch: str, timeout: int) -> tuple[bool, str]:
    ok, _, err = _git_ok(
        repo,
        ["merge-base", "--is-ancestor", f"refs/heads/{branch}", f"refs/heads/{main}"],
        timeout,
    )
    if ok:
        return True, ""
    # rc==1 means "not an ancestor"; anything else is a verification failure.
    if err.strip():
        return False, f"merge-base check failed: {err.strip()}"
    return False, f"branch '{branch}' is not merged into {main}"


def _list_branches(repo: Path) -> list[str]:
    ok, out, err = _git_ok(repo, ["for-each-ref", "--format=%(refname:short)", "refs/heads"], DEFAULT_GIT_TIMEOUT)
    if not ok:
        raise StartupCleanupError(f"git for-each-ref failed: {err.strip()}")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _current_branch(repo: Path) -> str | None:
    ok, out, _ = _git_ok(repo, ["rev-parse", "--abbrev-ref", "HEAD"], DEFAULT_GIT_TIMEOUT)
    return out.strip() if ok and out.strip() != "HEAD" else None


def _worktree_git_dir(wt: Path, timeout: int) -> Path | None:
    ok, out, err = _git_ok(wt, ["rev-parse", "--absolute-git-dir"], timeout)
    if not ok:
        return None
    path = Path(out.strip())
    return path if path.exists() else None


def _parse_remote_slug(repo: Path) -> str | None:
    ok, out, err = _git_ok(repo, ["remote", "get-url", "origin"], DEFAULT_GIT_TIMEOUT)
    if not ok or not out.strip():
        return None
    match = re.search(r"[:/]([^/]+/[^/.]+?)(?:\.git)?$", out.strip())
    return match.group(1) if match else None


def _resolve_gh_bin() -> str | None:
    return shutil.which("gha")


def _open_prs(gh_bin: str, repo_slug: str, branch: str, timeout: int) -> tuple[str, list[dict]]:
    """Return (status, prs). status: "none" | "open" | "unavailable" | "error"."""
    proc = None
    try:
        proc = _run(
            [
                gh_bin, "pr", "list",
                "--repo", repo_slug,
                "--head", branch,
                "--state", "open",
                "--json", "number,title,url",
                "--limit", "10",
            ],
            cwd=Path.cwd(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "error", []
    except OSError as exc:
        return "unavailable", []
    if proc.returncode != 0:
        return "error", []
    try:
        prs = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return "error", []
    if not isinstance(prs, list):
        return "error", []
    return ("open" if prs else "none"), prs


def _trash_with_send2trash(path: Path, timeout: int) -> tuple[bool, str]:
    try:
        proc = _run(
            [sys.executable, "-c",
             "import sys; from send2trash import send2trash; send2trash(sys.argv[1])",
             str(path)],
            path.parent,
            timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"send2trash timed out after {timeout}s"
    except OSError as exc:
        return False, f"send2trash failed to start: {exc}"
    if proc.returncode != 0:
        return False, proc.stderr.strip() or "send2trash failed"
    return not path.exists(), "send2trash did not remove the path"


def _trash_with_cli(path: Path, timeout: int) -> tuple[bool, str]:
    trash_bin = shutil.which("trash")
    if not trash_bin:
        return False, "no /usr/bin/trash"
    try:
        proc = _run([trash_bin, str(path)], cwd=path.parent, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"trash CLI timed out after {timeout}s"
    except OSError as exc:
        return False, f"trash CLI failed to start: {exc}"
    if proc.returncode != 0:
        return False, (proc.stderr.strip() or "trash CLI returned non-zero")
    return not path.exists(), "trash CLI did not remove the path"


def _trash_with_osascript(path: Path, timeout: int) -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "no supported trash backend on this platform"
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Finder" to delete (POSIX file "{escaped}" as alias)'
    try:
        proc = _run(["osascript", "-e", script], cwd=path.parent, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"osascript timed out after {timeout}s"
    except OSError as exc:
        return False, f"osascript failed to start: {exc}"
    if proc.returncode != 0:
        return False, (proc.stderr.strip() or "osascript returned non-zero")
    return not path.exists(), "osascript did not remove the path"


def trash_path(path: Path, timeout: int = DEFAULT_TRASH_TIMEOUT) -> tuple[bool, str]:
    """Move a path to a recoverable Trash. Never uses rm or git clean."""
    path = path.resolve()
    if not path.exists():
        return True, "already absent"
    ok, reason = _trash_with_cli(path, timeout)
    if ok:
        return True, "trash CLI"
    ok2, reason2 = _trash_with_osascript(path, timeout)
    if ok2:
        return True, "osascript"
    ok3, reason3 = _trash_with_send2trash(path, timeout)
    if ok3:
        return True, "send2trash"
    return False, "; ".join(filter(None, [reason, reason2, reason3]))


def _prepare_branch_deletion(
    repo: Path, branch: str, main: str, timeout: int
) -> tuple[tuple[Path, list[str]] | None, str]:
    """Check that `git branch -d` can delete the branch against local main.

    Returns ((primary checkout, command-local git options), "") when it can,
    or (None, reason) when it cannot. Nothing is changed.
    """
    merged, reason = _branch_merged(repo, main, branch, timeout)
    if not merged:
        return None, reason
    try:
        worktrees = _list_worktrees(repo)
    except StartupCleanupError as exc:
        return None, str(exc)
    if not worktrees:
        return None, "no primary checkout available for safe branch deletion"
    primary = Path(worktrees[0].path)
    if worktrees[0].branch != main or not primary.is_dir():
        return None, f"primary checkout is not on {main}"
    ok, main_tip, err = _git_ok(repo, ["rev-parse", "--verify", f"refs/heads/{main}"], timeout)
    if not ok:
        return None, err.strip() or "cannot resolve main tip"
    ok, primary_head, err = _git_ok(primary, ["rev-parse", "HEAD"], timeout)
    if not ok or primary_head.strip() != main_tip.strip():
        return None, "primary checkout HEAD does not match main"
    # `git branch -d` normally checks the tracked upstream instead of HEAD.
    # A task branch can advance alongside origin/task after our ancestry check;
    # deleting it then would lose a tip that is not in local main. Supply a
    # command-local remote whose fetch refspec resolves that upstream to main.
    # The saved branch tracking configuration is never changed.
    try:
        config = _git(repo, ["config", "--null", "--get-all", f"branch.{branch}.merge"], timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"cannot inspect branch upstream: {exc}"
    if config.returncode == 0:
        if not config.stdout.endswith("\0"):
            return None, "malformed branch upstream configuration"
        merge_values = config.stdout[:-1].split("\0")
        if len(merge_values) != 1 or not merge_values[0]:
            return None, "branch has ambiguous upstream merge configuration"
        merge_ref = merge_values[0]
    elif config.returncode == 1 and not config.stdout and not config.stderr:
        merge_ref = f"refs/heads/{branch}"
    else:
        return None, config.stderr.strip() or "cannot inspect branch upstream"
    if not merge_ref.startswith("refs/heads/"):
        return None, f"unsupported branch upstream ref: {merge_ref}"
    ok, _, err = _git_ok(repo, ["check-ref-format", merge_ref], timeout)
    if not ok:
        return None, err.strip() or "invalid branch upstream ref"

    remote = f"startup-cleanup-{uuid.uuid4().hex}"
    options = [
        "-c", f"branch.{branch}.remote={remote}",
        "-c", f"remote.{remote}.fetch={merge_ref}:refs/heads/{main}",
    ]
    if config.returncode == 1:
        options += ["-c", f"branch.{branch}.merge={merge_ref}"]
    ok, upstream, err = _git_ok(
        primary, [*options, "rev-parse", "--symbolic-full-name", f"{branch}@{{upstream}}"], timeout
    )
    if not ok or upstream.strip() != f"refs/heads/{main}":
        return None, err.strip() or "cannot map branch deletion check to local main"
    return (primary, options), ""


def _delete_prepared_branch(
    branch: str, prepared: tuple[Path, list[str]], timeout: int
) -> tuple[bool, str]:
    """Delete with `git branch -d`, which re-checks the merge and checkouts itself."""
    primary, options = prepared
    ok, _, err = _git_ok(primary, [*options, "branch", "-d", branch], timeout)
    if ok:
        return True, ""
    return False, err.strip() or "git branch -d failed"


def _delete_branch(repo: Path, branch: str, main: str, timeout: int) -> tuple[bool, str]:
    """Make Git's own deletion check use local main, not the branch's upstream."""
    prepared, reason = _prepare_branch_deletion(repo, branch, main, timeout)
    if prepared is None:
        return False, reason
    return _delete_prepared_branch(branch, prepared, timeout)


def _checked_out_branches(worktrees: list[Worktree]) -> set[str]:
    return {wt.branch for wt in worktrees if wt.branch}


def _active_cwds(timeout: int) -> tuple[set[Path] | None, str]:
    """Inspect process working directories; unknown activity blocks removal.

    An agent can be using a clean linked worktree other than the checkout that
    started this hook. On macOS, lsof lists the cwd of each visible process.
    A failed or unavailable inspection must preserve every linked worktree.
    """
    lsof = shutil.which("lsof")
    if not lsof:
        return None, "lsof unavailable; cannot verify active sessions"
    try:
        proc = _run([lsof, "-n", "-Fpcn", "-d", "cwd"], Path.cwd(), timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"active-session inspection failed: {exc}"
    if proc.returncode != 0:
        return None, f"active-session inspection failed (lsof exit {proc.returncode})"
    return {Path(line[1:]).resolve() for line in proc.stdout.splitlines()
            if line.startswith("n") and line[1:].startswith("/")}, ""


def _has_active_cwd(worktree: Path, active_cwds: set[Path]) -> bool:
    worktree = worktree.resolve()
    for cwd in active_cwds:
        if cwd == worktree or worktree in cwd.parents:
            return True
    return False


def _report_worktree_refusal(
    refusals: list[Refusal], wt: Worktree, reasons: list[str]
) -> None:
    if reasons:
        refusals.append(Refusal(type="worktree", target=wt.path, branch=wt.branch, reasons=reasons))


def _remove_worktree(
    repo: Path,
    wt: Worktree,
    main: str,
    trash_fn,
    timeout: int,
    dry_run: bool,
) -> Removal:
    removal = Removal(type="worktree", target=wt.path, branch=wt.branch)
    wt_path = Path(wt.path)
    git_dir = _worktree_git_dir(wt_path, timeout)
    common_dir = _git_common_dir(repo)

    if wt_path.is_symlink():
        removal.note = "refused: worktree path is a symlink"
        return removal
    if git_dir is None or common_dir is None:
        removal.note = "refused: cannot verify linked-worktree admin directory"
        return removal
    try:
        git_dir.resolve().relative_to((common_dir.resolve() / "worktrees"))
    except ValueError:
        removal.note = "refused: linked-worktree admin directory is outside common git dir"
        return removal
    # Check the branch can go before touching the worktree, so a branch Git
    # would keep never leaves its worktree half removed.
    prepared = None
    if wt.branch:
        prepared, reason = _prepare_branch_deletion(repo, wt.branch, main, timeout)
        if prepared is None:
            removal.note = f"refused: branch '{wt.branch}' cannot be deleted: {reason}"
            return removal

    if dry_run:
        removal.note = "dry-run: would trash worktree directory" + (
            f", admin dir {git_dir}" if git_dir else ""
        ) + f", and delete branch {wt.branch}"
        return removal

    # 1. Recoverably trash the worktree directory.
    ok, reason = trash_fn(wt_path)
    if not ok:
        removal.note = f"refused: trash failed for worktree directory: {reason}"
        return removal
    removal.trashed.append(str(wt_path))

    # 2. Recoverably trash the linked-worktree admin dir (surgical; equivalent
    #    to what `git worktree prune` would remove, but only for this entry).
    ok, reason = trash_fn(git_dir)
    if ok:
        removal.trashed.append(str(git_dir))
    else:
        removal.note = f"worktree directory trashed but admin dir kept (trash failed): {reason}"
        return removal

    # 3. Delete the now-unregistered branch with git's own merged-only safety.
    if prepared is not None:
        ok, err = _delete_prepared_branch(wt.branch, prepared, timeout)
        if ok:
            removal.branch_deleted = True
        else:
            removal.note = f"worktree removed but branch '{wt.branch}' kept: {err}"
    return removal


def _git_common_dir(repo: Path) -> Path | None:
    ok, out, err = _git_ok(repo, ["rev-parse", "--git-common-dir"], DEFAULT_GIT_TIMEOUT)
    if not ok:
        return None
    path = Path(out.strip())
    if not path.is_absolute():
        path = repo / path
    return path


def _read_throttle_stamp(stamp: Path) -> float | None:
    if not stamp.exists():
        return None
    try:
        return float(stamp.read_text().strip())
    except (OSError, ValueError) as exc:
        raise StartupCleanupError(f"cannot read throttle stamp {stamp}: {exc}") from exc


def _write_throttle_stamp(stamp: Path, now: float) -> None:
    try:
        stamp.write_text(f"{now:.6f}\n")
    except OSError as exc:
        # Best effort: the report remains truthful and a later startup retries.
        print(f"startup-cleanup: cannot write throttle stamp {stamp}: {exc}", file=sys.stderr)


def run_startup_cleanup(
    project_dir: Path,
    *,
    min_interval_seconds: int = DEFAULT_MIN_INTERVAL_SECONDS,
    max_worktrees: int = DEFAULT_MAX_WORKTREES,
    max_branches: int = DEFAULT_MAX_BRANCHES,
    timeout: int = DEFAULT_GIT_TIMEOUT,
    force: bool = False,
    dry_run: bool = False,
    gh_bin: str | None = None,
    trash_fn=trash_path,
    active_cwds_fn=None,
    now: float | None = None,
    max_duration_seconds: int = DEFAULT_MAX_DURATION_SECONDS,
    hook: bool = False,
) -> dict:
    """Run one bounded per-project startup cleanup check.

    Returns the JSON-serializable report. Never raises for environmental
    refusals; StartupCleanupError is raised only when the repository itself
    cannot be inspected. With ``hook=True`` a folder confirmed to be outside
    any Git repository yields an ok report with ``applicable`` false.
    """
    started = time.time()
    now = time.time() if now is None else now
    global _RUN_DEADLINE
    _RUN_DEADLINE = time.monotonic() + max_duration_seconds

    report: dict = {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "dry_run": dry_run,
        "throttled": False,
        "project_dir": str(project_dir),
        "removed": [],
        "planned": [],
        "refused": [],
        "reports": [],
    }

    try:
        repo = _resolve_hook_repo(project_dir) if hook else _resolve_repo(project_dir)
    except StartupCleanupError as exc:
        report["ok"] = False
        report["error"] = str(exc)
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report
    if repo is None:
        report["applicable"] = False
        report["summary"] = {"reason": "not in a git repository"}
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report
    report["repo_root"] = str(repo)

    common_dir = _git_common_dir(repo)
    if common_dir is None:
        report["ok"] = False
        report["error"] = "cannot resolve git common dir"
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report
    stamp = common_dir / THROTTLE_STAMP_NAME

    if not force and min_interval_seconds > 0:
        try:
            previous = _read_throttle_stamp(stamp)
        except StartupCleanupError as exc:
            report["ok"] = False
            report["error"] = str(exc)
            report["duration_ms"] = int((time.time() - started) * 1000)
            return report
        if previous is not None and (now - previous) < min_interval_seconds:
            report["throttled"] = True
            report["summary"] = {"reason": f"last run {int(now - previous)}s ago; interval {min_interval_seconds}s"}
            report["duration_ms"] = int((time.time() - started) * 1000)
            return report

    main = _resolve_main_branch(repo)
    if main is None:
        report["reports"].append(
            {"level": "warning", "message": "no main/master/trunk branch found; nothing removed"}
        )
        report["summary"] = {"reason": "no main branch"}
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report
    report["main_branch"] = main

    fresh, fresh_reason = _main_fresh(repo, main)
    report["main_fresh"] = fresh
    if not fresh:
        report["reports"].append(
            {"level": "warning", "message": f"main is not fresh: {fresh_reason}; automatic cleanup disabled"}
        )
        report["summary"] = {"reason": "main not fresh", "detail": fresh_reason}
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report

    try:
        worktrees = _list_worktrees(repo)
    except StartupCleanupError as exc:
        report["ok"] = False
        report["error"] = str(exc)
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report
    if len(worktrees) > max_worktrees:
        report["reports"].append(
            {
                "level": "warning",
                "message": (
                    f"{len(worktrees)} worktrees exceeds cap {max_worktrees}; "
                    "refusing automatic cleanup (bounded startup)"
                ),
            }
        )
        report["summary"] = {"reason": "worktree cap exceeded", "worktrees": len(worktrees)}
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report

    try:
        branches = _list_branches(repo)
    except StartupCleanupError as exc:
        report["ok"] = False
        report["error"] = str(exc)
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report
    if len(branches) > max_branches:
        report["reports"].append(
            {
                "level": "warning",
                "message": (
                    f"{len(branches)} branches exceeds cap {max_branches}; "
                    "refusing automatic cleanup (bounded startup)"
                ),
            }
        )
        report["summary"] = {"reason": "branch cap exceeded", "branches": len(branches)}
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report

    if gh_bin is None:
        gh_bin = _resolve_gh_bin()
    repo_slug = _parse_remote_slug(repo)

    # Primary checkout = first worktree block; also never touch the checkout
    # we are running from (the agent's active session).
    primary_path = worktrees[0].path if worktrees else None
    current_repo_path = str(repo)
    if active_cwds_fn is None:
        active_cwds_fn = _active_cwds
    active_cwds, activity_error = active_cwds_fn(timeout)
    refusals: list[Refusal] = []
    removed: list[Removal] = []
    budget_exhausted = False

    for wt in worktrees:
        if wt.path == primary_path:
            continue
        if Path(wt.path).resolve() == Path(current_repo_path).resolve():
            _report_worktree_refusal(
                refusals, wt, [f"active session worktree (current project checkout)"]
            )
            continue
        reasons: list[str] = []
        if time.monotonic() > _RUN_DEADLINE - 25:
            reasons.append("startup time budget nearly exhausted; preserve worktree")
            budget_exhausted = True
        if wt.prunable:
            reasons.append("worktree directory already missing (stale/prunable); report only")
        if wt.branch is None:
            reasons.append("detached worktree has no branch provenance")
        if wt.locked:
            reasons.append("worktree is locked")
        if active_cwds is None:
            reasons.append(activity_error)
        elif _has_active_cwd(Path(wt.path), active_cwds):
            reasons.append("active process has a working directory in this worktree")
        if wt.branch and not TASK_BRANCH_RE.match(wt.branch):
            reasons.append(f"branch '{wt.branch}' does not match task branch convention")
        if wt.branch and TASK_BRANCH_RE.match(wt.branch):
            merged, merged_reason = _branch_merged(repo, main, wt.branch, timeout)
            if not merged:
                reasons.append(merged_reason)
        if wt.prunable is False and Path(wt.path).exists():
            dirty, ignored = _worktree_status(Path(wt.path), timeout)
            if dirty:
                reasons.append(f"worktree is dirty: {', '.join(dirty[:5])}")
            if ignored:
                reasons.append(f"worktree has meaningful ignored files: {', '.join(ignored[:5])}")
        else:
            reasons.append("worktree directory missing; cannot verify clean state")
        if not reasons and wt.branch:
            if gh_bin is None:
                reasons.append("GitHub CLI unavailable (no gha); cannot verify no open PR")
            elif repo_slug is None:
                reasons.append("no origin remote; cannot verify no open PR")
            else:
                pr_status, prs = _open_prs(gh_bin, repo_slug, wt.branch, DEFAULT_GH_TIMEOUT)
                if pr_status == "open":
                    reasons.append(
                        "open PR(s): " + ", ".join(str(p.get("number", "?")) for p in prs)
                    )
                elif pr_status != "none":
                    reasons.append(f"open-PR check {pr_status}; cannot verify no open PR")
        if reasons:
            _report_worktree_refusal(refusals, wt, reasons)
        else:
            if time.monotonic() > _RUN_DEADLINE - 27:
                budget_exhausted = True
                _report_worktree_refusal(
                    refusals, wt, ["startup time budget too short for recoverable worktree removal"]
                )
                continue
            removal = _remove_worktree(repo, wt, main, trash_fn, timeout, dry_run)
            if removal.note.startswith("refused:"):
                refusals.append(Refusal("worktree", wt.path, wt.branch, [removal.note]))
            else:
                removed.append(removal)

    # Standalone branches: task-convention branches merged into main that are
    # not checked out in any remaining worktree.
    try:
        remaining_worktrees = _list_worktrees(repo)
        current_branches = _list_branches(repo)
    except StartupCleanupError as exc:
        report["ok"] = False
        report["error"] = f"could not refresh worktree list after removals: {exc}"
        report["planned" if dry_run else "removed"] = [r.__dict__ for r in removed]
        report["refused"] = [
            {"type": r.type, "target": r.target, "branch": r.branch, "reasons": r.reasons}
            for r in refusals
        ]
        report["duration_ms"] = int((time.time() - started) * 1000)
        return report
    checked_out = _checked_out_branches(remaining_worktrees)
    current_branch = _current_branch(repo)
    for branch in sorted(set(current_branches)):
        if branch == main:
            continue
        if not TASK_BRANCH_RE.match(branch):
            continue
        reasons: list[str] = []
        if time.monotonic() > _RUN_DEADLINE - 10:
            reasons.append("startup time budget nearly exhausted; preserve branch")
            budget_exhausted = True
        if branch == current_branch:
            reasons.append("current checkout branch (active session)")
        if branch in checked_out:
            reasons.append("branch is checked out in another worktree")
        merged, merged_reason = _branch_merged(repo, main, branch, timeout)
        if not merged:
            reasons.append(merged_reason)
        if not reasons:
            if gh_bin is None:
                reasons.append("GitHub CLI unavailable (no gha); cannot verify no open PR")
            elif repo_slug is None:
                reasons.append("no origin remote; cannot verify no open PR")
            else:
                pr_status, prs = _open_prs(gh_bin, repo_slug, branch, DEFAULT_GH_TIMEOUT)
                if pr_status == "open":
                    reasons.append(
                        "open PR(s): " + ", ".join(str(p.get("number", "?")) for p in prs)
                    )
                elif pr_status != "none":
                    reasons.append(f"open-PR check {pr_status}; cannot verify no open PR")
        if reasons:
            refusals.append(Refusal("branch", branch, branch, reasons))
            continue
        if dry_run:
            removed.append(Removal("branch", branch, branch, note="dry-run: would delete branch"))
            continue
        ok, err = _delete_branch(repo, branch, main, timeout)
        if ok:
            removed.append(Removal("branch", branch, branch, branch_deleted=True))
        else:
            refusals.append(Refusal("branch", branch, branch, [f"branch delete failed: {err}"]))

    report["planned" if dry_run else "removed"] = [r.__dict__ for r in removed]
    report["refused"] = [
        {"type": r.type, "target": r.target, "branch": r.branch, "reasons": r.reasons}
        for r in refusals
    ]
    report["summary"] = {
        "worktrees_scanned": max(0, len(worktrees) - 1),
        "branches_scanned": len([b for b in branches if b != main and TASK_BRANCH_RE.match(b)]),
        "worktrees_removed": sum(1 for r in removed if r.type == "worktree") if not dry_run else 0,
        "branches_deleted": sum(1 for r in removed if r.branch_deleted) if not dry_run else 0,
        "worktrees_planned": sum(1 for r in removed if r.type == "worktree") if dry_run else 0,
        "branches_planned": sum(1 for r in removed if r.branch) if dry_run else 0,
        "refusals": len(refusals),
    }
    for refusal in refusals:
        report["reports"].append(
            {
                "level": "warning",
                "message": (
                    f"preserved {refusal.type} '{refusal.target}'"
                    f"{(' (branch ' + refusal.branch + ')') if refusal.branch else ''}: "
                    + "; ".join(refusal.reasons)
                ),
            }
        )
    _maybe_stamp(dry_run or budget_exhausted or bool(refusals) or min_interval_seconds <= 0,
                 stamp, now)
    report["duration_ms"] = int((time.time() - started) * 1000)
    return report


def _maybe_stamp(dry_run: bool, stamp: Path, now: float) -> None:
    if not dry_run:
        _write_throttle_stamp(stamp, now)


def _read_hook_project_dir(required: bool = False) -> str | None:
    """Read a project dir from hook stdin JSON without blocking on a TTY.

    With ``required`` (hook mode) the payload must be a JSON object whose
    ``cwd`` is a non-empty string; the legacy aliases are not consulted.
    """
    try:
        raw = "" if sys.stdin.isatty() else sys.stdin.read()
        if not raw.strip():
            if required:
                raise StartupCleanupError("startup hook input is missing; expected JSON with cwd")
            return None
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise StartupCleanupError(f"invalid startup hook input: {exc}") from exc
    if required:
        cwd = payload.get("cwd") if isinstance(payload, dict) else None
        if not (isinstance(cwd, str) and cwd):
            raise StartupCleanupError(
                "invalid startup hook input: expected a JSON object with a non-empty cwd string"
            )
        return cwd
    try:
        cwd = payload.get("cwd") or payload.get("project_dir") or payload.get("working_directory")
    except AttributeError as exc:
        raise StartupCleanupError(f"invalid startup hook input: {exc}") from exc
    return str(cwd) if cwd else None


def _resolve_project_dir(cli_dir: str | None, hook: bool = False) -> Path:
    if cli_dir:
        path = Path(cli_dir)
        if not path.is_dir():
            raise StartupCleanupError(f"explicit project directory does not exist: {cli_dir}")
        return path.resolve()
    if hook:
        # The session cwd is authoritative; never fall back to the process cwd.
        cwd = _read_hook_project_dir(required=True)
        if cwd is None or not Path(cwd).is_dir():
            raise StartupCleanupError(f"startup hook cwd is not an existing directory: {cwd}")
        return Path(cwd).resolve()
    candidates = [_read_hook_project_dir(), os.getcwd()]
    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            return Path(candidate).resolve()
    raise StartupCleanupError("no valid project directory in hook input or current directory")


def _print_human(report: dict) -> None:
    if report.get("throttled"):
        print(f"startup-cleanup: throttled — {report['summary'].get('reason', '')}")
        return
    if not report.get("ok"):
        print(f"startup-cleanup: could not run — {report.get('error', 'unknown error')}")
        return
    if report.get("applicable") is False:
        print(f"startup-cleanup: skipped — {report['project_dir']} is not in a Git repository; "
              "no cleanup applies")
        return
    root = report.get("repo_root", report.get("project_dir", "?"))
    print(f"startup-cleanup: repo={root} main={report.get('main_branch', '?')} "
          f"fresh={report.get('main_fresh', '?')}")
    summary = report.get("summary", {})
    if report.get("dry_run"):
        print(
            "summary: dry-run "
            f"worktrees_planned={summary.get('worktrees_planned', 0)} "
            f"branches_planned={summary.get('branches_planned', 0)} "
            f"refusals={summary.get('refusals', 0)} "
            f"({report.get('duration_ms', 0)}ms)"
        )
    else:
        print(
            "summary: "
            f"worktrees_removed={summary.get('worktrees_removed', 0)} "
            f"branches_deleted={summary.get('branches_deleted', 0)} "
            f"refusals={summary.get('refusals', 0)} "
            f"({report.get('duration_ms', 0)}ms)"
        )
    for item in report.get("removed", []):
        print(f"  removed {item['type']} {item['target']}"
              f"{(' branch=' + item['branch']) if item.get('branch') else ''}"
              f"{(' note=' + item['note']) if item.get('note') else ''}")
    for item in report.get("planned", []):
        print(f"  planned {item['type']} {item['target']}"
              f"{(' branch=' + item['branch']) if item.get('branch') else ''}"
              f"{(' note=' + item['note']) if item.get('note') else ''}")
    for message in report.get("reports", []):
        print(f"  {message['level']}: {message['message']}")


def _hook_command(provider: str) -> str:
    # Emit the installed path (the real _tools checkout), not the sandbox
    # worktree path this copy may currently live in.
    script = "$HOME/projects/_tools/startup-cleanup/startup_cleanup.py"
    if provider == "claude":
        return json.dumps(
            {
                "matcher": "^startup$",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'python3 "{script}" --hook --human',
                        "timeout": 45,
                    }
                ]
            },
            indent=2,
        )
    return json.dumps(
        {
            "matcher": "^startup$",
            "hooks": [
                {
                    "type": "command",
                    "command": f'python3 "{script}" --hook --human',
                    "timeout": 45,
                }
            ]
        },
        indent=2,
    )


def _clear_inherited_repository_env() -> None:
    """Drop inherited Git variables that would point every git call elsewhere.

    A hook or wrapper can inherit GIT_DIR, GIT_WORK_TREE and similar from its
    parent, which would make the cleanup inspect and delete in that repository
    while reporting the project folder.
    """
    for name in GIT_REPOSITORY_ENV:
        os.environ.pop(name, None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="startup_cleanup.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project-dir", help="Project directory to inspect (default: hook env/stdin/PWD)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be removed without removing")
    parser.add_argument("--force", action="store_true", help="Bypass the throttle interval")
    parser.add_argument(
        "--min-interval",
        type=int,
        default=DEFAULT_MIN_INTERVAL_SECONDS,
        help=f"Minimum seconds between runs (default {DEFAULT_MIN_INTERVAL_SECONDS}; 0 disables)",
    )
    parser.add_argument("--max-worktrees", type=int, default=DEFAULT_MAX_WORKTREES)
    parser.add_argument("--max-branches", type=int, default=DEFAULT_MAX_BRANCHES)
    parser.add_argument("--timeout", type=int, default=DEFAULT_GIT_TIMEOUT, help="Per-git-subprocess timeout")
    parser.add_argument("--max-duration", type=int, default=DEFAULT_MAX_DURATION_SECONDS,
                        help="Total seconds allowed for one startup scan")
    parser.add_argument("--human", action="store_true", help="Human-readable output instead of JSON")
    parser.add_argument(
        "--hook",
        action="store_true",
        help="SessionStart hook mode: require the session cwd on stdin and report a "
             "folder outside any Git repository as not applicable (exit 0)",
    )
    parser.add_argument(
        "--print-claude-hook-config",
        action="store_true",
        help="Print the JSON hook entry to add to ~/.claude/settings.json SessionStart",
    )
    parser.add_argument(
        "--print-codex-hook-config",
        action="store_true",
        help="Print the JSON hook entry to add to ~/.codex/hooks.json SessionStart",
    )
    args = parser.parse_args(argv)

    if args.print_claude_hook_config:
        print(_hook_command("claude"))
        return 0
    if args.print_codex_hook_config:
        print(_hook_command("codex"))
        return 0

    try:
        _clear_inherited_repository_env()
        project_dir = _resolve_project_dir(args.project_dir, hook=args.hook)
    except StartupCleanupError as exc:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "ok": False, "error": str(exc)}))
        return 1
    report = run_startup_cleanup(
        project_dir,
        min_interval_seconds=args.min_interval,
        max_worktrees=args.max_worktrees,
        max_branches=args.max_branches,
        timeout=args.timeout,
        force=args.force,
        dry_run=args.dry_run,
        max_duration_seconds=args.max_duration,
        hook=args.hook,
    )

    if args.human:
        _print_human(report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StartupCleanupError as exc:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "ok": False, "error": str(exc)}))
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)

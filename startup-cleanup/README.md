# startup-cleanup

Safe, bounded, per-project startup cleanup for merged local **task worktrees and
branches**. This is the shared startup mechanism owned by `_tools` for the
post-merge leftovers that previously accumulated after PR merges (e.g. six
merged `claude-user-config` worktrees after PR #102, Muffin Pan Recipes
cleanup). It replaces the missing shutdown path (card #5635) with a startup
path that does not depend on a session-end event firing.

## What it does

On startup (or on demand) it inspects **only the git repository the invoking
agent started inside**. It inventories:

- all linked worktrees via `git worktree list --porcelain`, including
  worktrees outside `.claude/worktrees/` (isolated `/private/tmp` worktrees
  are covered), and
- all local branches via `git for-each-ref refs/heads`.

It automatically removes only entries that pass **every** gate below, and it
reports (preserving) everything else as a refusal.

## Automatic-removal gates (all required)

| Gate | Check |
|------|-------|
| Provenance | branch matches the task convention `task/<number>[-<slug>]` |
| Merged | `git merge-base --is-ancestor refs/heads/<branch> refs/heads/main` |
| Fresh main | local `main` equals `refs/remotes/origin/main` (no network fetch at startup) |
| Clean tracked state | `git status --porcelain` empty in the worktree |
| Clean untracked state | covered by the same status check |
| No meaningful ignored state | no `!!` entries in `git status --porcelain --ignored` |
| Not locked | worktree not marked `locked` in porcelain output |
| Not active | worktree is not the primary/current checkout, and no visible process has its working directory in the worktree or a child directory (`lsof`); unknown inspection preserves it |
| No open PR | `gha pr list --head <branch> --state open` returns zero results |
| GitHub verifiable | a GitHub CLI is available and the PR check succeeds (fail closed) |

Any ambiguity — detached worktrees, missing directories, a dirty tree,
unavailable `gha` or `lsof`, an origin remote that cannot be parsed, a cap being
exceeded — is **refused and reported**, never silently deleted.

## Recoverable Trash, never `rm` or `git clean`

Directory removal tries, in order:

1. the native macOS `/usr/bin/trash` CLI,
2. the Finder AppleScript fallback (`tell application "Finder" to delete ...`),
3. Python `send2trash` in a bounded subprocess (the same backend
   `pt retire-project` uses).

If none succeeds, deletion is refused and the item is preserved with a report.
After the worktree directory is trashed, its per-worktree admin directory under
`<main>/.git/worktrees/<name>` is trashed the same way (this is the surgical
equivalent of `git worktree prune`, scoped to exactly one entry), and finally
the branch is deleted with `git branch -d` from a verified primary `main`
checkout. A command-local Git configuration maps the branch's upstream to
local `main` for that deletion only; the saved tracking settings are untouched.
The tool verifies the mapping before deletion. Git then checks the current tip
against `main` and rejects a branch that has become unmerged or checked out in
another worktree.

Remote branches are never touched. `git clean -fdx` is never used.

## Bounded startup

- **Optional throttle**: a stamp file under the git common directory skips
  repeated fully checked runs when `--min-interval` is set. It defaults to 0
  so the next startup after a merge can clean immediately. Refusals and
  incomplete scans do not write the stamp; `--force` bypasses it.
- **Caps**: more than `--max-worktrees` (default 40) worktrees or more than
  `--max-branches` (default 100) branches makes the check fail closed and
  report instead of scanning unbounded input.
- **Timeouts**: the whole scan has a 35s budget and the native hooks allow
  45s. Each git subprocess has `--timeout` (default 3s), PR lookups 5s,
  and Trash backends 5s. Cleanup refuses a candidate when too little budget
  remains to finish its recoverable removal.
- Reruns are idempotent: once an entry is removed, later runs find nothing.

## Manual invocation

```bash
# JSON report (default for direct use)
python3 ~/projects/_tools/startup-cleanup/startup_cleanup.py --project-dir ~/projects/<project>

# Human-readable
python3 ~/projects/_tools/startup-cleanup/startup_cleanup.py --project-dir ~/projects/<project> --human

# Preview without removing anything (no stamp is written in dry-run)
python3 ~/projects/_tools/startup-cleanup/startup_cleanup.py --dry-run --human

# Bypass an optional throttle after a manual `git pull` on main
python3 ~/projects/_tools/startup-cleanup/startup_cleanup.py --force --human
```

Exit code is `0` for a completed check (including refusals) and `1` only if
the tool itself could not run. This keeps SessionStart hooks non-blocking.

### Direct runs versus hook mode

A direct run is repository-oriented: a folder outside any Git repository is
an error (`ok: false`, exit `1`).

SessionStart hooks run in every new session, including valid sessions in a
home folder. Their registered commands therefore pass `--hook`, which changes
only that applicability question:

- The session folder comes only from the stdin JSON object's `cwd`, which
  must be a non-empty string, or from an explicit `--project-dir`. The
  `project_dir`/`working_directory` aliases and the process working directory
  are never used as fallbacks. Missing or malformed input, an invalid `cwd`
  (even when an alias is valid), or a `cwd` that is not an existing directory
  fails with exit `1`.
- Inside a repository, root or subdirectory, the normal check runs with every
  gate above.
- Outside any repository the report is `ok: true` with `applicable: false`,
  exit `0`, and `--human` prints
  `startup-cleanup: skipped — <dir> is not in a Git repository; no cleanup applies`.
  No cleanup runs, no other folder is searched, and nothing is written.

Hook mode decides from a single probe, `git rev-parse --show-toplevel` run
with `LC_ALL=C` so its message is untranslated; no later probe can turn an
unexpected first failure into a skip. The skip requires that probe to exit
`128` with exactly
`fatal: not a git repository (or any of the parent directories): .git` on
stderr, plus distinct evidence: `GIT_DIR` is unset and no `.git` file or
directory exists in the folder or any ancestor. Exit `128` alone is not
enough, because Git also uses it for real errors. A timeout, a Git that
cannot start or exits otherwise, a malformed Git configuration file, any
other or additional diagnostic, a mount-boundary stop
(`GIT_DISCOVERY_ACROSS_FILESYSTEM`), a corrupt `.git` directory, a
linked-worktree `.git` file whose `gitdir` is gone, a bare repository, or an
unreadable ancestor all remain failures. Direct runs keep their original
repository probe and messages.

Output schema: `tools.startup-cleanup.v1` with `ok`, `project_dir`,
`repo_root`, `main_branch`, `main_fresh`, `throttled`, `summary`,
`removed[]`, `planned[]` (dry-run only), `refused[]` (each with `type`,
`target`, `branch`, `reasons[]`), `reports[]`, and `duration_ms`.

## Claude Code installation

Claude Code supports a native `SessionStart` hook (already exercised by other
hooks in `~/.claude/settings.json`). Add one entry to the existing
`hooks.SessionStart` array:

```bash
python3 ~/projects/_tools/startup-cleanup/startup_cleanup.py --print-claude-hook-config
```

The printed snippet is the value for one element of `hooks.SessionStart`:

```json
{
  "matcher": "^startup$",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"$HOME/projects/_tools/startup-cleanup/startup_cleanup.py\" --hook --human",
      "timeout": 45
    }
  ]
}
```

Insert it into `~/.claude/settings.json` under `"hooks"` → `"SessionStart"`
(next to the existing entries). Claude runs the hook at session start, passes
the project `cwd` on stdin, and surfaces the readable report in the session
context without blocking startup. The matcher runs cleanup on a new session
only; resume, clear, compact, and fork events do not repeat the scan.

After the PR lands, the floor manager installs this entry in the existing
user-scope hook configuration and checks one real startup.

## Codex installation

Codex also supports native `SessionStart` hooks through `~/.codex/hooks.json`
(the installed config already has a `SessionStart` group and
`[features] hooks = true` in `~/.codex/config.toml`). Add one entry to the
existing `hooks.SessionStart` array:

```bash
python3 ~/projects/_tools/startup-cleanup/startup_cleanup.py --print-codex-hook-config
```

```json
{
  "matcher": "^startup$",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"$HOME/projects/_tools/startup-cleanup/startup_cleanup.py\" --hook --human",
      "timeout": 45
    }
  ]
}
```

The matcher runs cleanup on a new session only; resume, clear, and compact
events do not repeat the scan.

### Documented wrapper path (fallback)

If a Codex build does not honor `SessionStart` hooks, do not claim otherwise.
The supported fallback is the existing
`~/.codex/codex-with-claude-hook-env.sh` wrapper, extended to run the check
before `exec codex`:

```zsh
#!/bin/zsh
set -euo pipefail
export CLAUDE_WORKING_DIRECTORY="${CLAUDE_WORKING_DIRECTORY:-$PWD}"
export CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

# Startup cleanup: best effort, never blocks, JSON goes to stderr for review.
python3 "$HOME/projects/_tools/startup-cleanup/startup_cleanup.py" \
  --project-dir "$PWD" >&2 || true

exec codex "$@"
```

An explicit `--project-dir` is checked first and never consumes stdin. The
registered native hooks pass `--hook`, which requires the stdin `cwd` with no
fallback (see "Direct runs versus hook mode"). A direct run without either
uses the stdin `cwd`, `project_dir` or `working_directory`, then the process
working directory. The wrapper is a direct run that passes
`--project-dir "$PWD"`, so a piped Codex prompt remains untouched.

## Rollback

Both removals are recoverable:

1. **Worktree directory and admin dir** — restore from Trash (Finder → Put
   Back, or `trash`/`send2trash` equivalent). `git worktree list` will show
   the worktree again once its admin dir is back in
   `<main>/.git/worktrees/<name>`.
2. **Branch** — the commits are still reachable from `main` (deletion requires
   them to be merged). Recreate the label with
   `git branch task/<id>-<slug> <sha>` where `<sha>` is the tip from the
   pre-deletion report or `main` history.

No remote refs are deleted, so nothing is unrecoverable from origin.

## Post-merge handoff

Cleanup does not rely on a session shutdown event. After a PR merges:

1. The merging agent keeps `main` fresh:
   `git checkout main && git pull --ff-only` (and `git fetch --prune` to drop
   deleted remote branch refs).
2. The next agent startup in that project runs the shared check and removes
   the now-merged task worktree/branch automatically.
3. To clean immediately without waiting for a startup, run
   `python3 ~/projects/_tools/startup-cleanup/startup_cleanup.py --force --human`
   from the project.

If `main` is not fresh, cleanup is skipped and reported — pull `main` first.

## Tests

```bash
python3 -m pytest tests/startup-cleanup/test_startup_cleanup.py
```

The synthetic suite covers safe deletion (merged clean worktree and standalone
branch, idempotent rerun, dry-run) and every refusal case: dirty tracked,
untracked, meaningful ignored, unmerged, open PR, `gh` unavailable, locked,
active-session worktree (including another session with a clean checkout),
unknown session activity, stale main, missing origin, ambiguous provenance,
detached worktree, branch checked out in a refused worktree, cross-project
scope, bounded caps, and throttle behavior. Hook-mode tests run the CLI as a
subprocess: a home-like folder is skipped while the direct CLI still fails;
repository roots and subdirectories keep normal scope; missing or malformed
input (including an invalid `cwd` beside valid aliases), corrupt markers, a
bare repository, malformed Git configuration, other exit-128 diagnostics, and
Git failures, timeouts or start errors on the first probe stay failures.

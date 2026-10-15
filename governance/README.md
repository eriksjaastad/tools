# Governance

Commit-time and push-time checks shared by every repository on these machines.

## How it is wired

- **pre-commit / pre-merge-commit:** the global `core.hooksPath`
  (`~/.claude/.githooks`, owned by claude-user-config) runs
  `governance-check.sh` on the staged files in every repository.
- **pre-push:** the same hooks directory runs `push-range-check.py`, which
  checks each commit a push would publish, catching cherry-picks, rebases and
  `--no-verify` commits that never passed pre-commit.
- **This repository's own checks:** `scripts/local-checks.sh` runs
  `silent-failure-gate.py`, the deletion check and the test suites on every
  push. `content-guard.py` runs only in GitHub's `content-guard.yml`, because
  its client-name patterns are private.

## What is here

| File | Checks |
|---|---|
| `validators/secrets-scanner.py` | API keys and tokens |
| `validators/absolute-path-check.py` | hard-coded user and machine paths |
| `validators/api-wrapper-check.py` | provider calls that bypass api-cost-tracker |
| `validators/source-deletion-check.py` | new permanent Python deletion sites (DS001) |
| `validators/silent-failure-check.py` | failure-masking handlers and empty env fallbacks (SF001–SF003), changed lines only |
| `validators/content-guard.py` | client identifiers in this public repository |
| `push-range-check.py` | the pre-commit validators again, per pushed commit |
| `silent-failure-gate.py`, `silent-failure-report.py` | whole-repository gate; read-only portfolio report |
| `install-hooks.sh`, `uninstall-hooks.sh` | per-repository hooks, from before the global hooks path |

Each script's docstring (`--help` for the Python ones) is its contract: what
it detects, its exit codes, and how to write a reviewed exception. Run any of
them by hand with `uv run governance/<path> <files>`; `governance-check.sh`'s
header says how to add a validator. Why the checks work the way they do is in
the repository's `DECISIONS.md`.

`git commit --no-verify` skips pre-commit, but the push-range check still
runs at push time; `git push --no-verify` skips that too. Use either only in
an emergency.

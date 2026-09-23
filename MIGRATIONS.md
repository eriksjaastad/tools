# Migration Manifests


Append-only log of `pt migration` sessions. Each section records the paths touched between `start` and `finish` for a named bulk operation.


## retire-pr-label-enforcement — 2026-09-23T21:32:18Z

- started_at:  `2026-09-23T21:30:43Z`
- finished_at: `2026-09-23T21:32:18Z`
- baseline_head: `596fa97873d5cbe063d3361989e6522b8041da2b`
- action: `manifest-only`

### New paths (introduced during session)
- `MIGRATIONS.md` (this manifest)

### Modified paths (status changed during session)
- `.github/workflows/auto-merge-on-tests.yml` (comment updated)
- `.github/workflows/pr-label-check.yml` (deleted)
- `.github/workflows/tests.yml` (obsolete suite description removed)
- `README.md` (rollout guidance updated)
- `claude-hooks/pr-enforcement.py` (obsolete workflow explanation removed)
- `governance/standardize-gh-repo.sh` (preserves existing status checks)
- `governance/sync-gh-workflows.sh` (installer retired)
- `tests/remediation/test_status_failures.py` (obsolete workflow explanation removed)
- `tests/workflows/test_pr_label_check.py` (deleted with the retired workflow)

---

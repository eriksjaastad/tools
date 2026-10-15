# Decisions

Why `_tools` works the way it does. Newest first. How the code behaves lives
in its docstrings and `--help`; this file keeps only the reasons.

## 2026-09-30 — The silent-failure check gates changed lines, not whole files (#6900)

`silent-failure-check.py --staged` runs in the shared pre-commit hook and
blocks a commit only for a finding on a line it added or edited, or a finding
that did not exist before (the model `source-deletion-check.py` already used).

**Why:** the original plan waited for every repository's owners to clear all
existing findings before turning the hook on, and it never converged. The
2026-09-30 dry run found 949 candidates in 413 files across 32 repositories,
up from 933 on 2026-09-25, while owner cards fixed one slice each. A replay of
September history found 187 new or changed-line findings across about 1,466
commits in the five largest repositories. Stopping that flow mattered more
than the backlog.

**Not a baseline exemption:** no finding is recorded as allowed, and editing a
flagged line brings it back under the gate. The existing findings are a
remediation backlog that `_tools` owns end to end (Erik, 2026-09-30).

**Limits:** the scanner is a syntactic pattern check, not proof that error
handling is correct. M2 review still covers everything outside SF001–SF003.

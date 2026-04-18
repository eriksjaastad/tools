# PROGRESS.md - _tools

**Session:** 2026-04-18
**Floor Manager:** Claude Opus 4.7 (1M context)

## What's Happening
Shipped hook prose-FP fix (#5999, #5998) end-to-end — branch → commit → code-reviewer → fixes → push → PR → merge. Bundled same-day session updates from other workers into the same PR per Erik's direction. Board now has one follow-up card (#6012) for same-class bugs still present in other validators.

## Decisions Made
- Fix scope for #5999/#5998: token-based matching via a new shared `command_parser.py` helper (stdlib only) rather than hardening individual regexes. Used `shlex` for argv tokenization plus subshell unpacking for `sh/bash/zsh -c` and `eval`.
- Kept regex for content patterns (Python/JS deletion code, TCC DB refs, subprocess-rm) because they legitimately look inside quoted args for code being executed.
- Tightened `CLAUDE_PR_REVIEW_PASSED=1` marker check to require real env-var position (not substring). Closed an incidental bypass where the marker in a PR body would fake approval.
- Did NOT fix same-class bugs in pipe-to-shell regex, heredoc commit-format regex, variable-evasion regex, or redirect-protection regex — scoped out to follow-up card #6012.
- Committed everyone's same-day work in one PR (not just mine) per Erik's explicit direction: "commit everything that is in Claude."

## What Got Done
- PR **eriksjaastad/claude-user-config#3** merged to main (merge commit `d600ae6b`, 13 files, +756/−279)
- New `hooks/command_parser.py` — shared tokenization helper
- `hooks/bash-validator.py`, `hooks/pre-pr-review.py`, `hooks/pr-enforcement.py` rewritten to use token matching for executable-verb patterns
- `hooks/test_bash_validator.py`: 128 → 145 tests (added 17 prose-FP regression tests)
- `hooks/test_pre_pr_review.py`: new, 28 tests
- Bundled in: `agents/claude-md-auditor.md` update, `skills/cleanup/SKILL.md` Steps 4.5/4.6, `skills/spec/SKILL.md` path rename, `skills/pm/SKILL.md` path fix, `hooks/session-progress.py` + `settings.json` wiring, `.gitignore` for bytecode and locks
- Code-reviewer ran full Ecosystem Governance & Review Protocol — returned FAIL with two findings (iterdir without try/except in session-progress.py; missing `timeout=` in test_pre_pr_review.py). Both fixed in follow-up commit before push.
- Cards #5999 and #5998: Done. Follow-up card #6012 created.

## Next Steps
- Card #5996 (code-reviewer head-to-head vs CodeRabbit/Greptile/Qodo) — Architect owns
- Card #6012 — follow-up hook validator cleanup (pipe-to-shell regex, heredoc commit-format regex, var-evasion regex, redirect-protection regex, shlex-first refactor to close the `pt tasks create "foo | rm /x"` bypass reviewer flagged)
- Erik asked for a journal entry — invoking /journal next

## Don't Forget
- `command_parser.py` extraction currently splits on pipeline separators BEFORE running shlex. Reviewer flagged this as a real security gap: a dangerous command embedded inside a quoted argument after a `|` (e.g. `pt tasks create "foo | rm /important"`) silently drops from argv analysis because the post-`|` fragment fails shlex. Fix in #6012 is to shlex-first, then split.
- Dogfooding bit me three times during this session: prose containing `gh pr create` in a python repro (pre-pr-review FP — the bug I was fixing), `sh|bash|zsh` in a commit message (pipe-to-shell regex FP), and `TCC.db` in a commit message (content-pattern FP). The `|<shell>|` and `TCC.db` cases are in #6012.
- `check_commit_format` has two regexes tried in order; the first extracts `$(cat <<` instead of the real heredoc body. Workaround is `git commit -F file`. Real fix in #6012.

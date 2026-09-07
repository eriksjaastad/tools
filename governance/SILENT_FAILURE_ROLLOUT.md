# Silent-failure enforcement rollout (#6900)

## Repository enforcement — 2026-09-07

#6981 resolves all 26 initial local findings; see the final dispositions in
[the triage record](SILENT_FAILURE_TRIAGE.md). The `_tools` CI workflow now runs
`silent-failure-gate.py` before tests, covering every tracked `.py`/`.pyi` file.
The scan blocks on SF001–SF003 and on unreadable, invalid, missing or unsafe
tracked input. No baseline or whole-file exemptions are used.

SF003 adds explicit empty-string environment-fallback candidates. It recognizes
`os.getenv` and `os.environ.get` defaults and `or ""`, but does not infer that
every environment setting is required. Local reviewed optional contracts can
be annotated. Immediate scalar validation ending in a raise is recognized;
client/container checks, early returns and nested unvalidated lookups are not.
Aliases, distant guards and arbitrary validators still require manual review.

The isolated Git fixture proves automatic invocation: an ordinary commit with
a logged failure returning `[]` is rejected, then corrected code passes. This
fixture keeps staged and working-tree bytes equal. The gate is designed for CI
checkout content, not partial staging; it is not installed as a pre-commit hook.
The motivating external `web_search.py` failure shape remains covered offline.

GitHub preflight found that `main` required only `check-label`. Publication must
also register the existing `pytest` job as required, preserving `check-label`,
and verify the resulting configuration. This makes a failed scan/test block
normal PR merging. It does not grant this agent merge authority.

[The updated portfolio comparison](silent-failure-2026-09-07.md) records the
current scanner against the previous scanner on the same bytes of each file.
The prospective `_tools` blocking set is clean. Other repositories' findings
remain candidates needing their owners' decisions; new SF003 candidates are
not automatically classified as defects.

The shared `governance-check.sh` array and installed portfolio hooks are still
unchanged. This repository can enforce its reviewed findings without activating
a live shared hook on unreviewed projects. **#6900 remains open for portfolio
owner triage and shared adoption**; #6981 can close after this PR merges.
#6453 separately awaits authenticated dashboard evidence and is unaffected.

## Historical initial rollout

The approved sequence is a deterministic scanner, a read-only portfolio
dry-run, and then blocking enforcement after findings and false positives are
resolved. Logging an exception does not make an empty result a successful
operation. The motivating case is the Firecrawl search handler in
`auxesis-research-labs/src/auxesis_research_labs/panel/web_search.py`, which logs
a failed request and returns `[]` to its caller.

## Dry-run evidence — 2026-09-06

The [recorded report](silent-failure-2026-09-06.md) scans 1,295 tracked Python
working-tree files across 37 immediate-child repositories/worktrees. All files
were scanned; there were zero errors and 12 explicit warnings (11 zero-Python
repositories and one unborn-HEAD warning). Findings: 150 SF001 plus 346 SF002,
496 total across 211 files. These are candidates, not 496 confirmed defects.

The final sweep includes the staged scanner, runner and their tests. The
report's scanner SHA256 matches the checked-in source. Earlier exploratory
sweeps scanned 1,289 files; added staged files and concurrent portfolio changes
account for the changed file count. The finding set remained unchanged after
review fixes. Revisions and dirty-state metadata are recorded per repository;
no claim is made that another checkout can recreate dirty source from HEAD.

[Local triage](SILENT_FAILURE_TRIAGE.md) accounts for the 26 existing `_tools`
findings: 12 to remediate, eight candidate justified exceptions and six open
contract questions. Follow-up #6981 owns that work. Other owners still need to
triage their findings. No portfolio source was changed or broadly exempted.

Previously there was no M2 scanner. These 211 files would produce findings in
the proposed scanner; this is not a claim that they pass all existing
governance validators. The shared validator set remains unchanged, so this
delivery introduces no newly blocked commits.

## Activation boundary

The scanner is not in `governance-check.sh`'s `VALIDATORS` array. M2 remains a
manual review requirement while rollout findings are unresolved. Running the
scanner explicitly can return a failing status; that is not evidence of an
installed automatic gate.

As inspected on 2026-09-06, three projects' effective pre-commit hooks call this
checkout's shared governance script: `ai-memory`, `project-scaffolding`, and
`project-tracker`. Three other repositories have similar installed hooks that
are overridden by their configured hook path. Changing the shared array would
therefore affect active consumers before this branch merges. `_tools` has no
effective pre-commit file; its existing CI runs regression tests.

Do not activate the gate merely because its tests pass. Do not use a blanket
baseline exemption to make existing findings disappear. Complete the dry-run
triage, route real defects to owners, and document justified narrow exceptions
before changing shared or installed hooks.

## Review decisions

The same syntax can express distinct contracts:

- A failed evidence search returning `[]` makes failed collection indistinguishable
  from a successful search with no hits. Logging alone does not fix that contract.
- A cache lookup returning `None` on an unreadable entry can be an intentional
  miss when the caller obtains the value elsewhere. Verify the caller before
  considering a local annotation.
- Catching `FileNotFoundError` while removing an already-absent temporary file
  can be intentional idempotent cleanup. A broad catch is not equivalent.
- A predicate returning `False` on a failed probe may or may not be correct.
  Verify whether it reports existence, availability, or success; do not classify
  it solely from the returned constant.

External source files, credentials, installed hooks and production token code
are not modified by this work. In particular, token-cache type validation stays
on #6978 and installed identity-hook cleanup stays on #6782.

One local exception in the new reporter was independently reviewed: a verified
absent branch ref returns `None` to a caller that records `head_state=unborn`
and emits an explicit warning. Its SF002 suppression applies only to that inner
handler; other Git failures propagate. Tests cover staged files before the first
commit and distinguish a corrupt ref. None of the existing portfolio findings
was suppressed during this rollout.

## Blocking-enforcement acceptance

1. Positive and negative scanner fixtures pass, including logged empty returns,
   inert handlers, required-value fallbacks and suppression scope. The initial
   implementation covers SF001/SF002 and suppression scope only; distinguishing
   required configuration from intentional optional defaults remains unresolved.
   An `os.environ["KEY"] or ""` heuristic was rejected: missing keys still raise,
   so that redundant expression does not establish a hidden configuration failure.
2. A complete portfolio dry-run records repository revisions, dirty snapshots,
   file/line/rule findings, and scanning failures. Zero results and scan errors
   must not be mistaken for a clean portfolio.
3. Every prospective blocking finding is remediated or justified through a
   reviewed local exception. Repeat the sweep after rule changes and compare
   which files would newly block; resolve false positives before activation.
4. Integrate with the intended automatic trigger using an isolated test
   repository. A deliberate failure must block without invoking a skill, and
   corrected code must pass. Read/parse failures must remain failures.
5. Verify actual installed hook paths or required CI configuration at each
   target. Update the automation claim only when that mechanism is active.

Until these conditions are met, #6900 remains incomplete even when the scanner
and dry-run tooling are ready for review.

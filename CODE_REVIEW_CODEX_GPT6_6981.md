# Review — local failure contracts and repository enforcement

Reviewed 2026-09-07 against `origin/main` at `7be464c`.
Scope: all 26 #6981 findings and the repository enforcement portion of #6900.
Verdict: PASS for PR handoff. Merging remains manual; portfolio adoption and
dashboard verification are explicitly outside the completed local scope.

## Verification

- Combined CI invocation: **766 tests passed**, preserving the previous
  563-test baseline and adding failure-contract/gate coverage and bench suites.
- Full benchmark suite: 108 passed with socket connections forbidden; the
  final additional malformed-JSON regression also passed. CI includes the
  affected registry, runner and scorer suites with bounded dependencies.
- Local gate: all 78 tracked Python files scanned, zero findings or errors.
- Automatic trigger: an ordinary commit in an isolated temporary Git repository
  invokes the gate and rejects a logged exception returning `[]`; corrected
  source commits successfully. This tests equal staged/working-tree content,
  not protection against partial staging. Production integration uses CI.
- The same-source portfolio comparison records new SF003 candidates and owner
  handoffs without modifying external files. No baseline exemptions are used.
- Governance and whitespace checks pass. Three existing synthetic broken-path
  fixtures use the established deliberate-absolute-path comment convention;
  validation rules are unchanged.
- `PROGRESS.md` exists, is ignored and untracked, and is excluded from commits.

## Data-flow and adversarial review

Independent agents reviewed the non-route caller contracts and the scanner/gate.
The manager reviewed route integration and all cross-component changes. The
review found and corrected two SF003 guard exemptions (early return before a
raise; checking a client result instead of its nested credential).

Route integration also caught native Codex rate-limit-only events with
`info: null`. Schema-only inspection of eight local logs found this shape in
each file; no session contents or credentials were printed. Regressions now
preserve cumulative usage across valid rate-limit updates while rejecting
missing or malformed usage evidence. A session with no usage evidence still
fails explicitly. Both usage sources resolve before the CLI prints totals.

Concrete failure trace: a malformed final cumulative usage record raises from
the Codex reader; `route summary` catches the failure at its command boundary,
prints a diagnostic and exits 2 before rendering either provider or the total.
Valid empty evidence still produces zero usage. Unsupported weekly/monthly
aggregate summaries now fail rather than mislabel all-time statistics.

Bench judge failure sets each affected result's nonempty `judge_error`. The
scorer counts that error and withholds a recommendation. An exception with an
empty message uses its class name; the test follows runner through scorecard.
Ollama availability is separately reported as offline; an inventory inspection
failure propagates and cannot render as “Not installed.”

Manual M2 review verified every retained handler exception against callers;
the disposition table accounts for all 26 initial findings. Added production
subprocess calls use checked return codes, timeouts and captured output (H1).
Actual read-only `grepai watch --status` returned exit 0 and the expected
stopped-status line. No daemon was started. Authentication changes are comments
only, supported by the existing cache replacement and protected-write tests.

## SHARP

Dogfood matched intended behavior: offline CLI failures now return nonzero,
the synthetic automatic gate blocks bad evidence, and the real local repository
scan passes after remediation. The native Codex event mismatch and scanner
guard bugs were fixed before this verdict; focused re-reviews pass.

**Skeptic:** Optional absence is not automatically a defect. Reviewed cache,
availability and explicit-error sentinels remain narrow and caller-tested.

**Breaker:** Invalid JSON/types, missing files, date filters, EOF, empty exception
messages, unsafe scan paths, early returns and nested credential fallbacks have
regressions. Native rate-limit-only Codex events remain valid.

**Security auditor:** New tests use temporary paths and stubbed APIs/SSH/PDF
dependencies. No live provider calls or credential reads are needed. Scanner
diagnostics exclude source snippets; scan errors fail closed.

**Architect:** A gate in this repository's CI does not activate shared live hooks.
The complete local finding set is reviewed before blocking. Portfolio owners
still own their unreviewed findings and adoption decisions.

**User proxy:** Incomplete work is visible through exit codes. Existing `.env`
benchmark configuration, transports and seat contracts remain intact; tests
stub dotenv before CLI import. No production PDFs or installed hooks are edited.

No critical or major issues remain in this PR. Existing limits include discovery
coverage outside the 26 enumerated findings, PDF write atomicity, historical
Codex model attribution/cache-accounting assumptions, and scanner alias/distant
data-flow analysis. These are not asserted correct by passing this pattern gate.

## Delivery limits

Adding `pytest` to GitHub's required checks is a separate verified publication
step; source changes alone cannot configure branch protection. Shared portfolio
gate activation remains pending owner triage. #6900 stays open for that scope.
#6981 may be marked Done only after merge; #6453 still requires dashboard evidence.

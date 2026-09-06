# Code Review — Codex GPT-6

Reviewed 2026-09-06 against `origin/main` at `7654cae`.
Scope: #6784, #6831, #6568, repository portion of #6782, and stale #6783 guidance.
Verdict: PASS for PR handoff; merging remains manual.

Review follows the canonical
[`REVIEWS_AND_GOVERNANCE_PROTOCOL.md`](../project-scaffolding/REVIEWS_AND_GOVERNANCE_PROTOCOL.md).
An independent review agent checked the complete implementation and new tests;
the manager ran governance and reviewed integration evidence.

## Verification

- Baseline: 250 governance and integrity-warden tests passed before edits.
- Exact CI command: 349 passed, including 58 authentication/hook tests and 41
  route pricing tests. Dependencies are bounded pytest and PyJWT; no live
  credentials or provider calls are needed.
- Benchmark registry plus route tests: 48 passed. Benchmark code is unchanged.
- Governance: secrets-scanner (M3), absolute-path-check (M1), and API-wrapper
  validator passed on all changed source, test, workflow and instruction files.
- Manual M2/H1: added handlers assert expected failure codes; no new swallowed
  failures. All three added subprocess sites use `check=True`, captured output,
  and timeouts. Production authentication remains unchanged.
- YAML parses; both label allowlists equal the canonical ten; repository CI
  has only the reporting pytest job and read-only contents permission.
- `PROGRESS.md` exists, is ignored by `.gitignore`, and is absent from tracked
  files and this change. Both instruction mirrors state the same guidance.

## SHARP

Dogfood: `uv run route/route estimate --role coder` lists the corrected rates
and added models. The combined test run initially exposed a conftest import
collision; moving the new fixture into its test module resolved it. The exact
CI invocation then passed all 349 tests.

**Skeptic:** Rates have official sources and verification dates; cache discounts
are model-specific. No retirement is inferred merely from model age.

**Breaker:** Tests cover the 300-second expiry boundary, missing/corrupt cache
entries, configuration drift, process concurrency, private modes, symlink races,
empty/failed token bundles, mixed token usage, zero usage and unknown IDs.

**Security auditor:** Wrapper tests use isolated executable paths and environment;
token tests use temporary caches and forbid credential/network operations.

**Architect:** Pricing API and benchmark/seat contracts remain unchanged. The
new scanner belongs to separate #6900 implementation, after a portfolio dry-run.

**User proxy:** Local and Linux CI use explicit dependencies. Existing CLI
formatting rounds subcent estimates to `$0.00`; exact arithmetic is tested.

Remediation: no critical or major findings remain in this change. Newly
reproduced production cache shape/type defects are recorded separately as
#6978, consistent with the approved boundary on authentication implementation.

## Data-flow trace and limits

The wrapper fixture supplies a synthetic resolved bundle; `gh-agent.sh` extracts
identity/token, rejects empty or failed resolution, sets the GitHub token and
bot author environment, and invokes the stub. Assertions verify the exact
arguments/token and that failure paths never invoke GitHub.

Route tests independently assert each published input/output/cache rate and
mixed Anthropic five-minute cache-write arithmetic. Flat estimates exclude
context tiers, one-hour writes, storage and service premiums, as documented.
Unknown IDs retain the existing zero-cost behavior; the benchmark coverage test
guards against known benchmark IDs becoming unpriced.

Inverse-test limits: offline tests do not validate live GitHub minting,
installation credentials, provider invoices, or installed user-hook behavior.
The installed hook still allows the retired wrapper, so #6782 remains open.
No exact registry ID was verified retired; historical rows and roles remain,
with lifecycle policy documented for future confirmed retirements.

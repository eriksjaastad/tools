# Code Review — Codex GPT-5

**Card:** #6493 — rework model-bench into a seat-fit bench
**Branch:** `feat/6493-seat-fit-bench`
**Verdict:** PASS
**Reviewed:** 2026-07-26

## Outcome

The implementation satisfies card #6493's acceptance criteria and is ready for
architect review. During integration review, I found and fixed:

- ambiguous partial model resolution;
- Google pin-to-registry mismatches;
- dead Ollama aliases remaining in the active registry;
- the seat CLI failing to load its local `.env`;
- Python 3.11-incompatible formatter output;
- seat temperature/token limits not reaching provider calls;
- JSON prompts omitting the project-owned schema;
- a retired Gemini candidate and unavailable Anthropic judge;
- unknown/zero pricing being reported as free;
- unguarded project-root iteration;
- FROZEN Markdown reports omitting the project reason; and
- absolute host paths leaking into committed run provenance.

No project `seats.yaml` or production model pin was changed.

## Gate 0 — Robotic Scan

| ID | Result | Evidence |
|---|---|---|
| M1 | PASS | Home-directory path scan returned no matches after portable provenance normalization. |
| M2 | PASS | No silent `except: pass` patterns remain in the changed component. |
| M3 | PASS | Key-pattern scan returned no matches; `.env` remains ignored and `.env.example` uses `replace-me`. |
| M4 | PASS | Unfilled `{{VAR}}` scan returned no matches. |
| H1 | N/A | The seat-fit implementation introduces no subprocess execution. Code artifacts require an injected sandbox executor and otherwise fail closed. |
| H7 | PASS | No DELETE, DROP, TRUNCATE, cleanup, or destructive data behavior was added. |
| H8 | PASS | Discovery is immediate-child only; there are no unbounded recursive globs. |

Repository `governance/governance-check.sh` completed successfully.

## Tests and Failure Paths

- `uvx ruff check model_bench tests`: PASS
- `uvx ruff format --check model_bench tests`: PASS
- `uv run --with pytest python -m pytest -q`: **90 passed**
- Coverage audit: 61% across the package including retired legacy modules;
  seat-fit core modules range from 40% orchestration to 96% scoring.
- Sealed run without `MODEL_BENCH_UNSEAL=1`: nonzero exit with
  `SealedAccessError`.
- Malformed contracts, missing references, unreadable project scans, ambiguous
  models, unsafe paths, unavailable pricing, invalid artifacts, and incomplete
  judge results have explicit failure coverage.

## E2E Trace

Representative input: the sealed Hypocrisy Now detection fixture
`detection-003`.

1. `discover_project_seats()` finds root-level `seats.yaml`, invokes the
   canonical `project-scaffolding` `seats.v1` validator, and resolves fixture
   and schema references inside the owning project.
2. `load_seat_cases()` enforces `MODEL_BENCH_UNSEAL=1`, selects the fixture by
   deterministic hash split, and adds one deterministic adversarial dirty
   variant for the seat.
3. `build_seat_prompt()` renders the project job, validation prose, full bounded
   JSON Schema, real fixture input, and bounded project context without the
   expected-output label.
4. `SeatRunner` calls the incumbent and two requested candidates with the
   seat's portable temperature/token limits.
5. `validate_seat_artifact()` parses and schema-validates each JSON artifact
   before any valid artifact reaches the judge; invalid artifacts receive zero.
6. The configured judge scores only valid artifacts against the withheld
   expected-output rubric.
7. `score_seat_run()` aggregates score, validity, latency, errors, and cost,
   requiring complete valid evidence before recommending a replacement.
8. `save_seat_report()` atomically writes portable JSON and Markdown evidence.

## PRD / Card Traceability

| Requirement | Status | Evidence |
|---|---|---|
| Strict MacBook project discovery and canonical schema validation | Implemented | Immediate-child discovery; hard errors for malformed files and invalid references. |
| FROZEN pins never receive replacement recommendations | Implemented | Report-only frozen manifest, incumbent-only enforcement, reason in JSON and Markdown. |
| Real project fixtures and sealed holdout discipline | Implemented | Deterministic dev/sealed loading with explicit environment unseal gate. |
| Validity before judging with hard-floor failure | Implemented | JSON Schema, free-text, image-byte, and injected code-executor gates. |
| Dirty variants for messy/adversarial seats | Implemented | One deterministic dirty variant per qualifying seat by default. |
| Per-seat score and cost evidence | Implemented | Atomic score/cost/latency/error matrices and fail-closed unknown pricing. |
| Hypocrisy Now committed pilot | Implemented | Three final sealed report pairs under `model-bench/results/`. |
| No production pin changes | Implemented | Read-only project contracts; advisory reports only. |
| Remove stale local-alias documentation | Implemented | README rewritten; nonexistent aliases removed from active registry. |

## Final Sealed Pilot

Run ID prefix: `20260726T052446Z-hypocrisynow`

| Seat | Result |
|---|---|
| detection | Consider `gpt-4.1-mini`; score 4.333 vs incumbent 3.500, 100% validity for both. |
| expert_review | Keep `gpt-4o-mini`; score 3.333 vs 3.000 for both candidates. |
| extraction | Keep `gpt-4o-mini`; incumbent score 1.500; candidate evidence did not justify replacement. |

All 11 sealed cases include three dirty variants in total. The final run has no
model-call, judge, or pricing errors, and every reported model has measured
nonzero cost.

## Dark Territory

- No project currently declares a `code` output seat. The validator supports an
  injected sandbox executor and fails closed without one, but a project-specific
  sandbox adapter must be supplied before publishing a code-seat result.
- Image artifact structure is tested, but binary image quality judging and
  per-image provider pricing have not yet been exercised by the committed pilot.
- Real provider APIs, model availability, and pricing can drift independently
  of this repository. The reviewed implementation now rejects unavailable
  pricing, but catalog refresh remains an operational responsibility.
- Very large fixture corpora are loaded one seat at a time rather than streamed.
  Context and schema sizes are bounded, but fixture-row volume is not yet
  batch-windowed.
- The CLI is covered through direct orchestration tests and live smoke/pilot
  execution, not a full Typer command unit-test matrix.

These items do not block the card's stated pilot acceptance; they define the
ceiling for subsequent portfolio expansion.

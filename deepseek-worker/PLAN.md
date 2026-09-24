# DeepSeek Coding-Worker Harness — Implementation Plan

**Card:** #7569  
**Companion:** `DESIGN.md`  
**Date:** 2026-09-24 (EDT)  
**Process:** Direct / internal tooling (Project-workflow light→spec style): design artifacts first; then reviewable PR slices (~500 substantive lines each). No product code in the design pass.

---

## Traceability (acceptance → slices)

| Acceptance | Primary slices |
|------------|----------------|
| 1 Pilot e2e | A → B → C → pilot run |
| 2 Three managers, one harness | A (CLI) + D |
| 3 Failure demos | E (plus unit tests in A–C) |
| 4 No idle manager burn / no unverified done | B (wake queue) + C (done gate) + D (docs) |
| 5 Ops + cost comparison | F |

---

## Recommended first PR slice (Slice A) — **do this next**

**Title:** `feat(deepseek-worker): submit → fake-worker → handoff → status` (vertical stub)

**Goal:** Smallest end-to-end path with **no** live DeepSeek spend yet.

**Includes:**

1. Package layout under `_tools/deepseek-worker/`:
   - `pyproject.toml` / `uv` runnable module
   - `dsw` console entry
   - `jobstore.py` (filesystem JobStore: one dir per job, `job.json` + `events.jsonl`)
   - `schemas.py` (work order + handoff pydantic/jsonschema)
   - `cli.py`: `submit`, `status`, `logs`, `cancel` (cancel = mark cancelled for stub)
2. **Stub worker:** subprocess that sleeps briefly, writes a valid `handoff.json`, exits 0 — proves process isolation + finalize path without API keys.
3. Idempotent submit + conflict lock tests.
4. Unit tests for state transitions and schema validation.
5. Minimal README pointing at DESIGN.md.

**Excludes:** real DeepCode spawn, off-peak gate, pt note reflection, manager adapters, OPS cost study.

**Done when:**

```bash
dsw submit --order fixtures/sample_order.yaml   # prints job_id
dsw status <job_id>                             # reaches succeeded
test -f "$(dsw status <job_id> --handoff-path)" # valid handoff
pytest deepseek-worker/tests -q
```

**Why first:** Unblocks every later slice on a real job ID + durable store; keeps risk off the paid API.

---

## Slice B — Process supervisor + durable wake queue

**Includes:**

- Real subprocess supervisor (pid, heartbeat file, SIGTERM/KILL grace).
- States `launching` / `running` / `completing` with crash/missing-pid reconcile on `dsw doctor` and CLI entry.
- Completion queue: `~/.deepseek-worker/wake/*.json` (or configured state root).
- `dsw wait JOB_ID` and `dsw dequeue` (cheap; no LLM).
- Recovery tests: kill -9 worker, restart harness, duplicate finalize.

**Done when:** crash demo leaves terminal job + wake item; `dsw wait` returns without manager model.

---

## Slice C — DeepCode/DeepSeek worker + budgets + off-peak gate

**Includes:**

- Spawn via `~/bin/deepseek` (Doppler) with model `deepseek-v4-pro`.
- Worktree/branch validation; forbid push/PR in wrapper env/prompt.
- Off-peak UTC gate + `peak_exception` audit fields.
- Budget caps (usd/time/retries); rate-limit stop.
- Usage capture best-effort from worker logs/API; `cost_status=unknown` when absent.
- pt reflection helper: append-only notes via `pt tasks update` (read-modify-write notes; never raw DB).

**Done when:** one manual paid smoke job off-peak produces handoff + card note link (can be a tiny throwaway repo or `_tools` fixture branch).

---

## Slice D — Manager adapter docs + exercised paths

**Includes:**

- Same CLI recipes for Codex, Claude, Grok (OPS section + short snippets).
- Dependent config PRs (separate repos/cards as needed):
  - `delegate` skill default `constraints.model` → Worker binding (`agent-runtime-config` compile).
  - Optional one-page `cheap-coder` / `model-seats` skill pointing at `dsw`.
- **No** three harness implementations — adapters are docs + skill text that call `dsw`.

**Done when:** each manager seat has a recorded dry-run: submit + status against Slice A/C harness (screenshots or log paths in card notes).

---

## Slice E — Failure demo harness / scripted scenarios

Scripted demos (fixture mode preferred to avoid spend):

1. Duplicate submission → same `job_id`
2. Restart/crash recovery
3. Missing worker process
4. Malformed handoff
5. Off-peak boundary (clock inject / fake clock)
6. Budget / timeout / retry cap
7. Failed tests / blocker handoff status

**Done when:** `make demos` or `pytest -m demos` green; checklist pasted to #7569 notes.

---

## Slice F — OPS + pilot cost comparison + rollback

**Includes:**

- `OPS.md`: MacBook (and optional Mini) install, Doppler, state dir, alert routing, rollback (disable `dsw`, cancel jobs, leave worktrees).
- Pilot e2e on a real small card: work order → DeepSeek → wake → manager verify → PR.
- Cost table: DeepSeek usage (provider or unknown) vs estimated manager-coding alternative (`route` shadow prices OK if labeled shadow).
- Rollback/recovery procedure exercised once.

**Done when:** Acceptance #1 and #5 evidence on the card; card ready for Review.

---

## Out of scope / later cards

- Hermes live supervisor changes (forbidden on #7569).
- Spawn-time Manager→Worker rewrite hooks (follow `ORCHESTRATOR_CHEAP_CODER_RULES` experiment #3 after harness exists).
- Flash→Pro cascade.
- Shared Mini/MacBook job federation.
- `image-workflow` anything.

---

## Defaults (if Erik does not answer NOTES)

| Topic | Default for implementation |
|-------|----------------------------|
| State root | `~/.deepseek-worker/` on submitting host |
| Pilot host | MacBook (`20a4703f-…`) |
| Worker binary | `~/bin/deepseek` → DeepCode / `deepseek-v4-pro` |
| Wake channel | Filesystem queue + `dsw wait` / `dsw dequeue`; optional `pt message` later |
| Pilot target | Tiny dedicated fixture repo or disposable `_tools` self-test card — not Holoscape |
| Holoscape writeup | Proceed with gap recorded; fold in if Hermes exports later |

---

## Suggested branch / PR hygiene

- Design pass branch: `task/7569-deepseek-worker-design` (docs only).
- Implementation: `task/7569-deepseek-worker-a` … per slice; one PR per slice; exact-head review gates unchanged.
- Do not push/open PR in the design-only pass unless Erik asks.

---

## Effort sketch (rough)

| Slice | Relative size |
|-------|-------------|
| A | S (first vertical) |
| B | M |
| C | M–L |
| D | S (mostly docs + config PRs) |
| E | S–M |
| F | S + calendar time for pilot |

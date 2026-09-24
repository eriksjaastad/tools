# DeepSeek coding-worker harness — Implementation Plan

**Card:** pt #7569  
**Design:** `./DESIGN.md`  
**Date:** 2026-09-24 (America/New_York)  
**Process:** shareable tooling under `_tools` — phased reviewable PRs (not Light Path)

## Guiding constraints

- Design docs first (this pass). Product code starts at **PR-1** below.
- `_tools` owns the harness; config repos own entry-point text only.
- Do **not** modify Hermes Holoscape live supervisor under this card.
- No direct Project Tracker DB writes — `pt` CLI only.
- Personal GitHub identity for manager-side PRs (`gha` / `eriksjaastad`).
- Prefer ~500 substantive LOC per PR when coherent.

## Acceptance → phase map

| Acc | Requirement | Phases that prove it |
|---|---|---|
| A1 | Pilot: pt → work order → DeepSeek process → durable completion → manager verify → PR w/ provenance/cost/status | PR-1 → PR-3 → PR-5 (pilot) |
| A2 | Codex + Claude + Grok same harness path | PR-4 |
| A3 | Demos: duplicate, crash, missing worker, malformed handoff, off-peak, budget/timeout/retry, failed tests/blocker | PR-2 + PR-3 demos |
| A4 | Idle wait ≠ manager turns; unverified result ≠ done / no review bypass | PR-3 notify + PR-5 policy checks |
| A5 | Operator setup, alerts, rollback; measured pilot vs manager coding | PR-5 + ops doc |

---

## PR slices

### PR-0 — Design artifacts only (this branch)

**Scope:** `deepseek-worker/DESIGN.md`, `PLAN.md`, `GAP_HOLOSCAPE_WRITEUP.md`  
**Out:** no executable product code  
**Done when:** files on `task/7569-deepseek-worker-design`; card remains In Progress with pointer note  
**Owner:** this session

---

### PR-1 — Smallest vertical slice (recommended first implementation)

**Goal:** Prove `submit → (stub or real) worker process → handoff file → status` with durable job id.

**In scope**
- Package layout under `_tools/deepseek-worker/` (Python, `uv`-friendly).
- SQLite job store + `jobs/<id>/` directory layout.
- CLI: `submit`, `status`, `logs` (minimal), `doctor` (data dir only).
- Work-order + handoff JSON schema validation (pydantic or jsonschema).
- Process spawn of a **Worker Runner** that:
  - reads work order,
  - runs in target worktree (or creates worktree from `base_ref`),
  - for PR-1 may be a **harness-controlled stub** that writes a valid handoff after a local no-op/test command **or** a thin DeepSeek/DeepCode invocation behind a `--worker {stub,deepseek}` flag (stub default in CI).
- Idempotent submit + reject conflicting active job on same `pt_task_id` / worktree.
- Unit tests for store, idempotency, schema, state transitions `queued→spawning→running→handoff_pending→completed`.

**Out of scope for PR-1**
- Off-peak enforcement (config stub ok).
- Notify queue / pt message.
- Real budget metering.
- Config-repo skill changes.
- Crash recovery daemon.

**Acceptance mapped:** foundation of A1; partial A3 (duplicate submit).

**Demo script (required in PR description)**
1. `dsw submit` twice with same idempotency key → same job id.
2. Conflicting second order on same worktree → exit 3.
3. Stub worker completes → `status` shows `completed` + handoff path + SHA field present (even if SHA is stub).

---

### PR-2 — Policy gates: off-peak, budget, timeout, retries, rate-limit stop

**In scope**
- UTC peak windows (Mon–Fri 01–04 & 06–10, CN holidays excluded) with `retrieved_at` config.
- `waiting_offpeak` + `allow_peak` + auditable `peak_exception`.
- Deadline / max_retries / max_cost_usd enforcement; `budget_exhausted`, `timed_out`, `rate_limited`.
- Record token/cost when provider returns them; else labeled estimate via `route` helpers if cheap to call.
- Tests with frozen clocks around peak boundaries + DST display helpers (America/New_York mapping).

**Demos:** off-peak deferral; peak without exception rejected; peak with exception logged; timeout; retry cap; simulated rate limit stop.

**Acceptance:** A3 policy portion.

---

### PR-3 — Recovery + notification (no manager polling)

**In scope**
- Heartbeat / PID tracking; `dsw reconcile` for crash & missing process.
- Malformed handoff → `malformed_handoff`; duplicate completion ignored + logged.
- Durable `notify/queue.jsonl`; optional `pt message send` integration (feature-flagged).
- Document anti-pattern: manager must not `sleep`/poll with expensive model turns.
- Card reflection helper: append/update **review-comment or carefully merged notes** with job link (never silent wipe of card body).

**Demos:** kill worker mid-run → reconcile → notify; bad JSON handoff; double handoff write.

**Acceptance:** A3 recovery; A4 idle-wait.

---

### PR-4 — Manager entry points (same harness, three docs/exercises)

**In scope (coordinate, don’t fork)**
- `agent-runtime-config`: update `delegate` defaults / add thin `cheap-coder` or `dsw` skill artifact that **shells out to `dsw` only**.
- Claude native adopt path (`claude-user-config` / `~/.claude/skills`) when that repo is available on the host — compile to Codex via existing runtime-doctor.
- Grok Bot: short memory/skill text pointing at `dsw` + `MODEL_SEATS.md` (no separate dispatcher).
- One exercised recipe each: Claude, Codex, Grok (can be scripted dry-run against stub worker).

**Out:** Hermes live rewrite.

**Acceptance:** A2.

---

### PR-5 — Real DeepSeek pilot + ops package

**In scope**
- Default `--worker deepseek` using Doppler-wrapped launcher (pattern from `~/.claude/scripts/deepcode-run.sh`; prefer sharing code rather than copying).
- End-to-end pilot on a real authorized `_tools` or agreed low-risk card: work order → DeepSeek → handoff → manager verify → PR with provenance/cost/task status.
- Operator doc: MacBook install, Doppler project/config, alert routing, rollback (`PATH` shim disable + leave SQLite), Mini notes (SSH via `pt info get mac_mini_ssh`) without requiring Mini connectivity in this session.
- Measure pilot USD (provider or shadow) vs estimated manager-coding counterfactual; record on card via `pt`.

**Hard gates**
- Worker still cannot push/PR/merge.
- Manager still runs independent review + CI before merge.
- Harness never marks card Done.

**Acceptance:** A1, A4, A5.

---

## Recommended first implementation PR

**Do PR-1 next** (smallest vertical: submit → worker runner → handoff → status), with stub worker default and optional DeepSeek behind a flag.  
Defer off-peak/notify/config skills until the store + CLI are trustworthy.

Suggested branch after design merge/PR-0: `task/7569-dsw-pr1-submit-status`.

---

## Risks

| Risk | Mitigation |
|---|---|
| Missing Holoscape writeup | Gap note; use live card traces; optional Erik paste |
| DeepCode single settings.json concurrency | PR-1 single-flight per host; later dedicated API client |
| Managers keep coding anyway | PR-4 skills + ledger/detection later (orchestrator R1) |
| Peak holiday calendar drift | Config + doctor warning; document refresh |
| Notify depends on pt message attention | Always write local queue first |
| Scope creep into Hermes | Explicit non-goal; separate card for migration |

---

## Open questions for Erik (blocking only; max 5)

1. **Worker runtime for production path:** keep DeepCode CLI (`deepseek` / `deepcode-run.sh`) as the coding agent, or prefer a headless DeepSeek API agent loop under `_tools` control?
2. **Holoscape writeup:** can you paste/point to the missing `deepseek-supervisor-architecture-writeup.md`, or should we treat live Holoscape card traces as sufficient reference?
3. **Notify address:** which `pt message --to` target(s) should wake managers on MacBook vs Mini (or queue-only for v1)?
4. **Pilot target repo/card:** which authorized low-risk card should be the first real DeepSeek pilot after PR-1–3?
5. **`claude-user-config`:** is the MacBook expected to clone `eriksjaastad/claude-user-config` for PR-4, or author only via `~/.claude` + `agent-runtime-config` adopt?

Non-blocking defaults if unanswered before PR-1: stub+DeepCode flag; queue-only notify; no Holoscape file; pilot chosen later; PR-4 via `~/.claude` + runtime-config.

---

## Rollback

- Disable `dsw` on PATH / uninstall console script.
- Leave job store intact for forensics.
- Skills that mention `dsw` can remain as no-ops with doctor failure — or revert config PR.
- Do not delete Doppler secrets as part of rollback.

## Next action after this design pass

1. Keep #7569 **In Progress**.
2. Open PR-0 for design docs (parent/cloud agent) when ready — **no push from this subagent unless parent asks**.
3. Start PR-1 implementation on a fresh task branch after Erik glances at open questions (or proceeds with defaults).

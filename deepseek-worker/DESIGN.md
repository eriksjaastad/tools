# DeepSeek Coding-Worker Harness — Design

**Card:** #7569 (`_tools`)  
**Status:** Design (no product implementation in this pass)  
**Date:** 2026-09-24 (America/New_York / EDT)  
**Owners:** `_tools` (shared executable + job lifecycle); config adapters coordinated with `agent-runtime-config` (and Claude skill surfaces). Hermes Holoscape supervisor is **reference only**.

**Policy inputs:** `~/projects/ORCHESTRATOR_CHEAP_CODER_RULES.md`, `~/projects/MODEL_SEATS.md`, `~/projects/Project-workflow.md` (Direct / internal-tooling path: design + phased plan before code).

---

## 1. Problem

Manager seats (Codex / Claude / Grok) burn expensive turns implementing code. Holoscape proved the easy half (schedule off-peak DeepSeek) and the hard failure: a prompt saying "use DeepSeek" is not durable — the manager quietly falls back to its own coding loop, with no job provenance.

We need one **deterministic, provider-neutral harness** so any manager can:

1. Submit a bounded work order for an authorized pt card.
2. Run coding in a **separate DeepSeek Pro process**.
3. Idle without burning manager-model turns.
4. Resume only on durable completion / failure / blocker signals.
5. Verify provenance before treating the work as done.

This is an **execution harness**, not a pt display feature and not chat advice.

---

## 2. Goals / Non-goals

### Goals

- Shared CLI/API usable by Codex, Claude, and Grok (one implementation; thin adapters).
- Durable jobs with full lifecycle metadata and append-only event log.
- Idempotent submit; no conflicting concurrent jobs on the same pt task + worktree.
- Off-peak DeepSeek window enforcement (UTC, DST-aware local ops notes); auditable peak exceptions.
- Spend / time / retry caps; provider token/cost evidence recorded when available.
- Worker: Doppler creds; local commits + structured handoff; **no push / PR / merge**.
- Durable completion signal so managers do not idle-poll with expensive models.
- Recovery for crash, missing process, malformed handoff, duplicate completion, restart.
- pt remains the board; job links reflected on the card via `pt` CLI only (no direct DB writes).

### Non-goals (this card)

- Changing Hermes / Holoscape live supervisor setup.
- Any `image-workflow` work.
- Replacing independent exact-head review / CI / PR gates.
- Building three separate manager-specific harnesses.
- Auto-merging or auto-pushing worker results.
- Portfolio-wide spawn hooks (those land later via `agent-runtime-config`; this harness is the executable they will call).

---

## 3. Roles (stable; bindings from MODEL_SEATS)

| Seat | Binding (2026-09-24) | In this system |
|------|----------------------|----------------|
| Manager | Codex / Claude / Grok Bot | Writes work order, submits job, waits (cheaply), verifies, opens PR |
| Worker | **DeepSeek Pro** (`deepseek-v4-pro` via DeepCode) | Implements in isolated worktree; local commits; structured handoff |
| Judge | Independent local `code-reviewer` | Exact-head review after manager verification — **outside** this harness |

**Invariant:** Manager never treats "worker said done" as done. Done = harness terminal state + verified handoff + project tests/CI + manager acceptance check.

---

## 4. Architecture overview

```text
┌─────────────────────────────────────────────────────────────┐
│ Manager (Codex / Claude / Grok)                             │
│  - writes Work Order (pt card, acceptance, constraints)     │
│  - calls `dsw submit` / status / logs / cancel              │
│  - exits or parks on cheap waiter; resumes on wake item     │
└───────────────────────────┬─────────────────────────────────┘
                            │ CLI (stable surface)
┌───────────────────────────▼─────────────────────────────────┐
│ deepseek-worker harness (_tools/deepseek-worker)            │
│  ├── JobStore (durable JSONL/SQLite under state dir)         │
│  ├── Scheduler / OffPeakGate (UTC windows + exceptions)     │
│  ├── ProcessSupervisor (spawn, pid, heartbeat, recover)     │
│  ├── BudgetLedger (time/spend/retries + provider usage)     │
│  ├── CompletionQueue (durable wake items)                   │
│  └── ptReflector (notes/links via `pt tasks update` only)   │
└───────────────────────────┬─────────────────────────────────┘
                            │ spawn (Doppler-wrapped)
┌───────────────────────────▼─────────────────────────────────┐
│ Worker process (separate OS process)                        │
│  ~/bin/deepseek → DeepCode CLI → DeepSeek API               │
│  cwd = isolated git worktree / branch                       │
│  outputs: local commits + handoff.json                      │
│  forbidden: git push, gh pr create/merge                    │
└─────────────────────────────────────────────────────────────┘
```

**Ownership boundary**

| Component | Repo |
|-----------|------|
| `dsw` CLI, JobStore, supervisor, off-peak gate, handoff schema, OPS docs | `_tools/deepseek-worker` |
| Delegate skill default `constraints.model` → Worker binding; optional `cheap-coder` skill; spawn-hook later | `agent-runtime-config` (+ Claude skill authoring surface) |
| Hermes Holoscape supervisor | **Do not modify** — cite as historical reference only |

---

## 5. Job model

### 5.1 Identity & fields

Every job record includes at minimum:

| Field | Notes |
|-------|-------|
| `job_id` | ULID / UUID; primary key |
| `idempotency_key` | Manager-supplied or derived (`pt_card` + `repo` + `worktree` + content hash of work order) |
| `pt_card_id` | Display id (e.g. 7569) |
| `repo_path` | Absolute path to git root |
| `worktree_path` / `branch` | Isolated worker checkout |
| `model` | Default `deepseek-v4-pro` from MODEL_SEATS |
| `state` | See state machine |
| `created_at` / `updated_at` / `started_at` / `finished_at` | ISO-8601 with offset |
| `deadline` | Absolute; hard stop |
| `retry_count` / `max_retries` | Cap retries |
| `budget` | `{ max_usd, max_wall_seconds, max_provider_requests }` |
| `off_peak_policy` | `require` \| `prefer` \| `allow_peak` |
| `peak_exception` | Optional `{ reason, approved_by, at }` — required if paid work during peak |
| `event_log[]` | Append-only `{ at, type, detail }` |
| `pid` / `hostname` | For recovery |
| `handoff_path` | Path to structured handoff artifact |
| `usage` | Provider-reported tokens/cost when available; else `unknown` (never invent $0) |
| `manager_seat` | `codex` \| `claude` \| `grok` (telemetry only) |

### 5.2 State machine

```text
queued → waiting_off_peak → launching → running → completing
                              ↓            ↓
                           cancelled ←—————+
                              ↓
                     failed | blocked | succeeded
```

Terminal states: `succeeded`, `failed`, `blocked`, `cancelled`.

Rules:

- Only one **active** (`queued|waiting_off_peak|launching|running|completing`) job per `(pt_card_id, worktree_path)` unless prior is terminal.
- Idempotent submit with same `idempotency_key` returns the existing job (no second process).
- Conflicting submit (same card/worktree, different key, active job) → reject with actionable error.

### 5.3 Work order (manager → harness)

YAML or JSON file referenced by submit:

```yaml
pt_card_id: 7569
repo: /Users/eriksjaastad/projects/example
worktree: /Users/eriksjaastad/projects/example/.claude/worktrees/dsw-7569
branch: task/7569-slice
goal: "Implement X only; do not redesign."
acceptance_criteria:
  - "pytest path/to/test_x.py passes"
  - "handoff lists files changed and commit SHA"
constraints:
  model: deepseek-v4-pro
  max_usd: 2.00
  max_wall_seconds: 3600
  max_retries: 1
  forbidden_actions: ["git push", "gh pr", "gh merge", "rm -rf"]
off_peak_policy: prefer   # or require / allow_peak
peak_exception_reason: null
```

Aligns with `/delegate` Task Envelope shape (`goal`, `acceptance_criteria`, `constraints.*`) so skills can compile into the same artifact.

### 5.4 Handoff (worker → harness → manager)

Required structured file (JSON) written by worker or wrapper before exit:

```json
{
  "job_id": "...",
  "status": "completed|failed|blocked|partial",
  "commit_sha": "...",
  "files_changed": ["..."],
  "checks_run": [{"cmd": "pytest ...", "exit_code": 0}],
  "blockers": [],
  "notes": "",
  "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cost_usd": null, "cost_status": "unknown|provider|estimated"},
  "model": "deepseek-v4-pro",
  "provider": "deepseek",
  "session_refs": []
}
```

Malformed / missing handoff → job `failed` with recovery event; **never** map to succeeded. Duplicate completion events are ignored after first terminal transition (idempotent finalize).

---

## 6. Off-peak & budget controls

### 6.1 DeepSeek window (as of official docs 2026-09)

Source: https://api-docs.deepseek.com/quick_start/pricing

- **Peak (UTC):** Mon–Fri `01:00–04:00` and `06:00–10:00`.
- **Off-peak:** all other UTC hours, including **weekends** and **Chinese public holidays** in full.
- Off-peak rates are half of peak.

Harness behavior:

- Evaluate window in **UTC** (no DST bug in the gate). Document America/New_York equivalents in OPS.md for operators (EDT peak ≈ 21:00–00:00 and 02:00–06:00; EST shifts one hour earlier).
- `off_peak_policy=require`: do not start paid worker calls in peak; stay in `waiting_off_peak` until window opens (or cancel).
- `prefer`: start only off-peak unless `peak_exception` present.
- `allow_peak`: start immediately; **must** persist auditable `peak_exception` (reason + who + timestamp).
- Rate-limit / budget / deadline stops transitions to `failed` or `blocked` with evidence in event log.
- Cost evidence: prefer provider-reported usage from DeepCode/API response; if unavailable set `cost_status=unknown` — **never** treat missing as $0.

### 6.2 Caps

Default caps (overridable per job, hard upper bounds in config):

- `max_usd`, `max_wall_seconds`, `max_retries`, `max_provider_requests`
- On any cap: stop worker (SIGTERM → SIGKILL grace), finalize terminal state, enqueue wake item.

---

## 7. Worker execution

### 7.1 Process & credentials

- Spawn a **separate OS process** on the target Mac host (pilot: MacBook; Mini optional later).
- Credentials via existing Doppler-wrapped launcher: `~/bin/deepseek` (DeepCode CLI; Doppler project `agent-runtime-config` / secret `DEEPSEEK_API_KEY`; default model `deepseek-v4-pro`).
- Harness must not embed API keys; must not leave secrets at rest beyond the wrapper’s ephemeral settings pattern.

### 7.2 Git isolation

- Require pre-created or harness-created **worktree + branch** (prefer `pt worktrees` / project convention).
- Worker may `git add` / `git commit` locally only.
- Wrapper env / prompt forbids: `git push`, `gh pr create`, `gh merge`, force-push.
- Manager (personal GitHub identity) owns push/PR after verification.

### 7.3 Provenance

A job is only `succeeded` when:

1. Process exit observed (or clean handoff with matching `job_id`), and
2. Handoff parses and schema-validates, and
3. `commit_sha` exists in the worktree, and
4. Usage block present (`unknown` allowed).

Manager instruction alone is never proof of execution (Holoscape lesson).

---

## 8. Manager interface (CLI / API)

Stable binary name: **`dsw`** (symlink/entry in `_tools/deepseek-worker`).

| Command | Behavior |
|---------|----------|
| `dsw submit --order PATH [--idempotency-key K]` | Create or return existing job; print `job_id` + state |
| `dsw status JOB_ID` | JSON status snapshot |
| `dsw logs JOB_ID [--follow]` | Event log + worker stdout/err paths |
| `dsw cancel JOB_ID` | Request cancel; wait for terminal |
| `dsw wait JOB_ID [--timeout S]` | **Cheap** process block (no LLM); exits 0 on success wake |
| `dsw dequeue [--manager SEAT]` | Pop durable wake item for resume after idle/cron |
| `dsw doctor` | Paths, Doppler, DeepCode, off-peak now?, store health |

Python library surface (same package) for in-process callers; CLI is the cross-manager contract.

### Idle without manager burn

Recommended manager pattern:

1. `dsw submit` → receive `job_id`.
2. Reflect link on pt card (`pt tasks update --notes` append).
3. **Exit the expensive session** (or park on `dsw wait` in a plain shell / launchd / cron — not inside Codex/Claude/Grok turns).
4. On resume: `dsw dequeue` or `dsw status`; only then spend manager tokens on verification.

Wake items are durable files under the state dir (and optionally a `pt message` / inbox ping — see NOTES for Erik decision). Blind 30-minute LLM polling is explicitly out of policy.

---

## 9. Recovery matrix

| Failure | Detection | Action |
|---------|-----------|--------|
| Worker crash / nonzero exit | Supervisor waitpid / heartbeat miss | Mark `failed` or retry if under cap; wake manager |
| Missing process after restart | `running` job, pid dead / hostname mismatch | Reconcile → `failed` or `blocked`; never leave zombie `running` |
| Malformed / missing handoff | Schema validation | `failed`; preserve raw stdout for manager |
| Duplicate completion | Second finalize attempt | No-op; log `duplicate_completion_ignored` |
| Host reboot mid-job | `dsw doctor` / boot reconcile | Same as missing process |
| Peak boundary crossed mid-run | Optional soft warn; hard stop only if policy=`require` and configured | Event + optional cancel |
| Budget / timeout / rate limit | Ledger / HTTP 429 | Stop; terminal with evidence |
| Conflicting concurrent submit | Lock on `(card, worktree)` | Reject with existing `job_id` |

---

## 10. pt board integration

- **Source of truth for work:** pt card status / notes (via CLI only).
- On submit: append note with `job_id`, worktree, model, order path.
- On terminal: append note with final state, handoff path, commit SHA, usage summary.
- Never write tracker SQLite directly.
- Card status transitions (In Progress / Review / Done) remain **manager** decisions after verification — harness does not auto-`pt tasks done`.

---

## 11. Config coordination (not duplicated dispatchers)

| Change | Where |
|--------|-------|
| Default Worker model string | `MODEL_SEATS.md` / future `pt info get model_seats` |
| `/delegate` default `constraints.model` + `role: worker` | Author Claude skill → `agent-runtime-config` compile |
| Documented `dsw` invoke snippets for each manager | `_tools/deepseek-worker/OPS.md` + short pointers in runtime docs |
| Spawn-time rewrite hooks (block Manager-family implementers) | Later card; depends on this harness existing |

Do **not** resurrect `_tools/_archive/multi-layer-delegation` as the product path; reuse only envelope ideas (Task/Result shapes already mirrored in the `delegate` skill).

---

## 12. Holoscape / Hermes reference (gap)

Cited input path does **not** exist on this MacBook:

- Missing: `~/projects/holoscape-agent/.scratch/deepseek-supervisor-architecture-writeup.md`
- Missing directory: `~/projects/holoscape-agent`
- `~/projects/holoscape/.scratch/` contains only `research-three-problems.md` (unrelated)
- No local `*deepseek-supervisor*` / `*architecture-writeup*` under `~/projects` or shallow home search

**What does exist (usable reference):**

- Live lessons in pt #7540 notes: Sep 20 DeepSeek managed-worker prototype; later reversion to Hermes default coding; need for explicit provenance (provider, model, session, worktree, handoff).
- #7550 note: Managed DeepSeek provenance for PR #178 — worktree `holoscape-deepseek-worker-pr178`, provider `deepseek-big`, model `deepseek-v4-pro`, handoff `.scratch/deepseek-second-review-handoff.md`.
- `~/bin/deepseek` Doppler→DeepCode wrapper (operational credential path).
- Archived envelope design under `_tools/_archive/multi-layer-delegation/` (protocol inspiration only).

Design proceeds from card requirements + ORCHESTRATOR rules + these live facts. If Hermes later exports the writeup, fold deltas into a follow-up note — **do not change Hermes live setup**.

---

## 13. Acceptance criteria → design mapping

| # | Acceptance | Design coverage |
|---|------------|-----------------|
| 1 | Pilot e2e: pt → work order → DeepSeek process → durable signal → manager verify → PR | §§4–8, 10; PLAN Slice A–C |
| 2 | Codex, Claude, Grok same harness | §8 CLI contract; PLAN Slice D adapters |
| 3 | Failure demos (dup submit, crash, missing worker, bad handoff, off-peak, caps, blockers) | §9 + PLAN Slice E |
| 4 | No idle manager burn; unverified result ≠ done | §8 idle pattern; §3/§7.3 done gate |
| 5 | Ops docs + pilot cost comparison | PLAN Slice F; OPS.md |

---

## 14. Security & safety

- Secrets: Doppler only; no keys in JobStore or handoff.
- No push/PR/merge from worker.
- No direct pt DB access.
- State dir permissions `0700`; logs may contain code paths — treat as private.
- Forbidden actions enforced in work-order constraints and wrapper policy; not trusted to model memory alone.

---

## 15. Open questions

See `NOTES.md` (blocking Erik decisions only). Non-blocking defaults are chosen in PLAN.md.

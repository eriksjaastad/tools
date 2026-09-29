# DeepSeek coding-worker harness — Design

**Card:** pt #7569 (`_tools`)  
**Status:** design only (no product implementation in this pass)  
**Date:** 2026-09-24 (America/New_York)  
**Branch:** `task/7569-deepseek-worker-design`  
**Audience:** Erik + Codex / Claude / Grok managers implementing PR slices

## 1. Problem

Manager seats (Codex / Claude / Grok) burn expensive turns doing mechanical coding.
Portfolio policy already names **DeepSeek Pro as Worker** (`~/projects/MODEL_SEATS.md`,
`~/projects/ORCHESTRATOR_CHEAP_CODER_RULES.md`), but enforcement is chat/skill-level today.
Hermes Holoscape proved a separate DeepSeek coding process works; managers still lack
**one shared, durable, provider-neutral interface** to submit work, observe it, and resume
only when the worker needs attention.

This harness is an **execution system**, not a Kanban display feature and not three
per-provider dispatchers.

## 2. Goals / non-goals

### Goals
- One CLI/API used by Codex, Claude, and Grok managers.
- Durable job lifecycle with provenance (pt card, repo, worktree, model, cost, events).
- DeepSeek Pro default worker; explicit auditable exception when manager/other model codes.
- Off-peak UTC gate around paid DeepSeek work; budget/time/retry caps; rate-limit stop.
- Separate worker process with Doppler credentials; local commits + structured handoff only.
- Idle wait does **not** burn manager turns (notification/queue resume).
- Unverified worker output cannot mark a card Done or bypass independent review/CI/PR gates.
- Keep `pt` as the board; reflect job links/progress on the card via `pt` only (no direct DB).

### Non-goals (this card / nearby slices)
- Changing Hermes Holoscape’s live supervisor setup (reference only).
- Replacing `agent-runtime-config` or inventing three native spawn stacks.
- Worker-side push / PR create / merge.
- Full Auxesis venture pipeline; this is shareable internal tooling under `_tools`.
- Auto-merging or auto-“done” from worker completion alone.

## 3. Inputs inspected (live)

| Input | Finding |
|---|---|
| `ORCHESTRATOR_CHEAP_CODER_RULES.md` / `MODEL_SEATS.md` | Manager/Worker/Judge seats; Worker=DeepSeek Pro; R1–R6 bind policy |
| `Project-workflow.md` | Shareable tooling → design + phased PRs; Light Path too small for this system |
| Card path `~/projects/holoscape-agent/.scratch/deepseek-supervisor-architecture-writeup.md` | **MISSING** — see `GAP_HOLOSCAPE_WRITEUP.md` |
| Hermes Holoscape pilot (live traces) | Cards with `created_by: holoscape-deepseek-supervisor`; review notes cite worktree `holoscape-deepseek-worker-pr178`, provider `deepseek-big`, model `deepseek-v4-pro`, handoff `.scratch/deepseek-*-handoff.md`, local worker commits integrated by manager |
| `_tools/route/` | Pricing/usage CLI — **reuse for cost display**, not job lifecycle |
| `_tools/_archive/multi-layer-delegation/` | Envelope protocol (Task/Result) — **schema inspiration**; adapters archived, do not revive as three dispatchers |
| `agent-runtime-config` + `delegate` skill | Envelope shape + compile/sync spine for manager entry points |
| `~/.claude/scripts/deepcode-run.sh` | Canonical Doppler pattern: `agent-runtime-config` / `prd` / `DEEPSEEK_API_KEY`; ephemeral settings; default model `deepseek-v4-pro` |
| `claude-user-config` | GitHub repo `eriksjaastad/claude-user-config`; **not cloned on this MacBook** — coordinate via skill/hook adopt path when entry points land |
| DeepSeek pricing (2026-09-24 docs) | Peak UTC Mon–Fri **01:00–04:00** and **06:00–10:00**, excluding Chinese public holidays; off-peak = half peak; Worker model id `deepseek-v4-pro` |

## 4. Architecture overview

```
┌─────────────────────────────────────────────────────────────┐
│ Manager (Codex / Claude / Grok)                             │
│  - authorized pt task                                       │
│  - write bounded work order + acceptance criteria           │
│  - dsw submit → job_id                                      │
│  - detach (no polling loop)                                 │
│  - on wake: dsw status/logs → verify → review/CI/PR         │
└───────────────┬─────────────────────────────────────────────┘
                │ one shared CLI/API
                ▼
┌─────────────────────────────────────────────────────────────┐
│ deepseek-worker harness (_tools/deepseek-worker)            │
│  - job store (SQLite) + event log                           │
│  - off-peak / budget / concurrency gates                    │
│  - process supervisor (spawn, heartbeat, recover)           │
│  - notify sink (queue file + optional pt message)           │
└───────────────┬─────────────────────────────────────────────┘
                │ doppler-wrapped worker process
                ▼
┌─────────────────────────────────────────────────────────────┐
│ Worker (DeepSeek Pro coding agent)                          │
│  - isolated worktree/branch                                 │
│  - edit / test / local commit                               │
│  - write structured handoff.json                            │
│  - MUST NOT push / open PR / merge                          │
└─────────────────────────────────────────────────────────────┘
```

**Ownership split**

| Layer | Owner | Responsibility |
|---|---|---|
| Shared executable + job lifecycle | `_tools/deepseek-worker` | submit/status/logs/cancel, store, gates, spawn, recovery, notify |
| Manager entry points (skills/hooks text) | `agent-runtime-config` (+ Claude native via `claude-user-config` when present) | document “call `dsw`”, pin Worker binding; **no second dispatcher** |
| Seats / off-peak policy text | `MODEL_SEATS.md` / orchestrator rules | bindings; harness reads concrete model id + window config |
| Board / cards | `pt` CLI only | progress notes, job links; never raw DB |
| Hermes Holoscape supervisor | Hermes (live) | **reference**; out of scope to modify under #7569 |

## 5. Job record (durable)

Each job persists at least:

| Field | Notes |
|---|---|
| `job_id` | ULID/UUID; primary key |
| `idempotency_key` | Manager-supplied or hash(`pt_task_id` + `repo` + `worktree` + content digest) |
| `pt_task_id` | Required for green-path pilots |
| `repo_path` / `repo_remote` | Absolute path + origin |
| `worktree_path` / `branch` | Isolated; conflict if another active job owns same |
| `manager_identity` | `codex` \| `claude` \| `grok` \| `hermes` \| other |
| `worker_model` | Default from seats → `deepseek-v4-pro` |
| `worker_provider` | e.g. `deepseek` / account label |
| `state` | see state machine |
| `created_at` / `updated_at` / `started_at` / `finished_at` | ISO-8601 with offset |
| `deadline_at` | Hard wall-clock stop |
| `retry_count` / `max_retries` | Cap |
| `budget_usd` / `spent_usd` | Cap; provider-reported when available |
| `off_peak_policy` | `require_off_peak` \| `allow_peak` |
| `peak_exception` | `{reason, approved_by, at}` or null |
| `manager_implements_exception` | When Worker skipped; reason required |
| `pid` / `hostname` | For crash/orphan detection |
| `event_log[]` | Append-only structured events |
| `handoff_path` / `handoff_sha` | Structured result |
| `token_usage` | prompt/completion/cache if provider reports |
| `notify` | queue item id / pt message id |

**Idempotent submit:** same `idempotency_key` while job is active or successfully completed returns existing `job_id` (no second process). Conflicting concurrent job on same `pt_task_id` or same `worktree_path` is rejected.

## 6. State machine

```
                 submit (idempotent)
                      │
                      ▼
                   queued
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
 waiting_offpeak   spawning     rejected
        │             │          (conflict / bad order)
        └──────┬──────┘
               ▼
            running ──────────────► cancelling ─► cancelled
               │
               ├─ rate_limited (stop; notify; not silent retry storm)
               ├─ budget_exhausted / timed_out / crashed
               ▼
         handoff_pending
               │
               ├─ malformed_handoff
               ├─ duplicate_completion (ignore second; log)
               ▼
     completed | failed | blocked
```

**Terminal states:** `completed`, `failed`, `blocked`, `cancelled`, `rejected`.  
**Manager-verified** is **not** a harness state — verification lives on the manager side + `pt` / PR gates. Harness may record `manager_ack` events but must never imply “card Done.”

### Recovery matrix

| Failure | Detection | Action |
|---|---|---|
| Crash / host reboot | `running` + missing PID/heartbeat | → `crashed`; optional auto-requeue if retries left |
| Missing process | heartbeat timeout | same as crash |
| Malformed handoff | schema validation fail | → `malformed_handoff`; notify manager; do not invent success |
| Duplicate completion | second handoff for same job | keep first valid; log `duplicate_completion` |
| Restart mid-job | supervisor boot scan | reconcile PIDs; re-notify open terminal events |
| Rate limit | provider/HTTP signal | stop; state `rate_limited` / `failed`; no burn |

## 7. Work order + handoff contracts

Reuse the spirit of the archived Task/Result envelopes; keep files on disk next to the job.

### Work order (`work_order.json`) — manager → worker

```json
{
  "schema": "deepseek-worker.work_order.v1",
  "pt_task_id": 7569,
  "goal": "one sentence success",
  "acceptance_criteria": ["testable …"],
  "context_paths": ["…"],
  "repo_path": "/Users/…/proj",
  "base_ref": "main",
  "branch": "task/7569-…",
  "constraints": {
    "model": "deepseek-v4-pro",
    "max_cost_usd": 1.0,
    "deadline_minutes": 45,
    "max_retries": 1,
    "forbidden_actions": ["git push", "gh pr create", "gh pr merge", "gha pr create", "gha pr merge"]
  },
  "test_commands": ["uv run pytest -q …"],
  "off_peak_policy": "require_off_peak",
  "peak_exception": null
}
```

### Handoff (`handoff.json`) — worker → manager

```json
{
  "schema": "deepseek-worker.handoff.v1",
  "job_id": "…",
  "pt_task_id": 7569,
  "status": "completed|failed|blocked|partial",
  "branch": "task/…",
  "head_sha": "full sha",
  "files_changed": [{"path": "…", "change": "M|A|D"}],
  "checks_run": [{"cmd": "…", "exit_code": 0, "summary": "…"}],
  "blockers": [],
  "notes": "…",
  "token_usage": {"prompt": 0, "completion": 0, "cache_hit": 0, "usd_estimate": 0.0},
  "worker_model": "deepseek-v4-pro",
  "finished_at": "2026-09-24T20:00:00-04:00"
}
```

**Invariant:** manager instruction text is never proof of execution. Only handoff + git SHA + event log count.

## 8. CLI surface (stable, manager-facing)

Binary name recommendation: `dsw` (shim) → `deepseek-worker` module under `_tools/deepseek-worker/`.

| Command | Behavior |
|---|---|
| `dsw submit --order PATH [--idempotency-key K] [--json]` | Validate order; enqueue; return `job_id` |
| `dsw status JOB_ID [--json]` | Current state + key fields |
| `dsw logs JOB_ID [--follow]` | Event log / worker stdout paths |
| `dsw cancel JOB_ID` | Cooperative cancel → `cancelled` |
| `dsw wait JOB_ID --notify-only` | **Forbidden for managers in green path** — documented anti-pattern; exists only for operator demos |
| `dsw doctor` | Doppler reachability, store path, off-peak now?, orphan scan |
| `dsw reconcile` | Crash/orphan recovery pass (cron-friendly) |

Exit codes: `0` ok, `2` usage/validation, `3` conflict/idempotency, `4` not found, `5` policy (peak without exception), `10` worker terminal failure mirrored for scripts.

## 9. Storage layout

Prefer machine-local durable state (not in git).

**Default path (decision for PR-1):** `~/.deepseek-worker/` (short, operator-visible; override with `DSW_DATA_DIR`).  
XDG `~/.local/share/deepseek-worker` is an acceptable alternate if Erik prefers standards compliance — pick one in PR-1 and document in `doctor`.

```
~/.deepseek-worker/
  jobs.sqlite
  jobs/<job_id>/
    work_order.json
    handoff.json          # when present
    events.jsonl
    worker.stdout.log
    meta.json
  notify/
    queue.jsonl           # durable wake items
```

**Do not** write Project Tracker SQLite directly.

## 10. Off-peak policy

Source of truth for windows: DeepSeek API docs (verify on change; mirror into harness config with `retrieved_at`).

- **Peak:** 01:00–04:00 and 06:00–10:00 **UTC**, Monday–Friday, **excluding Chinese public holidays**.
- **Off-peak:** all other hours (weekends + CN holidays full day).
- DST: windows are **UTC-fixed**; America/New_York mapping shifts with DST — display both in `doctor` / banners.
- `require_off_peak`: paid worker start deferred to `waiting_offpeak` until window opens (still durable; notify when started or if deadline can’t be met).
- `allow_peak`: requires `peak_exception.reason` (+ who/when); always logged.
- Cap spend/time/retries independently of peak; stop on rate limits.

Cost recording: prefer provider-reported usage; else estimate via `_tools/route` registry as **shadow**, labeled estimate-not-invoice.

## 11. Notification / resume (no idle manager burn)

Managers must **not** sit in a tool-loop polling every N minutes.

Wake channels (in order of preference for v1):

1. **Durable local queue** `notify/queue.jsonl` with `{job_id, pt_task_id, state, at, summary}`.
2. **`pt message send`** to a configured manager address (optional; `--to` / machine), high priority on terminal states.
3. **`pt tasks update --review-comment`** short pointer (job link + state) — never wipe authoritative `notes` blindly; append pattern or review-comment only.
4. Optional later: macOS notification / Hermes cron calling `dsw reconcile` + queue drain.

Manager resume recipe: cron or session-start skill checks queue → `dsw status` → verify → PR path.

## 12. Security (Doppler) + process isolation

- Worker credentials: **Doppler only**. Follow `deepcode-run.sh` defaults unless seats say otherwise:
  - project `agent-runtime-config`, config `prd`, secret `DEEPSEEK_API_KEY`
  - model `deepseek-v4-pro`
- Never persist API keys in job dirs; shred ephemeral launcher files.
- Worker runs as a **child process** (or launchd/user agent later) with cwd = worktree.
- Git: local commits allowed; hooks still apply. Manager uses **personal GitHub identity** (`gha` / `eriksjaastad`) for PR work per `_tools` CLAUDE.md cutover rules.
- Forbidden in worker environment / wrapper: `git push`, `gh`/`gha` PR create/merge (deny-list + docs; hard block where cheap).

## 13. What stays in manager vs worker

| Manager | Worker |
|---|---|
| Authorize from `pt` card | Implement bounded stage |
| Write work order + AC | Tool loop: edit/test/commit |
| Submit + detach | Write handoff |
| Verify provenance + spot-check AC | Report blockers/failures honestly |
| Independent code-reviewer + CI + PR | No review-of-self, no PR |
| Peak exception / manager-implements exception records | Obey model pin + forbidden actions |
| Cost comparison narrative | Token usage best-effort |

## 14. Provider coordination (no triple dispatcher)

```
Claude native skill/hook  ──adopt/compile──►  agent-runtime-config artifacts
Codex ~/.agents skill     ◄──runtime-compile──┘
Grok Bot memory/skill text ──points at same──►  `dsw` CLI
```

- Update `delegate` defaults (`constraints.model` → Worker binding; `role: worker`) in a **dependent** config PR, not by forking spawn logic inside Claude/Codex/Grok.
- Optional thin wrappers: `dsw-claude`, etc. **must** call the same Python entrypoint.
- Hermes Holoscape supervisor remains external reference; migration onto `dsw` is a later card if Erik wants parity.

## 15. Demo / acceptance mapping (design-level)

| Acceptance # | Design mechanism |
|---|---|
| 1 Pilot e2e | submit → worker → handoff → notify → manager verify → PR with job id + cost + pt status |
| 2 Three managers | one CLI; three documented invoke recipes; exercised in PLAN demos |
| 3 Failure demos | conflict submit, kill -9, missing binary, bad handoff JSON, peak boundary, budget/timeout/retry, failing tests → `blocked`/`failed` |
| 4 No idle burn / no fake done | queue wake; harness never calls `pt tasks done`; manager verification gate documented |
| 5 Ops | `dsw doctor`, MacBook (+ Mini later) install notes, alert routing via pt message/queue, rollback = disable launcher + leave store intact |

## 16. Risks (design)

- Holoscape writeup missing → risk of reinventing Hermes-specific edges (mitigate: cite live card traces; optional Erik paste).
- DeepSeek model/pricing churn → keep windows + model id in versioned config with `retrieved_at`.
- Concurrent DeepCode settings file races (known in `deepcode-run.sh`) → prefer API/CLI path that does not share one settings file, or one-job-at-a-time per host in v1.
- Managers ignoring detach recipe → skill/hook wording + demo evidence.
- Notification spam → coalesce per job; only terminal + blocker + rate_limit.

## 17. Open questions for Erik

See `PLAN.md` § Open questions (max 5, blocking only).

# DeepSeek Worker — Notes / Gaps / Decisions

**Card:** #7569  
**Date:** 2026-09-24 (EDT)

---

## Holoscape supervisor writeup — GAP

**Cited (missing):** `~/projects/holoscape-agent/.scratch/deepseek-supervisor-architecture-writeup.md`

| Check | Result |
|-------|--------|
| `~/projects/holoscape-agent/` | Does not exist on MacBook |
| `~/projects/holoscape/.scratch/` | Only `research-three-problems.md` |
| Glob `*deepseek-supervisor*` / `*architecture-writeup*` under `~/projects` | No hits |
| Hermes local state `~/.hermes` | Not present on MacBook (Mini-only per #7540) |

**Usable substitutes (not the missing writeup):**

- pt #7540 notes — Sep 20 DeepSeek managed-worker prototype; later reversion; provenance requirements.
- pt #7550 — Managed DeepSeek provenance (`deepseek-v4-pro`, worktree `holoscape-deepseek-worker-pr178`, handoff path).
- `~/bin/deepseek` — Doppler → DeepCode operational launcher.
- `_tools/_archive/multi-layer-delegation/` — historical envelope architecture (reference only; not resurrected).

**Action:** Proceed with DESIGN/PLAN from card + ORCHESTRATOR rules + substitutes. If Hermes can export the writeup to a MacBook path, re-diff against DESIGN.md in a follow-up — **without** changing Hermes live setup.

---

## Existing inventory (read-only findings)

| Asset | Relevance |
|-------|-----------|
| `_tools/route/` | Shadow pricing / session readers — use for cost *comparison* estimates, not as the job harness |
| `_tools/_archive/multi-layer-delegation/` | Envelope inspiration; adapters archived |
| `delegate` skill (`agent-runtime-config` artifacts) | Task/Result envelope; still defaults `model: sonnet` — update in Slice D |
| `~/bin/deepseek` | Preferred worker launcher |
| `pt jobs` | Unrelated (job *listings* import) — do not overload |
| `claude-user-config` path | Not present as `~/projects/claude-user-config`; Claude surfaces live under `~/.claude` + sync via `agent-runtime-config` |

---

## Blocking questions for Erik (max 5)

Non-answers → PLAN.md defaults apply.

1. **Wake channel for manager resume:** filesystem queue + `dsw wait` only for v1, or also auto `pt message` / Discord ping on terminal states?
2. **Pilot host:** MacBook-only for v1, or must Mini Hermes also run `dsw` in the first pilot?
3. **Worker runtime lock-in:** confirm DeepCode via `~/bin/deepseek` / `deepseek-v4-pro` as the only v1 worker (vs raw HTTP agent loop)?
4. **Pilot target repo:** OK to use a tiny disposable fixture / self-test under `_tools`, or must the first e2e be a real product card (which project)?
5. **Missing Holoscape writeup:** ask Hermes to export it before Slice C, or proceed without and treat #7540/#7550 notes as sufficient reference?

---

## Non-blocking decisions already taken in DESIGN

- Job store on submitting host under `~/.deepseek-worker/`.
- Off-peak evaluated in UTC per DeepSeek docs (peak Mon–Fri 01:00–04:00 & 06:00–10:00 UTC; weekends + Chinese holidays off-peak).
- pt updates via CLI notes append only.
- No Hermes/Holoscape live changes; no `image-workflow` touches.

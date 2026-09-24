# Gap note — Holoscape DeepSeek supervisor architecture writeup

**Card input path (authoritative on #7569):**  
`~/projects/holoscape-agent/.scratch/deepseek-supervisor-architecture-writeup.md`

## Result (2026-09-24, MacBook)

**Not found.**

| Check | Result |
|---|---|
| Directory `~/projects/holoscape-agent` | Does not exist on this MacBook |
| `~/projects/holoscape/.scratch/` | Exists; contains only `research-three-problems.md` (2026-09-12) — no supervisor writeup |
| Filename search `*deepseek*supervisor*`, `*supervisor*architecture*`, `*architecture*writeup*` under `~/projects` | No matching writeup |
| `ai-journal` / `ai-memory` targeted search for that filename / “supervisor architecture writeup” | No hit for this artifact |
| Hermes upstream clone `github-repos/hermes-agent` | Generic DeepSeek parsers/providers only; no Holoscape supervisor writeup |

## What *was* found (usable reference substitutes)

Live Holoscape / Hermes pilot **traces** (not a design writeup):

- pt cards with `created_by: "holoscape-deepseek-supervisor"` (e.g. Holoscape in-progress work).
- Review notes on Holoscape work citing:
  - worktree path pattern `…/holoscape-deepseek-worker-pr178`
  - provider label `deepseek-big`
  - model `deepseek-v4-pro`
  - handoff files under `.scratch/deepseek-*-handoff.md`
  - worker local commits integrated by manager; third-cycle review holds still apply
- Portfolio policy docs: `ORCHESTRATOR_CHEAP_CODER_RULES.md`, `MODEL_SEATS.md` (Holoscape lesson: chat-only Worker pin regresses).
- Doppler/DeepSeek launcher: `~/.claude/scripts/deepcode-run.sh`.

## Implication for #7569

Design proceeds from card text + policy docs + live traces above.  
If the writeup exists on Mac Mini or another path, paste or sync it before PR-5 so we do not miss Hermes-specific edges (scheduling, handoff fields, identity labels).

**Ask Erik:** locate/paste writeup, or confirm “live traces sufficient.”

## Additional substitute evidence (pt)

- **#7540** (project-tracker): Holoscape measurement card. Documents Sep 20 DeepSeek managed-worker prototype success, later reversion to default Hermes/manager coding, and the provenance lesson (provider/model/session/worktree/handoff required — not “use DeepSeek when useful”). Notes Mini Hermes state; MacBook lacks `~/.hermes`.
- **#7550** (holoscape, Review hold): Managed DeepSeek provenance on PR #178 — worktree `holoscape-deepseek-worker-pr178`, provider `deepseek-big`, model `deepseek-v4-pro`, handoff `.scratch/deepseek-second-review-handoff.md`, worker commit integrated by manager. Agent prompt also references missing path `~/projects/holoscape-agent` (same naming gap as the writeup).
- Launcher: `~/bin/deepseek` → `~/.claude/scripts/deepcode-run.sh`.

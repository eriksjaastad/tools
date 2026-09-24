# deepseek-worker

Shared DeepSeek coding-worker harness for Codex / Claude / Grok managers.

**Status:** design + plan only (pt #7569). No product implementation in the design pass.

| Doc | Purpose |
|---|---|
| [DESIGN.md](./DESIGN.md) | Architecture, state machine, CLI, storage, off-peak, notify, security |
| [PLAN.md](./PLAN.md) | Phased PR slices + acceptance map + first slice recommendation |
| [GAP_HOLOSCAPE_WRITEUP.md](./GAP_HOLOSCAPE_WRITEUP.md) | Missing Holoscape supervisor writeup |

Implementation starts at **PR-1** in `PLAN.md` (submit → worker → handoff → status).

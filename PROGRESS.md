# PROGRESS.md - _tools

**Session:** 2026-04-15/16 (evening)
**Floor Manager:** Claude Opus 4.6

## What happened

Board triage session with Erik. Started with 8 cards, ended with 2 after aggressive cleanup.

### Built
- **/prompt skill** (`~/.claude/skills/prompt/SKILL.md`) — turns hand-wavy asks into agent-ready prompts in a house format (`<role> <task> <files> <context> <acceptance> <constraints>`). Stateless, single-pass. No voice calibration (Erik cut it as overdone). Tested live on #5437, #5959, #5977, #5660, #5631. Erik used it end-to-end: /prompt → copy → /plan → hand to Architect. Card #5974 closed.

### Fixed
- **CLAUDE.md broken refs** (#5960) — fixed two stale references: `Documents/REVIEWS_AND_GOVERNANCE_PROTOCOL.md` repointed to canonical `~/projects/project-scaffolding/REVIEWS_AND_GOVERNANCE_PROTOCOL.md`, `pytest tests/` replaced with truthful test paths (`integrity-warden/tests/` etc.).
- **Dead librarian-mcp entry** (#5980) — removed from `~/.claude/claude_desktop_config.json`.
- **Leaked GOOGLE_CLIENT_SECRET** (#5979) — verified never in git, already in Doppler, settings.json uses env var interpolation, .zshrc loads from Doppler. Erik declined rotation (local-only blast radius).

### Cancelled (redundant or superseded)
- #5437 — AI Image Reader (real problem is Flo-fi context burn, not a new tool)
- #5624 — /morning-status (duplicates `pm` skill)
- #5481 — Stale branch cleanup (duplicates `cleanup` skill + journal integration)
- #5660 — Agentic Tool-Use Loop (no committed consumer; Holoscape FM confirmed no message board designed yet)
- #5631 — Gated Development Loop (superseded by upstream rigor: PRD → advisors → dual Kiro → merge)
- #5669 — Brain-context PreToolUse hook (AI Memory FM recommended cancel: SessionStart hooks + L2 on-demand cover it better)

### Created
- **#5977** — Consolidate hooks into `~/.claude/` (Architect completed same day)
- **#5978** — Dedupe governance protocol (moved to project-scaffolding board)

### Key decisions
- Agent collaboration model: agents need context (cards, prompts), not chat channels. Erik is the router. Don't build agent-to-agent infra without a concrete FM ask.
- Build process lesson: fix bad builds with upstream rigor (PRD → advisors → dual Kiro → merge), not downstream review gates. Learned from Holoscape 40-min-build/14-day-debug.
- Hooks consolidated to one scope (`~/.claude/`) — project-scope hooks eliminated.

## Remaining board (2 cards)

- **#5959** — PRD validator false-positives. Unblocked now (#5977 done). The validator at `~/.claude/hooks/prd-structure-validator.py` triggers on any file starting with "PRD" — needs a smarter gate. We were mid-discussion on the approach when session ended. Erik rejected the "2 H2 headers" heuristic as dumb. I suggested checking for `# PRD:` as the H1 title (every real PRD uses that pattern). **Pick up here tomorrow.**
- **#5666** — Universal ESLint no-redeclare hook. Card rewritten with full prompt. Ready to route to a worker.

## Next steps

1. Finish #5959 — decide on trigger heuristic for PRD validator, implement it
2. Route #5666 to a worker or build it
3. Check if project-scaffolding FM picked up #5978

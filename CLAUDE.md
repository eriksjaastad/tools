# CLAUDE.md - Tools Directory AI Collaboration Instructions

> **Purpose:** Instructions for AI reviewers working with Erik's tools ecosystem
> **Audience:** Claude (API/Web), Gemini, and other AI collaborators

---

## What Is This Directory?

`_tools/` is Erik's collection of infrastructure tools that power his AI-assisted development workflow. These are **shared utilities** used across multiple projects.

### Projects in This Directory

| Project | Purpose | Status |
|---------|---------|--------|
| **agent-hub** | Unified Agent System - message bus, model routing, budget management, circuit breakers | Active |
| **librarian-mcp** | MCP server for knowledge graph queries (wraps project-tracker) | Active |
| **claude-mcp** | MCP hub for agent communication | Active |
| **ollama-mcp** | MCP server for local Ollama models (draft tools, model execution) | Active |
| **ai_router** | Route requests to appropriate AI models | Active |
| **integrity-warden** | Security and compliance auditing | Active |
| **gsd** | "Get Shit Done" - task automation | Stable |
| **ssh_agent** | SSH key management | Stable |
| **pdf-converter** | PDF processing utilities | Stable |
| **claude-cli** | Claude CLI wrapper | Stable |

---

## Code Review Standards

**IMPORTANT:** All code reviews must follow the established protocols.

### Required Reading Before Reviewing

1. **`Documents/REVIEWS_AND_GOVERNANCE_PROTOCOL.md`** - Master checklist and audit process
2. **`Documents/patterns/code-review-standard.md`** - Naming conventions and workflow
3. **`Documents/CODE_QUALITY_STANDARDS.md`** - Hard rules (no silent failures, subprocess integrity, etc.)
4. **`Documents/reference/CODE_REVIEW_ANTI_PATTERNS.md`** - Common defects to catch
5. **`Documents/reference/REVIEW_SYSTEM_DESIGN.md`** - Two-layer defense model

### Review Output Format

All review documents must be named:
```
CODE_REVIEW_{REVIEWER_NAME}_{VERSION}.md
```

Example: `CODE_REVIEW_CLAUDE_v1.md`

### The Master Checklist

Every review must include evidence for these checks:

| ID | Check | Evidence Required |
|----|-------|-------------------|
| M1 | No hardcoded `/Users/` or `/home/` paths | `grep` output |
| M2 | No silent `except: pass` patterns | `grep` output |
| M3 | No API keys in code | `grep` output |
| H1 | Subprocess uses `check=True` and `timeout` | File/line list |
| H3 | Atomic writes for critical files | Verify pattern |
| E1 | Exit codes are accurate | Test failure path |

See `Documents/REVIEWS_AND_GOVERNANCE_PROTOCOL.md` for full checklist (M1-S2).

---

## Architecture Overview

### The Agent Pipeline

```
Erik (Human)
    │
    ▼
Claude (Super Manager) ◄──── You are here when reviewing
    │
    ▼
┌─────────────────────────────────────────┐
│           MCP Hub (claude-mcp)          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │PROPOSAL │  │ REVIEW  │  │VERDICT  │  │
│  │ _READY  │  │_NEEDED  │  │_SIGNAL  │  │
│  └────┬────┘  └────┬────┘  └────┬────┘  │
└───────┼────────────┼────────────┼───────┘
        ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │  Floor  │  │  Local  │  │  Judge  │
   │ Manager │  │Reviewer │  │(Claude) │
   │(Gemini) │  │(DeepSeek)│  │         │
   └─────────┘  └─────────┘  └─────────┘
        │
        ▼
   ┌─────────┐
   │Implement│
   │  (Qwen) │
   └─────────┘
```

### Key Concepts

- **MCP (Model Context Protocol):** JSON-RPC over stdio for agent communication
- **Constrained Messaging:** Fixed message types only (PROPOSAL_READY, REVIEW_NEEDED, etc.)
- **Heartbeat Monitoring:** Agents emit heartbeats every 30s; stall = 3 missed beats
- **Circuit Breakers:** 9 automatic halt conditions (cost, time, rebuttals, etc.)

---

## Safety Rules

### NEVER Modify

1. **Production data** - Any `data/` directories with real user data
2. **API keys** - `.env` files, never log or commit
3. **Git history** - No force pushes, no history rewrites

### Be Careful With

1. **MCP server code** - Affects all downstream agents
2. **Contract state machines** - Invalid transitions can deadlock
3. **Circuit breaker logic** - False positives halt automation

### Safe to Modify

1. **Documentation** - All `Documents/**/*.md`
2. **Tests** - All `tests/` directories
3. **Scripts** - Development utilities

---

## When Reviewing agent-hub Specifically

### Key Files

| File | Purpose | Review Focus |
|------|---------|--------------|
| `src/watchdog.py` | State machine, circuit breakers | Transitions, halt conditions |
| `src/listener.py` | Message loop | Threading, graceful shutdown |
| `src/hub_client.py` | MCP communication | Message validation |
| `src/worker_client.py` | Ollama integration | Timeout handling |
| `src/git_manager.py` | Branch management | Atomic operations |

### State Machine

Valid transitions are strictly defined. Review for:
- No impossible state jumps
- All error paths lead to `erik_consultation`
- Timeouts trigger appropriate transitions

### Circuit Breakers (9 Triggers)

1. Rebuttal limit exceeded
2. Destructive diff (>50% deletion)
3. Logical paradox (local fail + judge pass)
4. Hallucination loop (same hash failed before)
5. GPT-Energy nitpicking (3+ cycles of style-only)
6. Inactivity timeout
7. Budget exceeded
8. Scope creep (>20 files changed)
9. Review cycle limit

---

## Definition of Done (DoD) Template

When requesting a review, include:

```markdown
## Definition of Done

- [ ] All M1-M3 robot checks pass (no hardcoded paths, no silent errors, no secrets)
- [ ] All H1-H4 hardening checks pass
- [ ] Tests pass: `pytest tests/`
- [ ] No new security vulnerabilities introduced
- [ ] Documentation updated if behavior changed
```

---

## Questions to Ask Before Approving

1. **Does this change propagate?** (Tier 1 files affect all downstream)
2. **What's the blast radius if it fails?**
3. **Is there a rollback path?**
4. **Are timeouts and retries handled?**
5. **Does it respect the cost ceiling?**

---

## Contact

- **Project Owner:** Erik Sjaastad
- **Super Manager:** Claude (that's you, cousin)
- **Floor Manager:** Claude or Gemini (as available)

---

*Remember: Intelligence belongs in the checklist, not the prompt. Evidence-first.*

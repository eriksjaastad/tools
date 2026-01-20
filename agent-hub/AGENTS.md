# AGENTS.md - Agent Hub Source of Truth

> **Read the ecosystem constitution first:** `project-scaffolding/AGENTS.md`
> This document covers agent-hub specific workflows and the V4 Sandbox Draft Pattern.

---

## Project Overview

Agent Hub is the Floor Manager implementation for multi-agent task pipelines. It orchestrates task execution between Implementer, Local Reviewer, and Judge agents using an MCP message bus.

**Key Innovation (V4):** The Sandbox Draft Pattern allows local models to edit files safely through a gated sandbox.

---

## Tech Stack

- **Language:** Python 3.11+
- **Protocol:** Model Context Protocol (MCP)
- **Message Bus:** claude-mcp (hub)
- **Workers:** ollama-mcp (local models)

---

## V4 Sandbox Draft Pattern

### The Problem

Local models (Ollama) can generate code but couldn't write files directly. The Floor Manager had to parse their output and apply changes manually - leading to ~15% parse failures and brittle workflows.

### The Solution

**Draft → Gate → Apply**

Workers write to a sandbox. The Floor Manager reviews the diff and decides whether to apply it.

```
┌─────────────────────────────────────────────────────────────────┐
│                     V4 DRAFT WORKFLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Worker (Ollama)              Floor Manager           Target   │
│   ┌──────────────┐            ┌──────────────┐      ┌────────┐ │
│   │              │            │              │      │        │ │
│   │ 1. Request   │───────────▶│ Copy to      │      │        │ │
│   │    Draft     │            │ sandbox      │      │        │ │
│   │              │◀───────────│              │      │        │ │
│   │              │            │              │      │        │ │
│   │ 2. Edit      │            │              │      │        │ │
│   │    Draft     │───────────▶│ Write to     │      │        │ │
│   │              │            │ sandbox only │      │        │ │
│   │              │            │              │      │        │ │
│   │ 3. Submit    │───────────▶│ GATE:        │      │        │ │
│   │    Draft     │            │ - Diff       │      │        │ │
│   │              │            │ - Safety     │─────▶│ Apply  │ │
│   │              │            │ - Decision   │      │        │ │
│   │              │◀───────────│              │      │        │ │
│   │              │  ACCEPTED  │              │      │        │ │
│   │              │  REJECTED  │              │      │        │ │
│   │              │  ESCALATED │              │      │        │ │
│   └──────────────┘            └──────────────┘      └────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Draft Tools (ollama-mcp-go)

| Tool | Purpose |
|------|---------|
| `draft_read` | Read file from sandbox |
| `draft_write` | Write/update file in sandbox |
| `draft_patch` | Apply line-based patches to file |
| `draft_list` | List files in sandbox |

### Draft Gate (agent-hub)

When a `DRAFT_READY` message arrives, the Floor Manager:

1. **Validates** - Is the submission well-formed?
2. **Diffs** - What changed between original and draft?
3. **Analyzes** - Safety checks on the diff
4. **Decides** - Accept, Reject, or Escalate

### Security Layers

```
┌─────────────────────────────────────────────────┐
│               SECURITY LAYERS                    │
├─────────────────────────────────────────────────┤
│ Layer 1: Path Validation                         │
│   - Only _handoff/drafts/ is writable           │
│   - Path traversal blocked                       │
│   - Sensitive files blocked from drafting        │
├─────────────────────────────────────────────────┤
│ Layer 2: Content Analysis                        │
│   - Secret detection (API keys, passwords)       │
│   - Hardcoded path detection (/Users/, /home/)   │
│   - Deletion ratio monitoring (>50% = escalate)  │
├─────────────────────────────────────────────────┤
│ Layer 3: Floor Manager Gate                      │
│   - Diff review before apply                     │
│   - Conflict detection (hash mismatch)           │
│   - Escalation for large changes                 │
├─────────────────────────────────────────────────┤
│ Layer 4: Audit Trail                             │
│   - All decisions logged to transition.ndjson   │
│   - Submission metadata preserved                │
│   - Rollback capability via git                  │
└─────────────────────────────────────────────────┘
```

### Gate Decisions

| Decision | When | Action |
|----------|------|--------|
| **ACCEPT** | All checks pass | Apply diff to target file |
| **REJECT** | Security violation | Discard draft, log reason |
| **ESCALATE** | Large change / uncertain | Alert Conductor for review |

---

## Circuit Breakers (9 Triggers)

The Floor Manager will halt and alert the Conductor when:

1. **Rebuttal limit exceeded** - Too many review cycles
2. **Destructive diff** - >50% deletion in a single change
3. **Logical paradox** - Local review fails but Judge passes
4. **Hallucination loop** - Same hash failed before
5. **GPT-Energy nitpicking** - 3+ cycles of style-only changes
6. **Inactivity timeout** - No progress for configured duration
7. **Budget exceeded** - Cost ceiling reached
8. **Scope creep** - >20 files changed in one task
9. **Review cycle limit** - Max review rounds exceeded

---

## Definition of Done (DoD)

- [ ] Code passes all existing tests (`pytest tests/`)
- [ ] No hardcoded paths (`grep -r '/Users/' src/` returns empty)
- [ ] No silent exceptions (`grep -rn 'except.*pass' src/` returns empty)
- [ ] Subprocess calls have timeouts
- [ ] Changes logged to `_handoff/transition.ndjson`
- [ ] If modifying V4 components: security tests pass (`pytest tests/test_sandbox.py tests/test_draft_gate.py`)

---

## Execution Commands

```bash
# Health check
python scripts/health_check.py

# Start Floor Manager
./scripts/start_agent_hub.sh

# Run tests
pytest tests/

# Run specific test suites
pytest tests/test_sandbox.py      # Sandbox security
pytest tests/test_draft_gate.py   # Draft gate logic
pytest tests/test_e2e.py          # End-to-end pipeline
```

---

## Critical Constraints

- **NEVER** bypass the draft gate for file writes
- **NEVER** allow workers to write outside `_handoff/drafts/`
- **ALWAYS** validate paths before any file operation
- **ALWAYS** log gate decisions to transition.ndjson
- **ALWAYS** check for secrets before accepting drafts

---

## Message Types

| Message | Direction | Purpose |
|---------|-----------|---------|
| `PROPOSAL_READY` | → Floor Manager | New task to implement |
| `REVIEW_NEEDED` | → Judge | Request external review |
| `DRAFT_READY` | → Floor Manager | Worker submitted a draft |
| `DRAFT_ACCEPTED` | → Worker | Draft applied successfully |
| `DRAFT_REJECTED` | → Worker | Draft failed safety checks |
| `DRAFT_ESCALATED` | → Conductor | Needs human review |
| `STOP_TASK` | → All | Halt current task |

---

## Related Documentation

- [[V4_IMPLEMENTATION_COMPLETE]] - V4 implementation details
- [[PRD]] - Product requirements (V3.0)
- [[project-scaffolding/AGENTS]] - Ecosystem constitution
- [[ollama-mcp/AGENTS]] - Worker tools documentation

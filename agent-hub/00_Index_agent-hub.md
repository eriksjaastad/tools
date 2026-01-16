# 00_Index: Agent Hub

> **Type:** Tool / Infrastructure  
> **Status:** Active Development  
> **Created:** January 12, 2026  
> **Updated:** January 16, 2026

---

## What This Is

**Agent Hub** is an autonomous multi-agent orchestration system. It takes a task description and produces a reviewed, merged deliverable with zero manual handoffs.

```
You → Contract → Implementer (local) → Local Review → Judge (cloud) → Merge
                        ↑                                    │
                        └──────── Refinement Loop ───────────┘
```

## The Vision

- **Local models do the grunt work** (Qwen, DeepSeek) - FREE
- **Cloud models do the thinking** (Claude, Gemini) - SMART
- **Contracts enforce handoffs** - NO VIBES
- **Circuit breakers prevent disasters** - SAFE

---

## 📋 Start Here

| Document | What It Is |
|----------|-----------|
| **[PRD.md](PRD.md)** | ⭐ What we're building and why. Start here. |
| **[TODO.md](TODO.md)** | Implementation checklist and next actions |

---

## 📐 Design Documents

| Document | Purpose |
|----------|---------|
| [Agentic Blueprint.md](Documents/Agentic%20Blueprint.md) | High-level vision: 4-phase "Implementation Factory" |
| [Agentic Blueprint Setup V2.md](Documents/Agentic%20Blueprint%20Setup%20V2.md) | Detailed design: schema, state machine, circuit breakers |
| [Agentic_Blueprint_Setup_index.md](Documents/Agentic_Blueprint_Setup_index.md) | Index of all blueprint documents |
| [PRD integration.md](Documents/PRD%20integration.md) | Strategy for retroactive PRDs |

---

## 🔍 Peer Reviews

| Review | Reviewer | Key Insights |
|--------|----------|--------------|
| [Claude Code Review](Documents/Reviews/Agentic%20Blueprint%20Setup%20Claude%20code%20review.md) | Claude | Race conditions, CLI flags, lock mechanism |
| [Claude Review](Documents/Reviews/Agentic%20Blueprint%20Setup%20Claude%20review) | Claude | Role ambiguity, missing schema, circuit breakers |
| [GPT Review](Documents/Reviews/Agentic%20Blueprint%20Setup%20gpt%20review.md) | GPT-4 | File signaling races, idempotency, branch-per-task |
| [GPT Codex Review](Documents/Reviews/Agentic%20Blueprint%20Setup%20gpt%20codex%20review.md) | Codex | Schema versioning, checksums, retry limits |

---

## 🗂️ Directory Structure

```
agent-hub/
├── 00_Index_agent-hub.md   # ← You are here
├── PRD.md                  # Product Requirements Document
├── TODO.md                 # Implementation checklist
├── hub.py                  # Phase 1 foundation (Swarm + LiteLLM)
├── requirements.txt        # Python dependencies
│
├── Documents/              # Design docs & specs
│   ├── Agentic Blueprint.md
│   ├── Agentic Blueprint Setup V2.md
│   └── Reviews/            # Peer review archive
│
├── src/                    # Implementation (coming)
│   ├── watchdog.py         # State machine manager
│   ├── watcher.sh          # Claude CLI loop
│   └── validators.py       # Contract validation
│
├── templates/              # Contract & proposal templates
│   ├── PROPOSAL_FINAL.template.md   # ← Super Manager uses this
│   └── TASK_CONTRACT.template.json  # (coming)
│
└── _handoff/               # Runtime directory (gitignored)
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Agent Framework | Swarm (OpenAI) |
| Model Proxy | LiteLLM |
| Local Inference | Ollama (Qwen 2.5, DeepSeek) |
| Cloud Intelligence | Claude CLI, Gemini |
| Version Control | Git (branch-per-task) |

---

## Related Projects

| Project | Relationship |
|---------|--------------|
| `_tools/ai_router/` | May merge into Hub (routing logic) |
| `_tools/ollama-mcp/` | Separate (Cursor MCP integration) |
| `project-scaffolding/` | Hub will manage scaffold tasks |

---

## Quick Start (Coming Soon)

```bash
# Create a task
python watchdog.py create --project my-project --spec "Merge auth docs"

# Check status
python watchdog.py status DOC-001-AUTH-MERGE

# Resume from halt
python watchdog.py resume DOC-001-AUTH-MERGE --decision gemini
```

---

*Agent Hub: Stop babysitting AI. Start shipping.*

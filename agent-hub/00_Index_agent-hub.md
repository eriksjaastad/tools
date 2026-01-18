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
| **[PRD_UNIFIED_AGENT_SYSTEM.md](../PRD_UNIFIED_AGENT_SYSTEM.md)** | ⭐ Current system PRD. Start here. |
| **[00_Index_agent-hub.md](00_Index_agent-hub.md)** | This document. |
| **[TODO.md](TODO.md)** | Implementation checklist and next actions |

---

## 📐 Design & Architecture

| Document | Purpose |
|----------|---------|
| [AGENTS.md](AGENTS.md) | Role definitions: Super Manager, Agent Manager, Floor Manager, Worker |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Technical reference for UAS components |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Guide for environment setup and feature flags |
| [Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md](Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md) | Operational protocol for task management |

---

## 🔍 Code Reviews

| Review | Date | Status |
|--------|------|--------|
| **[CODE_REVIEW_CLAUDE_CODE_WEB_v1.md](CODE_REVIEW_CLAUDE_CODE_WEB_v1.md)** | 2026-01-18 | **REMEDIATING** (Critical fixes in progress) |
| [Legacy Review Archive](Documents/archive/2026-01-unified-agent-system/old-reviews/INDEX.md) | 2025/早期 2026 | Historical peer reviews |

---

## 🗂️ Directory Structure

```
agent-hub/
├── 00_Index_agent-hub.md   # ← You are here
├── AGENTS.md               # Role definitions
├── TODO.md                 # Implementation checklist
├── .env.example            # Template for required environment variables
│
├── src/                    # Implementation
│   ├── listener.py         # Main hub subscription loop
│   ├── hub_client.py       # Wrapper for hub interactions
│   ├── watchdog.py         # State machine & circuit breakers
│   ├── litellm_bridge.py   # Multi-tier routing & fallbacks
│   └── budget_manager.py   # Cost tracking & enforcement
│
├── docs/                   # UAS Documentation
│   ├── API_REFERENCE.md
│   └── CONFIGURATION.md
│
├── benchmarks/             # Performance & cost benchmarking
│
├── Documents/
│   ├── archive/            # Legacy planning & reviews (Jan 2026 Migration)
│   └── FLOOR_MANAGER_STARTUP_PROTOCOL.md
│
└── _handoff/               # Runtime handoff directory
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

# Agent Hub - Floor Manager

Autonomous Floor Manager for multi-agent task pipelines. Orchestrates task execution between Implementer, Local Reviewer, and Judge agents using a Model Context Protocol (MCP) message bus.

## Features

- **Message-Driven**: No polling, real-time agent coordination
- **Git Integration**: Automatic branch creation, checkpointing, and merging
- **Circuit Breakers**: 9 automatic halt conditions (paradox detection, hallucination loops, budget tracking)
- **MCP Native**: Plugs into any MCP-compatible environment
- **V4 Sandbox Draft Pattern**: Local models can safely edit files through a gated sandbox

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Hub                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│   │   Watchdog   │───▶│   Listener   │───▶│  Hub Client  │  │
│   │ State Machine│    │ Message Loop │    │  MCP Comms   │  │
│   └──────────────┘    └──────────────┘    └──────────────┘  │
│          │                   │                    │          │
│          ▼                   ▼                    ▼          │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│   │ Git Manager  │    │  Draft Gate  │    │Worker Client │  │
│   │   Branches   │    │   V4 Safety  │    │ Ollama Calls │  │
│   └──────────────┘    └──────────────┘    └──────────────┘  │
│                              │                               │
│                              ▼                               │
│                       ┌──────────────┐                       │
│                       │   Sandbox    │                       │
│                       │ _handoff/drafts/ │                   │
│                       └──────────────┘                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## V4 Sandbox Draft Pattern

Local models can now edit files safely through a controlled sandbox:

1. **Worker requests draft** - Source file copied to `_handoff/drafts/`
2. **Worker edits draft** - Changes made only in sandbox
3. **Worker submits draft** - Floor Manager reviews the diff
4. **Gate decides** - Accept (apply), Reject (discard), or Escalate (human review)

### Security Layers

| Layer | Protection |
|-------|------------|
| Path Validation | Only `_handoff/drafts/` is writable |
| Content Analysis | Secrets, hardcoded paths, deletion ratio |
| Floor Manager Gate | Diff review, conflict detection |
| Audit Trail | All decisions logged, rollback capable |

See `AGENTS.md` for full V4 documentation.

## Installation

### From agent-skills-library
```bash
agent-skill install floor-manager
```

### Manual Installation
```bash
git clone https://github.com/eriksjaastad/agent-hub
cd agent-hub
pip install -r requirements.txt
```

## Configuration

Set environment variables (required):

| Variable | Description |
|----------|-------------|
| `HUB_SERVER_PATH` | Path to claude-mcp server.js |
| `MCP_SERVER_PATH` | Path to ollama-mcp server.js |
| `HANDOFF_DIR` | Contract/artifact directory (default: `_handoff`) |

## Usage

### Health Check
```bash
python scripts/health_check.py
```

### Start the Floor Manager
```bash
./scripts/start_agent_hub.sh
```

### Run Tests
```bash
pytest tests/                    # All tests
pytest tests/test_sandbox.py     # Sandbox security
pytest tests/test_draft_gate.py  # Draft gate logic
pytest tests/test_e2e.py         # End-to-end pipeline
```

## Circuit Breakers

The Floor Manager automatically halts when:

1. Rebuttal limit exceeded
2. Destructive diff (>50% deletion)
3. Logical paradox (local fail + judge pass)
4. Hallucination loop (same hash failed before)
5. GPT-Energy nitpicking (3+ style-only cycles)
6. Inactivity timeout
7. Budget exceeded
8. Scope creep (>20 files changed)
9. Review cycle limit

## Audit Trail

All transitions and messages logged to `_handoff/transition.ndjson`.

## Documentation

- `AGENTS.md` - V4 workflow and project-specific rules
- `Documents/V4_IMPLEMENTATION_COMPLETE.md` - Implementation details
- `PRD.md` - Product requirements (V3.0)

## Related Projects

- [claude-mcp](../claude-mcp) - MCP hub for agent communication
- [ollama-mcp](../ollama-mcp) - MCP server for local Ollama models

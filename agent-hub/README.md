# Agent Hub - Unified Agent System

Autonomous Floor Manager for multi-agent task pipelines. Orchestrates task execution between Implementer, Local Reviewer, and Judge agents using a Model Context Protocol (MCP) message bus.

**Status:** Production Ready (Jan 2026)
**Version:** 2.0 (Unified Agent System)

## Features

- **Message-Driven**: Real-time agent coordination via MCP message bus
- **Multi-Environment**: Works with Claude CLI, Cursor, and Antigravity
- **Tiered Model Routing**: Local-first with cloud fallback (LiteLLM integration)
- **Git Integration**: Automatic branch creation, checkpointing, and merging
- **Circuit Breakers**: 9 automatic halt conditions (paradox detection, hallucination loops, budget tracking)
- **Budget Management**: Cost tracking, preflight estimates, and ceiling enforcement
- **V4 Sandbox Draft Pattern**: Local models can safely edit files through a gated sandbox
- **Feature Flags**: Gradual rollout of new capabilities

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

### Quick Start

```bash
cp .env.example .env
cp config/routing.yaml.example config/routing.yaml
cp config/feature_flags.yaml.example config/feature_flags.yaml
# Edit files with your paths
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HUB_SERVER_PATH` | Yes | Path to claude-mcp-go binary |
| `MCP_SERVER_PATH` | Yes | Path to ollama-mcp-go binary |
| `HANDOFF_DIR` | No | Contract/artifact directory (default: `_handoff`) |
| `PROJECTS_ROOT` | No | Base path for portable prompts |
| `AGENT_HUB_DRY_RUN` | No | Set to `1` for dry-run mode |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

### Model Routing (`config/routing.yaml`)

Configure tiered model fallback chains:

```yaml
tiers:
  tier_1_free:     # Local Ollama models
  tier_2_cheap:    # Gemini Flash, etc.
  tier_3_premium:  # Claude Sonnet/Opus

fallback_chains:
  default: ["local-fast", "cloud-fast", "cloud-premium"]
  code_generation: ["local-coder", "cloud-fast", "cloud-premium"]
```

### Feature Flags (`config/feature_flags.yaml`)

Enable/disable features via YAML or environment variables:

```yaml
ollama_http_client:
  enabled: false
  env_override: "UAS_OLLAMA_HTTP"

budget_manager:
  enabled: false
  env_override: "UAS_BUDGET_MGR"
```

## Usage

### Health Check
```bash
python scripts/health_check.py
```

### Start the Floor Manager
```bash
./scripts/start_agent_hub.sh
```

### Dispatch a Task
```bash
python scripts/dispatch_task.py --proposal path/to/PROPOSAL_FINAL.md
```

### Monitor Pipeline
```bash
python scripts/monitor_pipeline.py
```

### Generate MCP Config
```bash
python scripts/generate_mcp_config.py > mcp.json
```

### Run Benchmarks
```bash
python scripts/benchmark_phase_1.py
```

### Run Tests
```bash
pytest tests/                    # All tests
pytest tests/test_sandbox.py     # Sandbox security
pytest tests/test_draft_gate.py  # Draft gate logic
pytest tests/test_e2e.py         # End-to-end pipeline
```

## Core Modules

| Module | Purpose |
|--------|---------|
| `watchdog.py` | State machine, transitions, halt conditions |
| `listener.py` | MCP message loop, event handling |
| `hub_client.py` | MCP communication layer |
| `worker_client.py` | Ollama model invocation |
| `git_manager.py` | Branch creation, checkpoints, merge |
| `draft_gate.py` | V4 sandbox review and decision logic |
| `sandbox.py` | Draft file isolation and validation |
| `circuit_breakers.py` | Extended halt conditions (router, SQLite, budget) |
| `budget_manager.py` | Cost tracking and ceiling enforcement |
| `router.py` | Tiered model selection and fallback |
| `litellm_bridge.py` | LiteLLM provider abstraction |
| `message_bus.py` | SQLite-backed message queue |
| `config.py` | Configuration loading and validation |
| `audit_logger.py` | Transition logging to NDJSON |

### Environment Adapters

| Adapter | Environment |
|---------|-------------|
| `environment/claude_cli.py` | Claude Code CLI |
| `environment/cursor.py` | Cursor IDE |
| `environment/antigravity.py` | Google Antigravity |

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
- `Documents/API.md` - API reference for key modules
- `Documents/V4_IMPLEMENTATION_COMPLETE.md` - Implementation details
- `Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md` - Startup procedures
- `Documents/CURSOR_MCP_SETUP.md` - Cursor integration guide
- `PRD.md` - Product requirements (V3.0)

## Related Projects

- [claude-mcp-go](../claude-mcp-go) - MCP hub for agent communication (Go)
- [ollama-mcp-go](../ollama-mcp-go) - MCP server for local Ollama models (Go)

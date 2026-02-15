# Agent Hub - Unified Agent System

Autonomous Floor Manager for multi-agent task pipelines. Dispatches work to local Ollama workers via the Go MCP server.

## Quick Start

```bash
# 1. Pre-flight check — see available roles, models, and tasks
python scripts/handoff_info.py

# 2. Dispatch a task using a ROLE (not a model name)
python scripts/dispatch_task.py <task_file.md> <role> [max_iterations]

# 3. Monitor progress
python scripts/monitor_pipeline.py
```

## Roles

**Always use roles, never raw model names.** Roles are defined in `config/routing.yaml` and resolve to whatever model is currently installed. Models are managed by model-updater and can change at any time.

| Role | What it does | Resolves to |
|------|-------------|-------------|
| `coder` | Code generation, refactoring, implementation | `coding:current` |
| `reviewer` | Code review, debugging, reasoning | `coding:current` |
| `implementer` | Same as coder (alias) | `coding:current` |
| `embedder` | Embedding generation | `embedding:current` |

### Examples

```bash
# Good — use roles
python scripts/dispatch_task.py _handoff/TASK_001.md coder
python scripts/dispatch_task.py _handoff/TASK_002.md reviewer

# Also OK — use Ollama aliases directly
python scripts/dispatch_task.py _handoff/TASK_001.md coding:current

# BAD — never hardcode full model tags (these break when models update)
# python scripts/dispatch_task.py _handoff/TASK_001.md qwen2.5-coder:32b-instruct-q3_K_L
```

## How Model Resolution Works

```
Your input        config/routing.yaml     Ollama alias system       Actual model
─────────── ───→  ─────────────────── ───→ ──────────────────── ───→ ────────────
"coder"           role_aliases:            coding:current            qwen2.5-coder:32b
                    coder: coding:current                            (managed by model-updater)
```

1. **You say:** `coder`
2. **routing.yaml** resolves the role alias to `coding:current`
3. **Ollama** resolves `coding:current` to the actual model (managed weekly by model-updater)
4. **You never need to know** what the actual model is

## Pre-Flight Check

Run `python scripts/handoff_info.py` before starting work. It shows:

- Available roles and what they resolve to
- Installed Ollama models
- Active tasks in `_handoff/`
- Stall reports and system state
- Config validation errors (if any models are missing)

Use `--json` for machine-readable output.

## Task File Format

Tasks live in `_handoff/TASK_*.md`:

```markdown
**Objective:** Implement the login validation function

**Target File:** src/auth.py

**Acceptance Criteria:**
- [ ] Validates email format
- [ ] Returns error for empty password
- [ ] Unit tests pass
```

## Troubleshooting

**"Preflight check failed: Model X not installed"**
→ The model in `config/routing.yaml` isn't in Ollama. Run `ollama list` to see what's available, then update `routing.yaml`.

**"MCP server not found"**
→ Build the Go server: `cd ../ollama-mcp-go && go build -o bin/server ./cmd/server`

**Broken pipe or silent failure**
→ Usually means the model doesn't exist. The preflight check should catch this before it happens.

---

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

Local models edit files safely through a controlled sandbox:

1. **Worker requests draft** - Source file copied to `_handoff/drafts/`
2. **Worker edits draft** - Changes made only in sandbox
3. **Worker submits draft** - Floor Manager reviews the diff
4. **Gate decides** - Accept (apply), Reject (discard), or Escalate (human review)

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HUB_SERVER_PATH` | Yes | Path to claude-mcp-go binary |
| `MCP_SERVER_PATH` | Yes | Path to ollama-mcp-go binary |
| `HANDOFF_DIR` | No | Contract/artifact directory (default: `_handoff`) |
| `PROJECTS_ROOT` | No | Base path for portable prompts |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

### Model Routing (`config/routing.yaml`)

All model configuration lives here. Role aliases, tier definitions, and task routing matrix.

### Key Config Files

| File | Purpose |
|------|---------|
| `config/routing.yaml` | Model tiers, role aliases, task routing matrix |
| `config/models.py` | Centralized model resolution (imported by all scripts) |
| `config/budget.yaml` | Cost ceiling enforcement |

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
| `circuit_breakers.py` | Extended halt conditions |
| `budget_manager.py` | Cost tracking and ceiling enforcement |
| `router.py` | Tiered model selection and fallback |
| `litellm_bridge.py` | LiteLLM provider abstraction |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/handoff_info.py` | Pre-flight report (run first) |
| `scripts/dispatch_task.py` | Send task to worker (main entry point) |
| `scripts/monitor_pipeline.py` | Watch task progress |
| `scripts/health_check.py` | System health verification |
| `scripts/start_agent_hub.sh` | Start the Floor Manager |

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

## Tests

```bash
pytest tests/                              # All tests
pytest tests/test_dispatch_task.py         # Role resolution (unit)
pytest tests/test_routing_validation.py    # Model availability (integration)
pytest tests/test_sandbox.py               # Sandbox security
pytest tests/test_e2e.py                   # End-to-end pipeline
```

## Related Projects

- [claude-mcp-go](../claude-mcp-go) - MCP hub for agent communication (Go)
- [ollama-mcp-go](../ollama-mcp-go) - MCP server for local Ollama models (Go)
- [model-updater](../../model-updater) - Weekly model discovery and alias management

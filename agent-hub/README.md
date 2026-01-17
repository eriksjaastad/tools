# Agent Hub - Floor Manager

Autonomous Floor Manager for multi-agent task pipelines. Orchestrates task execution between Implementer, Local Reviewer, and Judge agents using a Model Context Protocol (MCP) message bus.

## Features
- **Message-Driven**: No polling, real-time agent coordination.
- **Git Integration**: Automatic branch creation, checkpointing, and merging.
- **Circuit Breakers**: Logical paradox detection, hallucination loop prevention, budget tracking.
- **MCP Native**: Plugs into any MCP-compatible environment.

## Skill Installation

### From agent-skills-library
```bash
agent-skill install floor-manager
```

### Manual Installation
```bash
git clone https://github.com/eriksjaastad/agent-hub
cd agent-hub
./scripts/pre_install.sh
./scripts/post_install.sh
```

### Configuration

Set environment variables or edit `skill.json`:

| Variable | Default | Description |
|----------|---------|-------------|
| `HUB_SERVER_PATH` | `/path/to/claude-mcp/dist/server.js` | MCP Hub server |
| `MCP_SERVER_PATH` | `/path/to/ollama-mcp/dist/server.js` | Ollama MCP server |
| `HANDOFF_DIR` | `_handoff` | Contract/artifact directory |
| `FLOOR_MANAGER_ID` | `floor_manager` | Agent identifier |

### Health Check
```bash
python scripts/health_check.py
```

### Start the Floor Manager
```bash
./scripts/start_agent_hub.sh
```

## Audit Trail
Transitions and messages are logged in `_handoff/transition.ndjson`.

# Phase 9: Floor Manager Skill Package

**Goal:** Package the Agent Hub Floor Manager as a reusable skill for `agent-skills-library`. This makes it installable and configurable for other projects.

**Prerequisites:** Phase 8 complete, all MCP messaging working.

---

## The Shift

| Before (Phase 8) | After (Phase 9) |
|------------------|-----------------|
| Agent Hub is a standalone project | Floor Manager is an installable skill |
| Config hardcoded in source files | Config loaded from `skill.json` |
| Paths are absolute | Paths are relative to skill root |
| One Floor Manager per machine | Multiple Floor Managers possible |

---

## Prompt 9.1: Skill Manifest (`skill.json`)

### Context
Every skill in `agent-skills-library` needs a manifest that describes what it does, its dependencies, and configuration options.

### Task
Create `skill.json` in the project root:

```json
{
  "name": "floor-manager",
  "version": "1.0.0",
  "description": "Autonomous Floor Manager for multi-agent task pipelines",
  "author": "Erik Sjaastad",
  "license": "MIT",

  "entry_point": "src/listener.py",
  "main_class": "MessageListener",

  "dependencies": {
    "python": ">=3.10",
    "packages": [
      "pathlib",
      "uuid",
      "threading"
    ],
    "mcp_servers": [
      {
        "name": "claude-mcp",
        "path": "${CLAUDE_MCP_PATH}",
        "required": true
      },
      {
        "name": "ollama-mcp",
        "path": "${OLLAMA_MCP_PATH}",
        "required": true
      }
    ]
  },

  "config": {
    "agent_id": {
      "type": "string",
      "default": "floor_manager",
      "description": "Unique identifier for this Floor Manager instance"
    },
    "hub_path": {
      "type": "path",
      "default": "${HUB_SERVER_PATH}",
      "description": "Path to MCP hub server.js"
    },
    "handoff_dir": {
      "type": "path",
      "default": "_handoff",
      "description": "Directory for contracts and artifacts"
    },
    "heartbeat_interval": {
      "type": "integer",
      "default": 30,
      "description": "Seconds between heartbeats"
    },
    "message_poll_interval": {
      "type": "integer",
      "default": 5,
      "description": "Seconds between message checks"
    }
  },

  "commands": {
    "start": "python -m src.listener",
    "status": "python -m src.watchdog status",
    "setup-task": "python -m src.watchdog setup-task",
    "run-implementer": "python -m src.watchdog run-implementer",
    "run-local-review": "python -m src.watchdog run-local-review"
  },

  "message_types": {
    "receives": ["PROPOSAL_READY", "STOP_TASK", "QUESTION", "VERDICT_SIGNAL"],
    "sends": ["REVIEW_NEEDED", "ANSWER", "HEARTBEAT"]
  },

  "hooks": {
    "pre_install": "scripts/pre_install.sh",
    "post_install": "scripts/post_install.sh",
    "health_check": "scripts/health_check.py"
  }
}
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/skill.json`

---

## Prompt 9.2: Configuration Loader (`config.py`)

### Context
Currently, paths like `HUB_SERVER_PATH` are hardcoded or read from environment variables. The skill needs a unified config system.

### Task
Create `src/config.py`:

```python
"""
Configuration loader for Floor Manager skill.
Reads from skill.json, environment variables, and runtime overrides.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class FloorManagerConfig:
    agent_id: str = "floor_manager"
    hub_path: Path = None
    mcp_server_path: Path = None
    handoff_dir: Path = Path("_handoff")
    heartbeat_interval: int = 30
    message_poll_interval: int = 5

    # Limits
    max_rebuttals: int = 2
    max_review_cycles: int = 5
    cost_ceiling_usd: float = 0.50
    global_timeout_hours: int = 4

    @classmethod
    def load(cls, skill_root: Path = None) -> "FloorManagerConfig":
        """
        Load config with priority:
        1. Environment variables (highest)
        2. skill.json
        3. Defaults (lowest)
        """
        config = cls()

        # Find skill.json
        if skill_root is None:
            skill_root = Path(__file__).parent.parent

        skill_json = skill_root / "skill.json"
        if skill_json.exists():
            with open(skill_json) as f:
                manifest = json.load(f)
                cfg = manifest.get("config", {})

                for key, spec in cfg.items():
                    if hasattr(config, key):
                        setattr(config, key, spec.get("default"))

        # Environment overrides
        config.hub_path = Path(os.getenv(
            "HUB_SERVER_PATH",
            str(config.hub_path or "/Users/eriksjaastad/projects/_tools/claude-mcp/dist/server.js")
        ))
        config.mcp_server_path = Path(os.getenv(
            "MCP_SERVER_PATH",
            str(config.mcp_server_path or "/Users/eriksjaastad/projects/_tools/ollama-mcp/dist/server.js")
        ))
        config.handoff_dir = Path(os.getenv("HANDOFF_DIR", str(config.handoff_dir)))
        config.agent_id = os.getenv("FLOOR_MANAGER_ID", config.agent_id)

        return config

    def validate(self) -> list[str]:
        """Returns list of validation errors, empty if valid."""
        errors = []

        if not self.hub_path.exists():
            errors.append(f"Hub server not found: {self.hub_path}")
        if not self.mcp_server_path.exists():
            errors.append(f"MCP server not found: {self.mcp_server_path}")

        return errors


# Global config instance
_config: Optional[FloorManagerConfig] = None

def get_config() -> FloorManagerConfig:
    global _config
    if _config is None:
        _config = FloorManagerConfig.load()
    return _config
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/src/config.py`

---

## Prompt 9.3: Update Imports to Use Config

### Context
Multiple files currently import `HUB_SERVER_PATH` and `MCP_SERVER_PATH` directly. They should use the config system.

### Task
Update the following files to use `get_config()`:

#### `src/watchdog.py`
```python
# Before:
MCP_SERVER_PATH = Path(os.getenv("MCP_SERVER_PATH", "/Users/eriksjaastad/..."))
HUB_SERVER_PATH = Path(os.getenv("HUB_SERVER_PATH", "/Users/eriksjaastad/..."))

# After:
from .config import get_config

def main(argv):
    config = get_config()
    errors = config.validate()
    if errors:
        for e in errors:
            print(f"Config error: {e}")
        sys.exit(1)

    # Use config.hub_path, config.mcp_server_path, etc.
```

#### `src/listener.py`
```python
# Before:
from .watchdog import HUB_SERVER_PATH

# After:
from .config import get_config

def main():
    config = get_config()
    listener = MessageListener(config.agent_id, config.hub_path)
    # ...
```

### Files to Modify
- `/Users/eriksjaastad/projects/_tools/agent-hub/src/watchdog.py`
- `/Users/eriksjaastad/projects/_tools/agent-hub/src/listener.py`

---

## Prompt 9.4: Install Scripts

### Context
When someone installs this skill, we need to verify dependencies and set up the environment.

### Task
Create installation scripts:

#### `scripts/pre_install.sh`
```bash
#!/bin/bash
# Pre-installation checks for Floor Manager skill

set -e

echo "=== Floor Manager Pre-Install Check ==="

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ $(echo "$PYTHON_VERSION < 3.10" | bc -l) -eq 1 ]]; then
    echo "Error: Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi
echo "Python: OK ($PYTHON_VERSION)"

# Check for required MCP servers
if [ -z "$HUB_SERVER_PATH" ]; then
    echo "Warning: HUB_SERVER_PATH not set"
fi

if [ -z "$MCP_SERVER_PATH" ]; then
    echo "Warning: MCP_SERVER_PATH not set"
fi

echo "Pre-install checks passed."
```

#### `scripts/post_install.sh`
```bash
#!/bin/bash
# Post-installation setup for Floor Manager skill

set -e

echo "=== Floor Manager Post-Install Setup ==="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Create handoff directory
mkdir -p "$PROJECT_ROOT/_handoff"

# Make scripts executable
chmod +x "$PROJECT_ROOT/scripts/"*.sh

echo "Post-install setup complete."
echo ""
echo "To start the Floor Manager:"
echo "  cd $PROJECT_ROOT && ./scripts/start_agent_hub.sh"
```

#### `scripts/health_check.py`
```python
#!/usr/bin/env python3
"""Health check for Floor Manager skill."""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.mcp_client import MCPClient
from src.hub_client import HubClient

def main():
    config = get_config()

    print("=== Floor Manager Health Check ===")

    # Check config
    errors = config.validate()
    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return 1
    print("[OK] Configuration valid")

    # Check hub connection
    try:
        with MCPClient(config.hub_path) as mcp:
            hub = HubClient(mcp)
            if hub.connect("health_check"):
                print("[OK] MCP Hub connection")
            else:
                print("[FAIL] MCP Hub connection")
                return 1
    except Exception as e:
        print(f"[FAIL] MCP Hub: {e}")
        return 1

    # Check Ollama connection
    try:
        with MCPClient(config.mcp_server_path) as mcp:
            # Just verify we can connect
            print("[OK] Ollama MCP connection")
    except Exception as e:
        print(f"[FAIL] Ollama MCP: {e}")
        return 1

    print("\nAll checks passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### File Locations
- `/Users/eriksjaastad/projects/_tools/agent-hub/scripts/pre_install.sh`
- `/Users/eriksjaastad/projects/_tools/agent-hub/scripts/post_install.sh`
- `/Users/eriksjaastad/projects/_tools/agent-hub/scripts/health_check.py`

---

## Prompt 9.5: Skill Registry Entry

### Context
The `agent-skills-library` maintains a registry of available skills. Floor Manager needs an entry.

### Task
Create the registry entry file that can be copied to `agent-skills-library`:

```json
{
  "floor-manager": {
    "repo": "https://github.com/eriksjaastad/agent-hub",
    "path": "/",
    "version": "1.0.0",
    "category": "orchestration",
    "tags": ["multi-agent", "pipeline", "mcp", "automation"],
    "description": "Autonomous Floor Manager that orchestrates task pipelines with Implementer, Local Reviewer, and Judge agents.",
    "requires": ["claude-mcp", "ollama-mcp"],
    "compatible_with": ["claude-code", "antigravity", "cursor"]
  }
}
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/registry-entry.json`

---

## Prompt 9.6: Update README for Skill Installation

### Context
The README needs installation instructions for using this as a skill.

### Task
Add a "Skill Installation" section to the README:

```markdown
## Installation as a Skill

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
```

### File Location
Modify: `/Users/eriksjaastad/projects/_tools/agent-hub/README.md`

---

## Execution Order

1. **9.1** - Create `skill.json` manifest
2. **9.2** - Create `config.py` loader
3. **9.3** - Update imports in watchdog.py and listener.py
4. **9.4** - Create install scripts
5. **9.5** - Create registry entry
6. **9.6** - Update README

---

## Success Criteria

Phase 9 is DONE when:
- [x] `skill.json` exists and is valid JSON
- [x] `config.py` loads config from manifest + env vars
- [x] `watchdog.py` and `listener.py` use `get_config()`
- [x] `scripts/health_check.py` passes all checks
- [x] `pre_install.sh` and `post_install.sh` run without errors
- [x] README has skill installation instructions
- [x] Floor Manager can start from fresh clone with only env vars set

---

## What This Enables

After Phase 9:
1. **Portability**: Clone → Set env vars → Run
2. **Multi-instance**: Run multiple Floor Managers with different `agent_id`
3. **Discoverability**: Listed in agent-skills-library registry
4. **Validation**: Health check catches config issues before runtime

---

*Phase 9 makes Floor Manager a proper citizen of the agent-skills-library ecosystem.*

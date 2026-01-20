# Agent Hub API Reference

> Quick reference for key classes and functions. For architecture details, see `AGENTS.md`.

---

## Circuit Breakers (`src/circuit_breakers.py`)

Extended halt conditions beyond the core 9 triggers.

```python
from src.circuit_breakers import get_circuit_breaker, HaltReason

breaker = get_circuit_breaker()

# Record failures
breaker.record_router_failure("All models exhausted")
breaker.record_sqlite_failure("Connection refused")
breaker.record_ollama_failure("Timeout")

# Record successes (resets counters)
breaker.record_router_success()

# Check status
if breaker.should_halt():
    print("System halted")

status = breaker.get_status()
# Returns: {is_halted, halt_reason, router_failures, sqlite_failures, ...}

# Reset after manual intervention
breaker.reset()
```

### HaltReason Enum

| Value | Trigger |
|-------|---------|
| `ROUTER_EXHAUSTED` | All models in fallback chain failed |
| `SQLITE_FAILURE` | Message bus connection errors |
| `BUDGET_EXCEEDED` | Cost ceiling reached |
| `OLLAMA_UNAVAILABLE` | Local model server down |
| `MODEL_COOLDOWN_CASCADE` | All models in cooldown |
| `MESSAGE_BUS_CORRUPT` | Unrecoverable bus state |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `UAS_ROUTER_FAILURE_LIMIT` | 5 | Router failures before halt |
| `UAS_SQLITE_FAILURE_LIMIT` | 3 | SQLite failures before halt |
| `UAS_OLLAMA_FAILURE_LIMIT` | 3 | Ollama failures before degraded mode |
| `UAS_HALT_FILE` | `HALT.md` | Halt file location |

---

## Configuration (`src/config.py`)

```python
from src.config import get_config, get_hub_path, get_mcp_path

config = get_config()

# Access settings
print(config.agent_id)           # "floor_manager"
print(config.handoff_dir)        # Path("_handoff")
print(config.max_rebuttals)      # 2
print(config.cost_ceiling_usd)   # 0.50
print(config.global_timeout_hours)  # 4

# Get validated paths (raises ConfigError if invalid)
hub_path = get_hub_path()
mcp_path = get_mcp_path()

# Validate configuration
errors = config.validate()
if errors:
    print(f"Config errors: {errors}")
```

### FloorManagerConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent_id` | str | `"floor_manager"` | Agent identifier |
| `hub_path` | Path | None | Path to claude-mcp-go binary |
| `mcp_server_path` | Path | None | Path to ollama-mcp-go binary |
| `handoff_dir` | Path | `_handoff` | Contract directory |
| `heartbeat_interval` | int | 30 | Seconds between heartbeats |
| `message_poll_interval` | int | 5 | Seconds between message checks |
| `max_rebuttals` | int | 2 | Max review cycles |
| `max_review_cycles` | int | 5 | Total review limit |
| `cost_ceiling_usd` | float | 0.50 | Budget ceiling |
| `global_timeout_hours` | int | 4 | Max task duration |

---

## Draft Gate (`src/draft_gate.py`)

Reviews worker draft submissions and decides whether to apply.

```python
from src.draft_gate import DraftGate, GateDecision

gate = DraftGate(handoff_dir=Path("_handoff"))

# Process a draft submission
result = gate.process_draft(
    draft_path=Path("_handoff/drafts/file.py"),
    original_path=Path("src/file.py"),
    submission_metadata={"worker": "qwen", "task_id": "123"}
)

# Check decision
if result.decision == GateDecision.ACCEPT:
    print(f"Applied: {result.diff_summary}")
elif result.decision == GateDecision.REJECT:
    print(f"Rejected: {result.reason}")
elif result.decision == GateDecision.ESCALATE:
    print(f"Needs review: {result.reason}")
```

### GateDecision Enum

| Value | Meaning |
|-------|---------|
| `ACCEPT` | All checks passed, diff applied |
| `REJECT` | Security violation, draft discarded |
| `ESCALATE` | Large change or uncertainty, needs human review |

---

## Sandbox (`src/sandbox.py`)

Isolates worker file edits to a safe directory.

```python
from src.sandbox import Sandbox

sandbox = Sandbox(base_dir=Path("_handoff/drafts"))

# Validate a path is within sandbox
if sandbox.is_safe_path(path):
    # OK to write
    pass

# Get draft path for a source file
draft_path = sandbox.get_draft_path(Path("src/module.py"))
# Returns: _handoff/drafts/src/module.py

# Copy source to sandbox for editing
sandbox.create_draft(source=Path("src/module.py"))

# Apply approved draft back to source
sandbox.apply_draft(draft=draft_path, target=Path("src/module.py"))

# Clean up drafts
sandbox.cleanup()
```

---

## Git Manager (`src/git_manager.py`)

Handles branch operations, checkpoints, and merges.

```python
from src.git_manager import GitManager

git = GitManager(repo_path=Path("."))

# Create task branch
git.create_task_branch("feature-123")

# Create checkpoint (lightweight tag)
git.checkpoint("after-phase-1")

# Rollback to checkpoint
git.rollback("after-phase-1")

# Merge to main
git.merge_to_main()
```

---

## Feature Flags (`src/utils/feature_flags.py`)

Runtime feature toggling via YAML or environment.

```python
from src.utils.feature_flags import is_feature_enabled, get_all_flags

# Check if feature is enabled
if is_feature_enabled("budget_manager"):
    # Use budget tracking
    pass

# Get all flags
flags = get_all_flags()
# Returns: {"ollama_http_client": False, "budget_manager": True, ...}
```

### Enabling Features

1. **YAML:** Set `enabled: true` in `config/feature_flags.yaml`
2. **Environment:** Set the env_override variable (e.g., `UAS_BUDGET_MGR=1`)

Environment variables take precedence over YAML.

---

## Message Types

| Message | Direction | Purpose |
|---------|-----------|---------|
| `PROPOSAL_READY` | to Floor Manager | New task to implement |
| `REVIEW_NEEDED` | to Judge | Request external review |
| `DRAFT_READY` | to Floor Manager | Worker submitted a draft |
| `DRAFT_ACCEPTED` | to Worker | Draft applied successfully |
| `DRAFT_REJECTED` | to Worker | Draft failed safety checks |
| `DRAFT_ESCALATED` | to Conductor | Needs human review |
| `STOP_TASK` | broadcast | Halt current task |

---

## Quick Start Example

```python
from src.config import get_config
from src.circuit_breakers import get_circuit_breaker
from src.draft_gate import DraftGate
from src.git_manager import GitManager

# Initialize
config = get_config()
errors = config.validate()
if errors:
    raise RuntimeError(f"Invalid config: {errors}")

breaker = get_circuit_breaker()
gate = DraftGate(handoff_dir=config.handoff_dir)
git = GitManager()

# Check system health
if breaker.should_halt():
    print("System halted - check HALT.md")
    exit(1)

# Ready to process tasks
print("Agent Hub ready")
```

# UAS API Reference

> Unified Agent System - Complete API Documentation
> Version: 1.0.0

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Components](#core-components)
   - [HubClient](#hubclient)
   - [WorkerClient](#workerclient)
   - [BudgetManager](#budgetmanager)
   - [LiteLLMBridge](#litellmbridge)
3. [Communication](#communication)
   - [Message Bus](#message-bus)
   - [State Adapter](#state-adapter)
4. [Reliability](#reliability)
   - [Circuit Breakers](#circuit-breakers)
   - [Graceful Degradation](#graceful-degradation)
5. [Monitoring](#monitoring)
   - [Audit Logger](#audit-logger)
   - [Dashboard](#dashboard)
6. [Environment Variables](#environment-variables)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

```bash
cd agent-hub
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Basic Usage

```python
from src.hub_client import HubClient
from src.budget_manager import get_budget_manager

# Check budget before expensive operations
budget = get_budget_manager()
can_afford, reason = budget.can_afford("cloud-fast", 1000, 500)

if can_afford:
    # Use HubClient for orchestration
    hub = HubClient()
    # ... your code here
```

---

## Core Components

### HubClient

The main orchestration client for managing agent workflows.

**Location:** `src/hub_client.py`

**Constructor:**
```python
HubClient(mcp_client=None)
```

**Key Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `spawn_worker(task, model)` | Spawn a worker agent | `WorkerResult` |
| `ask_parent(question, run_id)` | Ask parent for clarification | `str` (message_id) |
| `check_answer(message_id)` | Check if answer available | `str | None` |
| `get_pending_questions(run_id)` | Get unanswered questions | `List[dict]` |
| `reply_to_worker(message_id, answer)` | Answer a worker's question | `bool` |

**Example:**
```python
hub = HubClient()

# Spawn a worker
result = hub.spawn_worker(
    task="Implement the login feature",
    model="local-coder"
)

# Check for pending questions
questions = hub.get_pending_questions()
for q in questions:
    print(f"Worker {q['subagent_id']} asks: {q['question']}")
```

---

### WorkerClient

Client for worker agents to communicate with their parent.

**Location:** `src/worker_client.py`

**Constructor:**
```python
WorkerClient(mcp_client=None)
```

**Key Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `ask_for_clarification(question, timeout, poll_interval)` | Ask parent and wait for answer | `str | None` |
| `report_progress(status)` | Report current progress | `None` |

**Example:**
```python
worker = WorkerClient()

# Need clarification? Ask parent
answer = worker.ask_for_clarification(
    "Should I use REST or GraphQL?",
    timeout_seconds=300,
    poll_interval=5.0
)

if answer:
    print(f"Parent says: {answer}")
else:
    print("No response, using default approach")
```

---

### BudgetManager

Track and enforce cost limits for model calls.

**Location:** `src/budget_manager.py`

**Constructor:**
```python
BudgetManager(
    budget_path: Path | str | None = None,
    session_id: str | None = None,
    session_limit: float | None = None,
    daily_limit: float | None = None,
)
```

**Key Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `can_afford(model, tokens_in, tokens_out)` | Pre-flight budget check | `tuple[bool, str]` |
| `record_cost(model, tokens_in, tokens_out, task_type, was_fallback)` | Record actual cost | `float` |
| `get_status()` | Get current budget status | `dict` |
| `request_override(reason, duration_minutes)` | Request temporary override | `None` |
| `clear_override()` | Clear active override | `None` |
| `is_override_active()` | Check if override is active | `bool` |

**Example:**
```python
from src.budget_manager import get_budget_manager

budget = get_budget_manager()

# Check before calling
can_afford, reason = budget.can_afford("cloud-premium", 5000, 2000)
if not can_afford:
    print(f"Cannot afford: {reason}")
    return

# After successful call, record cost
cost = budget.record_cost(
    model="cloud-premium",
    tokens_in=5000,
    tokens_out=2000,
    task_type="code",
    was_fallback=True
)
print(f"Cost: ${cost:.4f}")
```

---

### LiteLLMBridge

Model routing with automatic fallbacks.

**Location:** `src/litellm_bridge.py`

**Constructor:**
```python
LiteLLMBridge(config: dict | None = None)
```

**Key Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `chat(messages, task_type, preferred_model, require_budget_check)` | Send chat with fallback | `dict` |

**Raises:**
- `BudgetExceededError`: When no affordable models available

**Example:**
```python
from src.litellm_bridge import LiteLLMBridge

bridge = LiteLLMBridge()

response = bridge.chat(
    messages=[{"role": "user", "content": "Write a hello world"}],
    task_type="code",
    preferred_model="local-coder"
)

print(response["content"])
```

---

## Communication

### Message Bus

SQLite-based message storage for agent communication.

**Location:** `src/message_bus.py`

**Constructor:**
```python
MessageBus(db_path: str | Path | None = None)
```

**Key Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `ask_parent(run_id, subagent_id, question)` | Worker asks question | `str` (message_id) |
| `reply_to_worker(message_id, answer)` | Parent answers | `bool` |
| `check_answer(message_id)` | Check for answer | `str | None` |
| `get_pending_questions(run_id)` | Get unanswered questions | `list[dict]` |
| `update_agent_heartbeat(agent_id, progress)` | Update heartbeat | `None` |

---

### State Adapter

Abstraction layer for state storage backends.

**Location:** `src/state_adapter.py`

**Usage:**
```python
from src.state_adapter import get_state_adapter

# Automatically uses SQLite if UAS_SQLITE_BUS=1
adapter = get_state_adapter()

msg_id = adapter.ask_parent("run-1", "worker-1", "Question?")
```

---

## Reliability

### Circuit Breakers

Automatic halt on repeated failures.

**Location:** `src/circuit_breakers.py`

**Key Methods:**

| Method | Description |
|--------|-------------|
| `record_router_failure(error)` | Record routing failure |
| `record_sqlite_failure(error)` | Record SQLite failure |
| `record_ollama_failure(error)` | Record Ollama failure |
| `should_halt()` | Check if halted |
| `reset()` | Reset after manual intervention |

**Thresholds (Environment Variables):**
- `UAS_ROUTER_FAILURE_LIMIT`: Default 5
- `UAS_SQLITE_FAILURE_LIMIT`: Default 3
- `UAS_OLLAMA_FAILURE_LIMIT`: Default 3

---

### Graceful Degradation

Handle Ollama unavailability with cloud fallback.

**Location:** `src/degradation.py`

**Key Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `check_ollama_health()` | Check if Ollama responding | `bool` |
| `is_degraded()` | Check if in Low Power Mode | `bool` |
| `get_best_available_model(preferred)` | Get model considering degradation | `str` |

**Example:**
```python
from src.degradation import get_degradation_manager

degradation = get_degradation_manager()

if degradation.is_degraded():
    print("Running in Low Power Mode - using cloud fallback")

model = degradation.get_best_available_model("local-coder")
# Returns "cloud-fast" if degraded, "local-coder" if healthy
```

---

## Monitoring

### Audit Logger

Comprehensive event logging in NDJSON format.

**Location:** `src/audit_logger.py`

**Key Methods:**

| Method | Description |
|--------|-------------|
| `log(event_type, source, data)` | Log an event |
| `log_model_call(model, tokens_in, tokens_out, latency_ms, success, ...)` | Log model call |
| `get_events(event_type, source, since, limit)` | Query events |
| `get_session_summary()` | Get session stats |

**Event Types:**
- `MODEL_CALL_START`, `MODEL_CALL_SUCCESS`, `MODEL_CALL_FAILURE`
- `CIRCUIT_BREAKER_FAILURE`, `CIRCUIT_BREAKER_HALT`
- `DEGRADATION_ENTERED`, `DEGRADATION_RECOVERED`
- `BUDGET_CHECK_PASSED`, `BUDGET_CHECK_FAILED`
- `QUESTION_ASKED`, `QUESTION_ANSWERED`

---

### Dashboard

Terminal TUI for monitoring.

**Location:** `src/dashboard.py`

**Usage:**
```bash
python -m src.dashboard
```

**Features:**
- Active agents table
- Pending questions
- Budget status (color-coded)
- Cloud escapes list
- Interactive question answering

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| **Feature Flags** | | |
| `UAS_OLLAMA_HTTP` | `0` | Use HTTP client for Ollama |
| `UAS_PERSISTENT_MCP` | `0` | Keep MCP connections alive |
| `UAS_ADAPTIVE_POLL` | `0` | Use adaptive polling |
| `UAS_LITELLM_ROUTING` | `0` | Use LiteLLM for routing |
| `UAS_SQLITE_BUS` | `0` | Use SQLite message bus |
| **Budget** | | |
| `UAS_SESSION_BUDGET` | `1.00` | Session limit in USD |
| `UAS_DAILY_BUDGET` | `5.00` | Daily limit in USD |
| `UAS_DISABLE_BUDGET_CHECK` | `0` | Bypass budget checks |
| **Circuit Breakers** | | |
| `UAS_ROUTER_FAILURE_LIMIT` | `5` | Router failures before halt |
| `UAS_SQLITE_FAILURE_LIMIT` | `3` | SQLite failures before halt |
| `UAS_OLLAMA_FAILURE_LIMIT` | `3` | Ollama failures before degraded |
| `UAS_HALT_FILE` | `ERIK_HALT.md` | Halt file location |
| **Ollama** | | |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `UAS_HEALTH_CHECK_TIMEOUT` | `5.0` | Health check timeout (seconds) |
| **Logging** | | |
| `UAS_AUDIT_LOG` | `data/audit.ndjson` | Audit log location |

---

## Troubleshooting

### Budget Exceeded

**Symptom:** `BudgetExceededError` raised

**Solutions:**
1. Check current status: `budget.get_status()`
2. Request override: `budget.request_override("reason", duration_minutes=60)`
3. Increase limits via environment variables
4. Use local models (free)

### Ollama Unavailable

**Symptom:** System enters "Low Power Mode"

**Check:**
```python
from src.degradation import get_degradation_manager
print(get_degradation_manager().get_status())
```

**Solutions:**
1. Start Ollama: `ollama serve`
2. Check URL: `curl http://localhost:11434/api/tags`
3. System will auto-recover when Ollama responds

### Circuit Breaker Triggered

**Symptom:** `ERIK_HALT.md` file created

**Solutions:**
1. Read halt file for context
2. Fix underlying issue
3. Reset: `get_circuit_breaker().reset()`
4. Delete halt file

### Messages Not Delivered

**Symptom:** Workers not receiving answers

**Check:**
```python
from src.state_adapter import get_state_adapter
adapter = get_state_adapter()
print(adapter.get_pending_questions("run-id"))
```

**Solutions:**
1. Ensure `UAS_SQLITE_BUS=1` is set
2. Check database path permissions
3. Verify run_id matches between parent and worker

---

*Generated for UAS v1.0.0*

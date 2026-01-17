# Remediation Prompt 3: agent-hub MEDIUM Priority Fixes

**Source:** CODE_REVIEW_CLAUDE_v1.md
**Priority:** MEDIUM (Address Soon)
**Estimated Scope:** 4 files + new test file

---

## Context

Code review identified three MEDIUM priority issues that improve reliability and testability.

---

## Task 1: Remove Hardcoded Paths

**Files to modify:**
- `src/config.py` - Lines 44-45
- `scripts/start_agent_hub.sh` - Line 8
- `tests/test_mcp_client.py` - Line 85

**What to do:**

**config.py:**
```python
# BEFORE
default_hub_path = "/Users/eriksjaastad/projects/_tools/claude-mcp/dist/server.js"
default_mcp_path = "/Users/eriksjaastad/projects/_tools/ollama-mcp/dist/server.js"

# AFTER
default_hub_path = None  # Must be set via HUB_SERVER_PATH env var
default_mcp_path = None  # Must be set via MCP_SERVER_PATH env var
```

Then add validation that raises a clear error if paths aren't configured:
```python
def get_hub_path() -> str:
    path = os.environ.get("HUB_SERVER_PATH")
    if not path:
        raise ConfigError("HUB_SERVER_PATH environment variable must be set")
    return path
```

**start_agent_hub.sh:**
```bash
# BEFORE
HUB_PATH="${HUB_SERVER_PATH:-/Users/eriksjaastad/projects/_tools/claude-mcp/dist/server.js}"

# AFTER
HUB_PATH="${HUB_SERVER_PATH:?Error: HUB_SERVER_PATH must be set}"
```

**tests/test_mcp_client.py:**
```python
# BEFORE
SERVER_PATH = Path("/Users/eriksjaastad/projects/_tools/ollama-mcp/dist/server.js")

# AFTER
SERVER_PATH = Path(os.environ.get("OLLAMA_MCP_PATH", ""))

@pytest.fixture
def skip_if_no_server():
    if not SERVER_PATH.exists():
        pytest.skip("OLLAMA_MCP_PATH not set or server not found")
```

**Why:** Hardcoded paths break portability and fail on other machines.

---

## Task 2: Add Cost Tracking Tests

**File to create:** `tests/test_cost_tracking.py`

**What to test:**

The `update_cost()` function in watchdog.py is currently untested. Add tests for:

```python
import pytest
from src.watchdog import update_cost, get_current_cost, COST_CEILING

def test_update_cost_accumulates():
    """Cost should accumulate across calls."""
    initial = get_current_cost()
    update_cost(0.10)
    update_cost(0.05)
    assert get_current_cost() == initial + 0.15

def test_cost_ceiling_triggers_halt():
    """Exceeding cost ceiling should trigger circuit breaker."""
    # This may need to mock the state or use a test fixture
    pass

def test_cost_persists_across_restarts():
    """Cost tracking should persist in state file."""
    pass
```

**Why:** Cost tracking is a circuit breaker trigger - if it fails silently, runaway costs could occur.

---

## Task 3: Add Token Pre-flight Check

**File to modify:** `src/worker_client.py`

**What to do:**

Before sending content to the LLM, estimate token count and warn/truncate if too large:

```python
def estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ~ 4 characters."""
    return len(text) // 4

MAX_INPUT_TOKENS = 100000  # Adjust based on model limits

def prepare_prompt(content: str) -> str:
    """Prepare prompt with token safety check."""
    estimated = estimate_tokens(content)
    if estimated > MAX_INPUT_TOKENS:
        logger.warning(f"Content exceeds token limit ({estimated} > {MAX_INPUT_TOKENS}), truncating")
        # Truncate to approximate limit
        max_chars = MAX_INPUT_TOKENS * 4
        content = content[:max_chars] + "\n\n[TRUNCATED - content exceeded token limit]"
    return content
```

**Why:** Sending oversized content to LLMs wastes money and can cause failures.

---

## Acceptance Criteria

- [ ] No `/Users/` or `/home/` paths in source files (grep returns empty)
- [ ] Config raises clear error when required env vars missing
- [ ] Integration tests skip gracefully when server paths not configured
- [ ] `tests/test_cost_tracking.py` exists with at least 3 test cases
- [ ] `worker_client.py` has token estimation before LLM calls
- [ ] All existing tests still pass

---

## Verification Commands

```bash
# Check for hardcoded paths
grep -r '/Users/\|/home/' src/ scripts/ tests/

# Run new cost tracking tests
pytest tests/test_cost_tracking.py -v

# Run all tests
pytest tests/

# Test missing env var behavior
unset HUB_SERVER_PATH && python -c "from src.config import get_hub_path; get_hub_path()"
# Should raise ConfigError
```

---

*This prompt addresses items M1, T1 (cost tracking gap), and S1 from CODE_REVIEW_CLAUDE_v1.md*

# _tools - Master TODO

> **Purpose:** Wire up MCP infrastructure and fix broken references
> **Assignee:** Floor Manager
> **Created:** 2026-01-19

---

## Summary

Go MCP servers are built but not connected. 18+ files reference non-existent Node.js paths. Tests will fail until paths are fixed.

---

## Task 1: Fix generate_mcp_config.py

**File:** `agent-hub/scripts/generate_mcp_config.py`

**Problem:** Lines 24-28 reference non-existent Node.js servers.

**Fix:** Replace MCP_SERVERS dict:

```python
MCP_SERVERS = {
    "ollama-mcp": {
        "command": str(Path.home() / "projects" / "_tools" / "ollama-mcp-go" / "bin" / "server"),
        "args": [],
        "env": {"SANDBOX_ROOT": str(Path.home() / "projects")},
        "description": "Ollama MCP - local model inference via Go server",
    },
    "claude-mcp": {
        "command": str(Path.home() / "projects" / "_tools" / "claude-mcp-go" / "bin" / "claude-mcp-go"),
        "args": [],
        "description": "Claude MCP - hub messaging and review tools",
    },
}
```

**Test:** `python scripts/generate_mcp_config.py --list` should show both servers with correct paths.

---

## Task 2: Fix test_mcp_communication.py

**File:** `agent-hub/scripts/test_mcp_communication.py`

**Problems:**
1. Lines 118-119: Wrong directory paths
2. Lines 134, 204: Uses `node dist/server.js` instead of Go binaries
3. Lines 101-109: Expected tool names don't match Go server tools

**Fix:**

1. Update paths (lines 118-119):
```python
claude_mcp_bin = os.path.join(root_dir, "claude-mcp-go", "bin", "claude-mcp-go")
ollama_mcp_bin = os.path.join(root_dir, "ollama-mcp-go", "bin", "server")
```

2. Update MCPServerProcess calls to use binaries directly:
```python
claude_server = MCPServerProcess([claude_mcp_bin], root_dir, args.verbose)
ollama_server = MCPServerProcess([ollama_mcp_bin], root_dir, args.verbose)
```

3. Update expected tool lists:
```python
EXPECTED_CLAUDE_TOOLS = [
    "claude_health",
    "claude_judge_review",
    "claude_resolve_conflict",
    "claude_security_audit",
    "claude_validate_proposal",
    "hub_connect",
    "hub_send_message",
    "hub_receive_messages",
    "hub_heartbeat",
    "hub_send_answer",
    "hub_get_all_messages",
    "request_draft_review",
    "submit_review_verdict",
]

EXPECTED_OLLAMA_TOOLS = [
    "ollama_run",
    "ollama_run_many",
    "draft_read",
    "draft_write",
    "draft_patch",
    "draft_list",
    "agent_loop",
]
```

**Test:** `python scripts/test_mcp_communication.py` should pass all checks.

---

## Task 3: Fix .env.example

**File:** `agent-hub/.env.example`

**Problem:** References Node.js paths.

**Fix:**
```
# MCP Server Paths (Go binaries)
HUB_SERVER_PATH=/Users/eriksjaastad/projects/_tools/claude-mcp-go/bin/claude-mcp-go
MCP_SERVER_PATH=/Users/eriksjaastad/projects/_tools/ollama-mcp-go/bin/server

# Optional
HANDOFF_DIR=_handoff
SANDBOX_ROOT=/Users/eriksjaastad/projects
LOG_LEVEL=INFO
```

---

## Task 4: Update watchdog.py MCP paths

**File:** `agent-hub/src/watchdog.py`

**Problem:** Lines with `HUB_SERVER_PATH` and `MCP_SERVER_PATH` may use wrong defaults.

**Fix:** Ensure environment variables or defaults point to Go binaries. Check lines 58, 358, 373, 385, 596, 724.

---

## Task 5: Update dispatch_task.py

**File:** `agent-hub/scripts/dispatch_task.py`

**Problem:** Line 15 hardcodes path to `ollama-mcp-go/bin/server` - verify this is correct.

**Check:** Path should be `root_dir / "ollama-mcp-go" / "bin" / "server"` (already correct).

---

## Task 6: Update documentation

**Files to update:**
- `agent-hub/Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md` - Fix tool names
- `agent-hub/Documents/CURSOR_MCP_SETUP.md` - Update paths
- `agent-hub/Documents/API.md` - Update tool references
- `agent-hub/AGENTS.md` - Update MCP references
- `agent-hub/README.md` - Update setup instructions

**Tool name mappings:**
| Old (Node.js) | New (Go) |
|---------------|----------|
| `ollama_request_draft` | `draft_read` |
| `ollama_write_draft` | `draft_write` |
| `ollama_read_draft` | `draft_read` |
| `ollama_submit_draft` | N/A (use draft_write + review flow) |
| `ollama_agent_run` | `agent_loop` |
| `ollama_list_models` | N/A (call ollama CLI directly) |

---

## Task 7: Delete HALT.md

**File:** `agent-hub/HALT.md`

**Action:** Delete this file to unblock budget.

---

## Task 8: Create .env from example

**Action:** Copy `agent-hub/.env.example` to `agent-hub/.env` with correct paths.

---

## Task 9: Write E2E pipeline test

**File:** `agent-hub/tests/test_e2e_mcp_pipeline.py`

**Purpose:** Prove the full pipeline works.

```python
"""
E2E test: Verify MCP servers can communicate.
Run: pytest tests/test_e2e_mcp_pipeline.py -v
"""
import subprocess
import json
import time
import os
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
OLLAMA_BIN = ROOT / "ollama-mcp-go" / "bin" / "server"
CLAUDE_BIN = ROOT / "claude-mcp-go" / "bin" / "claude-mcp-go"

@pytest.fixture
def ollama_server():
    """Start ollama-mcp-go server."""
    proc = subprocess.Popen(
        [str(OLLAMA_BIN)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "SANDBOX_ROOT": str(ROOT)}
    )
    time.sleep(1)
    yield proc
    proc.terminate()
    proc.wait()

@pytest.fixture
def claude_server():
    """Start claude-mcp-go server."""
    proc = subprocess.Popen(
        [str(CLAUDE_BIN)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "HUB_STATE_DIR": str(ROOT / "agent-hub" / "_handoff")}
    )
    time.sleep(1)
    yield proc
    proc.terminate()
    proc.wait()

def mcp_call(proc, method, params=None):
    """Send MCP request and get response."""
    request = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        request["params"] = params
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())

class TestOllamaMCP:
    def test_server_starts(self, ollama_server):
        assert ollama_server.poll() is None

    def test_tools_list(self, ollama_server):
        resp = mcp_call(ollama_server, "tools/list")
        tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
        assert "ollama_run" in tools
        assert "agent_loop" in tools
        assert "draft_read" in tools
        assert "draft_write" in tools

class TestClaudeMCP:
    def test_server_starts(self, claude_server):
        assert claude_server.poll() is None

    def test_tools_list(self, claude_server):
        resp = mcp_call(claude_server, "tools/list")
        tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
        assert "hub_connect" in tools
        assert "hub_send_message" in tools
        assert "request_draft_review" in tools

class TestHubMessaging:
    def test_connect_and_send(self, claude_server):
        # Connect
        resp = mcp_call(claude_server, "tools/call", {
            "name": "hub_connect",
            "arguments": {"agent_id": "test", "role": "tester"}
        })
        assert "error" not in resp

        # Send message
        resp = mcp_call(claude_server, "tools/call", {
            "name": "hub_send_message",
            "arguments": {
                "to_id": "test",
                "from_id": "test",
                "message": "ping",
                "msg_type": "PROPOSAL_READY"
            }
        })
        assert "error" not in resp
```

---

## Task 10: Verify Ollama integration

**Test command:**
```bash
cd /Users/eriksjaastad/projects/_tools
SANDBOX_ROOT=$(pwd) ./ollama-mcp-go/bin/server &
# In another terminal, send test request
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ollama_run","arguments":{"model":"qwen2.5-coder:7b","prompt":"Say hello"}}}' | nc localhost 11434
```

---

## Files Needing Path Updates

Full list of files referencing old paths:

```
agent-hub/tests/test_config_generator.py
agent-hub/README.md
agent-hub/registry-entry.json
agent-hub/scripts/test_mcp_communication.py
agent-hub/scripts/generate_mcp_config.py
agent-hub/scripts/dispatch_task.py
agent-hub/Documents/API.md
agent-hub/Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md
agent-hub/Documents/CURSOR_MCP_SETUP.md
agent-hub/AGENTS.md
agent-hub/00_Index_agent-hub.md
agent-hub/skill.json
agent-hub/src/watchdog.py
agent-hub/src/mcp_connection_pool.py
agent-hub/src/worker_client.py
agent-hub/src/claude_client.py
```

---

## Go MCP Server Reference

### ollama-mcp-go tools:
| Tool | Description |
|------|-------------|
| `ollama_run` | Run single Ollama model |
| `ollama_run_many` | Run multiple models concurrently |
| `draft_read` | Read file from sandbox |
| `draft_write` | Write file to sandbox |
| `draft_patch` | Apply patches to file |
| `draft_list` | List sandbox files |
| `agent_loop` | Iterative agent with tool-calling |

### claude-mcp-go tools:
| Tool | Description |
|------|-------------|
| `hub_connect` | Connect agent to hub |
| `hub_send_message` | Send message to agent |
| `hub_receive_messages` | Get pending messages |
| `hub_heartbeat` | Send heartbeat |
| `hub_send_answer` | Reply to question |
| `hub_get_all_messages` | Get all messages |
| `claude_health` | Health check |
| `claude_judge_review` | Request judge review |
| `claude_validate_proposal` | Validate proposal |
| `claude_security_audit` | Security audit |
| `claude_resolve_conflict` | Resolve conflicts |
| `request_draft_review` | Request draft review |
| `submit_review_verdict` | Submit review verdict |

---

## Acceptance Criteria

1. `python scripts/generate_mcp_config.py --list` shows correct Go binary paths
2. `python scripts/test_mcp_communication.py` passes all tests
3. `pytest tests/test_e2e_mcp_pipeline.py -v` passes
4. No files reference `ollama-mcp/` or `claude-mcp/` (only `*-go` versions)
5. `.env` exists with correct paths
6. `HALT.md` deleted

---

## Task 11: Add `ollama_list_models` tool to Go server

**Status:** TODO

**Why:** Agents need to know what models are available before calling `ollama_run`. Current workaround ("call Ollama CLI directly") leaks implementation details.

**Files to modify:**

1. **`ollama-mcp-go/internal/ollama/client.go`** - Add `ListModels` method:
```go
// Model represents a local Ollama model.
type Model struct {
    Name       string `json:"name"`
    ModifiedAt string `json:"modified_at"`
    Size       int64  `json:"size"`
}

// ListModelsResponse from /api/tags
type ListModelsResponse struct {
    Models []Model `json:"models"`
}

// ListModels returns all locally available models.
func (c *Client) ListModels(ctx context.Context) (*ListModelsResponse, error) {
    url := fmt.Sprintf("%s/api/tags", c.BaseURL)
    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        return nil, err
    }

    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        body, _ := io.ReadAll(resp.Body)
        return nil, fmt.Errorf("ollama error (status %d): %s", resp.StatusCode, string(body))
    }

    var listResp ListModelsResponse
    if err := json.NewDecoder(resp.Body).Decode(&listResp); err != nil {
        return nil, err
    }

    return &listResp, nil
}
```

2. **`ollama-mcp-go/internal/tools/run.go`** - Add handler method:
```go
// ListModels returns available Ollama models.
func (h *RunHandler) ListModels(args map[string]any) (any, error) {
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    resp, err := h.client.ListModels(ctx)
    if err != nil {
        return nil, fmt.Errorf("failed to list models: %w", err)
    }

    return resp.Models, nil
}
```

3. **`ollama-mcp-go/cmd/server/main.go`** - Register the tool:
```go
toolExecutor.Register("ollama_list_models", runHandler.ListModels)

mcpHandler.RegisterTool(mcp.Tool{
    Name:        "ollama_list_models",
    Description: "List all locally available Ollama models",
    InputSchema: json.RawMessage(`{
        "type": "object",
        "properties": {},
        "required": []
    }`),
    Handler: runHandler.ListModels,
})
```

4. **Update tests** - Add to `EXPECTED_OLLAMA_TOOLS` in:
   - `agent-hub/scripts/test_mcp_communication.py`
   - `agent-hub/tests/test_e2e_mcp_pipeline.py`

**Test:** After rebuild, `ollama_list_models` tool should appear in `tools/list` response and return model names when called.

**Rebuild:**
```bash
cd /Users/eriksjaastad/projects/_tools/ollama-mcp-go
go build -o bin/server ./cmd/server
```

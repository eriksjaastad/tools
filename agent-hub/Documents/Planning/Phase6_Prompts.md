# Phase 6: The MCP Bridge (Activation)

> **For:** Gemini 3 Flash (Floor Manager in Cursor/Antigravity)
> **Context:** Agent Hub implementation
> **Created:** 2026-01-17
> **Author:** Claude Code CLI (Super Manager backup)

This phase connects Agent Hub to the existing `ollama-mcp` infrastructure. Instead of rewriting Ollama integration in Python, we build a bridge that speaks MCP protocol to the Node.js server Erik already built.

**Why MCP Bridge instead of raw Ollama calls:**
- Reuses existing `ollama-mcp` logic, safety checks, and telemetry
- Consistent behavior between Cursor and Antigravity
- Future updates to `ollama-mcp` automatically benefit Agent Hub

---

## Prompt 6.1: MCP Client (Python JSON-RPC Transport)

```markdown
# Floor Manager Task: Implement MCP Client

You are the Floor Manager. We need a Python client that can communicate with our existing `ollama-mcp` Node.js server using the Model Context Protocol (JSON-RPC over stdio).

## Context

The `ollama-mcp` server lives at:
- Source: `/Users/eriksjaastad/projects/_tools/ollama-mcp/`
- Entry: `dist/server.js` (compiled TypeScript)
- Protocol: MCP (JSON-RPC 2.0 over stdio)
- Tools exposed: `ollama_run`, `ollama_list_models`

We need Python to spawn this server and talk to it the same way Cursor does.

## Requirements

Create `_tools/agent-hub/src/mcp_client.py` with:

1. **`MCPClient` class**
   - `__init__(self, server_path: Path)` - Path to the Node.js server
   - `start()` - Spawns the server as a subprocess with stdio pipes
   - `stop()` - Gracefully terminates the subprocess
   - `call_tool(name: str, arguments: dict, timeout: int = 600) -> dict` - Sends JSON-RPC request, returns response
   - Context manager support (`__enter__`, `__exit__`)

2. **JSON-RPC 2.0 Protocol**
   - Request format: `{"jsonrpc": "2.0", "id": <int>, "method": "tools/call", "params": {"name": "<tool>", "arguments": {...}}}`
   - Response parsing: Extract `result` or raise on `error`
   - Incrementing request IDs

3. **Error Handling**
   - `MCPError` exception class for protocol errors
   - `MCPTimeoutError` for timeouts (important for watchdog integration)
   - Handle subprocess crashes gracefully

4. **Logging**
   - Log all requests/responses at DEBUG level
   - Log errors at ERROR level

## Example Usage

```python
from mcp_client import MCPClient
from pathlib import Path

server_path = Path("/Users/eriksjaastad/projects/_tools/ollama-mcp/dist/server.js")

with MCPClient(server_path) as client:
    # List available models
    result = client.call_tool("ollama_list_models", {})
    print(result)

    # Run a model
    result = client.call_tool("ollama_run", {
        "model": "qwen2.5-coder:14b",
        "prompt": "Write a hello world in Python",
        "timeout": 300
    })
    print(result)
```

## Done Criteria

- [ ] `mcp_client.py` exists in `src/`
- [ ] Can spawn and communicate with `ollama-mcp` server
- [ ] Handles timeouts and returns `MCPTimeoutError`
- [ ] Handles server crashes gracefully
- [ ] All methods have type hints and docstrings

## Tests Required

Create `_tools/agent-hub/tests/test_mcp_client.py`:

- [ ] Test: Client starts and stops cleanly
- [ ] Test: Can call `ollama_list_models` (if Ollama running)
- [ ] Test: Timeout raises `MCPTimeoutError`
- [ ] Test: Invalid tool name returns error

**Note:** For tests where Ollama isn't available, mock the subprocess.
```

---

## Prompt 6.2: Worker Client (High-Level Interface)

```markdown
# Floor Manager Task: Implement Worker Client

You are the Floor Manager. We need a clean Python interface that wraps the MCP client and provides task-oriented methods for the Agent Hub pipeline.

## Context

The `MCPClient` from Prompt 6.1 handles low-level JSON-RPC. Now we need a higher-level interface that:
- Reads task contracts
- Builds appropriate prompts for each role (Implementer, Local Reviewer)
- Captures output and updates handoff data
- Detects stalls (empty output, malformed responses)

## Requirements

Create `_tools/agent-hub/src/worker_client.py` with:

1. **`WorkerClient` class**
   - `__init__(self, mcp_client: MCPClient)` - Takes an initialized MCP client
   - `implement_task(contract: dict) -> dict` - Runs Implementer, returns result
   - `run_local_review(contract: dict, changed_files: list) -> dict` - Runs Local Reviewer
   - `check_ollama_health() -> bool` - Verifies Ollama is responsive

2. **`implement_task(contract)` method**
   - Reads `contract["specification"]` for requirements, target file, source files
   - Builds a structured prompt for the Implementer (use contract["roles"]["implementer"] model)
   - Calls `ollama_run` via MCP client
   - Parses response and writes to target file
   - Returns `{"success": bool, "output": str, "files_changed": list, "tokens": dict}`

3. **`run_local_review(contract, changed_files)` method**
   - Reads the changed files
   - Builds a security/syntax review prompt for Local Reviewer (use contract["roles"]["local_reviewer"] model)
   - Calls `ollama_run` via MCP client
   - Parses response for issues
   - Returns `{"passed": bool, "issues": list, "critical": bool}`

4. **Stall Detection**
   - If response is empty or just whitespace → `{"success": False, "stall_reason": "empty_output"}`
   - If response doesn't contain expected markers → `{"success": False, "stall_reason": "malformed_output"}`
   - If timeout → `{"success": False, "stall_reason": "timeout"}`

5. **Prompt Templates**
   - Store prompt templates as constants or in a `prompts/` directory
   - Implementer prompt should include: task_id, requirements, source files, constraints
   - Reviewer prompt should include: files to review, security checklist, syntax checklist

## Example Usage

```python
from mcp_client import MCPClient
from worker_client import WorkerClient
from pathlib import Path

server_path = Path("/Users/eriksjaastad/projects/_tools/ollama-mcp/dist/server.js")

with MCPClient(server_path) as mcp:
    worker = WorkerClient(mcp)

    # Check health first
    if not worker.check_ollama_health():
        raise RuntimeError("Ollama not available")

    # Run implementation
    contract = load_contract(Path("_handoff/TASK_CONTRACT.json"))
    result = worker.implement_task(contract)

    if result["success"]:
        # Run local review
        review = worker.run_local_review(contract, result["files_changed"])
        if review["critical"]:
            # Halt - critical security flaw
            pass
```

## Done Criteria

- [ ] `worker_client.py` exists in `src/`
- [ ] `implement_task()` builds prompt and invokes Implementer model
- [ ] `run_local_review()` builds prompt and invokes Local Reviewer model
- [ ] Stall detection returns structured failure reasons
- [ ] All methods have type hints and docstrings

## Tests Required

Create `_tools/agent-hub/tests/test_worker_client.py`:

- [ ] Test: `implement_task` with mocked MCP client
- [ ] Test: `run_local_review` detects security issue in mock response
- [ ] Test: Empty response triggers stall detection
- [ ] Test: Timeout triggers stall detection
```

---

## Prompt 6.3: Watchdog Integration

```markdown
# Floor Manager Task: Wire MCP Bridge into Watchdog

You are the Floor Manager. Now that we have the MCP client and worker client, we need to integrate them into the watchdog state machine so tasks run autonomously.

## Context

Currently `watchdog.py` has the state machine but no way to invoke Ollama. We need to add:
- A command to run the Implementer phase
- A command to run the Local Review phase
- Proper state transitions based on results
- Stall handling with the Two-Strike Rule

## Requirements

Update `_tools/agent-hub/src/watchdog.py`:

1. **New CLI Commands**
   - `run-implementer` - Executes the Implementer phase
   - `run-local-review` - Executes the Local Review phase

2. **`run-implementer` command flow**
   ```
   1. Load contract
   2. Check status == "pending_implementer"
   3. Acquire lock
   4. Initialize MCP client and WorkerClient
   5. Call worker.implement_task(contract)
   6. If success:
      - Update handoff_data.changed_files
      - Transition to "pending_local_review"
   7. If stall:
      - If attempt == 1: increment attempt, stay in "pending_implementer" (Strike 1)
      - If attempt >= 2: transition to "erik_consultation", write STALL_REPORT.md (Strike 2)
   8. Release lock
   9. Git checkpoint
   ```

3. **`run-local-review` command flow**
   ```
   1. Load contract
   2. Check status == "pending_local_review"
   3. Initialize MCP client and WorkerClient
   4. Call worker.run_local_review(contract, changed_files)
   5. If passed:
      - Set handoff_data.local_review_passed = True
      - Transition to "pending_judge_review" (triggers REVIEW_REQUEST.md via save_contract)
   6. If critical:
      - Transition to "erik_consultation"
      - Write ERIK_HALT.md with security issue details
   7. If minor issues:
      - Store in handoff_data.local_review_issues
      - Still transition to "pending_judge_review" (Judge will see context)
   8. Git checkpoint
   ```

4. **Configuration**
   - MCP server path should be configurable (env var or config file)
   - Default: `/Users/eriksjaastad/projects/_tools/ollama-mcp/dist/server.js`

5. **Health Check**
   - Before any MCP operation, check `worker.check_ollama_health()`
   - If unhealthy, halt with reason "ollama_unavailable"

## Example Usage

```bash
# Start the pipeline after contract is created
python src/watchdog.py setup-task          # Create git branch
python src/watchdog.py run-implementer     # Invoke Qwen via MCP
python src/watchdog.py run-local-review    # Invoke DeepSeek via MCP
# REVIEW_REQUEST.md is created automatically
# watcher.sh picks it up and invokes Judge (Claude)
python src/watchdog.py report-judge        # Process verdict
python src/watchdog.py finalize-task       # Merge if PASS
```

## Done Criteria

- [x] `run-implementer` command works end-to-end
- [x] `run-local-review` command works end-to-end
- [x] Two-Strike Rule implemented (attempt counter, STALL_REPORT.md)
- [x] Health check prevents operations when Ollama is down
- [x] State transitions match Blueprint V2 spec

## Tests Required

Update `_tools/agent-hub/tests/test_e2e.py`:

- [x] Test: Full pipeline with mocked MCP (proposal → merged)
- [x] Test: Stall on first attempt retries (Strike 1)
- [x] Test: Stall on second attempt halts with STALL_REPORT.md (Strike 2)
- [x] Test: Critical security flaw halts with ERIK_HALT.md
```

---

## Phase 6 Checklist

After completing all prompts:

- [x] `src/mcp_client.py` - JSON-RPC transport to ollama-mcp
- [x] `src/worker_client.py` - High-level Implementer/Reviewer interface
- [x] `src/watchdog.py` - Updated with `run-implementer` and `run-local-review` commands
- [x] All new tests passing
- [x] Can run a task from `pending_implementer` to `pending_judge_review` without manual intervention

---

## Notes for Floor Manager

1. **MCP Server Path:** The `ollama-mcp` server is already built. You just need to spawn it and talk JSON-RPC.

2. **Stall Detection is Critical:** This is BI-002 from the Judge Report. Make sure empty/malformed output triggers proper handling.

3. **Don't Forget Token Tracking:** If `ollama_run` returns token counts, pipe them to `update_cost()`.

4. **Test with Real Ollama:** At least one manual test should verify actual Ollama invocation works.

---

*Phase 6 bridges the gap between orchestration (what we built) and activation (invoking actual models). After this, the pipeline is fully autonomous.*

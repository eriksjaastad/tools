# Phase 8: Full MCP Mode (Deprecate File Polling)

**Goal:** Remove file polling as a trigger mechanism. MCP messages are now the primary (and only) way agents communicate. Files remain as artifacts for humans and audit trails.

**Prerequisites:** Phase 7 complete, all messaging tests passing.

---

## The Shift

| Before (Phase 7) | After (Phase 8) |
|------------------|-----------------|
| `--mcp-mode` flag enables messaging | MCP is always on, no flag needed |
| `watcher.sh` polls for files | `watcher.sh` replaced by message listener |
| `REVIEW_REQUEST.md` written as signal | Only `REVIEW_NEEDED` message sent |
| Floor Manager watches `_handoff/` | Floor Manager subscribes to message queue |
| System works without MCP hub | **MCP hub required** (with graceful error) |

---

## Prompt 8.1: Message Listener (`listener.py`)

### Context
Replace `watcher.sh` file polling with a Python process that connects to the MCP hub and waits for messages. This is the new "main loop" for the Floor Manager.

### Task
Create `src/listener.py`:

```python
#!/usr/bin/env python3
"""
Message Listener - The new main loop for Agent Hub.
Replaces watcher.sh file polling with MCP message subscription.
"""

class MessageListener:
    def __init__(self, agent_id: str, hub_path: Path):
        self.agent_id = agent_id
        self.hub_path = hub_path
        self.running = False
        self.handlers = {}  # message_type -> handler function

    def register_handler(self, msg_type: str, handler: Callable):
        """Register a handler for a specific message type."""
        self.handlers[msg_type] = handler

    def start(self):
        """
        Main loop:
        1. Connect to hub
        2. Emit heartbeat every 30 seconds
        3. Check for messages every 5 seconds
        4. Dispatch to registered handlers
        """

    def stop(self):
        """Graceful shutdown."""

    def handle_proposal_ready(self, message: dict):
        """
        Handler for PROPOSAL_READY:
        1. Read proposal from message['payload']['proposal_path']
        2. Convert to contract
        3. Start implementation pipeline
        """

    def handle_stop_task(self, message: dict):
        """
        Handler for STOP_TASK:
        1. Log the stop request
        2. Halt current operation
        3. Clean up resources
        """

    def handle_question(self, message: dict):
        """
        Handler for QUESTION from Super Manager:
        1. Present options to Floor Manager logic
        2. Select best option (or escalate to Erik)
        3. Send ANSWER back
        """


def main():
    listener = MessageListener("floor_manager", HUB_SERVER_PATH)

    # Register handlers
    listener.register_handler("PROPOSAL_READY", listener.handle_proposal_ready)
    listener.register_handler("STOP_TASK", listener.handle_stop_task)
    listener.register_handler("QUESTION", listener.handle_question)

    # Run until interrupted
    try:
        listener.start()
    except KeyboardInterrupt:
        listener.stop()
```

### Requirements
- Must emit heartbeat every 30 seconds while running
- Must check for messages every 5 seconds (configurable)
- Must handle graceful shutdown on SIGINT/SIGTERM
- Must log all received messages to `transition.ndjson`
- Must exit with clear error if hub is not reachable

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/src/listener.py`

---

## Prompt 8.2: Update `watchdog.py` (Remove MCP Flag)

### Context
In Phase 7, we added `--mcp-mode` as an optional flag. In Phase 8, MCP is the default and only mode.

### Task
Modify `src/watchdog.py`:

1. **Remove `--mcp-mode` flag handling**
   - Delete lines that check for `--mcp-mode`
   - Delete the `use_mcp` conditional logic
   - MCP is always used

2. **Remove file signal generation**
   - In `save_contract()`, remove the code that writes `REVIEW_REQUEST.md`
   - Only send `REVIEW_NEEDED` message

3. **Add hub health check on startup**
   ```python
   def check_hub_available(hub_path: Path) -> bool:
       """Verify MCP hub is running before any operation."""
       try:
           with MCPClient(hub_path) as mcp:
               hub = HubClient(mcp)
               return hub.connect("health_check")
       except Exception:
           return False

   # At start of main():
   if not check_hub_available(HUB_SERVER_PATH):
       print("Error: MCP Hub not available. Start claude-mcp first.")
       sys.exit(1)
   ```

4. **Simplify command handlers**
   - Remove all `if use_mcp:` conditionals
   - The MCP path is now the only path

### File Location
Modify in place: `/Users/eriksjaastad/projects/_tools/agent-hub/src/watchdog.py`

---

## Prompt 8.3: Deprecate `watcher.sh`

### Context
`watcher.sh` was the file-polling loop. It's no longer needed since `listener.py` handles message-based triggers.

### Task
1. **Rename** `src/watcher.sh` to `src/watcher.sh.deprecated`
2. **Add header comment** explaining it's deprecated:
   ```bash
   #!/bin/bash
   # DEPRECATED: Phase 8 replaced file polling with message listener.
   # See: src/listener.py
   # This file is kept for reference only.
   ```
3. **Update any documentation** that references `watcher.sh`

### Note
Don't delete it - keep for reference and potential emergency fallback.

---

## Prompt 8.4: Update `save_contract()` - Message Only

### Context
Currently `save_contract()` has conditional logic: if MCP mode, send message; else write file signal. Now it should only send messages.

### Task
Modify the `save_contract()` function in `watchdog.py`:

**Before:**
```python
if mcp_mode:
    # send REVIEW_NEEDED message
else:
    # write REVIEW_REQUEST.md
```

**After:**
```python
# Always send message (no file signal)
if contract.get("status") == "pending_judge_review":
    with MCPClient(HUB_SERVER_PATH) as mcp:
        hub = HubClient(mcp)
        hub.connect("floor_manager")
        hub.send_message("judge", "REVIEW_NEEDED", {
            "task_id": contract["task_id"],
            "contract_path": str(path)
        })
```

Remove the file-writing fallback entirely.

---

## Prompt 8.5: Startup Script (`start_agent_hub.sh`)

### Context
With MCP as the only communication method, we need a clean startup process that ensures the hub is running.

### Task
Create `scripts/start_agent_hub.sh`:

```bash
#!/bin/bash
# Start Agent Hub with MCP message listener

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HUB_PATH="${HUB_SERVER_PATH:-/Users/eriksjaastad/projects/_tools/claude-mcp/dist/server.js}"

echo "=== Agent Hub Startup ==="

# 1. Check if hub is already running
if ! pgrep -f "claude-mcp" > /dev/null; then
    echo "Starting MCP Hub..."
    node "$HUB_PATH" &
    sleep 2
fi

# 2. Verify hub is responsive
python3 -c "
from src.hub_client import HubClient
from src.mcp_client import MCPClient
from pathlib import Path
with MCPClient(Path('$HUB_PATH')) as mcp:
    hub = HubClient(mcp)
    if hub.connect('startup_check'):
        print('Hub: OK')
    else:
        exit(1)
" || {
    echo "Error: Hub not responsive"
    exit 1
}

# 3. Start message listener
echo "Starting Message Listener..."
cd "$PROJECT_ROOT"
python3 -m src.listener

echo "Agent Hub stopped."
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/scripts/start_agent_hub.sh`

---

## Prompt 8.6: Integration Test (End-to-End Message Flow)

### Context
Verify the full message flow works without any file polling.

### Task
Create `tests/test_e2e_messages.py`:

```python
"""
End-to-end test: Full pipeline via messages only.
No file polling involved.
"""

def test_proposal_to_review_message_flow():
    """
    Simulate:
    1. Super Manager sends PROPOSAL_READY
    2. Floor Manager receives, converts to contract
    3. Floor Manager sends REVIEW_NEEDED
    4. Judge receives, reviews, sends VERDICT_SIGNAL
    5. Floor Manager receives verdict

    All via messages. No file triggers.
    """

def test_stop_task_interrupts_work():
    """
    1. Start a long-running task
    2. Send STOP_TASK
    3. Verify task halts within 10 seconds
    """

def test_question_answer_negotiation():
    """
    1. Floor Manager sends QUESTION with 3 options
    2. Super Manager sends ANSWER selecting option 2
    3. Floor Manager receives and proceeds
    """
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/tests/test_e2e_messages.py`

---

## Execution Order

1. **8.1** - Create `listener.py` (the new main loop)
2. **8.2** - Update `watchdog.py` (remove MCP flag, hub health check)
3. **8.3** - Deprecate `watcher.sh`
4. **8.4** - Update `save_contract()` (message only)
5. **8.5** - Create startup script
6. **8.6** - Run integration tests

---

## Success Criteria

Phase 8 is DONE when:
- [x] `listener.py` runs and receives messages
- [x] `watchdog.py` works without `--mcp-mode` flag
- [x] No file signals are written (`REVIEW_REQUEST.md` never created)
- [x] Hub health check fails gracefully with clear error
- [x] `start_agent_hub.sh` brings up the full system
- [x] End-to-end message flow test passes
- [x] `watcher.sh` is deprecated (renamed, not deleted)

---

## What's Still a File (Artifacts, Not Triggers)

These files still exist for humans and audit trails:
- `PROPOSAL_FINAL.md` - The proposal document (read by Floor Manager after message)
- `TASK_CONTRACT.json` - The contract (read/written throughout)
- `JUDGE_REPORT.md` / `.json` - Review output (written by Judge)
- `transition.ndjson` - Audit log
- `ERIK_HALT.md` - When circuit breakers trigger
- `STALL_REPORT.md` - When agents stall

**None of these are polled for.** They're artifacts that get read/written as part of normal operations, triggered by messages.

---

*Phase 8 cuts the cord on file polling. After this, Agent Hub is a fully message-driven system.*

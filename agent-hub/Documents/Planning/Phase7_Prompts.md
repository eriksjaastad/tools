# Phase 7: Direct Agent Communication (DAC)

**Goal:** Replace file-based polling with MCP message bus. Test it thoroughly before wiring into production.

**Philosophy:** Build the pipes first, flood them with test messages, verify nothing leaks. Then wire in the real work.

---

## Prompt 7.1: Message Bus Client (`hub_client.py`)

### Context
We're building a message bus for agent-to-agent communication. The `claude-mcp` server (located at `/Users/eriksjaastad/projects/_tools/claude-mcp/`) will be the hub. This client talks to it.

### Task
Create `src/hub_client.py` that provides:

```python
class HubClient:
    def __init__(self, mcp_client: MCPClient):
        self.mcp = mcp_client
        self.agent_id = None  # Set on connect

    def connect(self, agent_id: str) -> bool:
        """Register this agent with the hub."""

    def send_message(self, recipient: str, msg_type: str, payload: dict) -> str:
        """
        Send a message to another agent.
        Returns: message_id

        Valid msg_types: PROPOSAL_READY, REVIEW_NEEDED, STOP_TASK,
                        QUESTION, ANSWER, VERDICT_SIGNAL, HEARTBEAT
        """

    def receive_messages(self, since: str = None) -> List[dict]:
        """
        Check inbox for pending messages.
        Returns list of: {id, from, type, payload, timestamp}
        """

    def emit_heartbeat(self, progress: str = None) -> None:
        """
        Signal "I'm alive and working on {progress}"
        Called every 30 seconds by active agents.
        """

    def send_question(self, recipient: str, question: str, options: List[str]) -> str:
        """
        Ask a constrained question (2-4 options required).
        Returns: message_id
        """

    def send_answer(self, question_id: str, selected_option: int) -> str:
        """
        Answer a previous question by selecting an option index.
        Returns: message_id
        """
```

### Constraints
- Message types are FIXED. Reject any type not in the valid list.
- `send_question()` MUST require 2-4 options. No open-ended questions.
- `send_answer()` MUST reference a valid question_id.
- All messages get a unique ID (UUID).
- All messages include timestamp.

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/src/hub_client.py`

### Dependencies
- Import from `.mcp_client` (already exists)
- Use `uuid` for message IDs
- Use `datetime` for timestamps

---

## Prompt 7.2: Test Harness (`test_messaging.py`)

### Context
Before wiring messaging into the real system, we need to verify:
1. Messages flow correctly between agents
2. Heartbeats are recorded
3. Stall detection works
4. Invalid messages are rejected

### Task
Create `tests/test_messaging.py` with these test scenarios:

#### Test 1: Ping-Pong (20 messages)
```
Super Manager -> PROPOSAL_READY -> Floor Manager
Floor Manager -> QUESTION (3 options) -> Super Manager
Super Manager -> ANSWER (option 1) -> Floor Manager
Floor Manager -> REVIEW_NEEDED -> Judge
Judge -> VERDICT_SIGNAL (PASS) -> Floor Manager
... repeat 4x = 20 messages total
```
**Pass criteria:** All 20 messages delivered, in order, no drops.

#### Test 2: Heartbeat Flood (100 heartbeats)
```
Agent emits 100 heartbeats at 50ms intervals
Hub records all 100
```
**Pass criteria:** All 100 heartbeats received, timestamps sequential.

#### Test 3: Question Validation
```
Try to send question with 0 options -> REJECTED
Try to send question with 1 option -> REJECTED
Try to send question with 5 options -> REJECTED
Send question with 2 options -> ACCEPTED
Send question with 4 options -> ACCEPTED
```
**Pass criteria:** Invalid questions rejected, valid ones accepted.

#### Test 4: Invalid Message Type
```
Try to send message type "GO_FUCK_YOURSELF" -> REJECTED
Try to send message type "ARBITRARY_PROMPT" -> REJECTED
```
**Pass criteria:** Unknown message types rejected with clear error.

#### Test 5: Stall Detection
```
Agent connects, emits 3 heartbeats, then goes silent
After 90 seconds (3 missed beats), hub should flag as stalled
```
**Pass criteria:** Hub detects stall within 100 seconds of last heartbeat.

### Output Format
```
$ python -m pytest tests/test_messaging.py -v

test_ping_pong_20_messages ... PASSED (20/20 delivered)
test_heartbeat_flood_100 ... PASSED (100/100 recorded)
test_question_validation ... PASSED (3 rejected, 2 accepted)
test_invalid_message_type ... PASSED (2 rejected)
test_stall_detection ... PASSED (stall detected at 91s)
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/tests/test_messaging.py`

### Note
This test can run against a mock hub OR the real `claude-mcp` server. Use environment variable `MCP_HUB_PATH` to specify which.

---

## Prompt 7.3: Claude Client (`claude_client.py`)

### Context
The Floor Manager needs to invoke Claude for specific, constrained operations. NOT arbitrary prompts - a fixed menu of tools.

### Task
Create `src/claude_client.py` that wraps the `claude-mcp` tools:

```python
class ClaudeClient:
    def __init__(self, mcp_client: MCPClient):
        self.mcp = mcp_client

    def judge_review(self, contract_path: str, working_dir: str) -> dict:
        """
        Request architectural review from Claude.
        Returns: {success, verdict, report_path, blocking_issues}
        """

    def validate_proposal(self, proposal_path: str) -> dict:
        """
        Check if proposal is complete before conversion.
        Returns: {valid, issues}
        """

    def security_audit(self, files: List[str], working_dir: str) -> dict:
        """
        Deep security review of specific files.
        Returns: {findings: [{severity, file, line, description, recommendation}]}
        """

    def resolve_conflict(self, contract_path: str, rebuttal_path: str,
                         judge_report_path: str) -> dict:
        """
        Decide who's right when Floor Manager and Judge disagree.
        Returns: {side: 'floor_manager'|'judge', reasoning, recommendation}
        """

    def health_check(self) -> bool:
        """Verify claude-mcp is responsive."""
```

### Constraints
- These are the ONLY operations available to the Floor Manager
- No arbitrary prompt injection
- Each method maps to a specific tool in `claude-mcp`

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/src/claude_client.py`

---

## Prompt 7.4: Watchdog Integration

### Context
Once messaging tests pass, wire it into the real system.

### Task
Modify `src/watchdog.py` to support MCP mode:

#### Changes Required

1. **Add `--mcp-mode` flag to CLI**
```python
if "--mcp-mode" in argv:
    USE_MCP = True
else:
    USE_MCP = False
```

2. **Emit heartbeats during long operations**
```python
# In run-implementer command:
if USE_MCP:
    hub.emit_heartbeat(f"implementing {contract['task_id']}")

# Every 30 seconds during implementation:
# (Use threading or periodic check)
```

3. **Check for STOP_TASK messages**
```python
# At start of each command:
if USE_MCP:
    messages = hub.receive_messages()
    for msg in messages:
        if msg["type"] == "STOP_TASK":
            print(f"Received STOP signal: {msg['payload']}")
            sys.exit(0)
```

4. **Replace REVIEW_REQUEST.md with message**
```python
# In save_contract(), when status moves to pending_judge_review:
if USE_MCP:
    hub.send_message("judge", "REVIEW_NEEDED", {
        "task_id": contract["task_id"],
        "contract_path": str(contract_path)
    })
else:
    # V2 fallback: write REVIEW_REQUEST.md (existing code)
```

### Backward Compatibility
- If `--mcp-mode` is NOT set, all existing file-based behavior works unchanged
- This lets us test MCP mode without breaking the current system

### File Location
Modify in place: `/Users/eriksjaastad/projects/_tools/agent-hub/src/watchdog.py`

---

## Execution Order

1. **7.1** - Build `hub_client.py` (can't test without it)
2. **7.2** - Run tests, iterate until all pass
3. **7.3** - Build `claude_client.py` (independent of 7.1/7.2)
4. **7.4** - Wire into watchdog (only after 7.2 passes)

---

## Success Criteria

Phase 7 is DONE when:
- [x] `test_messaging.py` passes all 5 tests
- [x] 100 messages flow through without drops
- [x] Invalid messages are rejected
- [x] Stall detection triggers within threshold
- [x] `watchdog.py --mcp-mode` works alongside `--no-mcp-mode`
- [x] File polling still works as fallback

---

*Phase 7 builds the communication layer. Phase 8 will deprecate file polling entirely.*

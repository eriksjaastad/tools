# Subagent Communication Example Flow

This walkthrough demonstrates a worker encountering a logic blocker and resolving it via the parent.

## Walkthrough Scenario
A worker is trying to refactor a component but encounters an ambiguous requirement: "Should I use camelCase or snake_case for the new state variables?"

### Step 1: Worker Asks Question
The worker identifies a blocker and pauses.

**Request (JSON-RPC):**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/call",
  "params": {
    "name": "ask_parent",
    "arguments": {
      "question": "The project style guide is unclear for internal state variables. Should I use camelCase or snake_case?"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "message_id": "msg-9922-abc"
  }
}
```

### Step 2: Parent Replies
The Super Manager (or User) sees the pending question and provides the answer.

**Request (JSON-RPC):**
```json
{
  "jsonrpc": "2.0",
  "id": "101",
  "method": "tools/call",
  "params": {
    "name": "reply_subagent",
    "arguments": {
      "subagent_id": "worker-42",
      "message": "Use snake_case for all internal state variables to match the Python backend patterns."
    }
  }
}
```

### Step 3: Worker Polls and Receives Answer
After a few `null` responses, the worker polls and finds the answer.

**Request (JSON-RPC):**
```json
{
  "jsonrpc": "2.0",
  "id": "5",
  "method": "tools/call",
  "params": {
    "name": "check_answer",
    "arguments": {
      "message_id": "msg-9922-abc"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "5",
  "result": {
    "answer": "Use snake_case for all internal state variables to match the Python backend patterns."
  }
}
```

### Timing Diagram (Async)

```text
Worker: [Doing Task] -> [Blocker!] -> ask_parent()
Worker: [Sleeping...]
Worker: [Polling...] -> null
Parent: [Sees Question] -> [Thinks] -> reply_subagent()
Worker: [Polling...] -> "Use snake_case"
Worker: [Continues Task] -> [Success!]
```

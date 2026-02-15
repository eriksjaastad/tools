# Subagent Protocol Specification

This document defines the tool schemas and state transitions for the subagent bi-directional communication loop.

## Message Flow Diagram

```text
  WORKER (Subagent)             MESSAGE BUS (SQLite)            PARENT (Super/Floor Manager)
      |                             |                               |
      | 1. ask_parent(question)     |                               |
      |---------------------------->|                               |
      |     [returns message_id]    |                               |
      |                             | 2. notify / poll              |
      |                             |------------------------------>|
      |                             |                               |
      | 3. check_answer(message_id) |                               | 4. reply_subagent(ans)
      |---------------------------->|                               |<-----------------
      |      [returns null]         |       (ANSWERED)              |
      |                             |                               |
      | 5. check_answer(message_id) |                               |
      |---------------------------->|                               |
      |      [returns answer]       |                               |
      |                             |                               |
      v             (RETRIEVED)     v                               v
```

## MCP Tools

### `ask_parent(question: str)`
- **Role:** Called by Worker to halt execution and seek clarification.
- **Parameters:**
  - `question`: The natural language question for the parent.
- **Returns:**
  - `message_id`: A unique UUID string identifying the question.
- **State Change:** Creates a record with status `PENDING`.

### `reply_subagent(subagent_id: str, message: str)`
- **Role:** Called by Parent to provide an answer.
- **Parameters:**
  - `subagent_id`: The ID of the worker/run being answered.
  - `message`: The actual answer/instruction.
- **Returns:**
  - `success`: Boolean indicating if the message was delivered.
- **State Change:** Updates existing `PENDING` message to `ANSWERED`.

### `check_answer(message_id: str)`
- **Role:** Called by Worker (polling) to check for completion.
- **Parameters:**
  - `message_id`: The ID returned by `ask_parent`.
- **Returns:**
  - `answer`: String containing the response, or `null` if still pending.
- **State Change:** On delivery, status moves to `RETRIEVED`.

### `get_pending_questions(run_id?: str)`
- **Role:** Called by Parent (or UI) to list unanswered queries.
- **Parameters:**
  - `run_id` (optional): Filter questions by a specific agent run.
- **Returns:**
  - `list[Question]`: Array of `{message_id, question, timestamp}`.

## State Machine
A message must move through the following states in order:
1. **PENDING:** Question has been written to the bus; parent has not replied.
2. **ANSWERED:** Parent has provided a response to the bus.
3. **RETRIEVED:** Worker has successfully polled the answer.

## Timeout Behavior
- **Worker Level:** Workers should have a configurable timeout (default 300s) for individual `check_answer` cycles. If no answer is received, the worker should fail with a "Stalled: Parent No-Response" error.
- **Bus Level:** `PENDING` questions older than 24 hours are automatically marked as `EXPIRED`.

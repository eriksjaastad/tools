# Subagent Integration Notes

These notes outline how the bi-directional protocol integrates with the Unified Agent System architecture.

## SQLite Message Bus Schema (Phase 3)
We utilize a centralized `agent_hub.db` to handle the asynchronous message state.

```sql
CREATE TABLE subagent_messages (
    message_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,          -- Identifies the specific task run
    subagent_id TEXT NOT NULL,     -- The worker requesting help
    question TEXT NOT NULL,
    answer TEXT,
    status TEXT DEFAULT 'PENDING', -- PENDING, ANSWERED, RETRIEVED, EXPIRED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Polling Strategy
To avoid burning tokens or CPU with high-frequency empty calls:
1. **Initial Delay:** Pulse-check 2 seconds after `ask_parent`.
2. **Adaptive Interval:** Start at 5s, doubling until a max of 30s.
3. **External Trigger:** If the parent environment supports it, we can use a Unix Socket or Signal to "wake up" the worker poll, but polling is the fallback "air-gap" safe method.

## Edge Case Handling

### Parent Offline
- **Behavior:** `ask_parent` still succeeds in writing to the SQLite bus.
- **Outcome:** The Worker continues to poll. When the parent eventually connects/wakes up and checks `get_pending_questions`, the query is waiting.

### Worker Timeout
- **Behavior:** If the worker reaches its max timeout (e.g., 10 minutes) while polling.
- **Outcome:** Worker terminates and marks the task as `stalled`. The parent must manually resume or retry.

### Multiple Pending Questions
- **Policy:** A worker SHOULD NOT ask a second question until the first is answered (`RETRIEVED`). 
- **Exception:** Critical "panic" messages can be logged without polling, but for the bi-directional loop, we enforce a strict 1-at-a-time blocking question policy per `subagent_id`.

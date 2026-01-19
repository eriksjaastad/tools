# Unified Agent System Implementation Prompts

**Target:** Complete Phases 1-4 of PRD_UNIFIED_AGENT_SYSTEM.md
**Reference:** `/Users/eriksjaastad/projects/_tools/PRD_UNIFIED_AGENT_SYSTEM.md`
**Tracking:** Timed implementation

---

## Progress Tracker

| Prompt | Phase | Status | Notes |
|--------|-------|--------|-------|
| Prompt 1: Adaptive Polling | 1 | 🔲 TODO | |
| Prompt 2: Cost Logging | 1 | 🔲 TODO | |
| Prompt 3: Model Router | 2 | 🔲 TODO | |
| Prompt 4: Fallback Chains | 2 | 🔲 TODO | |
| Prompt 5: Environment Detection | 2 | 🔲 TODO | |
| Prompt 6: SQLite Message Bus | 3 | 🔲 TODO | |
| Prompt 7: Bi-Directional Messaging | 3 | 🔲 TODO | |
| Prompt 8: Budget Manager | 4 | 🔲 TODO | |
| Prompt 9: Pre-Flight Checks | 4 | 🔲 TODO | |
| Prompt 10: Integration & Tests | All | 🔲 TODO | |
| **Code Review** | - | 🔲 TODO | |

---

## Context

The agent-hub system already exists at `/Users/eriksjaastad/projects/_tools/agent-hub/`. We're extending it with new capabilities, not starting from scratch.

Key existing files:
- `agent-hub/src/watchdog.py` - State machine, circuit breakers
- `agent-hub/src/listener.py` - Message loop
- `agent-hub/src/hub_client.py` - MCP communication
- `agent-hub/config/` - Configuration files

MCP servers (Go, complete):
- `claude-mcp-go/` - Hub messaging, review tools
- `ollama-mcp-go/` - Ollama HTTP client, draft tools, agent loop

---

## Prompt 1: Adaptive Polling (Phase 1)

### Task
Implement adaptive polling that speeds up on activity and slows down when idle.

### Instructions

```
Add adaptive polling to the agent-hub listener.

Location: agent-hub/src/listener.py (modify existing) or new file

Requirements from PRD (FR-1.3):
- Start polling at 1-second intervals
- Backoff to 10-second intervals when idle
- Reset to 1-second on new activity

Implementation:
1. Create AdaptivePoller class:
   - min_interval: 1.0 seconds
   - max_interval: 10.0 seconds
   - backoff_factor: 1.5
   - current_interval: starts at min

2. Poll logic:
   - If activity detected: reset to min_interval
   - If no activity: current_interval *= backoff_factor (capped at max)
   - Sleep for current_interval between polls

3. "Activity" means:
   - New message received
   - State change detected
   - User input received

4. Integrate with existing listener.py message loop

Do NOT run tests - that will be done during code review.
```

### Definition of Done
- [ ] AdaptivePoller class implemented
- [ ] Integrated with listener.py
- [ ] Polling speeds up on activity
- [ ] Polling slows down when idle
- [ ] Code compiles/runs without errors

---

## Prompt 2: Cost Logging (Phase 1)

### Task
Implement basic cost logging for all model calls.

### Instructions

```
Create a cost logger that tracks all model calls.

Location: agent-hub/src/cost_logger.py (new file)

Requirements from PRD (FR-4.1):
- Track Local (compute) vs Cloud (API dollars) separately
- Log tokens, model, and cost per call
- Persist cost data across sessions

Implementation:
1. Create CostLogger class:
   - log_file: Path to audit.ndjson (append-only)
   - persist_file: Path to budget_state.json

2. Implement log_call method:
   - Parameters: model, input_tokens, output_tokens, cost_usd, is_local
   - Write NDJSON line with timestamp
   - Update running totals in memory

3. Implement get_session_totals method:
   - Returns: { local_calls, cloud_calls, local_tokens, cloud_tokens, cloud_cost_usd }

4. Implement persist/load for budget_state.json:
   - Save: daily totals, session totals
   - Load: restore on startup

5. Cost calculation:
   - Local models: $0
   - Gemini Flash: $0.0001 per 1K tokens
   - Claude Sonnet: $0.003 per 1K tokens

Reference config: agent-hub/config/routing.yaml (if exists) or create

Do NOT run tests - that will be done during code review.
```

### Definition of Done
- [ ] CostLogger class implemented
- [ ] NDJSON logging works
- [ ] Session totals tracked
- [ ] State persists across restarts
- [ ] Code compiles/runs without errors

---

## Prompt 3: Model Router (Phase 2)

### Task
Implement the model routing layer using LiteLLM.

### Instructions

```
Create a model router that selects the appropriate tier based on task type and complexity.

Location: agent-hub/src/router.py (new file)

Requirements from PRD (FR-2.1):
- Support three tiers: Free (Ollama), Cheap (Gemini), Premium (Claude)
- Route based on task type and complexity
- Allow tier configuration via YAML

Implementation:
1. Create Router class:
   - Load config from agent-hub/config/routing.yaml
   - Use litellm library for provider abstraction

2. Implement route method:
   - Parameters: task_type (str), complexity (str), input_tokens (int)
   - Returns: ModelSelection { model, tier, fallback_chain }

3. Task types: triage, implementation, review, judge
4. Complexity levels: simple, medium, complex

5. Routing matrix (from PRD Section 6.2):
   - triage/any → local
   - implementation/simple,medium → local, complex → cheap
   - review/simple → local, medium → cheap, complex → premium
   - judge/simple → cheap, medium,complex → premium

6. Create config/routing.yaml with tier definitions:
   - local: ollama/qwen2.5-coder:14b, ollama/deepseek-r1-distill:32b
   - cheap: gemini/gemini-2.0-flash
   - premium: anthropic/claude-sonnet-4

Do NOT run tests - that will be done during code review.
```

### Definition of Done
- [ ] Router class implemented
- [ ] Config loaded from YAML
- [ ] route() returns correct tier per matrix
- [ ] LiteLLM integration works
- [ ] Code compiles/runs without errors

---

## Prompt 4: Fallback Chains (Phase 2)

### Task
Implement automatic fallback when models fail.

### Instructions

```
Extend the router with fallback chain execution.

Location: agent-hub/src/router.py (extend existing)

Requirements from PRD (FR-2.2):
- Automatically try next tier on model failure
- Implement cooldown cache for failing models
- Log all fallback events with reason

Implementation:
1. Add to Router class:
   - cooldown_cache: dict mapping model → expiry_timestamp
   - cooldown_seconds: 300 (from config)

2. Implement execute_with_fallback method:
   - Parameters: selection (ModelSelection), prompt (str), system (str)
   - Try primary model
   - On failure: log reason, add to cooldown, try next in chain
   - Continue until success or chain exhausted
   - Return: Response or raise after all failures

3. Implement is_model_cooled_down method:
   - Check if model is in cooldown cache
   - Return True if available, False if cooling down

4. Implement add_to_cooldown method:
   - Add model to cache with expiry = now + cooldown_seconds

5. Fallback chains:
   - local → cheap → premium
   - cheap → premium
   - premium → (fail, no fallback)

6. Log format for fallback events:
   - { timestamp, original_model, failed_reason, fallback_model, attempt }

Do NOT run tests - that will be done during code review.
```

### Definition of Done
- [ ] execute_with_fallback implemented
- [ ] Cooldown cache works
- [ ] Fallback events logged
- [ ] Chain traversal works correctly
- [ ] Code compiles/runs without errors

---

## Prompt 5: Environment Detection (Phase 2)

### Task
Detect which environment the agent is running in.

### Instructions

```
Create environment detection and adapter system.

Location: agent-hub/src/environment.py (new file)

Requirements from PRD (FR-5.1, FR-5.2):
- Detect Claude CLI via CLAUDE_SESSION_ID env var
- Detect Cursor via CURSOR_SESSION or .cursor/ directory
- Detect Anti-Gravity via ANTIGRAVITY_SESSION env var
- Implement adapters for each environment

Implementation:
1. Create Environment enum:
   - CLAUDE_CLI
   - CURSOR
   - ANTIGRAVITY
   - UNKNOWN

2. Create detect_environment function:
   - Check env vars in order
   - Check for .cursor/ directory as fallback
   - Return Environment enum

3. Create base EnvironmentAdapter class:
   - notify(message) - send notification to user
   - trigger_agent(prompt) - spawn sub-agent if supported
   - get_mcp_config_path() - return config file path

4. Create ClaudeCLIAdapter:
   - notify: print to stdout
   - trigger_agent: not supported (already in session)
   - mcp_config: ~/.claude/mcp.json

5. Create CursorAdapter:
   - notify: print to stdout
   - trigger_agent: subprocess call to cursor-agent
   - mcp_config: ~/.cursor/mcp.json

6. Create AntigravityAdapter:
   - notify: write to _handoff/notifications.md
   - trigger_agent: write to _handoff/pending_tasks.json
   - mcp_config: ~/.antigravity/mcp.json

7. Create get_adapter function:
   - Detect environment, return appropriate adapter

Do NOT run tests - that will be done during code review.
```

### Definition of Done
- [ ] Environment detection works
- [ ] All three adapters implemented
- [ ] Adapters have correct MCP config paths
- [ ] Code compiles/runs without errors

---

## Prompt 6: SQLite Message Bus (Phase 3)

### Task
Implement SQLite-backed message bus for agent communication.

### Instructions

```
Create a SQLite message bus to replace file-based messaging.

Location: agent-hub/src/message_bus.py (new file)

Requirements from PRD (FR-3.2):
- Use SQLite database (hub.db) for message storage
- Support concurrent read/write from multiple agents
- Maintain backward compatibility with file-based state during transition

Implementation:
1. Create MessageBus class:
   - db_path: Path to hub.db
   - Initialize with connection pool (sqlite3)

2. Create schema (on init):
   ```sql
   CREATE TABLE IF NOT EXISTS messages (
     id TEXT PRIMARY KEY,
     type TEXT NOT NULL,
     from_agent TEXT NOT NULL,
     to_agent TEXT NOT NULL,
     payload TEXT,  -- JSON
     timestamp TEXT NOT NULL,
     read INTEGER DEFAULT 0
   );
   
   CREATE TABLE IF NOT EXISTS heartbeats (
     agent_id TEXT PRIMARY KEY,
     progress TEXT,
     timestamp TEXT NOT NULL
   );
   
   CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_agent);
   CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
   ```

3. Implement CRUD methods:
   - send_message(msg: Message) -> str (returns id)
   - get_messages(to_agent: str, since: datetime = None) -> List[Message]
   - mark_read(message_id: str)
   - update_heartbeat(agent_id: str, progress: str)
   - get_heartbeats() -> Dict[str, Heartbeat]

4. Implement migration from file-based state:
   - If hub_state.json exists and hub.db is empty, import messages
   - Log migration event

5. Use WAL mode for concurrent access:
   - PRAGMA journal_mode=WAL;

Do NOT run tests - that will be done during code review.
```

### Definition of Done
- [ ] SQLite schema created
- [ ] All CRUD methods work
- [ ] WAL mode enabled
- [ ] Migration from file-based state works
- [ ] Code compiles/runs without errors

---

## Prompt 7: Bi-Directional Messaging (Phase 3)

### Task
Implement ask/reply protocol for agent communication.

### Instructions

```
Create bi-directional messaging tools for workers to ask questions.

Location: agent-hub/src/bidirectional.py (new file)

Requirements from PRD (FR-3.1):
- ask_parent(question) for workers
- reply_to_worker(message_id, answer) for parents
- check_answer(message_id) for workers
- get_pending_questions(run_id) for parents

Implementation:
1. Create BidirectionalMessenger class:
   - Uses MessageBus for storage
   - Tracks question/answer pairs

2. Implement ask_parent:
   - Parameters: question (str), context (dict, optional), timeout_seconds (int, default 300)
   - Create message with type="QUESTION"
   - Return message_id for polling

3. Implement reply_to_worker:
   - Parameters: message_id (str), answer (str)
   - Create message with type="ANSWER", referencing original question
   - Return success/failure

4. Implement check_answer:
   - Parameters: message_id (str)
   - Look for ANSWER message referencing this question
   - Return answer string or None if pending

5. Implement get_pending_questions:
   - Parameters: run_id (str, optional)
   - Return all QUESTION messages without corresponding ANSWER
   - Filter by run_id if provided

6. Message types:
   - QUESTION: { question, context, asked_at }
   - ANSWER: { question_id, answer, answered_at }

7. Integrate with existing claude-mcp-go hub tools (they use file-based state)

Do NOT run tests - that will be done during code review.
```

### Definition of Done
- [ ] All four methods implemented
- [ ] Questions can be asked and answered
- [ ] Polling for answers works
- [ ] Pending questions can be retrieved
- [ ] Code compiles/runs without errors

---

## Prompt 8: Budget Manager (Phase 4)

### Task
Implement budget tracking and limits.

### Instructions

```
Create a budget manager with session and daily limits.

Location: agent-hub/src/budget_manager.py (new file)

Requirements from PRD (FR-4.2, FR-4.3):
- Estimate cost before execution
- Halt if estimated cost exceeds session limit
- Allow explicit override for budget exceptions
- Support configurable session and daily limits
- Alert when approaching limits

Implementation:
1. Create BudgetManager class:
   - Uses CostLogger for tracking
   - Load limits from config/budget.yaml

2. Create config/budget.yaml:
   ```yaml
   limits:
     session_usd: 5.0
     daily_usd: 10.0
   alerts:
     warn_at_percent: 80
     halt_at_percent: 100
   enforcement:
     pre_flight_check: true
     allow_override: true
   ```

3. Implement estimate_cost:
   - Parameters: model (str), input_tokens (int), estimated_output_tokens (int)
   - Return estimated cost in USD

4. Implement can_afford:
   - Parameters: estimated_cost (float)
   - Check against session and daily limits
   - Return: { allowed: bool, reason: str, remaining_budget: float }

5. Implement record_spend:
   - Parameters: model, tokens, cost, is_local
   - Delegate to CostLogger
   - Check if approaching limits, trigger alerts

6. Implement get_status:
   - Return: { session_spent, session_limit, daily_spent, daily_limit, percent_used }

7. Implement override_budget:
   - Parameters: amount (float), reason (str)
   - Log override event
   - Temporarily allow exceeding limit

Do NOT run tests - that will be done during code review.
```

### Definition of Done
- [ ] BudgetManager class implemented
- [ ] Config loaded from YAML
- [ ] Estimation works
- [ ] Limits enforced
- [ ] Override mechanism works
- [ ] Code compiles/runs without errors

---

## Prompt 9: Pre-Flight Checks (Phase 4)

### Task
Implement pre-flight budget and capability checks.

### Instructions

```
Add pre-flight checks before executing model calls.

Location: agent-hub/src/preflight.py (new file)

Requirements from PRD (FR-4.2):
- Estimate cost before execution
- Halt if estimated cost exceeds session limit
- Allow explicit override for budget exceptions

Implementation:
1. Create PreFlightChecker class:
   - Uses BudgetManager for cost checks
   - Uses Router for capability checks

2. Implement check method:
   - Parameters: task_type, complexity, estimated_tokens, allow_override
   - Returns: PreFlightResult { 
       approved: bool, 
       model: str, 
       estimated_cost: float,
       warnings: List[str],
       halt_reason: str (if not approved)
     }

3. Check sequence:
   a. Route to get model selection
   b. Estimate cost for selected model
   c. Check budget with can_afford
   d. If budget exceeded and allow_override=False, halt
   e. If budget exceeded and allow_override=True, add warning
   f. Return result

4. Integrate with agent loop:
   - Before each model call, run pre-flight
   - If not approved, create ERIK_HALT.md with context
   - Halt execution

5. ERIK_HALT.md format:
   ```markdown
   # Agent Halt: Budget Exceeded
   
   **Time:** {timestamp}
   **Task:** {task_type} ({complexity})
   **Estimated Cost:** ${estimated_cost}
   **Session Remaining:** ${remaining}
   
   ## Context
   {context}
   
   ## Options
   1. Override and continue: `hub override {amount}`
   2. Reduce scope
   3. Wait for daily reset
   ```

Do NOT run tests - that will be done during code review.
```

### Definition of Done
- [ ] PreFlightChecker implemented
- [ ] Integrates with budget and router
- [ ] ERIK_HALT.md created on budget halt
- [ ] Override flow works
- [ ] Code compiles/runs without errors

---

## Prompt 10: Integration & Tests (All Phases)

### Task
Wire everything together and write unit tests.

### Instructions

```
Integrate all new components and write comprehensive tests.

1. Integration in agent-hub/src/hub.py (new or modify existing):
   - Initialize all components on startup
   - Wire dependencies correctly
   - Expose unified API

2. Startup sequence:
   a. Detect environment
   b. Load configs (routing.yaml, budget.yaml)
   c. Initialize CostLogger
   d. Initialize MessageBus (with migration check)
   e. Initialize Router with LiteLLM
   f. Initialize BudgetManager
   g. Initialize BidirectionalMessenger
   h. Initialize AdaptivePoller
   i. Start message loop

3. Write unit tests in agent-hub/tests/:
   - test_adaptive_poller.py
   - test_cost_logger.py
   - test_router.py
   - test_fallback.py
   - test_environment.py
   - test_message_bus.py
   - test_bidirectional.py
   - test_budget_manager.py
   - test_preflight.py

4. Test patterns:
   - Use pytest
   - Mock external services (LiteLLM, Ollama)
   - Use temp directories for file operations
   - Use in-memory SQLite for message bus tests

5. Verify all PRD Section 9 unit tests can pass:
   - [ ] Ollama HTTP client connection pooling → ollama-mcp-go
   - [ ] Router tier selection logic → test_router.py
   - [ ] Fallback chain execution → test_fallback.py
   - [ ] Budget estimation accuracy → test_budget_manager.py
   - [ ] SQLite message bus CRUD operations → test_message_bus.py
   - [ ] Environment detection logic → test_environment.py

Do NOT run tests yourself - report back when files are created.
```

### Definition of Done
- [ ] All components integrated in hub.py
- [ ] Startup sequence works
- [ ] All 9 test files created
- [ ] Tests cover PRD Section 9.1 requirements
- [ ] Code compiles without errors

---

## Code Review Checklist

**IMPORTANT:** These checks are run by Erik/Super Manager, NOT the Floor Manager.

### After All Prompts Complete

```bash
# Run all tests
cd agent-hub && pytest tests/ -v

# Check for lint errors
ruff check src/

# Verify imports
python -c "from src.hub import Hub; print('OK')"
```

### PRD Section 9.1 Verification

| Test | Command | Expected |
|------|---------|----------|
| Router tier selection | `pytest tests/test_router.py -v` | PASS |
| Fallback chain | `pytest tests/test_fallback.py -v` | PASS |
| Budget estimation | `pytest tests/test_budget_manager.py -v` | PASS |
| SQLite message bus | `pytest tests/test_message_bus.py -v` | PASS |
| Environment detection | `pytest tests/test_environment.py -v` | PASS |

### Integration Verification

```bash
# Start hub and verify components initialize
python -m src.hub --dry-run

# Verify MCP servers connect
echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | ./ollama-mcp-go/bin/server
echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | ./claude-mcp-go/bin/server
```

---

## Notes

- All new code goes in `agent-hub/src/`
- Use existing patterns from `watchdog.py` and `listener.py`
- Integrate with existing circuit breakers in `watchdog.py`
- LiteLLM handles provider abstraction - don't reimplement
- SQLite is the source of truth for messages, file-based is legacy

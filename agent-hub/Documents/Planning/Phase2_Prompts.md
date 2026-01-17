# Phase 2: Contract-Driven Pipeline - Floor Manager Prompts

> **For:** Gemini 3 Flash (Floor Manager in Cursor)  
> **Context:** Agent Hub implementation  
> **Created:** 2026-01-17

These prompts are designed to be handed to the Floor Manager (Gemini) for execution. Each includes done criteria and tests where appropriate.

---

## Prompt 2.1: TASK_CONTRACT.json Schema Validation

```markdown
# Floor Manager Task: Implement Contract Schema Validation

You are the Floor Manager. Implement schema validation for TASK_CONTRACT.json.

## Context

The TASK_CONTRACT.json is the single source of truth for the Agent Hub pipeline. Before any agent processes a contract, we need to validate it against our V2 schema.

## Source Material

Read these files:
1. `_tools/agent-hub/Documents/Agentic Blueprint Setup V2.md` - Section 2 (The Schema)
2. `_tools/agent-hub/PRD.md` - FR-00 through FR-10

## Requirements

Create `_tools/agent-hub/src/validators.py` with:

1. **`validate_contract(contract: dict) -> tuple[bool, list[str]]`**
   - Returns (is_valid, list_of_errors)
   - Checks required fields exist
   - Checks status is a valid value
   - Checks complexity is valid (trivial/minor/major/critical)
   - Checks paths in allowed_paths don't overlap with forbidden_paths

2. **`load_and_validate(path: Path) -> dict`**
   - Loads JSON from file
   - Validates schema
   - Raises `ContractValidationError` if invalid
   - Returns parsed contract if valid

3. **Required field validation:**
   - schema_version (must be "2.0")
   - task_id (non-empty string)
   - project (non-empty string)
   - status (one of the valid statuses)
   - specification.target_file (must exist)
   - specification.requirements (non-empty list)

## Done Criteria ✓

- [x] `validators.py` exists in `_tools/agent-hub/src/`
- [x] `validate_contract()` catches missing required fields
- [x] `validate_contract()` catches invalid status values
- [x] `validate_contract()` catches path conflicts (allowed vs forbidden)
- [x] `load_and_validate()` raises clear error messages
- [x] All functions have type hints and docstrings

## Tests Required

Create `_tools/agent-hub/tests/test_validators.py`:

- [x] Test: Valid contract passes validation
- [x] Test: Missing task_id fails with clear error
- [x] Test: Invalid status value fails
- [x] Test: Path in both allowed and forbidden fails
- [x] Test: Empty requirements list fails
- [x] Test: Wrong schema_version fails

## Output Files

- `_tools/agent-hub/src/validators.py`
- `_tools/agent-hub/tests/test_validators.py`
- Update `_tools/agent-hub/requirements.txt` if new deps needed
```

---

## Prompt 2.2: Watchdog State Machine

```markdown
# Floor Manager Task: Implement Watchdog State Machine

You are the Floor Manager. Implement the core state machine for Agent Hub.

## Context

The watchdog manages state transitions for tasks. It's the heart of the pipeline - detecting status changes, invoking models, and handling circuit breakers.

## Source Material

Read these files:
1. `_tools/agent-hub/Documents/Agentic Blueprint Setup V2.md` - Section 4 (State Machine) and Section 5 (Circuit Breaker)
2. `_tools/agent-hub/PRD.md` - FR-05 through FR-10, NFR-03 through NFR-08

## Requirements

Create `_tools/agent-hub/src/watchdog.py` with:

1. **State Machine Core:**
   ```python
   VALID_STATUSES = [
       "pending_implementer",
       "implementation_in_progress",
       "pending_local_review",
       "pending_judge_review",
       "judge_review_in_progress",
       "review_complete",
       "pending_rebuttal",
       "merged",
       "timeout_implementer",
       "timeout_judge",
       "erik_consultation"
   ]
   
   def transition(state: str, event: str, contract: dict) -> tuple[str, str]:
       """Returns (new_status, status_reason). Raises InvalidTransition if not allowed."""
   ```

2. **Lock Mechanism:**
   ```python
   def acquire_lock(contract: dict, actor: str) -> bool:
       """Try to acquire lock. Returns False if held by another actor."""
   
   def release_lock(contract: dict) -> None:
       """Release the lock."""
   ```

3. **Circuit Breaker Checks:**
   ```python
   def check_circuit_breakers(contract: dict) -> tuple[bool, str]:
       """Returns (should_halt, reason). Checks all 9 triggers from V2 doc."""
   ```

4. **Contract Operations:**
   ```python
   def load_contract(path: Path) -> dict:
   def save_contract(contract: dict, path: Path) -> None:  # Atomic write
   def log_transition(contract: dict, event: str, old_status: str) -> None:
   ```

## Done Criteria ✓

- [x] `watchdog.py` exists in `_tools/agent-hub/src/`
- [x] All valid status transitions are defined
- [x] Invalid transitions raise `InvalidTransition` error
- [x] Lock mechanism prevents concurrent modifications
- [x] All 9 circuit breaker conditions are checked
- [x] `save_contract()` uses atomic write (temp → rename)
- [x] Transitions are logged to `transition.ndjson`
- [x] All functions have type hints and docstrings

## Tests Required

Create `_tools/agent-hub/tests/test_watchdog.py`:

- [x] Test: Valid transition succeeds
- [x] Test: Invalid transition raises error
- [x] Test: Lock acquisition works
- [x] Test: Lock blocks second actor
- [x] Test: Expired lock can be acquired
- [x] Test: Rebuttal limit triggers circuit breaker
- [x] Test: Timeout triggers circuit breaker
- [x] Test: Atomic write survives interruption (mock)

## Output Files

- `_tools/agent-hub/src/watchdog.py`
- `_tools/agent-hub/tests/test_watchdog.py`
```

---

## Prompt 2.3: Watcher Shell Script

```markdown
# Floor Manager Task: Create Claude CLI Watcher Script

You are the Floor Manager. Create the bash watcher that invokes Claude CLI for Judge reviews.

## Context

Claude CLI doesn't have a daemon mode. We use a simple bash loop that polls for review requests and invokes Claude once per request.

## Source Material

Read: `_tools/agent-hub/Documents/Agentic Blueprint Setup V2.md` - Section 7 (Watcher Implementation)

## Requirements

Create `_tools/agent-hub/src/watcher.sh`:

1. **Poll Loop:**
   - Check for `_handoff/REVIEW_REQUEST.md` every 5 seconds
   - When found, move to `REVIEW_IN_PROGRESS.md` (prevent double-trigger)
   - Invoke Claude CLI once with Judge prompt
   - Use `timeout` command with 15 minute limit
   - Handle timeout gracefully (update contract status)
   - Clean up marker files

2. **Claude Invocation:**
   - Use `claude --dangerously-skip-permissions` for non-interactive
   - Pass the Judge prompt from V2 doc
   - Capture exit code

3. **Atomic Output:**
   - Claude writes to `.tmp` files
   - Script renames to final filenames

4. **Logging:**
   - Echo timestamped status messages
   - Log to `_handoff/watcher.log`

## Done Criteria ✓

- [x] `watcher.sh` exists and is executable
- [x] Polls every 5 seconds
- [x] Prevents double-trigger with marker file
- [x] Invokes Claude once per request (no internal looping)
- [x] Handles 15-minute timeout
- [x] Uses atomic file renames
- [x] Logs all actions with timestamps

## Tests (Manual)

- [ ] Start watcher, create REVIEW_REQUEST.md, verify Claude is invoked
- [ ] Kill watcher mid-review, verify no corruption
- [ ] Create request while review in progress, verify no double-trigger

## Output Files

- `_tools/agent-hub/src/watcher.sh` (chmod +x)
```

---

## Prompt 2.4: Atomic File Operations

```markdown
# Floor Manager Task: Implement Atomic File Operations

You are the Floor Manager. Create utility functions for safe file operations.

## Context

Race conditions are a major risk. All handoff files must be written atomically (temp file → rename) to prevent partial reads.

## Source Material

Read: `_tools/agent-hub/Documents/Agentic Blueprint Setup V2.md` - Section 3 (Atomic Write Protocol)

## Requirements

Add to `_tools/agent-hub/src/utils.py`:

1. **`atomic_write(path: Path, content: str) -> None`**
   - Write to `{path}.tmp`
   - Rename to `{path}` (atomic on POSIX)
   - Handle errors (cleanup temp file)

2. **`atomic_write_json(path: Path, data: dict) -> None`**
   - JSON serialize with indent=2
   - Call atomic_write

3. **`safe_read(path: Path) -> str | None`**
   - Return None if file doesn't exist
   - Return content if exists
   - Handle partial read (check for tmp file, wait briefly)

4. **`archive_file(path: Path, archive_dir: Path, suffix: str = "") -> Path`**
   - Move file to archive directory
   - Add suffix (e.g., task_id) to filename
   - Return new path

## Done Criteria ✓

- [x] `utils.py` exists in `_tools/agent-hub/src/`
- [x] `atomic_write()` uses temp → rename pattern
- [x] `atomic_write()` cleans up temp file on error
- [x] `atomic_write_json()` produces valid JSON
- [x] `safe_read()` handles missing files gracefully
- [x] `archive_file()` creates archive dir if needed

## Tests Required

Create `_tools/agent-hub/tests/test_utils.py`:

- [ ] Test: atomic_write creates file
- [ ] Test: atomic_write doesn't leave temp file on success
- [ ] Test: atomic_write cleans up temp on error
- [ ] Test: safe_read returns None for missing file
- [ ] Test: archive_file moves and renames correctly

## Output Files

- `_tools/agent-hub/src/utils.py`
- `_tools/agent-hub/tests/test_utils.py`
```

---

## Prompt 2.5: Proposal → Contract Conversion

```markdown
# Floor Manager Task: Implement Proposal to Contract Conversion

You are the Floor Manager. Implement the logic that converts PROPOSAL_FINAL.md to TASK_CONTRACT.json.

## Context

When Super Manager writes PROPOSAL_FINAL.md, the Floor Manager must parse it and create a valid contract. This is the bridge between human planning and machine execution.

## Source Material

Read:
1. `_tools/agent-hub/Documents/Agentic Blueprint Setup V2.md` - Section 1 (Proposal Flow), Section 2 (Schema)
2. `_tools/agent-hub/templates/PROPOSAL_FINAL.template.md` - Expected proposal format
3. `_tools/agent-hub/PRD.md` - FR-00, FR-00a

## Requirements

Create `_tools/agent-hub/src/proposal_converter.py`:

1. **`parse_proposal(content: str) -> dict`**
   - Extract: title, target_project, complexity
   - Extract: source_files, target_file
   - Extract: requirements (as list)
   - Extract: acceptance_criteria (as list)
   - Extract: constraints (allowed_paths, forbidden_paths, delete_allowed)
   - Return structured dict

2. **`generate_task_id(project: str, title: str) -> str`**
   - Format: `{PROJECT}-{SEQUENCE}-{SLUG}`
   - Example: `PROJECT-A-001-AUTH-MERGE`

3. **`create_contract(proposal: dict) -> dict`**
   - Build full TASK_CONTRACT.json structure
   - Set schema_version to "2.0"
   - Set appropriate limits based on complexity
   - Set cost ceiling based on complexity
   - Initialize handoff_data, lock, breaker, history

4. **`convert_proposal(proposal_path: Path, handoff_dir: Path) -> Path`**
   - Read proposal
   - Parse and validate
   - Generate contract
   - Write to handoff_dir/TASK_CONTRACT.json (atomic)
   - Archive proposal to handoff_dir/archive/
   - Return contract path

5. **Rejection handling:**
   - If proposal is malformed, write PROPOSAL_REJECTED.md
   - Include specific issues and what's needed

## Done Criteria ✓

- [x] `proposal_converter.py` exists in `_tools/agent-hub/src/`
- [x] Parses all sections from template format
- [x] Generates unique task IDs
- [x] Creates schema-valid contracts
- [x] Sets complexity-based limits ($0.25 - $5.00)
- [x] Archives proposal after conversion
- [x] Writes PROPOSAL_REJECTED.md for malformed proposals

## Tests Required

Create `_tools/agent-hub/tests/test_proposal_converter.py`:

- [ ] Test: Valid proposal converts to valid contract
- [ ] Test: Missing target_file triggers rejection
- [ ] Test: Empty requirements triggers rejection
- [ ] Test: Complexity "major" gets $2.00 ceiling
- [ ] Test: Task ID generation is unique
- [ ] Test: Proposal is archived after conversion

## Output Files

- `_tools/agent-hub/src/proposal_converter.py`
- `_tools/agent-hub/tests/test_proposal_converter.py`
```

---

## Prompt 2.6: End-to-End Test

```markdown
# Floor Manager Task: Create End-to-End Integration Test

You are the Floor Manager. Create a test that runs a simple task through the entire pipeline.

## Context

We need to verify all components work together. This test uses a mock/simple task to exercise the full flow.

## Source Material

Read:
1. `_tools/agent-hub/Documents/Agentic Blueprint Setup V2.md` - Full document
2. `_tools/agent-hub/PRD.md` - Definition of Done

## Requirements

Create `_tools/agent-hub/tests/test_e2e.py`:

**CRITICAL IMPLEMENTATION NOTE:** This test must be fully self-contained. Do NOT attempt to run the actual `watcher.sh` or `watchdog.py` as separate processes. You MUST mock `subprocess.run` and any external system calls to simulate the behavior of the other agents. The goal is to test the *logic* of the pipeline, not the operating system's process management.

1. **Test Setup:**
   - Create temp directory for test
   - Create mock `_handoff/` structure
   - Create sample source files

2. **Test: Full Pipeline (Mocked Models)**
   - Write a simple PROPOSAL_FINAL.md
   - Call proposal_converter to create contract
   - Verify contract is valid
   - Simulate implementer (write mock output)
   - Simulate local review (pass)
   - Simulate judge (PASS verdict)
   - Verify final status is "merged"

3. **Test: Circuit Breaker Triggers**
   - Create contract at rebuttal limit
   - Trigger one more rebuttal
   - Verify status becomes "erik_consultation"
   - Verify ERIK_HALT.md is created

4. **Test: Stall Recovery**
   - Create contract
   - Simulate timeout
   - Verify Two-Strike flow
   - Verify STALL_REPORT.md on second strike

## Done Criteria ✓

- [x] `test_e2e.py` exists in `_tools/agent-hub/tests/`
- [x] Full pipeline test passes with mocks
- [x] Circuit breaker test verifies halt behavior
- [x] Stall recovery test verifies Two-Strike Rule
- [x] All tests clean up temp files
- [x] Tests can run without Ollama/Claude (mocked)

## Output Files

- `_tools/agent-hub/tests/test_e2e.py`
- `_tools/agent-hub/tests/conftest.py` (shared fixtures)
```

---

## Execution Order

1. **2.4 first** - Atomic file operations (utils.py) - other modules depend on this
2. **2.1 second** - Schema validation - needed before contracts can be used
3. **2.5 third** - Proposal conversion - creates contracts
4. **2.2 fourth** - Watchdog state machine - core logic
5. **2.3 fifth** - Watcher script - ties to watchdog
6. **2.6 last** - E2E test - verifies everything works together

---

*Prompts created by Super Manager (Claude Opus 4.5) for Floor Manager (Gemini 3 Flash) execution.*

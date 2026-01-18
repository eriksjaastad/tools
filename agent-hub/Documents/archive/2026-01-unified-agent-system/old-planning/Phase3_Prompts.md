# Phase 3: Resilience & Advanced Circuit Breakers

> **For:** Gemini 3 Flash (Floor Manager in Cursor)  
> **Context:** Agent Hub implementation  
> **Created:** 2026-01-17

These prompts finalize the circuit breaker logic in `watchdog.py` and ensure the internal state machine is bulletproof before we introduce Git integration in Phase 4.

---

## Prompt 3.1: Finalizing Circuit Breakers (9/9)

```markdown
# Floor Manager Task: Implement Remaining Circuit Breakers

You are the Floor Manager. We have 6 out of 9 circuit breakers implemented in `watchdog.py`. Complete the set.

## Context

Refer to `Documents/Agentic Blueprint Setup V2.md` - Section 5. We need to implement the three missing triggers to prevent the AI from wasting money or corrupting files.

## Requirements

Update `check_circuit_breakers` in `_tools/agent-hub/src/watchdog.py` to include:

1. **Trigger 2: Destructive Diff**
   - If `diff_lines_deleted / total_lines_in_file > 0.5` (or 50% for now), trigger halt.
   - Note: You may need to add a simple utility or use `handoff_data` to track this if not already provided.

2. **Trigger 4: Hallucination Loop**
   - Check `history` in the contract.
   - If the current file hash (SHA256) matches a hash that was previously rejected by a Judge verdict of "FAIL", trigger halt.

3. **Trigger 5: GPT-Energy Nitpicking**
   - If `review_cycle_count >= 3` AND all issues in the `JUDGE_REPORT.json` are tagged with suggestions or descriptions containing keywords like "style", "formatting", "indentation", or "spacing" (and no "BLOCKING" issues), trigger halt.
   - This prevents agents from arguing over tabs vs spaces.

## Done Criteria ✓

- [x] `check_circuit_breakers()` now handles all 9 triggers.
- [x] Hallucination detection correctly scans the contract history.
- [x] Nitpicking detection parses the `JUDGE_REPORT.json` for style-related keywords.
- [x] All functions have type hints and updated docstrings.

## Tests Required

Update `_tools/agent-hub/tests/test_watchdog.py`:

- [x] Test: Destructive diff (above 50%) triggers halt.
- [x] Test: Hash match with previously failed attempt triggers halt.
- [x] Test: 3 cycles of pure style/formatting suggestions triggers halt.

## Output Files

- `_tools/agent-hub/src/watchdog.py`
- `_tools/agent-hub/tests/test_watchdog.py`
```

---

## Prompt 3.2: Error Handling & Reliability Audit

```markdown
# Floor Manager Task: Reliability Audit

You are the Floor Manager. Audit the existing `src/` files for common edge cases and error handling.

## Requirements

1. **`src/utils.py`**:
   - Ensure `safe_read()` handles file locking at the OS level if possible, or at least retries more aggressively (3 times) before giving up.
   
2. **`src/watchdog.py`**:
   - Add a "Global Timeout" check. Even if individual steps don't time out, if the total time since `created_at` exceeds 4 hours, halt.
   - Ensure `save_contract` properly handles PermissionError or DiskFull errors.

3. **Logging**:
   - Ensure `transition.ndjson` captures the `status_reason` for every transition, not just the event.

## Done Criteria ✓

- [x] Comprehensive error handling in `utils.py`.
- [x] Global task timeout implemented.
- [x] Transition logs enriched with reasons.

## Output Files

- `_tools/agent-hub/src/utils.py`
- `_tools/agent-hub/src/watchdog.py`
```

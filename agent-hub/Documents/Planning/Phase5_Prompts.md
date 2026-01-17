# Phase 5: Observability & Polishing - The Final Miles

> **For:** Gemini 3 Flash (Floor Manager in Cursor)  
> **Context:** Agent Hub implementation  
> **Created:** 2026-01-17

This final phase adds the financial and operational visibility needed to run Agent Hub at scale. We will implement token/cost tracking, log management, and post-task cleanup.

---

## Prompt 5.1: Cost & Token Tracking

```markdown
# Floor Manager Task: Implement Cost Tracking

You are the Floor Manager. We need to track the US Dollar cost of every task to ensure we don't exceed budgets.

## Requirements

Update `_tools/agent-hub/src/watchdog.py` and `_tools/agent-hub/src/utils.py`:

1.  **Model Cost Map:** Create a dictionary in `utils.py` with costs per 1k tokens for the models we use (Gemini 1.5 Flash, Qwen 2.5 Coder, DeepSeek-R1). 
    *   *Note:* Use current estimates (e.g., $0.10/1M for Flash, etc.) or placeholders.
2.  **`update_cost(contract: Dict, tokens_in: int, tokens_out: int, model: str)`**:
    - Calculate cost based on the model and token counts.
    - Increment `breaker.tokens_used` and `breaker.cost_usd` in the contract.
3.  **Integration:**
    - Update `log_transition` to include the cumulative cost so far in the NDJSON log.
    - Path audit: Ensure `JUDGE_REPORT.json` (from Phase 2) includes token usage metadata that Watchdog can read.

## Done Criteria ✓

- [x] Costs are calculated and saved in the contract.
- [x] `transition.ndjson` tracks spending per step.
- [x] Circuit breaker Trigger 7 (Budget Exceeded) now has real data to act on.

## Tests Required

- [x] Test: `update_cost` correctly calculates cost for different models.
- [x] Test: Cost accumulates across multiple transitions in a single task.
```

---

## Prompt 5.2: Audit Log & Handoff Cleanup

```markdown
# Floor Manager Task: Operational Cleanup

You are the Floor Manager. A professional tool doesn't leave junk files behind.

## Requirements

Update `_tools/agent-hub/src/watchdog.py`:

1.  **Post-Merge Cleanup:**
    - When a task reaches the `merged` status and `finalize-task` is called:
    - Move all related files from `_handoff/` (except `transition.ndjson`) into `_handoff/archive/{task_id}/`.
    - This includes `TASK_CONTRACT.json`, `JUDGE_REPORT.md`, etc.
2.  **NDJSON Rotation:**
    - If `transition.ndjson` exceeds 5MB, rename it to `transition.ndjson.1` and start a new one.
3.  **Halt Report Cleanup:**
    - Ensure `ERIK_HALT.md` is removed once a task is successfully resumed or resolved.

## Done Criteria ✓

- [x] `_handoff/` stays clean; only active tasks are visible.
- [x] Historical data is safely archived for later analysis.
- [x] NDJSON rotation prevents infinite file growth.

## Tests Required

- [x] Test: Archiving correctly moves files after a successful merge.
- [x] Test: NDJSON rotation triggers at the specified size.
```

---

## Prompt 5.3: Final Documentation & CLI Help

```markdown
# Floor Manager Task: Polishing & CLI Help

You are the Floor Manager. Make the tool easy to use for Erik.

## Requirements

1.  **CLI Summary:** Update `watchdog.py` so that when a command matches `status`, it prints a beautiful human-readable summary of the current `TASK_CONTRACT.json` (ID, Status, Cost, Path).
2.  **`hub.py` Check:** Ensure the main entry point (from Phase 1) correctly links to these new `watchdog.py` CLI commands.

## Done Criteria ✓

- [x] Beautiful CLI status output.
- [x] End-to-end integration manual verified.
```

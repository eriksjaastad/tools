# Agent Hub Pipeline Flow Verification

This document traces the mechanical flow of a task through the Agent Hub pipeline, identifying the triggers, file I/O, and code responsibility for each stage.

## Pipeline Trace

### 1. Proposal Submission
- **Trigger:** `_handoff/PROPOSAL_FINAL.md` is created/saved by the Architect or Super Manager.
- **Agent:** Floor Manager (Internal Logic).
- **Files Read:** `_handoff/PROPOSAL_FINAL.md`.
- **Files Written:** `_handoff/TASK_CONTRACT.json`.
- **Next Step Trigger:** The presence of a valid task contract.

### 2. Initialization & Branching
- **Trigger:** CLI command `python3 src/watchdog.py setup-task`.
- **Logic:** `src/watchdog.py` -> `GitManager.create_task_branch`.
- **Files Read:** `_handoff/TASK_CONTRACT.json`.
- **Files Written:** `_handoff/TASK_CONTRACT.json` (updated with `git` metadata).
- **Side Effect:** A new git branch `task/{task_id}` is created and checked out.

### 3. Implementation
- **Trigger:** `TASK_CONTRACT.json` status is `pending_implementer`.
- **Agent:** Implementer (e.g., Qwen2.5-Coder).
- **Files Read:** `TASK_CONTRACT.json`, Source Files.
- **Files Written:** Target Files, `TASK_CONTRACT.json` (status changed to `pending_local_review`).
- **Next Step Trigger:** State change in JSON.

### 4. Local Review
- **Trigger:** `TASK_CONTRACT.json` status is `pending_local_review`.
- **Agent:** Local Reviewer (e.g., DeepSeek-R1).
- **Files Read:** Target Files, `TASK_CONTRACT.json`.
- **Files Written:** `TASK_CONTRACT.json` (status changed to `pending_judge_review`).
- **Next Step Trigger:** Signal file creation (see Step 5).

### 5. Judge Activation (Watcher)
- **Signal File:** `_handoff/REVIEW_REQUEST.md`.
- **Waking Code:** `src/watcher.sh` polls for this file.
- **Signature of Signal Creator:** `src/watchdog.py:save_contract`.
- **Line Code:**
  ```python
  if contract.get("status") == "pending_judge_review":
      signal_path = path.parent / "REVIEW_REQUEST.md"
      if not signal_path.exists():
          signal_path.write_text(signal_content, encoding="utf-8")
  ```
- **Files Read:** `REVIEW_REQUEST.md`, `TASK_CONTRACT.json`, Source/Target Files.
- **Files Written:** `_handoff/JUDGE_REPORT.md` and `_handoff/JUDGE_REPORT.json`.
- **Next Step Trigger:** `watcher.sh` calls `python3 src/watchdog.py report-judge`.

### 6. Verdict Processing
- **Trigger:** `report-judge` CLI command.
- **Logic:** `src/watchdog.py` parses reports and updates account/cost.
- **Files Read:** `_handoff/JUDGE_REPORT.json`.
- **Files Written:** `TASK_CONTRACT.json` (status changed to `review_complete`).
- **Next Step Trigger:** Logic branch based on `PASS`/`FAIL`.

### 7. Finalization (Merge & Cleanup)
- **Trigger:** CLI command `python3 src/watchdog.py finalize-task` (called when status is `merged`).
- **Logic:** `GitManager.merge_task_branch` + `cleanup_task_files`.
- **Files Read:** `TASK_CONTRACT.json`.
- **Files Written:** Git merge commit, files moved to `_handoff/archive/{task_id}/`.
- **Side Effect:** Branch merged to `main`, `_handoff/` directory cleaned.

## Verification of No "Magic"
- **State Transitions:** All governed by `src/watchdog.py:transition()`.
- **File System Persistence:** All governed by `src/utils.py:atomic_write_json`.
- **Judge Awareness:** Polling `watcher.sh` is the bridge between local/cloud models and the shell environment.

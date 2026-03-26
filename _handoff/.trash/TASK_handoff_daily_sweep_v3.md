### TASK_TITLE
Add daily handoff sweep (auto-trash stale files) v3

**Objective:** Before creating new handoff files, sweep `_handoff` and move any files whose modified date is NOT today into `_handoff/.trash/`. Preserve manual review flow.

### REQUIRED TOOL CALLS (EXACT ORDER)
1. `draft_read` `_tools/agent-hub/src/listener.py`
2. `draft_write` `_tools/agent-hub/src/listener.py`
3. `draft_submit`

### EDITS TO APPLY
- In `_tools/agent-hub/src/listener.py`:
  - Add helper function `sweep_stale_handoff(handoff_dir: Path) -> int` near the top (after imports or before `MessageListener`).
  - Logic:
    - `today = datetime.now().date()`
    - `trash_dir = handoff_dir / ".trash"` (mkdir)
    - Iterate all files under `handoff_dir` (including nested drafts), skipping:
      - any file inside `.trash`
      - `.gitignore` and `.gitkeep`
    - If file's `stat().st_mtime` date != today, move to `trash_dir`.
    - On name collision, append unix timestamp.
    - Return count of moved files.
  - Call `sweep_stale_handoff(self.handoff_dir)`:
    - at start of `start()` (before connecting to hub)
    - at top of `handle_proposal_ready` (before `convert_proposal(...)`)

### DO NOT
- Do not delete files directly.
- Do not edit any other files.
- Do not change task status logic.



## Worker Output (2026-02-26T18:18:30.463413)

{"name": "draft_read", "arguments": {"path": "_tools/agent-hub/src/listener.py"}}

---
**Stats:** 12 iterations, 0 tool calls.

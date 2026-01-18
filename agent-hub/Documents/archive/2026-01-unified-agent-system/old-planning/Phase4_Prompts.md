# Phase 4: Git Integration - The Hands of the Machine

> **For:** Gemini 3 Flash (Floor Manager in Cursor)  
> **Context:** Agent Hub implementation  
> **Created:** 2026-01-17

This phase gives Agent Hub the ability to manage the filesystem using Git. We will implement branch-per-task isolation, checkpoint commits for every status change, and automatic merging on success.

---

## Prompt 4.1: Git Utility Wrapper

```markdown
# Floor Manager Task: Implement Git Utilities

You are the Floor Manager. We need a safe wrapper for Git operations to ensure the pipeline can manage branches and commits without corruption.

## Context

The system needs to isolate work in branches and track progress via commits. This allows Erik to see exactly what changed at each step and roll back if necessary.

## Requirements

Create `_tools/agent-hub/src/git_manager.py` with:

1. **`GitManager` class** initialized with `repo_root`.
2. **`create_task_branch(task_id: str, base_branch: str = "main")`**
   - Checks if repo is clean (no uncommitted changes).
   - Creates and switches to `task/<task_id>`.
   - Returns the branch name.
3. **`checkpoint_commit(task_id: str, status: str, event: str)`**
   - Adds all changed files (including `_handoff/` if not ignored, but usually just target files).
   - Commits with message: `[TASK: {task_id}] Transition: {status} (Event: {event})`.
   - Returns commit hash.
4. **`merge_task_branch(task_id: str, target_branch: str = "main")`**
   - Switches to target branch.
   - Merges the task branch.
   - On conflict: stops and raises `GitConflictError` (which should trigger an Erik Halt).
5. **`rollback_to_base(base_branch: str)`**
   - Aborts ongoing merges/reverts.
   - Switches back to base branch and cleans up.

## Done Criteria ✓

- [x] `git_manager.py` exists in `src/`.
- [x] Successfully creates branches and performs commits.
- [x] Handles merge conflicts by raising a specific exception.
- [x] All functions have docstrings and type hints.

## Tests Required

Create `_tools/agent-hub/tests/test_git_manager.py`:

- [x] Test: Branch creation works.
- [x] Test: Commit creation works and has correct message format.
- [x] Test: Merge works when no conflicts.
- [x] Test: Conflict raises `GitConflictError`.

**Note:** Use a temporary git repo for tests (initialize it in the temp directory).
```

---

## Prompt 4.2: Watchdog Git Integration

```markdown
# Floor Manager Task: Integrate Git into Watchdog State Machine

You are the Floor Manager. Now that we have a Git wrapper, we need to wire it into the `watchdog.py` state machine.

## Context

Every time the status changes, we want a Git commit. When the task starts, we want a branch. When the task finishes with PASS, we want a merge.

## Requirements

Update `_tools/agent-hub/src/watchdog.py`:

1.  **Initialize Git:** Initialize `GitManager` in the lead-up to the pipeline start.
2.  **Branch on Setup:** When converting a proposal to a contract (in `proposal_converter.py` or `watchdog.py` startup), call `create_task_branch`.
3.  **Checkpointing:** Update the `log_transition` or `save_contract` logic to also call `checkpoint_commit` whenever the status changes.
    - *Note:* Ensure we only commit files in `allowed_paths` to avoid cluttering the repo with handoff logs unless desired.
4.  **Auto-Merge:** When the verdict is `PASS` and the status transitions to `merged`, call `merge_task_branch`.
5.  **Halt Protection:** If any Git operation fails (conflict, permission), call `trigger_halt`.

## Done Criteria ✓

- [x] Watchdog automatically manages branches.
- [x] Git history shows one commit per state transition.
- [x] Pipeline naturally ends with a merge into `main`.

## Tests Required

Update `_tools/agent-hub/tests/test_e2e.py`:

- [x] Verify that the E2E flow now results in multiple git commits.
- [x] Verify that the final state results in the code being in the `main` branch.
```

---

## Prompt 4.3: Handoff & GitIgnore Audit

```markdown
# Floor Manager Task: Git Architecture Audit

You are the Floor Manager. Ensure the Git-Agent relationship is professional and doesn't leak secrets.

## Requirements

1.  **`.gitignore` Check:** Ensure `_handoff/` is in the project's `.gitignore` to prevent contract JSONs and temporary reports from being committed to the main repo history (only the resulting code changes should be committed).
2.  **Atomic Integrity:** Verify that a `git checkout` or `git merge` doesn't happen while a file is being atomically written in `_handoff/`.
3.  **Metadata:** Ensure the `TASK_CONTRACT.json` tracks the `base_commit` and `task_branch` correctly (Schema version 2.0 already has these fields).

## Done Criteria ✓

- [x] `.gitignore` properly configured.
- [x] Audit verified no race conditions between Git and Watchdog.
```

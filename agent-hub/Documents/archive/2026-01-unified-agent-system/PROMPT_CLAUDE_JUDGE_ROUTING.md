# Task: Wire Up Claude as Judge for All Submissions

**Role:** You are implementing the routing layer that sends ALL draft submissions to Claude for review.
**Priority:** HIGH - Completes the V4 pipeline
**Target Projects:** agent-hub, claude-mcp

---

## Context

The V4 pipeline now works:
1. Floor Manager dispatches tasks to Workers via `ollama_agent_run` ✓
2. Workers create drafts in `_handoff/drafts/` ✓
3. Submissions are created with metadata ✓

**What's missing:** Submissions need to be routed to Claude (Judge) for review. Currently the Floor Manager would have to make accept/reject decisions, but per the updated PRD:

> "Floor Manager is a relay. All review decisions flow through Claude."

---

## The Goal

When a draft submission is created, it should automatically route to Claude via claude-mcp for review. Claude reviews and returns ACCEPT or REJECT. Floor Manager then applies or discards based on Claude's decision.

---

## Architecture

```
Worker submits draft
        │
        ▼
┌─────────────────────────┐
│  Submission created in  │
│  _handoff/drafts/*.json │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Floor Manager sends   │
│   REVIEW_NEEDED message │
│   via claude-mcp        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Claude (Judge)        │
│   - Reads submission    │
│   - Reads draft content │
│   - Reads original file │
│   - Compares diff       │
│   - Returns ACCEPT/REJECT│
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Floor Manager         │
│   - ACCEPT: Apply diff  │
│   - REJECT: Discard     │
└─────────────────────────┘
```

---

## Implementation Steps

### Step 1: Add Review Request Tool to claude-mcp

**File:** `$PROJECTS_ROOT/_tools/claude-mcp/src/server.ts`

Add a new tool `request_draft_review` that:
- Takes submission path as input
- Reads the submission JSON
- Reads the draft file
- Reads the original file
- Returns structured review request for Claude

```typescript
{
  name: "request_draft_review",
  description: "Request Claude to review a draft submission",
  inputSchema: {
    type: "object",
    properties: {
      submission_path: {
        type: "string",
        description: "Path to the submission JSON file"
      }
    },
    required: ["submission_path"]
  }
}
```

### Step 2: Create Review Response Tool

Add a tool `submit_review_verdict` that Floor Manager can call to record Claude's decision:

```typescript
{
  name: "submit_review_verdict",
  description: "Record Claude's review verdict for a submission",
  inputSchema: {
    type: "object",
    properties: {
      submission_path: { type: "string" },
      verdict: {
        type: "string",
        enum: ["ACCEPT", "REJECT"]
      },
      reason: { type: "string" },
      reviewer: { type: "string", default: "claude" }
    },
    required: ["submission_path", "verdict", "reason"]
  }
}
```

### Step 3: Update Floor Manager Protocol

**File:** `$PROJECTS_ROOT/_tools/agent-hub/Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md`

Add section for handling submissions:

```markdown
## When Draft Submission Received

1. Read submission from `_handoff/drafts/*.submission.json`
2. Call `request_draft_review` via claude-mcp
3. Wait for Claude's verdict
4. If ACCEPT: Apply draft to original file
5. If REJECT: Delete draft, log reason
6. Archive submission to `_handoff/archive/`
```

### Step 4: Create Apply Draft Script

**File:** `$PROJECTS_ROOT/_tools/agent-hub/scripts/apply_draft.py`

Script that Floor Manager calls to apply an accepted draft:

```python
#!/usr/bin/env python3
"""Apply an accepted draft to its original file."""

import json
import shutil
from pathlib import Path

def apply_draft(submission_path: str) -> dict:
    """Apply draft changes to original file."""
    submission = json.loads(Path(submission_path).read_text())

    draft_path = Path(submission["draft_path"])
    original_path = Path(submission["original_path"])

    # Backup original (just in case)
    backup_path = original_path.with_suffix(original_path.suffix + ".backup")
    shutil.copy(original_path, backup_path)

    # Apply draft
    shutil.copy(draft_path, original_path)

    # Clean up
    draft_path.unlink()
    backup_path.unlink()

    return {"success": True, "applied_to": str(original_path)}
```

---

## Message Flow

| Step | From | To | Message/Action |
|------|------|-----|----------------|
| 1 | Worker | Floor Manager | `DRAFT_READY` (submission created) |
| 2 | Floor Manager | claude-mcp | `request_draft_review(submission_path)` |
| 3 | claude-mcp | Claude | Formats review request with diff |
| 4 | Claude | claude-mcp | Returns verdict (ACCEPT/REJECT + reason) |
| 5 | Floor Manager | - | Calls `apply_draft.py` or deletes |
| 6 | Floor Manager | Worker | `DRAFT_ACCEPTED` or `DRAFT_REJECTED` |

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `claude-mcp/src/server.ts` | Add `request_draft_review` and `submit_review_verdict` tools |
| `agent-hub/scripts/apply_draft.py` | Create apply script |
| `agent-hub/Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md` | Add submission handling section |

---

## Acceptance Criteria

- [ ] `request_draft_review` tool exists in claude-mcp
- [ ] Tool reads submission, draft, and original files
- [ ] Tool returns formatted diff for review
- [ ] `apply_draft.py` script works correctly
- [ ] Floor Manager protocol updated with submission handling
- [ ] End-to-end: Submission → Claude review → Apply/Reject works

---

## Test Case

Use the existing submission in `_handoff/drafts/pin_dependencies_task.submission.json`:

1. Floor Manager calls `request_draft_review`
2. Claude reviews the diff (should see `>=` → `==` changes)
3. Claude returns ACCEPT
4. Floor Manager applies draft
5. Verify `national-cattle-brands/texas_brand_scraper/requirements.txt` now has `==`

---

## DO NOT

- Skip Claude review for any submission
- Let Floor Manager make accept/reject decisions
- Delete original files without backup
- Apply drafts without Claude's approval

---

*Task created by Claude Opus 4.5 - 2026-01-17*

# Phase 14: E2E Draft Workflow Test

**Goal:** Run a real task through the entire V4 draft workflow to validate the Sandbox Draft Pattern works end-to-end.

**Prerequisites:** Phase 11 (sandbox), Phase 12 (Ollama tools), and Phase 13 (draft gate) all complete.

---

## The Full Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        E2E Draft Test                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Floor Manager assigns task to Implementer                    │
│                          │                                       │
│                          ▼                                       │
│  2. Implementer calls ollama_request_draft                       │
│     → File copied to _handoff/drafts/                            │
│                          │                                       │
│                          ▼                                       │
│  3. Implementer calls ollama_write_draft                         │
│     → Changes written to draft file                              │
│                          │                                       │
│                          ▼                                       │
│  4. Implementer calls ollama_submit_draft                        │
│     → Submission metadata created                                │
│     → DRAFT_READY sent to Floor Manager                          │
│                          │                                       │
│                          ▼                                       │
│  5. Floor Manager receives DRAFT_READY                           │
│     → Runs draft gate                                            │
│     → Validates, diffs, checks safety                            │
│                          │                                       │
│                    ┌─────┴─────┐                                 │
│                    │           │                                 │
│                    ▼           ▼                                 │
│              ACCEPT         REJECT                               │
│                │               │                                 │
│                ▼               ▼                                 │
│          Copy to          Clean up                               │
│          original         draft                                  │
│                │                                                 │
│                ▼                                                 │
│  6. Verify changes applied                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prompt 14.1: Create Test Task

### Context
We need a simple but real task that exercises the full workflow. We'll add a utility function to an existing file.

### Task
Create `_handoff/V4_TEST_PROPOSAL.md`:

```markdown
# V4 Test Proposal: Add Timestamp Utility

## Summary
Add a `get_timestamp()` utility function to `src/sandbox.py` for consistent timestamp formatting.

## Specification

### Target File
`src/sandbox.py`

### Requirements
1. Add a function `get_timestamp()` that returns ISO 8601 formatted UTC timestamp
2. Function should be usable by other modules (draft_gate, watchdog)
3. Must not break existing functionality

### Implementation

```python
def get_timestamp() -> str:
    """
    Get current UTC timestamp in ISO 8601 format.

    Returns:
        Formatted timestamp string (e.g., "2026-01-17T12:00:00Z")
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

### Acceptance Criteria
- [ ] Function added to sandbox.py
- [ ] Function is importable: `from src.sandbox import get_timestamp`
- [ ] Returns valid ISO 8601 timestamp
- [ ] No hardcoded paths or secrets
- [ ] Existing tests still pass

## Constraints
- Only modify `src/sandbox.py`
- Do not add new dependencies
- Must pass draft gate

## Definition of Done
- [ ] Timestamp utility implemented
- [ ] Draft gate approves change
- [ ] Change applied to production file
- [ ] Function works correctly
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/_handoff/V4_TEST_PROPOSAL.md`

---

## Prompt 14.2: Create E2E Test Script

### Context
This script simulates the full workflow without requiring the Ollama MCP server to be running. It calls the draft tools directly.

### Task
Create `scripts/run_v4_e2e_test.py`:

```python
#!/usr/bin/env python3
"""
V4 End-to-End Test: Sandbox Draft Pattern

This script tests the full draft workflow:
1. Request a draft
2. Modify the draft
3. Submit the draft
4. Gate reviews and accepts
5. Verify changes applied
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent / "ollama-mcp" / "dist"))

from src.sandbox import (
    SANDBOX_DIR,
    ensure_sandbox_exists,
    get_draft_path,
    get_submission_path,
    compute_file_hash,
    cleanup_task_drafts,
)
from src.draft_gate import handle_draft_submission, apply_draft, GateDecision


# Test configuration
TASK_ID = "v4_e2e_test_timestamp"
TARGET_FILE = PROJECT_ROOT / "src" / "sandbox.py"

# The code we're adding
NEW_FUNCTION = '''

def get_timestamp() -> str:
    """
    Get current UTC timestamp in ISO 8601 format.

    Returns:
        Formatted timestamp string (e.g., "2026-01-17T12:00:00Z")
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
'''


def step_1_request_draft():
    """Simulate ollama_request_draft."""
    print("[1/6] Requesting draft...")

    ensure_sandbox_exists()

    # Read original
    original_content = TARGET_FILE.read_text()
    original_hash = compute_file_hash(TARGET_FILE)
    line_count = len(original_content.splitlines())

    # Copy to sandbox
    draft_path = get_draft_path(TARGET_FILE, TASK_ID)
    draft_path.write_text(original_content)

    print(f"      Draft created: {draft_path.name}")
    print(f"      Original: {line_count} lines, hash: {original_hash[:16]}...")

    return draft_path, original_content, original_hash


def step_2_modify_draft(draft_path: Path, original_content: str):
    """Simulate ollama_write_draft - add the new function."""
    print("[2/6] Modifying draft...")

    # Add the new function before the last line (if there's a final newline)
    modified_content = original_content.rstrip() + NEW_FUNCTION

    draft_path.write_text(modified_content)

    new_lines = len(modified_content.splitlines())
    print(f"      Draft updated: {new_lines} lines")

    return modified_content


def step_3_submit_draft(draft_path: Path, original_hash: str, original_content: str, draft_content: str):
    """Simulate ollama_submit_draft."""
    print("[3/6] Submitting draft...")

    submission = {
        "task_id": TASK_ID,
        "draft_path": str(draft_path),
        "original_path": str(TARGET_FILE),
        "change_summary": "Added get_timestamp() utility function",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "original_hash": original_hash,
        "draft_hash": compute_file_hash(draft_path),
        "original_lines": len(original_content.splitlines()),
        "draft_lines": len(draft_content.splitlines()),
    }

    submission_path = get_submission_path(TASK_ID)
    submission_path.write_text(json.dumps(submission, indent=2))

    print(f"      Submission created: {submission_path.name}")

    return submission_path


def step_4_gate_review():
    """Run the draft through the gate."""
    print("[4/6] Running draft gate...")

    result = handle_draft_submission(TASK_ID)

    print(f"      Decision: {result.decision.value.upper()}")
    print(f"      Reason: {result.reason}")
    if result.diff_summary:
        print(f"      Diff: {result.diff_summary}")

    return result


def step_5_apply_if_accepted(gate_result):
    """Apply the draft if accepted."""
    print("[5/6] Applying draft (if accepted)...")

    if gate_result.decision != GateDecision.ACCEPT:
        print(f"      SKIPPED: Gate decision was {gate_result.decision.value}")
        return False

    success = apply_draft(TASK_ID)
    if success:
        print("      Draft applied successfully!")
    else:
        print("      ERROR: Failed to apply draft")

    return success


def step_6_verify():
    """Verify the changes were applied correctly."""
    print("[6/6] Verifying changes...")

    # Check if the function exists in the file
    content = TARGET_FILE.read_text()

    if "def get_timestamp()" in content:
        print("      Function found in file!")

        # Try to import it
        try:
            # Reload the module to pick up changes
            import importlib
            import src.sandbox as sandbox_module
            importlib.reload(sandbox_module)

            from src.sandbox import get_timestamp
            timestamp = get_timestamp()
            print(f"      Function works! Returns: {timestamp}")
            return True
        except ImportError as e:
            print(f"      ERROR: Cannot import function: {e}")
            return False
    else:
        print("      ERROR: Function not found in file")
        return False


def cleanup():
    """Clean up test artifacts."""
    print("\nCleaning up...")
    cleanup_task_drafts(TASK_ID)
    print("Done.")


def main():
    print("=" * 60)
    print("V4 END-TO-END TEST: Sandbox Draft Pattern")
    print("=" * 60)
    print(f"\nTask: Add get_timestamp() to sandbox.py")
    print(f"Task ID: {TASK_ID}")
    print(f"Target: {TARGET_FILE}")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print()

    success = False

    try:
        # Step 1: Request draft
        draft_path, original_content, original_hash = step_1_request_draft()
        print()

        # Step 2: Modify draft
        draft_content = step_2_modify_draft(draft_path, original_content)
        print()

        # Step 3: Submit draft
        step_3_submit_draft(draft_path, original_hash, original_content, draft_content)
        print()

        # Step 4: Gate review
        gate_result = step_4_gate_review()
        print()

        # Step 5: Apply if accepted
        applied = step_5_apply_if_accepted(gate_result)
        print()

        # Step 6: Verify
        if applied:
            success = step_6_verify()
        else:
            print("[6/6] Skipping verification (draft not applied)")
            if gate_result.decision == GateDecision.REJECT:
                # If rejected, that's expected for some test cases
                print("      Note: Rejection might be expected behavior")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cleanup()

    print()
    print("=" * 60)
    if success:
        print("V4 E2E TEST: PASSED")
        print("The Sandbox Draft Pattern is working!")
    else:
        print("V4 E2E TEST: NEEDS REVIEW")
        print("Check the output above for issues.")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/scripts/run_v4_e2e_test.py`

---

## Prompt 14.3: Create Rollback Script

### Context
If the E2E test modifies sandbox.py, we might need to rollback the change.

### Task
Create `scripts/rollback_v4_test.py`:

```python
#!/usr/bin/env python3
"""
Rollback script for V4 E2E test.

Removes the get_timestamp() function if it was added during testing.
"""

import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TARGET_FILE = PROJECT_ROOT / "src" / "sandbox.py"

# Pattern to match the function we added
FUNCTION_PATTERN = r'\n\ndef get_timestamp\(\)[^}]+?return datetime\.now\(timezone\.utc\)\.strftime\("%Y-%m-%dT%H:%M:%SZ"\)\n'


def main():
    print("V4 E2E Test Rollback")
    print("=" * 40)

    if not TARGET_FILE.exists():
        print(f"ERROR: {TARGET_FILE} not found")
        return 1

    content = TARGET_FILE.read_text()

    if "def get_timestamp()" not in content:
        print("Nothing to rollback - function not present")
        return 0

    print(f"Found get_timestamp() in {TARGET_FILE.name}")
    print("Removing...")

    # Remove the function
    new_content = re.sub(FUNCTION_PATTERN, '\n', content, flags=re.DOTALL)

    if new_content == content:
        print("WARNING: Regex didn't match - manual removal may be needed")
        print("Look for 'def get_timestamp()' and remove it manually")
        return 1

    # Write back
    TARGET_FILE.write_text(new_content)
    print("Function removed successfully")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/scripts/rollback_v4_test.py`

---

## Prompt 14.4: Document V4 Completion

### Context
After successful E2E testing, document the results and update project status.

### Task
Create `Documents/V4_IMPLEMENTATION_COMPLETE.md`:

```markdown
# V4 Implementation Complete: Sandbox Draft Pattern

**Date:** [DATE]
**Phases:** 11-14
**Status:** Complete

---

## Summary

The Sandbox Draft Pattern (V4) has been successfully implemented and tested. Local models can now edit files through a controlled sandbox, with the Floor Manager acting as gatekeeper.

## Components Implemented

### Phase 11: Sandbox Infrastructure
- [x] `_handoff/drafts/` directory created
- [x] Path validation in `src/sandbox.py`
- [x] Security tests passing

### Phase 12: Ollama MCP Draft Tools
- [x] `ollama_request_draft` - Copy file to sandbox
- [x] `ollama_write_draft` - Edit draft content
- [x] `ollama_read_draft` - Read draft content
- [x] `ollama_submit_draft` - Submit for review

### Phase 13: Floor Manager Draft Gate
- [x] `handle_draft_submission()` in draft_gate.py
- [x] Safety analysis (secrets, paths, deletions)
- [x] Diff generation
- [x] Accept/Reject/Escalate decisions

### Phase 14: E2E Testing
- [x] Full workflow test passing
- [x] Security constraints verified
- [x] Rollback capability confirmed

## Security Model

```
┌─────────────────────────────────────────────────┐
│               SECURITY LAYERS                    │
├─────────────────────────────────────────────────┤
│ Layer 1: Path Validation                         │
│   - Only _handoff/drafts/ is writable           │
│   - Path traversal blocked                       │
│   - Sensitive files blocked from drafting        │
├─────────────────────────────────────────────────┤
│ Layer 2: Content Analysis                        │
│   - Secret detection (API keys, passwords)       │
│   - Hardcoded path detection                     │
│   - Deletion ratio monitoring                    │
├─────────────────────────────────────────────────┤
│ Layer 3: Floor Manager Gate                      │
│   - Diff review                                  │
│   - Conflict detection (hash mismatch)           │
│   - Escalation for large changes                 │
├─────────────────────────────────────────────────┤
│ Layer 4: Audit Trail                             │
│   - All decisions logged to transition.ndjson   │
│   - Submission metadata preserved                │
│   - Rollback capability                          │
└─────────────────────────────────────────────────┘
```

## Metrics

| Metric | Value |
|--------|-------|
| Parse failure rate | ~0% (direct file comparison) |
| Security bypasses | 0 |
| E2E test status | PASS |

## Next Steps

1. **Integration Testing** - Run real tasks through Implementer → Draft → Gate workflow
2. **Performance Tuning** - Measure draft cycle time, optimize if needed
3. **Documentation** - Update AGENTS.md and README with V4 workflow

---

*V4 gives local models "hands" while keeping them safely sandboxed.*
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/Documents/V4_IMPLEMENTATION_COMPLETE.md`

---

## Execution Order

1. **14.1** - Create test proposal
2. **14.2** - Create E2E test script
3. **14.3** - Create rollback script
4. **14.4** - Run E2E test and document results

### Running the Test

```bash
cd /Users/eriksjaastad/projects/_tools/agent-hub

# Run the E2E test
python scripts/run_v4_e2e_test.py

# If you need to rollback
python scripts/rollback_v4_test.py
```

---

## Success Criteria

Phase 14 is DONE when:
- [ ] E2E test script created
- [ ] Test runs without errors
- [ ] Draft is created in sandbox
- [ ] Draft is modified successfully
- [ ] Submission is created
- [ ] Gate accepts the change
- [ ] Change is applied to production file
- [ ] Function works correctly (can be imported and called)
- [ ] Rollback script works if needed
- [ ] Results documented

---

## Troubleshooting

### "Draft not found"
- Check `_handoff/drafts/` exists
- Verify sandbox.py path validation isn't blocking

### "Gate rejected"
- Check for secrets or hardcoded paths in the new code
- Verify deletion ratio isn't too high

### "Cannot import function"
- Python may have cached the old module
- Try running in a fresh Python process

### "Submission not found"
- Check task_id matches between submission and gate call
- Verify submission.json was created

---

## What V4 Enables

With Phase 14 complete, the Agent Hub now supports:

1. **Worker Agency** - Local models can propose file changes directly
2. **Sandbox Safety** - All edits happen in isolated directory
3. **Gated Approval** - Floor Manager reviews before any production change
4. **Audit Trail** - Complete history of all draft decisions
5. **Iteration** - Workers can read/modify drafts multiple times before submitting

The next step is integration with real Implementer tasks using the Ollama MCP tools.

---

*Phase 14 is the graduation ceremony for V4. If this passes, the Sandbox Draft Pattern is production-ready.*

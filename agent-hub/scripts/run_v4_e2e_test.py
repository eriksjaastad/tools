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
import importlib
from pathlib import Path
from datetime import datetime, timezone

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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
    modified_content = original_content.rstrip() + NEW_FUNCTION + "\n"

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
            import src.sandbox as sandbox_module
            importlib.reload(sandbox_module)

            from src.sandbox import get_timestamp
            timestamp = get_timestamp()
            print(f"      Function works! Returns: {timestamp}")
            return True
        except ImportError as e:
            print(f"      ERROR: Cannot import function: {e}")
            return False
        except Exception as e:
            print(f"      ERROR: Function call failed: {e}")
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

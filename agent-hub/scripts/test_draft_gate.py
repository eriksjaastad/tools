#!/usr/bin/env python3
"""
Smoke test for draft gate.
Creates a mock submission and runs it through the gate.
"""

import sys
import json
from pathlib import Path
import tempfile
import shutil
import hashlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sandbox import SANDBOX_DIR, ensure_sandbox_exists, GateDecision
from src.draft_gate import (
    handle_draft_submission,
    apply_draft,
    reject_draft,
)


def setup_test_submission(task_id: str, original_content: str, draft_content: str) -> tuple[Path, Path]:
    """Create test files for a submission."""
    # Ensure sandbox exists
    ensure_sandbox_exists()

    # Create a temp original file in a dummy workspace
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "_test_workspace"
    test_dir.mkdir(exist_ok=True)

    original_path = test_dir / "test_file.py"
    original_path.write_text(original_content)

    # Create draft in sandbox
    draft_path = SANDBOX_DIR / f"test_file.py.{task_id}.draft"
    draft_path.write_text(draft_content)

    # Create submission metadata
    original_hash = hashlib.sha256(original_content.encode()).hexdigest()

    submission = {
        "task_id": task_id,
        "draft_path": str(draft_path),
        "original_path": str(original_path),
        "change_summary": "Test change",
        "submitted_at": "2026-01-17T12:00:00Z",
        "original_hash": original_hash,
        "draft_hash": hashlib.sha256(draft_content.encode()).hexdigest(),
        "original_lines": len(original_content.splitlines()),
        "draft_lines": len(draft_content.splitlines()),
    }

    submission_path = SANDBOX_DIR / f"{task_id}.submission.json"
    submission_path.write_text(json.dumps(submission))

    return original_path, draft_path


def cleanup_test(task_id: str):
    """Clean up test files."""
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "_test_workspace"
    if test_dir.exists():
        shutil.rmtree(test_dir)

    # Clean sandbox
    for f in SANDBOX_DIR.glob(f"*{task_id}*"):
        f.unlink()


def main():
    print("=" * 50)
    print("DRAFT GATE SMOKE TEST")
    print("=" * 50)
    print()

    passed = 0
    failed = 0

    # Test 1: Clean change should be accepted
    print("Test 1: Clean change should be ACCEPTED...")
    task_id = "test_clean_001"
    try:
        original = "def hello():\n    print('hello')\n"
        draft = "def hello():\n    print('Hello, World!')\n"
        setup_test_submission(task_id, original, draft)

        result = handle_draft_submission(task_id)
        if result.decision == GateDecision.ACCEPT:
            print("  PASS: Clean change accepted")
            passed += 1
        else:
            print(f"  FAIL: Expected ACCEPT, got {result.decision}: {result.reason}")
            failed += 1
    finally:
        cleanup_test(task_id)

    # Test 2: Secret in draft should be rejected
    print("Test 2: Secret in draft should be REJECTED...")
    task_id = "test_secret_002"
    try:
        original = "config = {}\n"
        draft = 'config = {"api_key": "sk-1234567890abcdefghij"}\n'
        setup_test_submission(task_id, original, draft)

        result = handle_draft_submission(task_id)
        if result.decision == GateDecision.REJECT:
            print("  PASS: Secret detected and rejected")
            passed += 1
        else:
            print(f"  FAIL: Expected REJECT, got {result.decision}")
            failed += 1
    finally:
        cleanup_test(task_id)

    # Test 3: Hardcoded path should be rejected
    print("Test 3: Hardcoded path should be REJECTED...")
    task_id = "test_path_003"
    try:
        original = "path = './config.json'\n"
        draft = "path = '/Users/erik/projects/config.json'\n"
        setup_test_submission(task_id, original, draft)

        result = handle_draft_submission(task_id)
        if result.decision == GateDecision.REJECT:
            print("  PASS: Hardcoded path detected and rejected")
            passed += 1
        else:
            print(f"  FAIL: Expected REJECT, got {result.decision}")
            failed += 1
    finally:
        cleanup_test(task_id)

    # Test 4: Large deletion should be escalated
    print("Test 4: Large deletion should be ESCALATED...")
    task_id = "test_delete_004"
    try:
        original = "\n".join([f"line {i}" for i in range(100)]) + "\n"
        draft = "# Deleted most of the file\n"
        setup_test_submission(task_id, original, draft)

        result = handle_draft_submission(task_id)
        if result.decision == GateDecision.ESCALATE:
            print("  PASS: Large deletion escalated")
            passed += 1
        else:
            print(f"  FAIL: Expected ESCALATE, got {result.decision}")
            failed += 1
    finally:
        cleanup_test(task_id)

    print()
    print("=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 50)

    if failed > 0:
        print("\nPhase 13 has issues - review failures above.")
        return 1
    else:
        print("\nPhase 13 COMPLETE. Ready for Phase 14 (E2E Draft Workflow).")
        return 0


if __name__ == "__main__":
    sys.exit(main())

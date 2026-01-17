#!/usr/bin/env python3
"""
Smoke test for sandbox infrastructure.
Run this before Phase 12 to verify the foundation is solid.
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sandbox import (
    ensure_sandbox_exists,
    validate_sandbox_write,
    validate_source_read,
    get_draft_path,
    compute_file_hash,
    cleanup_task_drafts,
    SANDBOX_DIR,
)


def test_sandbox_exists():
    """Verify sandbox directory can be created."""
    print("Test 1: Sandbox directory creation...")
    ensure_sandbox_exists()

    assert SANDBOX_DIR.exists(), "Sandbox directory should exist"
    assert SANDBOX_DIR.is_dir(), "Sandbox should be a directory"
    print("  PASS: Sandbox directory exists")


def test_write_validation_security():
    """Verify write validation blocks unauthorized paths."""
    print("Test 2: Write validation security...")

    # Should allow sandbox paths
    valid_path = SANDBOX_DIR / "test.task1.draft"
    result = validate_sandbox_write(valid_path)
    assert result.valid, f"Should allow sandbox path: {result.reason}"

    # Should block escape attempts
    escape_attempts = [
        "/tmp/evil.draft",
        "/etc/passwd",
        SANDBOX_DIR / ".." / "escape.py",
        Path.home() / ".ssh" / "id_rsa",
    ]

    for attempt in escape_attempts:
        result = validate_sandbox_write(attempt)
        assert not result.valid, f"Should block: {attempt}"

    print("  PASS: All escape attempts blocked")


def test_read_validation():
    """Verify read validation works."""
    print("Test 3: Read validation...")

    # Should block sensitive files
    workspace = Path(__file__).parent.parent

    # Create a temp test file
    test_file = workspace / "src" / "sandbox.py" # Use sandbox.py instead of config.py which might not exist
    if test_file.exists():
        result = validate_source_read(test_file, workspace)
        assert result.valid, f"Should allow workspace files: {result.reason}"

    # Should block outside workspace
    result = validate_source_read("/etc/passwd", workspace)
    assert not result.valid, "Should block outside workspace"

    print("  PASS: Read validation working")


def test_draft_path_generation():
    """Verify draft paths are generated correctly."""
    print("Test 4: Draft path generation...")

    source = Path("/workspace/src/foo.py")
    draft = get_draft_path(source, "test_task_123")

    assert draft.parent == SANDBOX_DIR, "Draft should be in sandbox"
    assert "foo.py" in draft.name, "Draft should contain original filename"
    assert "test_task_123" in draft.name, "Draft should contain task ID"
    assert draft.suffix == ".draft", "Draft should have .draft extension"

    print("  PASS: Draft path generation correct")


def test_file_hashing():
    """Verify file hashing works."""
    print("Test 5: File hashing...")

    # Hash an existing file
    test_file = Path(__file__)
    hash1 = compute_file_hash(test_file)
    hash2 = compute_file_hash(test_file)

    assert hash1 == hash2, "Same file should produce same hash"
    assert len(hash1) == 64, "SHA256 should be 64 hex chars"

    print("  PASS: File hashing working")


def main():
    print("=" * 50)
    print("SANDBOX INFRASTRUCTURE SMOKE TEST")
    print("=" * 50)
    print()

    tests = [
        test_sandbox_exists,
        test_write_validation_security,
        test_read_validation,
        test_draft_path_generation,
        test_file_hashing,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print()
    print("=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 50)

    if failed > 0:
        print("\nPhase 11 NOT ready for Phase 12.")
        return 1
    else:
        print("\nPhase 11 COMPLETE. Ready for Phase 12 (Ollama MCP Tools).")
        return 0


if __name__ == "__main__":
    sys.exit(main())

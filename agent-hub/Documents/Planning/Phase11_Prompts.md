# Phase 11: Sandbox Infrastructure

**Goal:** Create the foundation for the Sandbox Draft Pattern (V4) - directory structure, path validation utilities, and security guardrails.

**Prerequisites:** Phase 10 complete. V4 spec reviewed (`Documents/Agentic Blueprint Setup V4.md`).

**Context:** This phase does NOT add Ollama tools yet. We're building the secure sandbox that Phase 12's tools will write to.

---

## The Architecture

```
_handoff/
├── drafts/                    # THE SANDBOX - workers can ONLY write here
│   ├── .gitkeep               # Ensure directory exists in git
│   └── README.md              # Explains the sandbox purpose
├── archive/                   # Existing - completed tasks
├── TASK_CONTRACT.json         # Existing - current task
└── transition.ndjson          # Existing - audit log
```

---

## Prompt 11.1: Create Sandbox Directory Structure

### Context
The `_handoff/drafts/` directory is the ONLY place local model workers will be allowed to write files. This isolation is the core security feature of V4.

### Task
Create the sandbox directory with documentation:

**File 1: `_handoff/drafts/.gitkeep`**
```
# This file ensures the drafts directory exists in git.
# Contents of this directory are ignored (see .gitignore).
```

**File 2: `_handoff/drafts/README.md`**
```markdown
# Sandbox Drafts Directory

**Purpose:** Isolated workspace for local model file edits.

## Security Model

This directory is the ONLY location where Ollama workers can write files.
The Floor Manager gates all changes before they reach production code.

## Workflow

1. Worker requests draft via `ollama_request_draft`
2. Original file is copied here as `{filename}.{task_id}.draft`
3. Worker edits the draft via `ollama_write_draft`
4. Worker submits via `ollama_submit_draft`
5. Floor Manager diffs, validates, accepts/rejects
6. Accepted drafts are copied to original location
7. All drafts are cleaned up after task completion

## Contents

- `*.draft` - Working drafts (temporary)
- `*.submission.json` - Submission metadata (temporary)
- Cleaned up after each task cycle

## Security Rules

- Workers CANNOT write outside this directory
- Workers CANNOT delete files
- Workers CANNOT execute commands
- All paths are validated before any operation
- Floor Manager is the ONLY gatekeeper to production
```

### File Locations
- `/Users/eriksjaastad/projects/_tools/agent-hub/_handoff/drafts/.gitkeep`
- `/Users/eriksjaastad/projects/_tools/agent-hub/_handoff/drafts/README.md`

---

## Prompt 11.2: Update .gitignore for Drafts

### Context
Draft files are temporary working files. We want to keep the directory structure in git but ignore the actual draft contents.

### Task
Update `_handoff/.gitignore` to ignore draft contents but keep the directory:

```gitignore
# Existing ignores...

# Sandbox drafts - ignore contents, keep structure
drafts/*.draft
drafts/*.submission.json
!drafts/.gitkeep
!drafts/README.md
```

If `_handoff/.gitignore` doesn't exist, check the root `.gitignore` and add there instead.

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/_handoff/.gitignore` (or root `.gitignore`)

---

## Prompt 11.3: Create Path Validation Module

### Context
Path validation is the CRITICAL security layer. Every file operation must pass through these checks. A single bypass could allow workers to write anywhere.

### Task
Create `src/sandbox.py`:

```python
#!/usr/bin/env python3
"""
Sandbox path validation for V4 Draft Pattern.

SECURITY CRITICAL: This module is the gatekeeper for all worker file operations.
Any bypass here compromises the entire sandbox model.
"""

from pathlib import Path
import hashlib
import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)

# The ONE directory workers can write to
SANDBOX_DIR = Path(__file__).parent.parent / "_handoff" / "drafts"


class ValidationResult(NamedTuple):
    """Result of path validation."""
    valid: bool
    reason: str
    resolved_path: Path | None = None


def validate_sandbox_write(path: str | Path) -> ValidationResult:
    """
    Validate that a path is safe for worker writes.

    SECURITY: This is the ONLY place workers can write.

    Args:
        path: The path to validate

    Returns:
        ValidationResult with valid=True if write is allowed
    """
    try:
        target = Path(path).resolve()
        sandbox = SANDBOX_DIR.resolve()

        # Check 1: Must be inside sandbox
        if not target.is_relative_to(sandbox):
            logger.warning(f"SECURITY: Write blocked - outside sandbox: {target}")
            return ValidationResult(
                valid=False,
                reason=f"Path outside sandbox: {target}"
            )

        # Check 2: No path traversal tricks
        if ".." in str(path):
            logger.warning(f"SECURITY: Write blocked - path traversal: {path}")
            return ValidationResult(
                valid=False,
                reason="Path traversal not allowed"
            )

        # Check 3: Must have .draft or .submission.json extension
        valid_extensions = {".draft", ".json"}
        if target.suffix not in valid_extensions:
            # Allow .submission.json specifically
            if not str(target).endswith(".submission.json"):
                logger.warning(f"SECURITY: Write blocked - invalid extension: {target}")
                return ValidationResult(
                    valid=False,
                    reason=f"Invalid extension: {target.suffix}"
                )

        logger.debug(f"Sandbox write validated: {target}")
        return ValidationResult(
            valid=True,
            reason="OK",
            resolved_path=target
        )

    except Exception as e:
        logger.error(f"SECURITY: Validation error: {e}")
        return ValidationResult(
            valid=False,
            reason=f"Validation error: {e}"
        )


def validate_source_read(path: str | Path, workspace_root: Path) -> ValidationResult:
    """
    Validate that a source file can be read for drafting.

    Args:
        path: The source file path
        workspace_root: The project workspace root

    Returns:
        ValidationResult with valid=True if read is allowed
    """
    try:
        target = Path(path).resolve()
        workspace = workspace_root.resolve()

        # Check 1: Must be inside workspace
        if not target.is_relative_to(workspace):
            logger.warning(f"SECURITY: Read blocked - outside workspace: {target}")
            return ValidationResult(
                valid=False,
                reason=f"Path outside workspace: {target}"
            )

        # Check 2: File must exist
        if not target.exists():
            return ValidationResult(
                valid=False,
                reason=f"File not found: {target}"
            )

        # Check 3: Must be a file, not directory
        if not target.is_file():
            return ValidationResult(
                valid=False,
                reason=f"Not a file: {target}"
            )

        # Check 4: Block sensitive files
        sensitive_patterns = [".env", "credentials", "secret", ".key", ".pem"]
        if any(pattern in target.name.lower() for pattern in sensitive_patterns):
            logger.warning(f"SECURITY: Read blocked - sensitive file: {target}")
            return ValidationResult(
                valid=False,
                reason=f"Cannot draft sensitive files: {target.name}"
            )

        logger.debug(f"Source read validated: {target}")
        return ValidationResult(
            valid=True,
            reason="OK",
            resolved_path=target
        )

    except Exception as e:
        logger.error(f"SECURITY: Validation error: {e}")
        return ValidationResult(
            valid=False,
            reason=f"Validation error: {e}"
        )


def get_draft_path(source_path: Path, task_id: str) -> Path:
    """
    Generate the sandbox draft path for a source file.

    Args:
        source_path: Original file path
        task_id: Current task identifier

    Returns:
        Path to the draft file in sandbox
    """
    # Sanitize task_id (alphanumeric and underscore only)
    safe_task_id = "".join(c if c.isalnum() or c == "_" else "_" for c in task_id)

    draft_name = f"{source_path.name}.{safe_task_id}.draft"
    return SANDBOX_DIR / draft_name


def get_submission_path(task_id: str) -> Path:
    """
    Generate the submission metadata path.

    Args:
        task_id: Current task identifier

    Returns:
        Path to the submission JSON in sandbox
    """
    safe_task_id = "".join(c if c.isalnum() or c == "_" else "_" for c in task_id)
    return SANDBOX_DIR / f"{safe_task_id}.submission.json"


def compute_file_hash(path: Path) -> str:
    """
    Compute SHA256 hash of a file for conflict detection.

    Args:
        path: File to hash

    Returns:
        Hex digest of SHA256 hash
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def ensure_sandbox_exists() -> None:
    """Ensure the sandbox directory exists."""
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Sandbox directory ready: {SANDBOX_DIR}")


def cleanup_task_drafts(task_id: str) -> int:
    """
    Clean up all drafts for a completed task.

    Args:
        task_id: Task identifier

    Returns:
        Number of files cleaned up
    """
    safe_task_id = "".join(c if c.isalnum() or c == "_" else "_" for c in task_id)
    pattern = f"*.{safe_task_id}.*"

    count = 0
    for draft_file in SANDBOX_DIR.glob(pattern):
        try:
            draft_file.unlink()
            count += 1
            logger.debug(f"Cleaned up: {draft_file}")
        except Exception as e:
            logger.warning(f"Failed to clean up {draft_file}: {e}")

    logger.info(f"Cleaned up {count} draft files for task {task_id}")
    return count
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/src/sandbox.py`

---

## Prompt 11.4: Create Sandbox Tests

### Context
The sandbox security is critical. We need tests that verify the guardrails hold.

### Task
Create `tests/test_sandbox.py`:

```python
#!/usr/bin/env python3
"""
Tests for sandbox path validation.

These tests verify that the security guardrails cannot be bypassed.
"""

import pytest
from pathlib import Path
import tempfile
import os

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sandbox import (
    validate_sandbox_write,
    validate_source_read,
    get_draft_path,
    compute_file_hash,
    SANDBOX_DIR,
)


class TestSandboxWriteValidation:
    """Test that sandbox write validation blocks unauthorized paths."""

    def test_valid_draft_path(self):
        """Valid .draft file in sandbox should pass."""
        path = SANDBOX_DIR / "test.task123.draft"
        result = validate_sandbox_write(path)
        assert result.valid is True
        assert result.reason == "OK"

    def test_valid_submission_path(self):
        """Valid .submission.json file in sandbox should pass."""
        path = SANDBOX_DIR / "task123.submission.json"
        result = validate_sandbox_write(path)
        assert result.valid is True

    def test_block_outside_sandbox(self):
        """Paths outside sandbox must be blocked."""
        path = Path("/tmp/malicious.draft")
        result = validate_sandbox_write(path)
        assert result.valid is False
        assert "outside sandbox" in result.reason.lower()

    def test_block_parent_directory(self):
        """Paths in parent directory must be blocked."""
        path = SANDBOX_DIR.parent / "escape.draft"
        result = validate_sandbox_write(path)
        assert result.valid is False

    def test_block_path_traversal(self):
        """Path traversal attempts must be blocked."""
        path = SANDBOX_DIR / ".." / ".." / "src" / "evil.py"
        result = validate_sandbox_write(path)
        assert result.valid is False
        assert "traversal" in result.reason.lower() or "outside" in result.reason.lower()

    def test_block_invalid_extension(self):
        """Only .draft and .submission.json extensions allowed."""
        path = SANDBOX_DIR / "malicious.py"
        result = validate_sandbox_write(path)
        assert result.valid is False
        assert "extension" in result.reason.lower()

    def test_block_absolute_escape(self):
        """Absolute paths outside sandbox must be blocked."""
        path = Path("/etc/passwd")
        result = validate_sandbox_write(path)
        assert result.valid is False


class TestSourceReadValidation:
    """Test that source read validation works correctly."""

    def test_valid_source_in_workspace(self, tmp_path):
        """Valid source file in workspace should pass."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        result = validate_source_read(test_file, tmp_path)
        assert result.valid is True

    def test_block_outside_workspace(self, tmp_path):
        """Files outside workspace must be blocked."""
        result = validate_source_read("/etc/passwd", tmp_path)
        assert result.valid is False
        assert "outside workspace" in result.reason.lower()

    def test_block_nonexistent_file(self, tmp_path):
        """Nonexistent files must be blocked."""
        result = validate_source_read(tmp_path / "missing.py", tmp_path)
        assert result.valid is False
        assert "not found" in result.reason.lower()

    def test_block_sensitive_files(self, tmp_path):
        """Sensitive files (.env, credentials, etc.) must be blocked."""
        env_file = tmp_path / ".env"
        env_file.write_text("SECRET=abc123")

        result = validate_source_read(env_file, tmp_path)
        assert result.valid is False
        assert "sensitive" in result.reason.lower()

    def test_block_directory(self, tmp_path):
        """Directories must be blocked (only files allowed)."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = validate_source_read(subdir, tmp_path)
        assert result.valid is False
        assert "not a file" in result.reason.lower()


class TestDraftPathGeneration:
    """Test draft path generation."""

    def test_draft_path_format(self):
        """Draft path should follow naming convention."""
        source = Path("/workspace/src/foo.py")
        draft = get_draft_path(source, "task_123")

        assert draft.parent == SANDBOX_DIR
        assert draft.name == "foo.py.task_123.draft"

    def test_sanitizes_task_id(self):
        """Task ID should be sanitized."""
        source = Path("/workspace/evil.py")
        draft = get_draft_path(source, "../../etc/passwd")

        # Should not contain path separators
        assert "/" not in draft.name
        assert ".." not in draft.name


class TestFileHash:
    """Test file hashing for conflict detection."""

    def test_consistent_hash(self, tmp_path):
        """Same content should produce same hash."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"

        content = "test content"
        file1.write_text(content)
        file2.write_text(content)

        assert compute_file_hash(file1) == compute_file_hash(file2)

    def test_different_hash_for_different_content(self, tmp_path):
        """Different content should produce different hash."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"

        file1.write_text("content a")
        file2.write_text("content b")

        assert compute_file_hash(file1) != compute_file_hash(file2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/tests/test_sandbox.py`

---

## Prompt 11.5: Integration Smoke Test

### Context
Before moving to Phase 12, verify the sandbox infrastructure works end-to-end.

### Task
Create `scripts/test_sandbox_infra.py`:

```python
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
    test_file = workspace / "src" / "config.py"
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
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/scripts/test_sandbox_infra.py`

---

## Execution Order

1. **11.1** - Create sandbox directory structure
2. **11.2** - Update .gitignore
3. **11.3** - Create path validation module (`src/sandbox.py`)
4. **11.4** - Create sandbox tests
5. **11.5** - Run smoke test

### Verification

```bash
# After completing all prompts:

# 1. Check directory exists
ls -la _handoff/drafts/

# 2. Run unit tests
pytest tests/test_sandbox.py -v

# 3. Run smoke test
python scripts/test_sandbox_infra.py
```

---

## Success Criteria

Phase 11 is DONE when:
- [ ] `_handoff/drafts/` directory exists with README
- [ ] `.gitignore` excludes draft contents but keeps structure
- [ ] `src/sandbox.py` exists with all validation functions
- [ ] All security tests pass (escape attempts blocked)
- [ ] Smoke test reports "Ready for Phase 12"

---

## Security Checklist

Before marking Phase 11 complete, verify:

- [ ] `validate_sandbox_write()` blocks ALL paths outside `_handoff/drafts/`
- [ ] Path traversal (`..`) is blocked
- [ ] Only `.draft` and `.submission.json` extensions allowed
- [ ] Sensitive files (`.env`, `credentials`, etc.) cannot be read for drafting
- [ ] No shell execution anywhere in sandbox.py
- [ ] All validation failures are logged with SECURITY prefix

---

## What This Enables

After Phase 11, we have:
1. **A secure sandbox** - Workers literally cannot write anywhere else
2. **Path validation** - Ready for Phase 12's Ollama tools to use
3. **Audit infrastructure** - Hashing for conflict detection
4. **Cleanup utilities** - For post-task hygiene

Phase 12 will add the actual Ollama MCP tools that call these validation functions.

---

*Phase 11 is the security foundation. Get this right, and V4 is safe. Get it wrong, and workers can escape the sandbox.*

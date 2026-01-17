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
        # Note: Depending on where tmp_path is, this might fail if it's not relative to workspace.
        # But here we are passing tmp_path AS the workspace_root, so it should be relative.
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

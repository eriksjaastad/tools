#!/usr/bin/env python3
"""
Tests for the draft gate.

These tests verify the gate correctly accepts, rejects, and escalates drafts.
"""

import pytest
import json
import re
from pathlib import Path
import tempfile
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.draft_gate import (
    analyze_safety,
    generate_diff,
    MAX_DELETION_RATIO,
    SECRET_PATTERNS,
    HARDCODED_PATH_PATTERNS,
)
from src.sandbox import SafetyAnalysis


class TestSafetyAnalysis:
    """Test the safety analysis function."""

    def test_detects_api_key(self):
        """Should detect API keys in content."""
        content = 'api_key = "sk-abc123xyz456"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_secrets is True

    def test_detects_password(self):
        """Should detect passwords in content."""
        content = 'password = "super_secret_123"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_secrets is True

    def test_detects_hardcoded_path_unix(self):
        """Should detect hardcoded Unix paths."""
        content = 'path = "/Users/erik/projects/file.py"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_hardcoded_paths is True

    def test_detects_hardcoded_path_linux(self):
        """Should detect hardcoded Linux home paths."""
        content = 'path = "/home/user/documents/file.txt"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_hardcoded_paths is True

    def test_allows_relative_paths(self):
        """Should allow relative paths."""
        content = 'path = "./config/settings.json"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_hardcoded_paths is False

    def test_calculates_deletion_ratio(self):
        """Should calculate deletion ratio correctly."""
        safety = analyze_safety("content", added_lines=5, removed_lines=50, original_lines=100)
        assert safety.deletion_ratio == 0.5

    def test_flags_high_deletion(self):
        """Should flag high deletion ratio."""
        safety = analyze_safety("content", added_lines=0, removed_lines=60, original_lines=100)
        assert safety.deletion_ratio > MAX_DELETION_RATIO
        assert len(safety.issues) > 0

    def test_clean_content_passes(self):
        """Clean content should pass all checks."""
        content = '''
def hello():
    print("Hello, World!")

if __name__ == "__main__":
    hello()
'''
        safety = analyze_safety(content, added_lines=5, removed_lines=2, original_lines=10)
        assert safety.has_secrets is False
        assert safety.has_hardcoded_paths is False
        assert safety.deletion_ratio < MAX_DELETION_RATIO


class TestDiffGeneration:
    """Test diff generation."""

    def test_generates_diff(self, tmp_path):
        """Should generate unified diff."""
        original = tmp_path / "original.py"
        draft = tmp_path / "draft.py"

        original.write_text("line1\nline2\nline3\n")
        draft.write_text("line1\nmodified\nline3\nnew_line\n")

        diff_text, added, removed = generate_diff(original, draft)

        assert added == 2  # "modified" and "new_line"
        assert removed == 1  # "line2"
        assert "modified" in diff_text

    def test_handles_identical_files(self, tmp_path):
        """Should handle identical files."""
        original = tmp_path / "original.py"
        draft = tmp_path / "draft.py"

        content = "same content\n"
        original.write_text(content)
        draft.write_text(content)

        diff_text, added, removed = generate_diff(original, draft)

        assert added == 0
        assert removed == 0


class TestSecretPatterns:
    """Test that secret patterns catch real secrets."""

    @pytest.mark.parametrize("secret", [
        'api_key = "sk-abcdef1234567890abcdef"',
        "API_KEY='sk-1234567890abcdefghij1234567890ab'",
        'password = "my_super_secret"',
        'secret = "dont_tell_anyone"',
        'key = "AIzaSyABC123def456GHI789jkl012MNO345pqr"',
    ])
    def test_catches_secrets(self, secret):
        """Should catch various secret patterns."""
        matched = any(
            re.search(pattern, secret)
            for pattern in SECRET_PATTERNS
        )
        assert matched, f"Should catch: {secret}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

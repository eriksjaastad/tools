"""Tests for governance/validators/content-guard.py.

Runs via `pytest governance/validators/tests/`. The `conftest.py` loader
is used to import the validator.
"""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def guard(tmp_path_factory):
    """Load the content-guard validator and provide test utilities."""
    import importlib.util
    import sys

    validators_dir = Path(__file__).parent.parent
    path = validators_dir / "content-guard.py"

    spec = importlib.util.spec_from_file_location("content_guard", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load validator from {path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules["content_guard"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestPatternLoading:
    """Test that patterns are loaded correctly from environment."""

    def test_load_from_env_variable(self, guard, monkeypatch):
        monkeypatch.setenv('CONTENT_GUARD_PATTERNS', 'pattern1\npattern2\npattern3')
        patterns = guard.load_patterns()
        assert patterns == ['pattern1', 'pattern2', 'pattern3']

    def test_load_from_file(self, guard, monkeypatch, tmp_path):
        patterns_file = tmp_path / "patterns.txt"
        patterns_file.write_text("filepattern1\nfilepattern2\n\nfilepattern3")

        monkeypatch.setenv('CONTENT_GUARD_PATTERNS_FILE', str(patterns_file))
        patterns = guard.load_patterns()
        assert patterns == ['filepattern1', 'filepattern2', 'filepattern3']

    def test_load_from_both_sources(self, guard, monkeypatch, tmp_path):
        patterns_file = tmp_path / "patterns.txt"
        patterns_file.write_text("file_pattern")

        monkeypatch.setenv('CONTENT_GUARD_PATTERNS', 'env_pattern')
        monkeypatch.setenv('CONTENT_GUARD_PATTERNS_FILE', str(patterns_file))

        patterns = guard.load_patterns()
        assert 'env_pattern' in patterns
        assert 'file_pattern' in patterns

    def test_empty_when_not_configured(self, guard, monkeypatch):
        monkeypatch.delenv('CONTENT_GUARD_PATTERNS', raising=False)
        monkeypatch.delenv('CONTENT_GUARD_PATTERNS_FILE', raising=False)

        patterns = guard.load_patterns()
        # Empty patterns will cause main() to exit 1 (fail-closed)
        assert patterns == []

    def test_configured_missing_file_fails_closed(self, guard, monkeypatch):
        monkeypatch.setenv('CONTENT_GUARD_PATTERNS_FILE', '/nonexistent/file.txt')
        with pytest.raises(OSError):
            guard.load_patterns()


class TestPatternScanning:
    """Test detection of forbidden patterns in content."""

    def test_detects_exact_pattern(self, guard):
        content = "This is a line with FORBIDDEN_CLIENT in it"
        patterns = ['FORBIDDEN_CLIENT']
        findings = guard.scan_for_patterns(content, patterns)
        assert len(findings) == 1
        assert findings[0]['line_num'] == 1

    def test_case_insensitive_detection(self, guard):
        content = "forbidden_client\nFORBIDDEN_CLIENT\nForbidden_Client"
        patterns = ['FORBIDDEN_CLIENT']
        findings = guard.scan_for_patterns(content, patterns)
        assert len(findings) == 3

    def test_multiple_patterns_detected(self, guard):
        content = "Line with CLIENT_A and CLIENT_B"
        patterns = ['CLIENT_A', 'CLIENT_B']
        findings = guard.scan_for_patterns(content, patterns)
        assert len(findings) == 2

    def test_pattern_in_multiple_lines(self, guard):
        content = """
        Line 1 has SECRET
        Line 2 is clean
        Line 3 has SECRET again
        """
        patterns = ['SECRET']
        findings = guard.scan_for_patterns(content, patterns)
        assert len(findings) == 2
        line_nums = [f['line_num'] for f in findings]
        assert 2 in line_nums
        assert 4 in line_nums

    def test_no_false_positives(self, guard):
        content = "This is completely clean content"
        patterns = ['FORBIDDEN', 'SECRET']
        findings = guard.scan_for_patterns(content, patterns)
        assert len(findings) == 0

    def test_redacts_pattern_in_output(self, guard):
        content = "Line with CLASSIFIED_INFO"
        patterns = ['CLASSIFIED_INFO']
        findings = guard.scan_for_patterns(content, patterns)
        assert len(findings) == 1
        # The pattern field should be redacted/hashed
        assert findings[0]['pattern'].startswith('<pattern-')
        assert 'CLASSIFIED_INFO' not in findings[0]['pattern']


class TestEndToEnd:
    """Integration tests for the full validator."""

    def test_exits_0_when_no_patterns_and_no_files(self, guard, monkeypatch):
        # When patterns exist but no forbidden content
        monkeypatch.setenv('CONTENT_GUARD_PATTERNS', 'FORBIDDEN')

        content = "This is clean content"
        findings = guard.scan_for_patterns(content, ['FORBIDDEN'])
        assert len(findings) == 0

    def test_finds_content_across_file_types(self, guard):
        patterns = ['SECRET_CLIENT']

        py_content = "client = 'SECRET_CLIENT'"
        js_content = "const client = 'SECRET_CLIENT';"
        yaml_content = "client: SECRET_CLIENT"

        for content in [py_content, js_content, yaml_content]:
            findings = guard.scan_for_patterns(content, patterns)
            assert len(findings) == 1

    def test_mixed_encoding_file_cannot_hide_ascii_identifier(self, guard, monkeypatch, tmp_path, capsys):
        target = tmp_path / "clients.csv"
        target.write_bytes(b"\xffname,FORBIDDEN_CLIENT\n")
        monkeypatch.setenv("CONTENT_GUARD_PATTERNS", "FORBIDDEN_CLIENT")
        monkeypatch.setattr("sys.argv", ["content-guard.py", str(target)])
        with pytest.raises(SystemExit) as result:
            guard.main()
        assert result.value.code == 1
        assert "FORBIDDEN_CLIENT" not in capsys.readouterr().err

    @pytest.mark.parametrize("encoding", ["utf-16", "utf-32", "utf-16-le", "utf-16-be",
                                          "utf-32-le", "utf-32-be"])
    def test_unicode_export_detected(self, guard, monkeypatch, tmp_path, encoding):
        target = tmp_path / "clients.csv"
        target.write_bytes("name,FORBIDDEN_CLIENT\n".encode(encoding))
        monkeypatch.setenv("CONTENT_GUARD_PATTERNS", "FORBIDDEN_CLIENT")
        monkeypatch.setattr("sys.argv", ["content-guard.py", str(target)])
        with pytest.raises(SystemExit) as result:
            guard.main()
        assert result.value.code == 1

    @pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
    def test_unicode_marker_without_nul_bytes(self, guard, monkeypatch, tmp_path, encoding):
        marker = "顧客名称"
        target = tmp_path / "clients.csv"
        target.write_bytes(marker.encode(encoding))
        assert b"\0" not in target.read_bytes()
        monkeypatch.setenv("CONTENT_GUARD_PATTERNS", marker)
        monkeypatch.setattr("sys.argv", ["content-guard.py", str(target)])
        with pytest.raises(SystemExit) as result:
            guard.main()
        assert result.value.code == 1

    def test_missing_input_fails_closed(self, guard, monkeypatch, tmp_path):
        monkeypatch.setenv("CONTENT_GUARD_PATTERNS", "FORBIDDEN_CLIENT")
        monkeypatch.setattr("sys.argv", ["content-guard.py", str(tmp_path / "missing.log")])
        with pytest.raises(SystemExit) as result:
            guard.main()
        assert result.value.code == 2

    def test_missing_configuration_uses_documented_exit(self, guard, monkeypatch, tmp_path):
        monkeypatch.delenv("CONTENT_GUARD_PATTERNS", raising=False)
        monkeypatch.delenv("CONTENT_GUARD_PATTERNS_FILE", raising=False)
        monkeypatch.setattr("sys.argv", ["content-guard.py", str(tmp_path / "report.log")])
        with pytest.raises(SystemExit) as result:
            guard.main()
        assert result.value.code == 2

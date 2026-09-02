"""Tests for governance/validators/secrets-scanner.py SKIP_PATTERNS.

Runs via `pytest governance/validators/tests/`. The `scanner` fixture, and the
importlib loading it needs, live in conftest.py — shared with the other
validator test modules rather than duplicated here.
"""
import pytest


class TestSkipPatterns:
    """Regression coverage for #6013 Finding 1: `tests?/` skip pattern
    used an unanchored `re.search` so `manifests/` and other directories
    whose names contain `tests` would be silently skipped."""

    # Paths that ARE test fixtures and MUST be skipped.
    @pytest.mark.parametrize("path", [
        "hooks/tests/fixtures.py",
        "hooks/test/conftest.py",
        "project/tests/helpers.py",
        "tests/fake_creds.py",  # tests/ at repo root
        "nested/deep/tests/secrets.py",
    ])
    def test_real_test_dirs_are_skipped(self, scanner, path):
        assert scanner.should_skip_file(path) is True

    # Paths that LOOK like they contain "tests" but are NOT test directories.
    # The old unanchored `tests?/` regex matched these incorrectly.
    @pytest.mark.parametrize("path", [
        "manifests/interest_tests_archive/real_creds.py",
        "contests/entries/creds.py",
        "requests/config.py",  # `requests` contains `tests`? Yes: r-e-q-u-e-s-t-s. The t-e-s-t-s substring at end.
    ])
    def test_substring_dirs_are_not_skipped(self, scanner, path):
        # These are not under a real tests/ dir, so should NOT be skipped.
        assert scanner.should_skip_file(path) is False

    # Filename-convention matches (independent of directory).
    @pytest.mark.parametrize("path", [
        "src/test_user.py",
        "pkg/foo_test.py",
    ])
    def test_filename_convention_still_skipped(self, scanner, path):
        assert scanner.should_skip_file(path) is True

    # Markdown and env-template skips unaffected.
    @pytest.mark.parametrize("path", [
        "README.md",
        "docs/guide.md",
        ".env.example",
        ".env.template",
        ".env.sample",
    ])
    def test_docs_and_env_templates_still_skipped(self, scanner, path):
        assert scanner.should_skip_file(path) is True

    # Real source paths must NOT be skipped.
    @pytest.mark.parametrize("path", [
        "src/main.py",
        "app/settings.py",
        "governance/validators/secrets-scanner.py",
    ])
    def test_real_source_is_not_skipped(self, scanner, path):
        assert scanner.should_skip_file(path) is False

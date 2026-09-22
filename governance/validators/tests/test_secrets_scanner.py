"""Tests for governance/validators/secrets-scanner.py SKIP_PATTERNS.

Runs via `pytest governance/validators/tests/`. The `scanner` fixture, and the
importlib loading it needs, live in conftest.py — shared with the other
validator test modules rather than duplicated here.
"""
import pytest


class TestGitHubTokenDetection:
    """Regression coverage for #7182: GitHub App installation token format
    changed 2026-04-27 to support stateless tokens (ghs_<APPID>_<JWT>).
    The new format includes dots and can be ~520 chars, not exactly 36."""

    @pytest.mark.parametrize("token", [
        "ghs_" + "a" * 36,
        "ghs_" + "Z" * 40,
        "ghs_" + "x" * 100,
        "ghs_16_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.BBBBBB.CCCCCCCCCCCCCCCCCCCCCCCCCCCC",
        "ghs_123456_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
    ])
    def test_new_ghs_format_detected(self, scanner, token):
        findings = scanner.scan_for_secrets(f"TOKEN = '{token}'")
        assert len(findings) == 1
        assert findings[0]["type"] == "GitHub Server Token"

    @pytest.mark.parametrize("token", [
        "ghp_" + "a" * 36,
        "ghp_" + "Z" * 40,
    ])
    def test_ghp_format_with_variable_length(self, scanner, token):
        findings = scanner.scan_for_secrets(f"TOKEN = '{token}'")
        assert len(findings) == 1
        assert findings[0]["type"] == "GitHub Personal Access Token"

    @pytest.mark.parametrize("token", [
        "gho_" + "a" * 36,
        "gho_" + "b" * 50,
    ])
    def test_gho_format_with_variable_length(self, scanner, token):
        findings = scanner.scan_for_secrets(f"TOKEN = '{token}'")
        assert len(findings) == 1
        assert findings[0]["type"] == "GitHub OAuth Token"

    def test_ghs_with_dots_and_underscores_detected(self, scanner):
        token = "ghs_16_ABC.DEF_GHI-JKL." + "x" * 50
        findings = scanner.scan_for_secrets(f"export GH_TOKEN={token}")
        assert len(findings) == 1
        assert findings[0]["type"] == "GitHub Server Token"

    def test_old_ghs_format_still_detected(self, scanner):
        token = "ghs_" + "A" * 36
        findings = scanner.scan_for_secrets(f"GH_TOKEN='{token}'")
        assert len(findings) == 1
        assert findings[0]["type"] == "GitHub Server Token"

    def test_no_false_positive_on_ghs_prefix_alone(self, scanner):
        findings = scanner.scan_for_secrets("ghs_short")
        assert len(findings) == 0

    def test_multiple_github_tokens_detected(self, scanner):
        content = f"""
        OLD_TOKEN = 'ghs_{"A" * 36}'
        NEW_TOKEN = 'ghs_16_{"x" * 100}.{"y" * 50}.{"z" * 200}'
        PERSONAL = 'ghp_{"B" * 40}'
        """
        findings = scanner.scan_for_secrets(content)
        assert len(findings) == 3


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

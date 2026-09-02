"""Tests for governance/validators/api-wrapper-check.py.

This validator gates every commit in every project via governance-check.sh,
so a false positive here blocks the whole portfolio. It had no tests at all
before #6459.

The validator is not in the M1-H1 checklist table in CLAUDE.md, but it is
wired into governance-check.sh's VALIDATORS array alongside M1 and M3, so it
carries the same blast radius.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import VALIDATORS_DIR

VALIDATOR_PATH = str(Path(VALIDATORS_DIR) / "api-wrapper-check.py")


class TestShouldCheckFile:
    """Which files the validator opens at all."""

    @pytest.mark.parametrize("path", [
        "src/agent.py", "web/app.js", "api/client.ts",
        "ui/Chat.tsx", "ui/Chat.jsx", "bin/run.mjs", "bin/run.cjs",
    ])
    def test_supported_extensions_are_checked(self, api_check, path):
        assert api_check.should_check_file(Path(path)) is True

    @pytest.mark.parametrize("path", [
        "README.md", "config.yaml", "main.go", "notes.txt",
    ])
    def test_other_extensions_are_not_checked(self, api_check, path):
        assert api_check.should_check_file(Path(path)) is False

    @pytest.mark.parametrize("path", [
        "ai_cost_tracker/core.py",
        "ai-cost-tracker/core.py",
        "api_cost_tracker/core.py",
        "tests/test_agent.py",
        "pkg/test/helper.py",
        "conftest.py",
        "pkg/conftest.py",
        "test_agent.py",
        "pkg/test_agent.py",
        "agent_test.py",
        "src/Chat.test.tsx",
        "src/Chat.test.js",
        "__mocks__/openai.js",
        "node_modules/openai/index.js",
        ".venv/lib/openai.py",
        "site-packages/openai/client.py",
    ])
    def test_skip_paths_are_honoured(self, api_check, path):
        assert api_check.should_check_file(Path(path)) is False

    @pytest.mark.parametrize("path", [
        "manifests/interests/agent.py",   # contains "test" only as a substring
        "contests/entry.py",
        "latest/agent.py",
    ])
    def test_substring_lookalikes_are_still_checked(self, api_check, path):
        """The `(?:^|/)tests?/` anchoring must not match these.

        Same class as the #6013 bug regression-tested in test_secrets_scanner.
        """
        assert api_check.should_check_file(Path(path)) is True

    @pytest.mark.parametrize("path", [
        "doc_audit/run.py",
        "scripts/doc_audit_batch.py",
        "nested/deep/doc_audit/x.py",
    ])
    def test_doc_audit_skip_is_unanchored(self, api_check, path):
        """`doc_audit` has no anchors, so it matches anywhere in a path.

        Pinning current behavior: this is broader than the other skip
        patterns and would exempt an unrelated path containing the substring.
        """
        assert api_check.should_check_file(Path(path)) is False


class TestRawApiPatterns:
    """Every provider pattern must fire."""

    @pytest.mark.parametrize("code,provider", [
        ("resp = client.messages.create(model='m')", "Anthropic"),
        ("resp = client.messages.stream(model='m')", "Anthropic"),
        ("resp = client.chat.completions.create(model='m')", "OpenAI/xAI"),
        ("resp = client.responses.create(model='m')", "OpenAI"),
        ("resp = model.generate_content('hi')", "Google Gemini"),
        ("const r = anthropic.messages.create({})", "Anthropic"),
        ("const r = openai.chat.completions.create({})", "OpenAI/xAI"),
    ])
    def test_each_provider_pattern_matches(self, api_check, code, provider):
        issues = api_check.find_raw_api_calls(code)
        assert issues, f"no issue raised for {code!r}"
        assert provider in {i["provider"] for i in issues}

    def test_clean_code_yields_nothing(self, api_check):
        assert api_check.find_raw_api_calls("x = compute(1)\ny = x + 2") == []

    def test_line_numbers_are_one_indexed(self, api_check):
        content = "import os\n\nresp = client.messages.create(model='m')"
        issues = api_check.find_raw_api_calls(content)
        assert [i["line_num"] for i in issues] == [3]

    def test_js_call_matches_both_generic_and_specific_patterns(self, api_check):
        """`anthropic.messages.create(` satisfies two patterns, so it reports
        twice. Pinned so a future de-duplication is a deliberate change."""
        issues = api_check.find_raw_api_calls("anthropic.messages.create({})")
        assert len(issues) == 2


class TestCommentAndDocstringHandling:
    """Regression for #6459 defect 3.

    Only lines that *started* with a comment or triple-quote were skipped, so a
    trailing comment and every line inside a docstring false-positived.
    """

    def test_trailing_comment_is_not_a_call(self, api_check):
        content = "x = 1  # client.messages.create(model='m')"
        assert api_check.find_raw_api_calls(content) == []

    def test_docstring_body_is_not_a_call(self, api_check):
        content = (
            'def helper():\n'
            '    """Usage:\n'
            "\n"
            "    resp = client.messages.create(model='m')\n"
            '    """\n'
            "    return None\n"
        )
        assert api_check.find_raw_api_calls(content) == []

    def test_single_quoted_docstring_body_is_not_a_call(self, api_check):
        content = (
            "TEXT = '''\n"
            "resp = client.messages.create(model='m')\n"
            "'''\n"
        )
        assert api_check.find_raw_api_calls(content) == []

    def test_real_call_after_a_docstring_is_still_found(self, api_check):
        """The block state must close again, or everything after a docstring
        would be silently exempt."""
        content = (
            'def helper():\n'
            '    """Docs."""\n'
            "    return client.messages.create(model='m')\n"
        )
        issues = api_check.find_raw_api_calls(content)
        assert [i["line_num"] for i in issues] == [3]

    def test_full_line_comment_is_still_skipped(self, api_check):
        assert api_check.find_raw_api_calls("# client.messages.create(x)") == []
        assert api_check.find_raw_api_calls("// openai.chat.completions.create(x)") == []

    def test_js_block_comment_continuation_is_skipped(self, api_check):
        content = "/*\n * anthropic.messages.create({})\n */\n"
        assert api_check.find_raw_api_calls(content) == []

    def test_url_is_not_treated_as_a_comment(self, api_check):
        """`//` inside a URL must not truncate the line."""
        content = "fetch('https://x.com'); openai.chat.completions.create({})"
        assert api_check.find_raw_api_calls(content)


class TestWrapperIndicators:
    """Any wrapper indicator exempts the whole file — by design."""

    @pytest.mark.parametrize("line", [
        "from api_trust_tracker import track",
        "import api_trust_tracker",
        "from ai_cost_tracker import track",
        "import ai_cost_tracker",
        "from tracker import track",
        "from .tracker import track",
        "require('api-trust-tracker')",
        "import { track } from 'api_trust_tracker'",
        "track(resp, 'anthropic')",
        "track(response, 'anthropic')",
    ])
    def test_each_indicator_exempts(self, api_check, line):
        assert api_check.file_uses_wrapper(line) is True

    def test_absent_wrapper_is_detected(self, api_check):
        assert api_check.file_uses_wrapper("x = 1") is False

    def test_exemption_is_file_global(self, tmp_path):
        """Pinned, not endorsed: one indicator anywhere exempts every call in
        the file, including calls nowhere near it. Documented design; changing
        it is a separate card."""
        f = tmp_path / "mixed.py"
        f.write_text(
            "from api_trust_tracker import track\n"
            "a = client.messages.create(model='m')\n"
            "b = client.messages.create(model='m')\n"
        )
        result = subprocess.run(
            [sys.executable, VALIDATOR_PATH, str(f)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0


class TestExitCodes:
    """End-to-end: the contract governance-check.sh depends on."""

    def _run(self, *paths):
        return subprocess.run(
            [sys.executable, VALIDATOR_PATH, *[str(p) for p in paths]],
            capture_output=True, text=True, timeout=30,
        )

    def test_clean_file_exits_zero(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("x = compute(1)\n")
        assert self._run(f).returncode == 0

    def test_raw_call_exits_one(self, tmp_path):
        f = tmp_path / "raw.py"
        f.write_text("resp = client.messages.create(model='m')\n")
        result = self._run(f)
        assert result.returncode == 1
        assert "RAW API CALLS DETECTED" in result.stderr

    def test_trailing_comment_no_longer_blocks(self, tmp_path):
        """Defect 3, proven through main() rather than the helper alone."""
        f = tmp_path / "commented.py"
        f.write_text("x = 1  # resp = client.messages.create(model='m')\n")
        assert self._run(f).returncode == 0

    def test_missing_file_is_ignored(self, tmp_path):
        assert self._run(tmp_path / "nope.py").returncode == 0

    def test_no_arguments_exits_zero(self):
        result = subprocess.run(
            [sys.executable, VALIDATOR_PATH],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0

    def test_only_first_five_issues_shown_per_file(self, tmp_path):
        f = tmp_path / "many.py"
        f.write_text("\n".join(
            f"r{i} = client.messages.create(model='m')" for i in range(8)
        ))
        result = self._run(f)
        assert result.returncode == 1
        assert "... and 3 more" in result.stderr

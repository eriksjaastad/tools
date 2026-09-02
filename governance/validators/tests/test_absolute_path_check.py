"""Tests for governance/validators/absolute-path-check.py (M1).

This validator gates every commit in every project via governance-check.sh,
so a false positive here blocks the whole portfolio. It had no tests at all
before #6459.

NOTE ON FIXTURES: path fixtures are assembled from fragments at runtime rather
than written as literals. This file is checked by the very validator it tests
-- a literal absolute path in the source would make the test suite unable to
pass its own repo's pre-commit hook.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import VALIDATORS_DIR

VALIDATOR_PATH = str(Path(VALIDATORS_DIR) / "absolute-path-check.py")


def _p(*parts: str) -> str:
    """Join path fragments at runtime. See NOTE ON FIXTURES above."""
    return "".join(parts)


MAC = _p("/", "Users", "/", "erik", "/")
LINUX = _p("/", "home", "/", "erik", "/")
BREW = _p("/", "opt", "/", "homebrew", "/")
WINDOWS = _p("C:", "\\", "Users", "\\", "erik", "\\")


class TestShouldCheckFile:
    """Which files the validator opens at all."""

    @pytest.mark.parametrize("path", [
        "src/main.py", "app/index.js", "types/api.ts", "ui/App.tsx",
        "README.md", "config.yaml", "compose.yml", "package.json",
        "run.sh", "setup.bash", "profile.zsh",
        "page.html", "style.css", "theme.scss",
        "main.go", "lib.rs", "app.rb",
        "pyproject.toml", "setup.ini", "app.cfg", "nginx.conf",
    ])
    def test_known_extensions_are_checked(self, path_check, path):
        assert path_check.should_check_file(Path(path)) is True

    @pytest.mark.parametrize("path", [
        "logo.png", "data.bin", "archive.zip", "font.woff2", "notes.txt",
    ])
    def test_unknown_extensions_are_not_checked(self, path_check, path):
        assert path_check.should_check_file(Path(path)) is False

    @pytest.mark.parametrize("name", [
        "Makefile", "Dockerfile", "Vagrantfile", "Gemfile",
    ])
    def test_extensionless_known_filenames_are_checked(self, path_check, name):
        assert path_check.should_check_file(Path(name)) is True

    def test_env_example_is_checked(self, path_check):
        """Regression for #6459 defect 1.

        `.env.example` sat in CHECK_EXTENSIONS, but Path('.env.example').suffix
        is '.example', so the entry was unreachable and env templates were
        never scanned despite the comment claiming they were. It is now matched
        by filename.
        """
        assert path_check.should_check_file(Path(".env.example")) is True
        assert path_check.should_check_file(Path("cfg/.env.example")) is True

    def test_real_env_file_is_still_skipped(self, path_check):
        """`.env` holds real values and is allowed to contain paths."""
        assert path_check.should_check_file(Path(".env")) is False
        assert path_check.should_check_file(Path("svc/.env")) is False

    @pytest.mark.parametrize("path", [
        ".git/config.py",
        "node_modules/pkg/index.js",
        "src/__pycache__/mod.py",
        "app.log",
    ])
    def test_skip_patterns_are_honoured(self, path_check, path):
        assert path_check.should_check_file(Path(path)) is False


class TestFindAbsolutePaths:
    """The four patterns, and what must not match."""

    @pytest.mark.parametrize("root", [MAC, LINUX, BREW, WINDOWS])
    def test_each_pattern_matches(self, path_check, root):
        issues = path_check.find_absolute_paths(f"CONFIG = '{root}data'", "f.py")
        assert len(issues) == 1

    def test_line_numbers_are_one_indexed(self, path_check):
        content = "\n".join(["import os", "", f"P = '{MAC}x'"])
        issues = path_check.find_absolute_paths(content, "f.py")
        assert [i["line_num"] for i in issues] == [3]

    def test_clean_content_yields_nothing(self, path_check):
        content = "P = os.environ['PROJECT_ROOT']\nQ = './data/file.csv'"
        assert path_check.find_absolute_paths(content, "f.py") == []

    @pytest.mark.parametrize("text", [
        _p("/", "usr", "/", "local", "/", "bin"),   # not a user home
        _p("/", "Users"),                            # no trailing user segment
        _p("Users", "/", "erik", "/"),               # relative, not absolute
        _p("/", "opt", "/", "local", "/"),           # not the homebrew prefix
    ])
    def test_near_misses_do_not_match(self, path_check, text):
        assert path_check.find_absolute_paths(f"P = '{text}'", "f.py") == []

    def test_multiple_matches_on_one_line(self, path_check):
        content = f"A = '{MAC}one'; B = '{MAC}two'"
        issues = path_check.find_absolute_paths(content, "f.py")
        assert len(issues) == 1
        assert len(issues[0]["matches"]) == 2

    def test_long_lines_are_truncated_to_100_chars(self, path_check):
        content = f"P = '{MAC}" + ("x" * 300) + "'"
        issues = path_check.find_absolute_paths(content, "f.py")
        assert len(issues[0]["line"]) == 100


class TestDocCommentBypass:
    """Regression for #6459 defect 2.

    The bypass previously fired if 'e.g.' or 'example:' appeared ANYWHERE on
    the line, so a real hardcoded path in code was silently allowed whenever
    an unrelated string on the same line happened to contain those characters.
    It is now scoped to matches that sit inside the comment itself.
    """

    @pytest.mark.parametrize("comment", [
        f"# e.g. {MAC}project",
        f"# example: {MAC}project",
        f"# this is an absolute path: {MAC}project",
        f"// e.g. {MAC}project",
    ])
    def test_documentation_comments_are_ignored(self, path_check, comment):
        assert path_check.find_absolute_paths(comment, "f.py") == []

    def test_marker_in_a_string_no_longer_suppresses_real_code(self, path_check):
        content = f"msg = 'e.g. see the docs'; CONFIG = '{MAC}secrets'"
        issues = path_check.find_absolute_paths(content, "f.py")
        assert len(issues) == 1, "a real hardcoded path was silently allowed"

    def test_code_before_a_doc_comment_is_still_flagged(self, path_check):
        content = f"CONFIG = '{MAC}secrets'  # e.g. any path works here"
        issues = path_check.find_absolute_paths(content, "f.py")
        assert len(issues) == 1
        assert issues[0]["matches"] == [MAC]

    def test_non_documentation_comment_is_still_flagged(self, path_check):
        """A comment without a doc marker is a real finding, not an exemption."""
        content = f"# TODO: move {MAC}data somewhere sane"
        assert len(path_check.find_absolute_paths(content, "f.py")) == 1


class TestCommentStart:
    """The helper that decides where a comment begins."""

    def test_hash_comment(self, path_check):
        assert path_check.comment_start("x = 1  # note") == 7

    def test_double_slash_comment(self, path_check):
        assert path_check.comment_start("x = 1; // note") == 7

    def test_url_is_not_a_comment(self, path_check):
        assert path_check.comment_start("url = 'https://example.com/a'") is None

    def test_hash_inside_a_string_is_not_a_comment(self, path_check):
        assert path_check.comment_start("color = '#ff0000'") is None

    def test_line_without_a_comment(self, path_check):
        assert path_check.comment_start("x = 1") is None


class TestExitCodes:
    """End-to-end: the contract governance-check.sh depends on."""

    def _run(self, *paths):
        return subprocess.run(
            [sys.executable, VALIDATOR_PATH, *[str(p) for p in paths]],
            capture_output=True, text=True, timeout=30,
        )

    def test_clean_file_exits_zero(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("P = os.environ['ROOT']\n")
        assert self._run(f).returncode == 0

    def test_offending_file_exits_one(self, tmp_path):
        f = tmp_path / "dirty.py"
        f.write_text(f"P = '{MAC}data'\n")
        result = self._run(f)
        assert result.returncode == 1
        assert "HARDCODED ABSOLUTE PATHS" in result.stderr

    def test_env_example_is_scanned_end_to_end(self, tmp_path):
        """Defect 1, proven through main() rather than the helper alone."""
        f = tmp_path / ".env.example"
        f.write_text(f"DATA_DIR={MAC}data\n")
        assert self._run(f).returncode == 1

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
        f.write_text("\n".join(f"P{i} = '{MAC}d{i}'" for i in range(8)))
        result = self._run(f)
        assert result.returncode == 1
        assert "... and 3 more" in result.stderr


class TestIntentionalMarker:
    """`# absolute path intentional: ...` exempts its line.

    An established convention across the portfolio: a PATH export that
    legitimately needs absolute entries under a minimal launchd/cron
    environment. Found by the #6459 portfolio sweep, which flagged four such
    files after the first cut of the defect-2 fix.
    """

    def test_marker_in_trailing_comment_exempts_the_line(self, path_check):
        content = f"PATH='{BREW}bin'  # absolute path intentional: minimal env"
        assert path_check.find_absolute_paths(content, "run.sh") == []

    def test_marker_must_be_in_a_comment(self, path_check):
        """A string mentioning the marker is not an exemption."""
        content = f"msg = 'absolute path'; P = '{MAC}data'"
        assert len(path_check.find_absolute_paths(content, "f.py")) == 1


class TestProseFiles:
    """Markdown and friends have no comment syntax.

    A documentation marker anywhere on the line has to scope the whole line,
    or prose describing a bad path is indistinguishable from the bad path.
    Found by the sweep: two AGENTS.md-style files and a README were flagged
    for the sentence that tells authors not to hardcode paths.
    """

    @pytest.mark.parametrize("name", ["doc.md", "doc.markdown", "doc.rst", "doc.txt"])
    def test_documentation_marker_scopes_the_line(self, path_check, name):
        content = f"- NO absolute paths (e.g., `{MAC}...`)."
        assert path_check.find_absolute_paths(content, name) == []

    def test_prose_without_a_marker_is_still_flagged(self, path_check):
        content = f"Set the data directory to {MAC}data before running."
        assert len(path_check.find_absolute_paths(content, "doc.md")) == 1

    def test_code_files_do_not_get_the_prose_carve_out(self, path_check):
        """The defect-2 case: in code, an unscoped marker must not exempt."""
        content = f"msg = 'e.g. see the docs'; CONFIG = '{MAC}secrets'"
        assert len(path_check.find_absolute_paths(content, "f.py")) == 1

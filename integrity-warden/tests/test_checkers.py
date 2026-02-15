"""Tests for checker implementations."""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from integrity_warden import (
    BaseChecker, WikiLinkChecker, MarkdownLinkChecker,
    AbsolutePathChecker, RelativePathChecker, ShellSourceChecker,
    PythonImportChecker, SymlinkChecker, CronChecker, GitHookChecker,
    ScanContext, Issue, run_checks
)


class TestBaseCheckerReadFile:
    """Test BaseChecker._read_file() method."""
    
    def test_read_valid_file(self, tmp_path):
        """Test reading a valid UTF-8 file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        checker = WikiLinkChecker()  # Use concrete implementation
        content = checker._read_file(test_file)
        
        assert content == "Hello, World!"
    
    def test_read_nonexistent_file(self, tmp_path):
        """Test reading a non-existent file returns None."""
        test_file = tmp_path / "nonexistent.txt"
        
        checker = WikiLinkChecker()
        content = checker._read_file(test_file)
        
        assert content is None
    
    def test_read_binary_file(self, tmp_path):
        """Test reading binary file with errors='ignore'."""
        test_file = tmp_path / "binary.bin"
        test_file.write_bytes(b"\x00\x01\x02\xFF\xFE")
        
        checker = WikiLinkChecker()
        content = checker._read_file(test_file)
        
        # Should return something (not None), even if garbled
        assert content is not None
    
    def test_read_large_file(self, tmp_path):
        """Test reading large files."""
        test_file = tmp_path / "large.txt"
        large_content = "x" * 100000
        test_file.write_text(large_content)
        
        checker = WikiLinkChecker()
        content = checker._read_file(test_file)
        
        assert len(content) == 100000
    
    def test_read_utf8_file(self, tmp_path):
        """Test reading UTF-8 file with special characters."""
        test_file = tmp_path / "utf8.txt"
        test_file.write_text("Héllo, Wörld! 你好", encoding="utf-8")
        
        checker = WikiLinkChecker()
        content = checker._read_file(test_file)
        
        assert "Héllo" in content
        assert "你好" in content
    
    def test_read_empty_file(self, tmp_path):
        """Test reading empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        checker = WikiLinkChecker()
        content = checker._read_file(test_file)
        
        assert content == ""


class TestBaseCheckerRelativePath:
    """Test BaseChecker._relative_path() method."""
    
    def test_relative_path_simple(self, tmp_path):
        """Test converting absolute path to relative."""
        root = tmp_path / "root"
        root.mkdir()
        file_path = root / "file.txt"
        file_path.write_text("test")
        
        ctx = ScanContext(root_path=root)
        checker = WikiLinkChecker()
        
        rel_path = checker._relative_path(file_path, ctx)
        
        assert rel_path == "file.txt"
    
    def test_relative_path_nested(self, tmp_path):
        """Test relative path for nested files."""
        root = tmp_path / "root"
        root.mkdir()
        nested_dir = root / "docs" / "guides"
        nested_dir.mkdir(parents=True)
        file_path = nested_dir / "intro.md"
        file_path.write_text("# Intro")
        
        ctx = ScanContext(root_path=root)
        checker = WikiLinkChecker()
        
        rel_path = checker._relative_path(file_path, ctx)
        
        assert rel_path == "docs/guides/intro.md"
    
    def test_relative_path_outside_root(self, tmp_path):
        """Test path outside root returns absolute path."""
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside" / "file.txt"
        outside.parent.mkdir()
        outside.write_text("test")
        
        ctx = ScanContext(root_path=root)
        checker = WikiLinkChecker()
        
        rel_path = checker._relative_path(outside, ctx)
        
        # Should return absolute path if outside root
        assert str(outside) in rel_path


class TestWikiLinkChecker:
    """Test WikiLinkChecker implementation."""
    
    def test_valid_wikilinks_found(self, project_with_wikilinks):
        """Test that valid wikilinks are indexed correctly."""
        ctx = ScanContext.build(project_with_wikilinks.parent)
        checker = WikiLinkChecker()
        
        issues = checker.check(ctx)
        
        # GUIDE.md has valid wikilinks, should have no issues
        guide_issues = [i for i in issues if "GUIDE" in i.file]
        assert len(guide_issues) == 0
    
    def test_broken_wikilinks_detected(self, project_with_wikilinks):
        """Test that broken wikilinks are detected."""
        ctx = ScanContext.build(project_with_wikilinks.parent)
        checker = WikiLinkChecker()
        
        issues = checker.check(ctx)
        
        # BROKEN.md has broken wikilinks
        broken_issues = [i for i in issues if "BROKEN" in i.file]
        assert len(broken_issues) > 0
        
        # Check specific broken targets
        targets = [i.target for i in broken_issues]
        assert "NonExistent" in targets
        assert "MissingGuide" in targets
    
    def test_wikilink_pattern_matching(self, tmp_path):
        """Test that wikilink pattern correctly identifies links."""
        root = tmp_path / "root"
        root.mkdir()
        docs = root / "docs"
        docs.mkdir()
        
        # Create a file with various wikilink patterns
        (docs / "README.md").write_text("# Doc")
        (docs / "TEST.md").write_text("""
Valid: [[README]]
With pipe: [[README|overview]]
Invalid: [[NonExistent]]
""")
        
        ctx = ScanContext.build(root)
        checker = WikiLinkChecker()
        
        issues = checker.check(ctx)
        
        # Should find broken link only
        assert any("NonExistent" in i.target for i in issues)
    
    def test_ignore_bash_patterns(self, tmp_path):
        """Test that bash conditionals are ignored."""
        root = tmp_path / "root"
        root.mkdir()
        docs = root / "docs"
        docs.mkdir()
        
        # Create file with bash patterns that look like wikilinks
        (docs / "GUIDE.md").write_text("""
# Guide

[[ $var -eq 0 ]] && echo "ok"
[[ -f file.txt ]] || create_it
[[ ! -z "$string" ]]
""")
        
        ctx = ScanContext.build(root)
        checker = WikiLinkChecker()
        
        issues = checker.check(ctx)
        
        # Should not report bash conditionals as broken wikilinks
        assert len(issues) == 0
    
    def test_ignore_known_placeholders(self, tmp_path):
        """Test that known placeholders are ignored."""
        root = tmp_path / "root"
        root.mkdir()
        docs = root / "docs"
        docs.mkdir()
        
        (docs / "GUIDE.md").write_text("""
# Guide

See [[Document Name]] for details
Check [[Project Name]] overview
memory:context notes
""")
        
        ctx = ScanContext.build(root)
        checker = WikiLinkChecker()
        
        issues = checker.check(ctx)
        
        # Should not report known placeholders
        assert len(issues) == 0


class TestMarkdownLinkChecker:
    """Test MarkdownLinkChecker implementation."""
    
    def test_valid_markdown_links(self, project_with_markdown_links):
        """Test that valid markdown links are not flagged."""
        ctx = ScanContext.build(project_with_markdown_links.parent)
        checker = MarkdownLinkChecker()
        
        issues = checker.check(ctx)
        
        # LINKS.md has valid links - should not appear in issues
        links_issues = [i for i in issues if "LINKS.md" in i.file and "BROKEN" not in i.file]
        assert len(links_issues) == 0
    
    def test_broken_markdown_links_detected(self, project_with_markdown_links):
        """Test that broken markdown links are detected."""
        ctx = ScanContext.build(project_with_markdown_links.parent)
        checker = MarkdownLinkChecker()
        
        issues = checker.check(ctx)
        
        # BROKEN_LINKS.md has broken links
        broken_issues = [i for i in issues if "BROKEN_LINKS" in i.file]
        assert len(broken_issues) > 0
    
    def test_skip_external_urls(self, tmp_path):
        """Test that external URLs are skipped."""
        root = tmp_path / "root"
        root.mkdir()
        docs = root / "docs"
        docs.mkdir()
        
        (docs / "README.md").write_text("""
- [GitHub](https://github.com)
- [Google](http://google.com)
- [Email](mailto:test@example.com)
- [Phone](tel:555-1234)
""")
        
        ctx = ScanContext.build(root)
        checker = MarkdownLinkChecker()
        
        issues = checker.check(ctx)
        
        # Should not report external URLs
        assert len(issues) == 0
    
    def test_skip_anchor_links(self, tmp_path):
        """Test that anchor-only links are skipped."""
        root = tmp_path / "root"
        root.mkdir()
        docs = root / "docs"
        docs.mkdir()
        
        (docs / "README.md").write_text("""
# Top section

See [section below](#bottom)

## Bottom
Text here
""")
        
        ctx = ScanContext.build(root)
        checker = MarkdownLinkChecker()
        
        issues = checker.check(ctx)
        
        # Should not report anchor links
        assert len(issues) == 0


class TestAbsolutePathChecker:
    """Test AbsolutePathChecker implementation."""
    
    def test_detect_broken_absolute_paths(self, tmp_path):
        """Test detection of broken absolute path references."""
        root = tmp_path / "root"
        root.mkdir()
        
        project_dir = root / "test-project"
        project_dir.mkdir(parents=True)
        
        # Create a reference file with broken absolute paths
        docs_dir = project_dir / "docs"
        docs_dir.mkdir()
        
        # Create reference to nonexistent absolute path
        (docs_dir / "README.md").write_text(f"""
# Project

Valid reference: {root}/test-project/docs
Broken reference: {root}/test-project/nonexistent/file.txt
""")
        
        ctx = ScanContext.build(root)
        checker = AbsolutePathChecker()
        
        issues = checker.check(ctx)
        
        # Verify broken paths are detected
        assert len(issues) > 0, "Expected at least one broken path to be detected"
        
        # Check that we have the correct issue type
        broken_file_issues = [i for i in issues if i.issue_type == "Broken File Path"]
        assert len(broken_file_issues) > 0, "Expected 'Broken File Path' issue type"
        
        # Verify the broken path is in the targets
        assert any("nonexistent" in i.target for i in broken_file_issues), "Expected 'nonexistent' in broken path target"
    
    def test_valid_absolute_paths_not_flagged(self, project_with_paths):
        """Test that valid absolute paths are not flagged."""
        ctx = ScanContext.build(project_with_paths.parent)
        checker = AbsolutePathChecker()
        
        issues = checker.check(ctx)
        
        # Check that valid paths referencing project-b are not in issues
        # (they should not be flagged as broken)
        for issue in issues:
            assert "project-b" not in issue.target or issue.target.count("/") > 2


class TestRelativePathChecker:
    """Test RelativePathChecker implementation."""
    
    def test_detect_broken_relative_paths(self, tmp_path):
        """Test detection of broken relative path references."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create project-a with a reference to broken relative path
        proj_a = root / "project-a"
        proj_a.mkdir()
        
        docs_a = proj_a / "docs"
        docs_a.mkdir()
        
        # Create valid cross-project reference to project-b
        proj_b = root / "project-b"
        proj_b.mkdir()
        docs_b = proj_b / "docs"
        docs_b.mkdir()
        (docs_b / "README.md").write_text("# Project B")
        
        # File in project-a that references broken relative path in project-a (which exists)
        (docs_a / "GUIDE.md").write_text("""
# Guide

Valid: ../project-b/docs/README.md
Missing file in project-a: ../project-a/nonexistent/file.md
Missing file in project-b: ../project-b/missing.md
""")
        
        ctx = ScanContext.build(root)
        checker = RelativePathChecker()
        
        issues = checker.check(ctx)
        
        # Verify at least one broken cross-project reference is detected
        assert len(issues) > 0, "Expected at least one broken cross-project reference"
        
        # Check that issue type is correct
        cross_project_issues = [i for i in issues if i.issue_type == "Broken Cross-Project Reference"]
        assert len(cross_project_issues) > 0, "Expected 'Broken Cross-Project Reference' issue type"
        
        # Verify the broken paths contain expected targets
        assert any("missing" in i.target for i in cross_project_issues), "Expected 'missing' in target"
    
    def test_skip_files_at_root(self, tmp_path):
        """Test that files at root are skipped."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create a file at root level (not in subdirectory)
        (root / "README.md").write_text("""
Reference ../nonexistent/file.md
""")
        
        # Also create a project so the scan works
        project_dir = root / "my-project"
        project_dir.mkdir()
        (project_dir / "index.md").write_text("# Index")
        
        ctx = ScanContext.build(root)
        checker = RelativePathChecker()
        
        issues = checker.check(ctx)
        
        # Should not process root-level files (they have < 2 parts in relative path)
        root_issues = [i for i in issues if i.file == "README.md"]
        assert len(root_issues) == 0


class TestShellSourceChecker:
    """Test ShellSourceChecker implementation."""
    
    def test_detect_broken_shell_sources(self, project_with_scripts):
        """Test detection of broken shell source references."""
        ctx = ScanContext.build(project_with_scripts.parent)
        checker = ShellSourceChecker()
        
        issues = checker.check(ctx)
        
        # main.sh sources from ../nonexistent/library.sh
        broken_issues = [i for i in issues if "nonexistent" in i.target]
        assert len(broken_issues) > 0
    
    def test_valid_shell_sources(self, project_with_scripts):
        """Test that valid shell sources are not flagged."""
        ctx = ScanContext.build(project_with_scripts.parent)
        checker = ShellSourceChecker()
        
        issues = checker.check(ctx)
        
        # Should not flag ./common.sh as broken
        common_issues = [i for i in issues if "common.sh" in i.target]
        assert len(common_issues) == 0
    
    def test_skip_system_paths(self, tmp_path):
        """Test that system paths are skipped."""
        root = tmp_path / "root"
        root.mkdir()
        scripts = root / "scripts"
        scripts.mkdir()
        
        # Create a shell script that sources only system paths
        (scripts / "test.sh").write_text("""
#!/bin/bash
source /dev/null
source -
echo "content"
""")
        
        ctx = ScanContext.build(root)
        checker = ShellSourceChecker()
        
        issues = checker.check(ctx)
        
        # Should not report /dev/null or - as broken sources (they're special cases)
        assert len(issues) == 0
    
    def test_skip_variable_references(self, tmp_path):
        """Test that variable references are skipped."""
        root = tmp_path / "root"
        root.mkdir()
        scripts = root / "scripts"
        scripts.mkdir()
        
        (scripts / "test.sh").write_text("""
#!/bin/bash
source "$LIBRARY_PATH/util.sh"
source ${LIB_DIR}/common.sh
""")
        
        ctx = ScanContext.build(root)
        checker = ShellSourceChecker()
        
        issues = checker.check(ctx)
        
        # Should not report variable references
        assert len(issues) == 0


class TestPythonImportChecker:
    """Test PythonImportChecker implementation."""
    
    def test_detect_broken_relative_imports(self, tmp_path):
        """Test detection of broken relative imports."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create package structure
        pkg_a = root / "package_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text("")
        (pkg_a / "module.py").write_text("""
from .nonexistent import something
from ..missing_module import helper
""")
        
        ctx = ScanContext.build(root)
        checker = PythonImportChecker()
        
        issues = checker.check(ctx)
        
        # Should find broken imports
        assert len(issues) > 0
    
    def test_valid_relative_imports(self, tmp_path):
        """Test that valid relative imports are not flagged."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create valid package structure
        pkg = root / "mypackage"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "utils.py").write_text("def helper(): pass")
        (pkg / "main.py").write_text("""
from .utils import helper
from . import utils
""")
        
        ctx = ScanContext.build(root)
        checker = PythonImportChecker()
        
        issues = checker.check(ctx)
        
        # Should not flag valid imports
        main_issues = [i for i in issues if "main.py" in i.file]
        assert len(main_issues) == 0
    
    def test_skip_absolute_imports(self, tmp_path):
        """Test that absolute imports are skipped."""
        root = tmp_path / "root"
        root.mkdir()
        src = root / "src"
        src.mkdir()
        
        (src / "test.py").write_text("""
import os
import sys
import requests
from pathlib import Path
""")
        
        ctx = ScanContext.build(root)
        checker = PythonImportChecker()
        
        issues = checker.check(ctx)
        
        # Should not report absolute imports
        assert len(issues) == 0
    
    def test_parent_directory_imports(self, tmp_path):
        """Test relative imports from parent directories."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create nested package structure
        pkg = root / "package"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        
        sub = pkg / "subpkg"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        (sub / "module.py").write_text("""
from .. import package_module
from ...missing import something
""")
        
        ctx = ScanContext.build(root)
        checker = PythonImportChecker()
        
        issues = checker.check(ctx)
        
        # Should find broken parent import
        broken_imports = [i for i in issues if "missing" in i.target]
        assert len(broken_imports) > 0


class TestSymlinkChecker:
    """Test SymlinkChecker implementation."""
    
    def test_detect_broken_symlinks(self, project_with_symlinks):
        """Test detection of broken symbolic links."""
        ctx = ScanContext.build(project_with_symlinks.parent)
        checker = SymlinkChecker()
        
        issues = checker.check(ctx)
        
        # Should find the broken symlink
        broken_issues = [i for i in issues if i.issue_type == "Broken Symlink"]
        assert len(broken_issues) > 0
        
        # Verify the broken link is in targets
        targets = [i.target for i in broken_issues]
        assert any("nonexistent" in t for t in targets)
    
    def test_not_flag_valid_symlinks(self, project_with_symlinks):
        """Test that valid symlinks are not flagged."""
        ctx = ScanContext.build(project_with_symlinks.parent)
        checker = SymlinkChecker()
        
        issues = checker.check(ctx)
        
        # Should not flag the valid symlink
        broken_link_issues = [i for i in issues if "valid_link" in i.file]
        assert len(broken_link_issues) == 0
    
    def test_symlink_severity_is_error(self, project_with_symlinks):
        """Test that broken symlink issues have error severity."""
        ctx = ScanContext.build(project_with_symlinks.parent)
        checker = SymlinkChecker()
        
        issues = checker.check(ctx)
        
        broken_issues = [i for i in issues if i.issue_type == "Broken Symlink"]
        if broken_issues:
            assert all(i.severity == "error" for i in broken_issues)
    
    def test_symlink_checker_on_empty_directory(self, tmp_path):
        """Test symlink checker on directory with no symlinks."""
        root = tmp_path / "empty_root"
        root.mkdir()
        (root / "regular_file.txt").write_text("just a file")
        
        ctx = ScanContext.build(root)
        checker = SymlinkChecker()
        
        issues = checker.check(ctx)
        
        # Should not report any symlink issues
        symlink_issues = [i for i in issues if "Symlink" in i.issue_type]
        assert len(symlink_issues) == 0


class TestCronChecker:
    """Test CronChecker implementation."""
    
    @patch('subprocess.run')
    def test_parse_broken_cron_script_paths(self, mock_run):
        """Test parsing cron lines with broken script paths."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""# My crontab
0 2 * * * /usr/local/bin/backup.sh
0 9 * * 1 /home/user/scripts/weekly-check.sh
30 * * * * /nonexistent/script.py
@daily /home/user/maintenance.sh
"""
        )
        
        root = Path("/tmp/projects")
        ctx = ScanContext(root_path=root)
        checker = CronChecker()
        
        issues = checker.check(ctx)
        
        # Should find the broken script reference
        broken_issues = [i for i in issues if "/nonexistent" in i.target]
        assert len(broken_issues) > 0
    
    @patch('subprocess.run')
    def test_skip_system_paths_in_cron(self, mock_run):
        """Test that system paths are skipped in cron."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""# Crontab
*/5 * * * * /usr/bin/curl https://example.com
0 * * * * /usr/local/bin/check_status
"""
        )
        
        root = Path("/tmp/projects")
        ctx = ScanContext(root_path=root)
        checker = CronChecker()
        
        issues = checker.check(ctx)
        
        # Should not flag system paths
        assert len(issues) == 0
    
    @patch('subprocess.run')
    def test_handle_empty_crontab(self, mock_run):
        """Test handling of empty crontab."""
        mock_run.return_value = MagicMock(
            returncode=1,  # No crontab for user
            stdout=""
        )
        
        root = Path("/tmp/projects")
        ctx = ScanContext(root_path=root)
        checker = CronChecker()
        
        issues = checker.check(ctx)
        
        # Should return empty list on crontab error
        assert issues == []
    
    @patch('subprocess.run')
    def test_cron_with_cd_command(self, mock_run, tmp_path):
        """Test cron parsing with cd command."""
        script_path = tmp_path / "script.sh"
        script_path.write_text("echo done")
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=f"""0 2 * * * cd {tmp_path} && ./script.sh
0 3 * * * cd /nonexistent && ./run.sh
"""
        )
        
        ctx = ScanContext(root_path=tmp_path)
        checker = CronChecker()
        
        issues = checker.check(ctx)
        
        # Should find the broken script in nonexistent directory
        broken_issues = [i for i in issues if "/nonexistent" in str(i.context)]
        assert len(broken_issues) > 0
    
    @patch('subprocess.run')
    def test_skip_cron_comments(self, mock_run):
        """Test that cron comments are skipped."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""# This is a comment with /path/to/file.sh
# Another comment: /nonexistent/important.sh
0 2 * * * /usr/bin/real_command
"""
        )
        
        root = Path("/tmp/projects")
        ctx = ScanContext(root_path=root)
        checker = CronChecker()
        
        issues = checker.check(ctx)
        
        # Should not report paths from comments
        assert len(issues) == 0


class TestGitHookChecker:
    """Test GitHookChecker implementation."""
    
    def test_detect_broken_script_references(self, tmp_path):
        """Test detecting broken script references in git hooks."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create a project with git directory
        git_dir = root / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        
        # Create a pre-commit hook with broken script reference
        hook_file = git_dir / "pre-commit"
        hook_file.write_text("""#!/bin/bash
set -e

# Source external scripts
source ./scripts/validate.sh
source /home/user/shared/lint.sh
source /nonexistent/checker.sh
""")
        
        ctx = ScanContext.build(root)
        checker = GitHookChecker()
        
        issues = checker.check(ctx)
        
        # Should find broken references
        broken_issues = [i for i in issues if "Broken Git Hook Reference" in i.issue_type]
        assert len(broken_issues) > 0
        
        # Verify the nonexistent path is caught
        targets = [i.target for i in broken_issues]
        assert any("/nonexistent" in t for t in targets)
    
    def test_skip_sample_files(self, tmp_path):
        """Test that .sample files are skipped."""
        root = tmp_path / "root"
        root.mkdir()
        
        git_dir = root / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        
        # Create a .sample file with broken references
        sample_file = git_dir / "pre-commit.sample"
        sample_file.write_text("""#!/bin/bash
source /nonexistent/file.sh
""")
        
        ctx = ScanContext.build(root)
        checker = GitHookChecker()
        
        issues = checker.check(ctx)
        
        # Should not check .sample files
        sample_issues = [i for i in issues if ".sample" in i.file]
        assert len(sample_issues) == 0
    
    def test_handle_hooks_that_source_missing_files(self, tmp_path):
        """Test handling hooks that source non-existent files."""
        root = tmp_path / "root"
        root.mkdir()
        
        git_dir = root / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        
        # Create a hook that sources missing files
        hook_file = git_dir / "commit-msg"
        hook_file.write_text("""#!/bin/bash
. ./common/functions.sh
source ../utils/helpers.sh
""")
        
        ctx = ScanContext.build(root)
        checker = GitHookChecker()
        
        issues = checker.check(ctx)
        
        # Should detect broken source references
        broken_issues = [i for i in issues if "Broken Git Hook Reference" in i.issue_type]
        assert len(broken_issues) > 0
    
    def test_git_hook_checker_severity(self, tmp_path):
        """Test that git hook issues have error severity."""
        root = tmp_path / "root"
        root.mkdir()
        
        git_dir = root / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        
        hook_file = git_dir / "pre-push"
        hook_file.write_text("source /nonexistent/checker.sh")
        
        ctx = ScanContext.build(root)
        checker = GitHookChecker()
        
        issues = checker.check(ctx)
        
        if issues:
            assert all(i.severity == "error" for i in issues)


class TestBaseCheckerReadFilePermissionError:
    """Test BaseChecker._read_file() permission error handling."""
    
    def test_read_file_permission_error(self, tmp_path):
        """Test reading file with no read permissions returns None."""
        test_file = tmp_path / "restricted.txt"
        test_file.write_text("Secret content")
        
        # Remove read permissions
        os.chmod(test_file, 0o000)
        
        try:
            checker = WikiLinkChecker()
            content = checker._read_file(test_file)
            
            # Should return None on permission error
            assert content is None
        finally:
            # Restore permissions for cleanup
            os.chmod(test_file, 0o644)



class TestRunChecksIntegration:
    """Integration tests for run_checks() function."""
    
    def test_run_checks_with_mixed_issues(self, tmp_path):
        """Test run_checks with multiple issue types present."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create docs with wikilink issues
        docs_dir = root / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Main")
        (docs_dir / "BROKEN.md").write_text("[[NonExistent]] reference")
        
        # Create shell script with broken source
        scripts_dir = root / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "test.sh").write_text("source /missing/lib.sh")
        
        issues = run_checks(root)
        
        # Should find multiple issue types
        assert len(issues) > 0
        
        # Verify we have different issue types
        issue_types = {i.issue_type for i in issues}
        assert len(issue_types) >= 2  # At least wikilink and shell source issues
    
    def test_run_checks_deduplication(self, tmp_path):
        """Test that run_checks deduplicates issues across checkers."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create a scenario where multiple checkers might report the same issue
        project_dir = root / "project"
        project_dir.mkdir()
        
        docs_dir = project_dir / "docs"
        docs_dir.mkdir()
        
        # Create files that might be reported by different checkers
        (docs_dir / "README.md").write_text("# Doc")
        (docs_dir / "BROKEN.md").write_text("""
# Broken references
[[README]]
[Valid Link](README.md)
[[NonExistent]]
[Broken Link](missing.md)
""")
        
        issues = run_checks(root)
        
        # Convert to set to check deduplication
        unique_issues = set(issues)
        
        # Deduplication should work based on (file, issue_type, target)
        assert len(unique_issues) == len(issues)
    
    def test_run_checks_returns_list(self, tmp_path):
        """Test that run_checks returns a list."""
        root = tmp_path / "root"
        root.mkdir()
        (root / "file.txt").write_text("test")
        
        issues = run_checks(root)
        
        assert isinstance(issues, list)
        assert all(isinstance(i, Issue) for i in issues)
    
    def test_run_checks_with_empty_project(self, tmp_path):
        """Test run_checks on project with no issues."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create valid structure
        docs_dir = root / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Main Doc")
        (docs_dir / "GUIDE.md").write_text("# Guide\n\nSee [README](README.md)")
        
        # Mock CronChecker to avoid picking up user's actual crontab
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            issues = run_checks(root)
        
        # Should have no issues (or minimal system-related issues)
        broken_issues = [i for i in issues if "Broken" in i.issue_type]
        assert len(broken_issues) == 0

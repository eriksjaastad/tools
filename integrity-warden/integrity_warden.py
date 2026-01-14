#!/usr/bin/env python3
"""
Integrity Warden - Comprehensive connection integrity checker.

Scans the ecosystem for broken links, dead references, and orphaned connections
across multiple domains: documentation, filesystem, cron, git, and code.

Architecture:
    - Plugin-based checker system
    - Each checker is self-contained and registers with the registry
    - Shared context computed once, passed to all checkers
    - Easy to extend: create a new Checker class, add to CHECKERS list

Usage:
    python integrity_warden.py --root /path/to/projects
    python integrity_warden.py --root /path/to/projects --verbose
    python integrity_warden.py --list-checkers
"""

import os
import re
import subprocess
import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional


# =============================================================================
# Configuration
# =============================================================================

EXCLUDE_DIRS: Set[str] = {
    "ai-journal",
    "cortana-personal-ai",
    "_trash",
    "archives",
    "_archive",
    "data",  # Data directories contain historical records, not code
    "snapshot",  # Generated snapshots
    "venv",
    ".venv",
    "node_modules",
    ".git",
    ".obsidian",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "site-packages",
    "integrity-warden",
}

# Files to exclude (generated files, context dumps, historical logs)
EXCLUDE_FILES: Set[str] = {
    "full_repo_context.txt",  # Generated repo snapshots
    "WARDEN_LOG.yaml",  # Historical activity log - contains paths to deleted files by design
}

# File extensions to scan for text content
# Note: .json excluded - JSON files are typically data/state, not documentation
# If you need to check specific JSON configs, add them to a separate checker
TEXT_EXTENSIONS: Set[str] = {
    ".md", ".py", ".sh", ".bash", ".zsh",
    ".yaml", ".yml",
    ".txt", ".cursorrules", ".plist",
    ".toml", ".cfg", ".ini",
}

# Default projects root (can be overridden via --root)
DEFAULT_ROOT = Path.home() / "projects"


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Issue:
    """A single integrity issue found by a checker."""
    file: str
    issue_type: str
    target: str
    context: str = ""
    severity: str = "warning"  # info, warning, error
    checker: str = ""

    def __hash__(self):
        return hash((self.file, self.issue_type, self.target))

    def __eq__(self, other):
        if not isinstance(other, Issue):
            return False
        return (self.file, self.issue_type, self.target) == (other.file, other.issue_type, other.target)


@dataclass
class ScanContext:
    """Shared context passed to all checkers. Computed once, reused."""
    root_path: Path
    md_files: Dict[str, List[Path]] = field(default_factory=dict)
    projects: List[str] = field(default_factory=list)
    all_files: List[Path] = field(default_factory=list)

    @classmethod
    def build(cls, root_path: Path) -> 'ScanContext':
        """Build the shared context by indexing the filesystem."""
        ctx = cls(root_path=root_path)
        ctx._index_md_files()
        ctx._index_projects()
        ctx._index_all_files()
        return ctx

    def _index_md_files(self):
        """Index all .md files by their stem name for wikilink resolution."""
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                if file.endswith(".md"):
                    stem = Path(file).stem
                    if stem not in self.md_files:
                        self.md_files[stem] = []
                    self.md_files[stem].append(Path(root) / file)

    def _index_projects(self):
        """List all project directories, sorted by length (longest first)."""
        self.projects = sorted(
            [p.name for p in self.root_path.iterdir() if p.is_dir() and p.name not in EXCLUDE_DIRS],
            key=len,
            reverse=True
        )

    def _index_all_files(self):
        """Index all scannable files."""
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                if file in EXCLUDE_FILES:
                    continue
                file_path = Path(root) / file
                if file_path.suffix.lower() in TEXT_EXTENSIONS:
                    self.all_files.append(file_path)


# =============================================================================
# Base Checker Interface
# =============================================================================

class BaseChecker(ABC):
    """
    Abstract base class for all integrity checkers.

    To create a new checker:
        1. Subclass BaseChecker
        2. Set name and description
        3. Implement check() method
        4. Add instance to CHECKERS list at bottom of file
    """

    name: str = "BaseChecker"
    description: str = "Override this description"

    @abstractmethod
    def check(self, ctx: ScanContext) -> List[Issue]:
        """
        Run the integrity check.

        Args:
            ctx: Shared scan context with indexed files and projects

        Returns:
            List of Issue objects found
        """
        pass

    def _read_file(self, file_path: Path) -> Optional[str]:
        """Safely read a file's contents."""
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

    def _relative_path(self, file_path: Path, ctx: ScanContext) -> str:
        """Get path relative to root for display."""
        try:
            return str(file_path.relative_to(ctx.root_path))
        except ValueError:
            return str(file_path)


# =============================================================================
# Documentation Checkers
# =============================================================================

class WikiLinkChecker(BaseChecker):
    """Check for broken Obsidian-style [[WikiLinks]]."""

    name = "WikiLinks"
    description = "Obsidian [[WikiLink]] references to non-existent pages"

    PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
    BASH_PATTERNS = ["!", "-f", "-d", "-z", "-n", "==", "!=", " -ge ", " -le "]
    IGNORE_TARGETS = {
        "Project Name", "Document Name", "page", "wikilinks", "file for review",
        "Document-Name", "Project-Name", "pattern-analysis", "tech-stack-matrix",
        "Pattern-Analysis", "Tech-Stack-Matrix", "WARDEN_LOG", "WARDEN_LOG.yaml",
        "Project Philosophy", "Documents/README", "deploy.cron", "services",
        "Weekly_Vault_Summary_2025-W52", "Daily_Vault_Pulse_2025-12-30",
    }

    def check(self, ctx: ScanContext) -> List[Issue]:
        issues = []

        for file_path in ctx.all_files:
            if not file_path.suffix == ".md":
                continue

            content = self._read_file(file_path)
            if not content:
                continue

            for match in self.PATTERN.finditer(content):
                target = match.group(1).strip()

                # Skip bash conditionals that look like wikilinks
                if any(p in target for p in self.BASH_PATTERNS):
                    continue
                if "*" in target and "/" not in target:
                    continue

                # Skip common placeholders and system references
                if target in self.IGNORE_TARGETS or target.startswith("memory:"):
                    continue

                # Skip quoted strings (likely not wikilinks but n8n nodes or similar)
                if target.startswith('"') and target.endswith('"'):
                    continue

                # Skip shell variable checks in brackets
                if target.startswith("$") and target.endswith(" -eq 0"):
                    continue

                # Normalize target
                target_stem = target[:-3] if target.endswith(".md") else target

                if target_stem not in ctx.md_files:
                    issues.append(Issue(
                        file=self._relative_path(file_path, ctx),
                        issue_type="Broken WikiLink",
                        target=target,
                        context=match.group(0),
                        checker=self.name
                    ))

        return issues


class MarkdownLinkChecker(BaseChecker):
    """Check for broken [text](path) style markdown links."""

    name = "MarkdownLinks"
    description = "Markdown [text](path) links to non-existent files"

    PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")
    SKIP_TARGETS = {
        "link", "www.pulumi.com", "www.terraform.io", "backstage.io",
        "reference.md", "examples.md"
    }

    def check(self, ctx: ScanContext) -> List[Issue]:
        issues = []

        for file_path in ctx.all_files:
            if not file_path.suffix == ".md":
                continue

            content = self._read_file(file_path)
            if not content:
                continue

            for match in self.PATTERN.finditer(content):
                link_path = match.group(1).strip()

                # Skip self-links with fragments
                if link_path.startswith(file_path.name + "#") or link_path.startswith("#"):
                    continue

                # Skip URLs, anchors, and known external placeholders
                if link_path.startswith(self.SKIP_PREFIXES) or link_path in self.SKIP_TARGETS:
                    continue

                # Clean path
                clean_path = link_path.split(" ")[0].strip("`'\"")

                try:
                    target_path = (file_path.parent / clean_path).resolve()
                    if not target_path.exists():
                        issues.append(Issue(
                            file=self._relative_path(file_path, ctx),
                            issue_type="Broken Markdown Link",
                            target=link_path,
                            context=match.group(0),
                            checker=self.name
                        ))
                except Exception:
                    pass

        return issues


# =============================================================================
# Path Reference Checkers
# =============================================================================

class AbsolutePathChecker(BaseChecker):
    """Check for broken absolute path references to projects."""

    name = "AbsolutePaths"
    description = "Hardcoded absolute paths pointing to deleted projects/files"

    def check(self, ctx: ScanContext) -> List[Issue]:
        issues = []
        abs_root = str(ctx.root_path) + "/"

        for file_path in ctx.all_files:
            content = self._read_file(file_path)
            if not content or abs_root not in content:
                continue

            # Find all absolute path references
            start = 0
            while True:
                idx = content.find(abs_root, start)
                if idx == -1:
                    break

                # Extract the path (stop at common delimiters)
                remaining = content[idx + len(abs_root):]
                end_idx = 0
                for char in remaining:
                    if char in "\"' \n\t#)>,;`":
                        break
                    end_idx += 1

                path_after_root = remaining[:end_idx]
                full_path = abs_root + path_after_root

                # Check if path exists
                if not Path(full_path).exists():
                    # Skip common placeholders, intentional absolute system paths, and historical recovery scripts
                    if any(p in full_path for p in ["my-project", "YOUR_PROJECT", "{dir_name}", "ai-journal/entries/2026/"]):
                        start = idx + 1
                        continue
                    if "recover_from_cursor_history.py" in str(file_path):
                        start = idx + 1
                        continue

                    # Determine if it's a project-level or file-level issue
                    first_part = path_after_root.split("/")[0] if "/" in path_after_root else path_after_root

                    # Check against known projects (handle spaces in names)
                    project_exists = any(path_after_root.startswith(p) for p in ctx.projects)

                    if not project_exists and first_part not in EXCLUDE_DIRS:
                        issue_type = "Dead Project Reference"
                    else:
                        issue_type = "Broken File Path"

                    context_start = max(0, idx - 20)
                    context_end = min(len(content), idx + len(full_path) + 20)

                    issues.append(Issue(
                        file=self._relative_path(file_path, ctx),
                        issue_type=issue_type,
                        target=full_path,
                        context=f"...{content[context_start:context_end]}...",
                        checker=self.name
                    ))

                start = idx + 1

        return issues


class RelativePathChecker(BaseChecker):
    """Check for broken relative cross-project references."""

    name = "RelativePaths"
    description = "Relative paths (../project/file) pointing to non-existent targets"

    PATTERN = re.compile(r"(\.\./([a-zA-Z0-9_\-\s]+)(/[^\s'\"#\)>,;`]+)?)")

    def check(self, ctx: ScanContext) -> List[Issue]:
        issues = []

        for file_path in ctx.all_files:
            # Only check files inside projects (not at root)
            try:
                rel_parts = file_path.relative_to(ctx.root_path).parts
                if len(rel_parts) < 2:
                    continue
            except ValueError:
                continue

            content = self._read_file(file_path)
            if not content:
                continue

            for match in self.PATTERN.finditer(content):
                full_rel_path = match.group(1)
                project_name = match.group(2).strip()

                # Only check if it references a known project
                if project_name in ctx.projects:
                    try:
                        target_path = (file_path.parent / full_rel_path).resolve()
                        if not target_path.exists():
                            context_start = max(0, match.start() - 20)
                            context_end = min(len(content), match.end() + 20)

                            issues.append(Issue(
                                file=self._relative_path(file_path, ctx),
                                issue_type="Broken Cross-Project Reference",
                                target=full_rel_path,
                                context=f"...{content[context_start:context_end]}...",
                                checker=self.name
                            ))
                    except Exception:
                        pass

        return issues


# =============================================================================
# Filesystem Checkers
# =============================================================================

class SymlinkChecker(BaseChecker):
    """Check for broken symbolic links."""

    name = "Symlinks"
    description = "Symbolic links pointing to non-existent targets"

    def check(self, ctx: ScanContext) -> List[Issue]:
        issues = []

        for root, dirs, files in os.walk(ctx.root_path):
            # Filter excluded dirs
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            # Check all items (files and dirs) for symlinks
            for name in files + dirs:
                item_path = Path(root) / name

                if item_path.is_symlink():
                    target = item_path.resolve() if item_path.exists() else None

                    # Check if target exists (resolve() on broken symlink raises or returns non-existent)
                    try:
                        link_target = os.readlink(item_path)
                        if not item_path.exists():
                            issues.append(Issue(
                                file=self._relative_path(item_path, ctx),
                                issue_type="Broken Symlink",
                                target=link_target,
                                severity="error",
                                checker=self.name
                            ))
                    except Exception as e:
                        issues.append(Issue(
                            file=self._relative_path(item_path, ctx),
                            issue_type="Unreadable Symlink",
                            target=str(e),
                            severity="error",
                            checker=self.name
                        ))

        return issues


# =============================================================================
# System Checkers
# =============================================================================

class CronChecker(BaseChecker):
    """Check for cron jobs referencing non-existent scripts."""

    name = "CronJobs"
    description = "Cron job entries pointing to non-existent scripts"

    def check(self, ctx: ScanContext) -> List[Issue]:
        issues = []

        # Get current user's crontab
        try:
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return issues  # No crontab or error

            crontab_content = result.stdout
        except Exception:
            return issues

        # Parse crontab lines
        for line_num, line in enumerate(crontab_content.splitlines(), 1):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Extract command part (after the 5 time fields or special strings)
            parts = line.split()

            # Handle @reboot, @daily, etc.
            if parts[0].startswith("@"):
                command_parts = parts[1:]
            elif len(parts) > 5:
                command_parts = parts[5:]
            else:
                continue

            if not command_parts:
                continue

            # Look for script paths in the command
            command = " ".join(command_parts)
            cd_match = re.search(r'\bcd\s+["\']?([^\s"\';&|]+)["\']?', command)
            cd_dir = cd_match.group(1) if cd_match else None

            # Find paths that look like scripts
            path_patterns = [
                r'(?:(?<=^)|(?<=[\s"\'`]))(/[^ \s;&|"\'`\)]+\.(?:sh|py|bash))',  # Absolute script paths
                r'(?:(?<=^)|(?<=[\s"\'`]))(/[^ \s;&|"\'`\)]+/[^ \s;&|"\'`\)]+)',  # Any absolute path to a file
                r'(?:(?<=^)|(?<=[\s"\'`]))((?!/)[^ \s;&|"\'`\)]+/[^ \s;&|"\'`\)]+\.(?:sh|py|bash))',  # Relative script paths
            ]

            for pattern in path_patterns:
                for match in re.finditer(pattern, command):
                    script_path = match.group(1)
                    
                    # Skip common system paths and non-project paths
                    if script_path.startswith(("/usr/bin", "/bin", "/usr/local/bin")):
                        continue
                    if script_path.endswith(("/activate", "python", "python3")):
                        continue

                    if script_path.startswith("/"):
                        full_path = Path(script_path)
                    elif cd_dir:
                        full_path = (Path(cd_dir) / script_path).resolve()
                    else:
                        full_path = Path(script_path)

                    if not full_path.exists():
                        issues.append(Issue(
                            file=f"crontab:line_{line_num}",
                            issue_type="Broken Cron Script",
                            target=script_path,
                            context=line[:80] + "..." if len(line) > 80 else line,
                            severity="error",
                            checker=self.name
                        ))

        return issues


class GitHookChecker(BaseChecker):
    """Check for git hooks referencing non-existent scripts."""

    name = "GitHooks"
    description = "Git hooks that reference missing scripts or files"

    SCRIPT_PATTERNS = [
        re.compile(r'(?:source|\.)\s+["\']?([^\s"\';&|]+)["\']?'),  # source or . commands
        re.compile(r'(?:exec|sh|bash|python|python3)\s+["\']?([^\s"\';&|]+)["\']?'),  # exec commands
        re.compile(r'(?:(?<=^)|(?<=[\s"\'`]))(/[^ \s"\';&|]+\.(?:sh|py))'),  # Absolute script paths
    ]

    def check(self, ctx: ScanContext) -> List[Issue]:
        issues = []

        # Find all .git/hooks directories
        for root, dirs, files in os.walk(ctx.root_path):
            # Optimization: skip common massive folders
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and d != ".git"]

            git_hooks_dir = Path(root) / ".git" / "hooks"
            if git_hooks_dir.is_dir():
                issues.extend(self._check_hooks_dir(git_hooks_dir, ctx))

        return issues

    def _check_hooks_dir(self, hooks_dir: Path, ctx: ScanContext) -> List[Issue]:
        issues = []
        repo_root = hooks_dir.parent.parent

        for hook_file in hooks_dir.iterdir():
            # Skip sample files
            if hook_file.suffix == ".sample" or not hook_file.is_file():
                continue

            content = self._read_file(hook_file)
            if not content:
                continue

            # Look for script references
            for pattern in self.SCRIPT_PATTERNS:
                for match in pattern.finditer(content):
                    script_path = match.group(1).strip()

                    # Skip common non-path matches
                    if script_path.startswith(("#", "-", "$")):
                        continue
                    if script_path in {"Proceeding", "Warden"}:
                        continue

                    # Resolve relative paths from hook location
                    if script_path.startswith("/"):
                        full_path = Path(script_path)
                    else:
                        full_path = (repo_root / script_path).resolve()

                    if not full_path.exists():
                        issues.append(Issue(
                            file=self._relative_path(hook_file, ctx),
                            issue_type="Broken Git Hook Reference",
                            target=script_path,
                            context=match.group(0),
                            severity="error",
                            checker=self.name
                        ))

        return issues


# =============================================================================
# Code Checkers
# =============================================================================

class ShellSourceChecker(BaseChecker):
    """Check for shell scripts sourcing non-existent files."""

    name = "ShellSources"
    description = "Shell scripts sourcing (source/.) files that don't exist"

    PATTERN = re.compile(r'(?:^|\s)(?:source|\.)\s+["\']?([^\s"\';&|#]+)["\']?', re.MULTILINE)

    def check(self, ctx: ScanContext) -> List[Issue]:
        issues = []

        for file_path in ctx.all_files:
            if file_path.suffix not in {".sh", ".bash", ".zsh"}:
                continue

            content = self._read_file(file_path)
            if not content:
                continue

            for match in self.PATTERN.finditer(content):
                source_path = match.group(1).strip()

                # Skip variable references and special cases
                if source_path.startswith("$") or source_path in {"/dev/null", "-"}:
                    continue

                # Resolve the path
                if source_path.startswith("/"):
                    full_path = Path(source_path)
                else:
                    full_path = (file_path.parent / source_path).resolve()

                if not full_path.exists():
                    issues.append(Issue(
                        file=self._relative_path(file_path, ctx),
                        issue_type="Broken Shell Source",
                        target=source_path,
                        context=match.group(0).strip(),
                        checker=self.name
                    ))

        return issues


class PythonImportChecker(BaseChecker):
    """Check for Python files importing non-existent local modules."""

    name = "PythonImports"
    description = "Python relative imports referencing non-existent modules"

    # Only check relative imports (from . or from ..)
    RELATIVE_IMPORT = re.compile(r'^from\s+(\.+[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s+import', re.MULTILINE)

    def check(self, ctx: ScanContext) -> List[Issue]:
        issues = []

        for file_path in ctx.all_files:
            if file_path.suffix != ".py":
                continue

            content = self._read_file(file_path)
            if not content:
                continue

            for match in self.RELATIVE_IMPORT.finditer(content):
                import_path = match.group(1)

                # Count leading dots
                dots = len(import_path) - len(import_path.lstrip('.'))
                module_parts = import_path.lstrip('.').split('.')

                # Navigate up directories based on dots
                current_dir = file_path.parent
                for _ in range(dots - 1):  # -1 because first dot is current package
                    current_dir = current_dir.parent

                # Check if module exists
                module_path = current_dir
                for part in module_parts:
                    module_path = module_path / part

                # Check for module.py or module/__init__.py
                exists = (
                    module_path.with_suffix('.py').exists() or
                    (module_path.is_dir() and (module_path / '__init__.py').exists())
                )

                if not exists:
                    issues.append(Issue(
                        file=self._relative_path(file_path, ctx),
                        issue_type="Broken Python Import",
                        target=import_path,
                        context=match.group(0),
                        checker=self.name
                    ))

        return issues


# =============================================================================
# Checker Registry
# =============================================================================

# Add new checkers here - they'll automatically be included in scans
CHECKERS: List[BaseChecker] = [
    # Documentation
    WikiLinkChecker(),
    MarkdownLinkChecker(),

    # Paths
    AbsolutePathChecker(),
    RelativePathChecker(),

    # Filesystem
    SymlinkChecker(),

    # System
    CronChecker(),
    GitHookChecker(),

    # Code
    ShellSourceChecker(),
    PythonImportChecker(),
]


# =============================================================================
# Main
# =============================================================================

def run_checks(root_path: Path, verbose: bool = False) -> List[Issue]:
    """Run all registered checkers and return deduplicated issues."""

    print(f"Building scan context for {root_path}...")
    ctx = ScanContext.build(root_path)
    print(f"  - Indexed {len(ctx.md_files)} unique markdown files")
    print(f"  - Found {len(ctx.projects)} projects")
    print(f"  - Scanning {len(ctx.all_files)} text files")

    all_issues = []

    for checker in CHECKERS:
        if verbose:
            print(f"\nRunning {checker.name}...")

        issues = checker.check(ctx)

        if verbose and issues:
            print(f"  Found {len(issues)} issues")

        all_issues.extend(issues)

    # Deduplicate
    return list(set(all_issues))


def print_report(issues: List[Issue], verbose: bool = False):
    """Print a formatted report of all issues."""

    if not issues:
        print("\n" + "=" * 60)
        print("ECOSYSTEM INTEGRITY VERIFIED")
        print("No broken connections found.")
        print("=" * 60)
        return

    # Group by type
    by_type: Dict[str, List[Issue]] = {}
    for issue in issues:
        if issue.issue_type not in by_type:
            by_type[issue.issue_type] = []
        by_type[issue.issue_type].append(issue)

    # Sort types by severity (errors first)
    severity_order = {"error": 0, "warning": 1, "info": 2}
    sorted_types = sorted(
        by_type.keys(),
        key=lambda t: (severity_order.get(by_type[t][0].severity, 1), t)
    )

    print("\n" + "=" * 60)
    print(f"INTEGRITY ISSUES FOUND: {len(issues)}")
    print("=" * 60)

    for issue_type in sorted_types:
        type_issues = sorted(by_type[issue_type], key=lambda x: x.file)
        severity = type_issues[0].severity.upper()
        checker = type_issues[0].checker

        print(f"\n[{severity}] {issue_type} ({len(type_issues)} found)")
        print(f"    Checker: {checker}")
        print("-" * 40)

        for issue in type_issues:
            print(f"  File: {issue.file}")
            print(f"    -> {issue.target}")
            if verbose and issue.context:
                print(f"       Context: {issue.context[:60]}...")
        print()


def list_checkers():
    """Print all available checkers and their descriptions."""
    print("\nAvailable Integrity Checkers:")
    print("=" * 60)

    for checker in CHECKERS:
        print(f"\n  {checker.name}")
        print(f"    {checker.description}")

    print("\n" + "=" * 60)
    print(f"Total: {len(CHECKERS)} checkers registered")


def main():
    parser = argparse.ArgumentParser(
        description="Integrity Warden: Comprehensive connection integrity checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --root ~/projects
    %(prog)s --root ~/projects --verbose
    %(prog)s --list-checkers

To add a new checker:
    1. Create a class that inherits from BaseChecker
    2. Implement the check() method
    3. Add an instance to the CHECKERS list
        """
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Root directory to scan (default: {DEFAULT_ROOT})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including context"
    )
    parser.add_argument(
        "--list-checkers",
        action="store_true",
        help="List all available checkers and exit"
    )

    args = parser.parse_args()

    if args.list_checkers:
        list_checkers()
        return

    root_path = args.root.resolve()

    if not root_path.is_dir():
        print(f"Error: {root_path} is not a directory")
        return 1

    print("=" * 60)
    print("INTEGRITY WARDEN")
    print("Scanning for broken connections across the ecosystem")
    print("=" * 60)
    print(f"\nRoot: {root_path}")
    print(f"Checkers: {len(CHECKERS)} registered")
    print(f"Excluding: {', '.join(sorted(EXCLUDE_DIRS))}")

    issues = run_checks(root_path, args.verbose)
    print_report(issues, args.verbose)

    return 1 if issues else 0


if __name__ == "__main__":
    exit(main() or 0)

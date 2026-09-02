#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Absolute Path Blocker - Standalone Git Hook Validator

Catches hardcoded absolute paths in code/config files.
Blocks commits that contain paths like:
- /Users/<name>/...
- /Users/*/...
- /home/*/...

Exit codes:
- 0: No absolute paths found, continue
- 1: Absolute paths found, block commit

Usage:
  python absolute-path-check.py file1.py file2.js ...
"""

import re
import sys
from pathlib import Path

# Patterns to catch
ABSOLUTE_PATH_PATTERNS = [
    r'/Users/\w+/',           # macOS user paths
    r'/home/\w+/',            # Linux user paths
    r'/opt/homebrew/',        # Homebrew — absolute path intentional: pattern literal
    r'C:\\Users\\\w+\\',      # Windows paths
]

# File extensions to check (skip binaries, images, etc.)
CHECK_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx',
    '.md', '.yaml', '.yml', '.json',
    '.sh', '.bash', '.zsh',
    '.html', '.css', '.scss',
    '.go', '.rs', '.rb',
    '.toml', '.ini', '.cfg', '.conf',
}

# Files matched by exact name rather than by extension.
CHECK_FILENAMES = {
    'Makefile', 'Dockerfile', 'Vagrantfile', 'Gemfile',
    # `.env.example` cannot be matched by suffix: Path('.env.example').suffix
    # is '.example'. It sat in CHECK_EXTENSIONS unreachable, so env templates
    # were never scanned despite the comment claiming they were.
    '.env.example',
}

# Files/patterns to skip (legitimate uses of absolute paths)
SKIP_PATTERNS = [
    r'\.git/',
    r'node_modules/',
    r'__pycache__/',
    r'\.env$',           # Actual env files can have paths
    r'\.log$',           # Log files
]


def should_check_file(file_path: Path) -> bool:
    """Determine if we should check this file."""
    path_str = str(file_path)

    # Skip certain paths
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, path_str):
            return False

    # Check by exact filename (extension cannot identify these)
    if file_path.name in CHECK_FILENAMES:
        return True

    # Check by extension
    suffix = file_path.suffix.lower()
    if suffix in CHECK_EXTENSIONS:
        return True

    return False


# Markers that make a comment documentation rather than a real hardcoded path.
DOC_MARKERS = ('example:', 'e.g.')

# An established convention for deliberate absolute paths, e.g.
#   PATH="...:/opt/homebrew/bin"  # absolute path intentional: minimal env
# A comment carrying this marker exempts its whole line.
INTENTIONAL_MARKER = 'absolute path'

# Extensions whose content is prose. These have no comment syntax, so a
# documentation marker anywhere on the line scopes the whole line.
# Only '.md' is reachable today -- the others are here so that adding them to
# CHECK_EXTENSIONS does not silently reintroduce the false positives this
# carve-out fixes.
PROSE_EXTENSIONS = {'.md', '.markdown', '.rst', '.txt'}


def comment_start(line: str) -> int | None:
    """Index where a line comment begins, or None if there is no comment.

    Recognises `#` and `//`. Quote state is tracked so a marker inside a string
    literal is not mistaken for a comment, and `//` preceded by `:` is ignored
    so URLs such as https://example.com survive.
    """
    in_single = in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '\\':
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == '#':
                return i
            if line.startswith('//', i) and (i == 0 or line[i - 1] != ':'):
                return i
        i += 1
    return None


def is_doc_comment(comment: str) -> bool:
    """True if a comment reads as documentation rather than a real path."""
    lowered = comment.lower()
    return any(marker in lowered for marker in DOC_MARKERS)


def find_absolute_paths(content: str, file_path: str) -> list[dict]:
    """
    Find absolute paths in content.
    Returns list of {line_num, line, matches} dicts.

    A match is ignored only when it sits inside a documentation comment.
    Previously any line containing 'e.g.' or 'example:' anywhere -- including
    inside a string in real code -- suppressed every match on that line.
    """
    issues = []
    lines = content.split('\n')
    is_prose = Path(file_path).suffix.lower() in PROSE_EXTENSIONS

    for line_num, line in enumerate(lines, 1):
        comment_at = comment_start(line)
        comment = line[comment_at:].lower() if comment_at is not None else ''

        # A deliberate-use marker in a comment exempts the whole line.
        if INTENTIONAL_MARKER in comment:
            continue

        # Prose has no comment syntax, so a marker anywhere on the line
        # scopes it. Without this, documentation describing a bad path is
        # indistinguishable from the bad path itself.
        if is_prose:
            lowered = line.lower()
            if INTENTIONAL_MARKER in lowered or any(m in lowered for m in DOC_MARKERS):
                continue

        doc_comment = comment_at is not None and is_doc_comment(comment)

        for pattern in ABSOLUTE_PATH_PATTERNS:
            matches = [
                m.group(0)
                for m in re.finditer(pattern, line)
                if not (doc_comment and m.start() >= comment_at)
            ]
            if matches:
                issues.append({
                    'line_num': line_num,
                    'line': line.strip()[:100],  # Truncate long lines
                    'matches': matches
                })

    return issues


def main():
    if len(sys.argv) < 2:
        print("Usage: absolute-path-check.py <file1> [file2] ...", file=sys.stderr)
        sys.exit(0)

    all_issues = []
    
    for file_path_str in sys.argv[1:]:
        file_path = Path(file_path_str)
        
        # Skip if file doesn't exist or shouldn't be checked
        if not file_path.exists():
            continue
            
        if not should_check_file(file_path):
            continue

        try:
            content = file_path.read_text()
        except (UnicodeDecodeError, PermissionError):
            # Skip binary files or files we can't read
            continue

        # Find absolute paths
        issues = find_absolute_paths(content, str(file_path))
        
        if issues:
            all_issues.append({
                "file": str(file_path),
                "issues": issues
            })

    if all_issues:
        print("\n🚫 HARDCODED ABSOLUTE PATHS DETECTED\n", file=sys.stderr)
        
        for file_result in all_issues:
            print(f"File: {file_result['file']}", file=sys.stderr)
            for issue in file_result['issues'][:5]:  # Limit to first 5 per file
                print(f"  Line {issue['line_num']}: {issue['line']}", file=sys.stderr)
            if len(file_result['issues']) > 5:
                print(f"  ... and {len(file_result['issues']) - 5} more", file=sys.stderr)
            print("", file=sys.stderr)

        print("Fix by using relative paths or environment variables instead.", file=sys.stderr)
        print("Example: Use './data/file.csv' or '$PROJECT_ROOT/data/file.csv'", file=sys.stderr)
        
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

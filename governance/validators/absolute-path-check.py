#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Absolute Path Blocker - Standalone Git Hook Validator

Catches hardcoded absolute paths in code/config files.
Blocks commits that contain paths like:
- /Users/eriksjaastad/...
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
    r'/opt/homebrew/',        # Homebrew paths
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
    '.env.example',  # Check example env files
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

    # Check by extension
    suffix = file_path.suffix.lower()
    if suffix in CHECK_EXTENSIONS:
        return True

    # Check files without extension (like Makefile, Dockerfile)
    if file_path.name in {'Makefile', 'Dockerfile', 'Vagrantfile', 'Gemfile'}:
        return True

    return False


def find_absolute_paths(content: str, file_path: str) -> list[dict]:
    """
    Find absolute paths in content.
    Returns list of {line_num, line, matches} dicts.
    """
    issues = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        for pattern in ABSOLUTE_PATH_PATTERNS:
            matches = re.findall(pattern, line)
            if matches:
                # Skip if it's in a comment explaining the issue
                if 'absolute path' in line.lower() and '#' in line:
                    continue
                # Skip if it looks like documentation/example
                if 'example:' in line.lower() or 'e.g.' in line.lower():
                    continue

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

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Content Guard — Standalone Git Hook Validator

Detects external client identifiers in tracked files to prevent leaking
private client information in public repositories.

The marker list is NEVER committed to the public repository. It is loaded from:
1. Environment variable CONTENT_GUARD_PATTERNS (newline-separated patterns)
2. A private file path in CONTENT_GUARD_PATTERNS_FILE

Exit codes:
- 0: No forbidden content found, continue
- 1: Forbidden content detected, block commit
- 2: Configuration error (no patterns available)

Usage:
  export CONTENT_GUARD_PATTERNS="pattern1
pattern2"
  python content-guard.py file1.py file2.js ...

Or:
  export CONTENT_GUARD_PATTERNS_FILE=/path/to/private/patterns.txt
  python content-guard.py file1.py file2.js ...
"""

import os
import re
import sys
from pathlib import Path

# File extensions to check (essentially everything that could contain text)
CHECK_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.mjs', '.cjs',
    '.md', '.txt', '.yaml', '.yml', '.json', '.toml',
    '.sh', '.bash', '.zsh', '.fish',
    '.html', '.css', '.scss', '.sass',
    '.go', '.rs', '.rb', '.java', '.c', '.cpp', '.h',
    '.sql', '.ini', '.cfg', '.conf',
}

# Patterns to skip (untracked/generated/vendor/binary areas only)
# Tests are NOT exempt - they are committed public content that can leak identifiers
SKIP_PATH_PATTERNS = [
    r'\.git/',
    r'node_modules/',
    r'\.venv/',
    r'venv/',
    r'__pycache__/',
    r'\.pytest_cache/',
    r'site-packages/',
    r'\.env$',
    r'\.log$',
]


def should_check_file(file_path: Path) -> bool:
    """Determine if this file should be scanned."""
    path_str = str(file_path)

    for pattern in SKIP_PATH_PATTERNS:
        if re.search(pattern, path_str):
            return False

    return file_path.suffix.lower() in CHECK_EXTENSIONS or file_path.suffix == ''


def load_patterns() -> list[str]:
    """Load forbidden patterns from environment variable or file.
    
    Returns empty list if no patterns are configured (which will cause
    the validator to exit with code 2).
    """
    patterns = []
    
    # Try environment variable first
    env_patterns = os.getenv('CONTENT_GUARD_PATTERNS')  # governance: allow-silent SF003: optional configuration checked explicitly below
    if env_patterns:
        patterns.extend([p.strip() for p in env_patterns.strip().split('\n') if p.strip()])
    
    # Try patterns file
    patterns_file = os.getenv('CONTENT_GUARD_PATTERNS_FILE')  # governance: allow-silent SF003: optional configuration checked explicitly below
    if patterns_file:
        try:
            file_path = Path(patterns_file.strip()).expanduser()
            if file_path.exists():
                content = file_path.read_text().strip()
                patterns.extend([p.strip() for p in content.split('\n') if p.strip()])
        except (OSError, PermissionError) as e:
            print(f"Warning: Could not read patterns file {patterns_file}: {e}", file=sys.stderr)
    
    return patterns


def scan_for_patterns(content: str, patterns: list[str]) -> list[dict]:
    """
    Scan content for forbidden patterns.
    
    Returns list of findings: [{"pattern": "...", "line_num": N, "line": "..."}]
    """
    findings = []
    
    for line_num, line in enumerate(content.split('\n'), 1):
        for pattern in patterns:
            # Case-insensitive search for the pattern
            if re.search(re.escape(pattern), line, re.IGNORECASE):
                # Redact the actual match from the output
                redacted_line = line[:80] + '...' if len(line) > 80 else line
                findings.append({
                    "pattern": f"<pattern-{hash(pattern) % 10000:04d}>",
                    "line_num": line_num,
                    "line": redacted_line,
                })
    
    return findings


def main():
    # Load patterns - fail closed if not configured
    patterns = load_patterns()
    
    if not patterns:
        print("\n🚨 CONTENT GUARD NOT CONFIGURED - BLOCKING COMMIT", file=sys.stderr)
        print("", file=sys.stderr)
        print("Set CONTENT_GUARD_PATTERNS (newline-separated) or", file=sys.stderr)
        print("CONTENT_GUARD_PATTERNS_FILE (path to patterns file).", file=sys.stderr)
        print("", file=sys.stderr)
        print("This is a fail-closed gate: commits are blocked until patterns", file=sys.stderr)
        print("are configured. Configure the repository secret or environment", file=sys.stderr)
        print("variable, then retry.", file=sys.stderr)
        sys.exit(1)
    
    if len(sys.argv) < 2:
        print("Usage: content-guard.py <file1> [file2] ...", file=sys.stderr)
        sys.exit(0)

    all_findings = []
    
    for file_path_str in sys.argv[1:]:
        file_path = Path(file_path_str)
        
        if not file_path.exists():
            continue
            
        if not should_check_file(file_path):
            continue

        try:
            content = file_path.read_text()
        except (UnicodeDecodeError, PermissionError):
            continue

        findings = scan_for_patterns(content, patterns)
        
        if findings:
            all_findings.append({
                "file": str(file_path),
                "findings": findings
            })

    if all_findings:
        print("\n🚨 FORBIDDEN CONTENT DETECTED\n", file=sys.stderr)
        
        for file_result in all_findings:
            print(f"File: {file_result['file']}", file=sys.stderr)
            for finding in file_result['findings'][:5]:
                print(f"  Line {finding['line_num']}: {finding['pattern']}", file=sys.stderr)
            if len(file_result['findings']) > 5:
                print(f"  ... and {len(file_result['findings']) - 5} more", file=sys.stderr)
            print("", file=sys.stderr)

        print("Files contain forbidden external client identifiers.", file=sys.stderr)
        print("These patterns must not be committed to the public repository.", file=sys.stderr)
        print("Remove the content or move it to a private location.", file=sys.stderr)
        
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

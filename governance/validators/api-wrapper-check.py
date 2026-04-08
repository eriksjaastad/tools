#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
API Wrapper Enforcement — Standalone Git Hook Validator

Catches raw API client calls that bypass the cost tracking wrapper.
Every API call must go through the api-trust-tracker wrapper so we
have visibility into spend.

Exit codes:
- 0: No raw API calls found, continue
- 1: Raw API calls detected, block commit

Usage:
  python api-wrapper-check.py file1.py file2.js ...
"""

import re
import sys
from pathlib import Path

# Raw API call patterns to detect
# Each tuple: (pattern, provider, description)
RAW_API_PATTERNS = [
    # Anthropic (Python)
    (r'\.messages\.create\s*\(', "Anthropic", "Direct messages.create() call"),
    (r'\.messages\.stream\s*\(', "Anthropic", "Direct messages.stream() call"),

    # OpenAI / xAI (Python) — Chat Completions API
    (r'\.chat\.completions\.create\s*\(', "OpenAI/xAI", "Direct chat.completions.create() call"),

    # OpenAI — Responses API
    (r'\.responses\.create\s*\(', "OpenAI", "Direct responses.create() call"),

    # Google Gemini (Python)
    (r'\.generate_content\s*\(', "Google Gemini", "Direct generate_content() call"),

    # Anthropic (JS/TS)
    (r'anthropic\.messages\.create\s*\(', "Anthropic JS", "Direct anthropic.messages.create() call"),

    # OpenAI (JS/TS)
    (r'openai\.chat\.completions\.create\s*\(', "OpenAI JS", "Direct openai.chat.completions.create() call"),
]

# Wrapper import patterns — if any of these appear in the file, it's using the wrapper
WRAPPER_INDICATORS = [
    r'from\s+api_trust_tracker\s+import',
    r'import\s+api_trust_tracker',
    r'from\s+ai_cost_tracker\s+import',
    r'import\s+ai_cost_tracker',
    r'from\s+\.?tracker\s+import\s+track',
    r'require\s*\(\s*[\'"]api[_-]trust[_-]tracker[\'"]\s*\)',
    r'import\s+.*from\s+[\'"]api[_-]trust[_-]tracker[\'"]',
    r'\btrack\s*\(\s*resp',          # track(resp, ...) call pattern
    r'\btrack\s*\(\s*response',      # track(response, ...) call pattern
]

# File extensions to check
CHECK_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.mjs', '.cjs',
}

# Paths to skip (these are allowed to make raw calls)
SKIP_PATH_PATTERNS = [
    r'ai[_-]cost[_-]tracker/',        # The wrapper itself
    r'api[_-]cost[_-]tracker/',        # Alternative naming
    r'(?:^|/)tests?/',                    # Test directories
    r'(?:^|/)conftest\.py$',             # Pytest config
    r'(?:^|/)test_[^/]*\.py$',           # Test files
    r'(?:^|/)[^/]*_test\.py$',           # Test files (alt naming)
    r'\.test\.[jt]sx?$',                # JS/TS test files
    r'(?:^|/)__mocks__/',                # Jest mocks
    r'node_modules/',                   # Dependencies
    r'\.venv/',                         # Virtual environments
    r'site-packages/',                  # Installed packages
    r'doc_audit',                       # Offline batch audit scripts (Gemini)
]


def should_check_file(file_path: Path) -> bool:
    """Determine if this file should be scanned."""
    path_str = str(file_path)

    for pattern in SKIP_PATH_PATTERNS:
        if re.search(pattern, path_str):
            return False

    return file_path.suffix.lower() in CHECK_EXTENSIONS


def file_uses_wrapper(content: str) -> bool:
    """Check if the file imports or uses the cost tracking wrapper."""
    for pattern in WRAPPER_INDICATORS:
        if re.search(pattern, content):
            return True
    return False


def find_raw_api_calls(content: str) -> list[dict]:
    """
    Find raw API calls that bypass the wrapper.
    Returns list of {line_num, line, provider, description} dicts.
    """
    issues = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('//'):
            continue
        # Skip string literals that look like documentation
        if stripped.startswith(('"""', "'''", '*', '/*')):
            continue

        for pattern, provider, description in RAW_API_PATTERNS:
            if re.search(pattern, line):
                issues.append({
                    'line_num': line_num,
                    'line': stripped[:120],
                    'provider': provider,
                    'description': description,
                })

    return issues


def main():
    if len(sys.argv) < 2:
        print("Usage: api-wrapper-check.py <file1> [file2] ...", file=sys.stderr)
        sys.exit(0)

    all_issues = []

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

        # If the file imports the wrapper, it's fine
        if file_uses_wrapper(content):
            continue

        # Look for raw API calls
        issues = find_raw_api_calls(content)

        if issues:
            all_issues.append({
                "file": str(file_path),
                "issues": issues,
            })

    if all_issues:
        print("\n\U0001f6ab RAW API CALLS DETECTED — use the cost tracking wrapper\n", file=sys.stderr)

        for file_result in all_issues:
            print(f"File: {file_result['file']}", file=sys.stderr)
            for issue in file_result['issues'][:5]:
                print(
                    f"  Line {issue['line_num']}: [{issue['provider']}] {issue['line']}",
                    file=sys.stderr,
                )
            if len(file_result['issues']) > 5:
                print(f"  ... and {len(file_result['issues']) - 5} more", file=sys.stderr)
            print("", file=sys.stderr)

        print("Every API call must go through the cost tracking wrapper:", file=sys.stderr)
        print("", file=sys.stderr)
        print("  from api_trust_tracker import track", file=sys.stderr)
        print("", file=sys.stderr)
        print("  resp = client.messages.create(model=..., ...)", file=sys.stderr)
        print('  track(resp, "anthropic", project="your-project")', file=sys.stderr)
        print("", file=sys.stderr)
        print("See: synth-insight-labs/api-cost-tracker/README.md", file=sys.stderr)

        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

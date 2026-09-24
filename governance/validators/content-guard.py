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
- 2: Configuration or scan error (including missing patterns)

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
import subprocess
import sys
from pathlib import Path

def load_patterns() -> list[str]:
    """Load forbidden patterns from environment variable or file.

    Returns empty list if no patterns are configured (which causes exit 2).
    """
    patterns = []

    # Try environment variable first
    env_patterns = os.getenv('CONTENT_GUARD_PATTERNS')  # governance: allow-silent SF003: optional configuration checked explicitly below
    if env_patterns:
        patterns.extend([p.strip() for p in env_patterns.strip().split('\n') if p.strip()])

    # Try patterns file
    patterns_file = os.getenv('CONTENT_GUARD_PATTERNS_FILE')  # governance: allow-silent SF003: optional configuration checked explicitly below
    if patterns_file:
        file_path = Path(patterns_file.strip()).expanduser()
        content = file_path.read_text().strip()
        if not content:
            raise ValueError("configured patterns file is empty")
        patterns.extend([p.strip() for p in content.split('\n') if p.strip()])

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


def tracked_paths() -> list[Path]:
    """Enumerate checkout blobs and symlinks; gitlinks have no local file body."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--stage", "-z"],
            capture_output=True, check=True, timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("cannot enumerate tracked files") from exc
    paths = []
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, name = entry.split(b"\t", 1)
            mode, _oid, stage = metadata.split(b" ")
        except ValueError as exc:
            raise RuntimeError("invalid tracked-file entry") from exc
        if stage != b"0":
            raise RuntimeError("unmerged tracked-file entry")
        if mode == b"160000":
            continue
        if mode not in (b"100644", b"100755", b"120000"):
            raise RuntimeError("unexpected tracked-file mode")
        paths.append(Path(os.fsdecode(name)))
    if not paths:
        raise RuntimeError("no tracked files to scan")
    return paths


def main():
    # Load patterns - fail closed if not configured
    try:
        patterns = load_patterns()
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Cannot load configured content patterns: {exc}", file=sys.stderr)
        sys.exit(2)

    if not patterns:
        print("\n🚨 CONTENT GUARD NOT CONFIGURED - BLOCKING COMMIT", file=sys.stderr)
        print("", file=sys.stderr)
        print("Set CONTENT_GUARD_PATTERNS (newline-separated) or", file=sys.stderr)
        print("CONTENT_GUARD_PATTERNS_FILE (path to patterns file).", file=sys.stderr)
        print("", file=sys.stderr)
        print("This is a fail-closed gate: commits are blocked until patterns", file=sys.stderr)
        print("are configured. Configure the repository secret or environment", file=sys.stderr)
        print("variable, then retry.", file=sys.stderr)
        sys.exit(2)

    if sys.argv[1:] == ["--tracked"]:
        try:
            file_paths = tracked_paths()
        except RuntimeError as exc:
            print(f"Content guard scan error: {exc}", file=sys.stderr)
            sys.exit(2)
    elif len(sys.argv) < 2:
        print("Usage: content-guard.py <file1> [file2] ...", file=sys.stderr)
        sys.exit(2)
    else:
        file_paths = [Path(value) for value in sys.argv[1:]]

    all_findings = []

    for file_path in file_paths:

        try:
            # Replacement keeps ASCII identifiers visible in mixed-encoding text.
            # Read symlink text itself; never follow a PR-controlled link into
            # files outside the checkout.
            if file_path.is_symlink():
                content = os.readlink(file_path)
            else:
                content = file_path.read_bytes().decode('utf-8', errors='replace')
        except OSError as exc:
            print(f"Cannot scan {file_path}: {exc}", file=sys.stderr)
            sys.exit(2)

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

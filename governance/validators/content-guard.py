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
import codecs
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


def checkout_root() -> Path:
    """Return the git work-tree root, or cwd when git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, check=True, timeout=10, text=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return Path.cwd()
    root = result.stdout.strip()
    return Path(root) if root else Path.cwd()


def repository_relative_name(path: Path, root: Path | None = None) -> str:
    """Name to scan for markers: in-repo relative path, never outside parents.

    Tracked paths from git are already relative and keep their full form.
    Absolute arguments under the checkout become repository-relative so
    marker-named directories inside the repo are still scanned. Absolute
    paths outside the checkout contribute only their leaf name so unrelated
    parent directories cannot false-positive a clean file.

    The final path component is preserved without following a trailing
    symlink, so a forbidden symlink name is still scanned even when its
    target is a clean pathname.
    """
    if not path.is_absolute():
        return path.as_posix()
    base = (root if root is not None else checkout_root()).resolve()
    # Resolve parents only; keep the final component (may be a symlink name).
    try:
        rel_parent = path.parent.resolve().relative_to(base)
    except ValueError:
        return path.name
    if str(rel_parent) == ".":
        return path.name
    return f"{rel_parent.as_posix()}/{path.name}"


def redact_markers(text: str, patterns: list[str]) -> str:
    """Replace forbidden markers in diagnostic text with the hashed pattern tag."""
    redacted = text
    for pattern in patterns:
        tag = f"<pattern-{hash(pattern) % 10000:04d}>"
        redacted = re.sub(re.escape(pattern), tag, redacted, flags=re.IGNORECASE)
    return redacted


def tracked_paths() -> list[Path]:
    """Enumerate checkout blobs, symlinks, and gitlink names."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--stage", "-z"],
            capture_output=True, check=True, timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("cannot enumerate tracked files") from exc
    paths = []
    gitlink_names = []
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
            # Gitlinks have no local file body, but scan the pathname itself
            gitlink_names.append(os.fsdecode(name))
            continue
        if mode not in (b"100644", b"100755", b"120000"):
            raise RuntimeError("unexpected tracked-file mode")
        paths.append(Path(os.fsdecode(name)))
    if not paths and not gitlink_names:
        raise RuntimeError("no tracked files to scan")
    return paths, gitlink_names


def decoded_views(data: bytes):
    """Try common Unicode byte orders without letting a missing BOM hide text.
    
    Always include a raw-byte ASCII-decoded view to catch literal ASCII markers
    even in mixed-encoding or malformed files with a BOM.
    """
    if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        yield data.decode("utf-32")
    elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        yield data.decode("utf-16")
    else:
        yield data.decode("utf-8", errors="replace")
        for encoding in ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
            yield data.decode(encoding, errors="replace")
    
    # Always scan raw bytes as ASCII to catch literal markers in mixed/malformed files
    yield data.decode("ascii", errors="replace")


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
            file_paths, gitlink_names = tracked_paths()
        except RuntimeError as exc:
            print(f"Content guard scan error: {exc}", file=sys.stderr)
            sys.exit(2)
    elif len(sys.argv) < 2:
        print("Usage: content-guard.py <file1> [file2] ...", file=sys.stderr)
        sys.exit(2)
    else:
        file_paths = [Path(value) for value in sys.argv[1:]]
        gitlink_names = []

    all_findings = []
    root = checkout_root()

    # Scan repository-relative pathnames (including gitlink names). Absolute
    # args under the checkout keep in-repo directories; outside parents are
    # ignored.
    for path_obj in file_paths:
        pathname = repository_relative_name(path_obj, root)
        findings = scan_for_patterns(pathname, patterns)
        if findings:
            all_findings.append({
                "file": f"<pathname:{redact_markers(pathname, patterns)}>",
                "findings": findings,
            })

    for gitlink_name in gitlink_names:
        findings = scan_for_patterns(gitlink_name, patterns)
        if findings:
            all_findings.append({
                "file": f"<gitlink:{redact_markers(gitlink_name, patterns)}>",
                "findings": findings,
            })

    for file_path in file_paths:

        try:
            # Replacement keeps ASCII identifiers visible in mixed-encoding text.
            # Read symlink text itself; never follow a PR-controlled link into
            # files outside the checkout.
            if file_path.is_symlink():
                views = (os.readlink(file_path),)
            else:
                views = decoded_views(file_path.read_bytes())
            findings = []
            for content in views:
                findings = scan_for_patterns(content, patterns)
                if findings:
                    break
        except (OSError, UnicodeError) as exc:
            print(f"Cannot scan {file_path}: {exc}", file=sys.stderr)
            sys.exit(2)

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

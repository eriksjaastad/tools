#!/usr/bin/env python3
"""Run the managed GitHub shim with a finite per-command timeout.

Standard streams are inherited so GitHub API --input - and shell command
substitutions keep their usual behavior. The shim, not this wrapper, chooses
the authenticated identity.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: gha-bounded.py <seconds> <gha-path> [args ...]", file=sys.stderr)
        return 2
    try:
        seconds = float(sys.argv[1])
    except ValueError:
        print("gha-bounded: timeout must be numeric", file=sys.stderr)
        return 2
    if seconds <= 0:
        print("gha-bounded: timeout must be positive", file=sys.stderr)
        return 2
    try:
        return subprocess.run(sys.argv[2:], timeout=seconds, check=False).returncode
    except subprocess.TimeoutExpired:
        print(f"gha-bounded: GitHub command timed out after {seconds:g}s", file=sys.stderr)
        return 124
    except OSError as exc:
        print(f"gha-bounded: could not start GitHub command: {exc}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    sys.exit(main())

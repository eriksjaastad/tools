#!/usr/bin/env python3
"""
Rollback script for V4 E2E test.

Removes the get_timestamp() function if it was added during testing.
"""

import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TARGET_FILE = PROJECT_ROOT / "src" / "sandbox.py"

# Pattern to match the function we added
FUNCTION_PATTERN = r'\n\ndef get_timestamp\(\) -> str:.*?return datetime\.now\(timezone\.utc\)\.strftime\("%Y-%m-%dT%H:%M:%SZ"\)\n'


def main():
    print("V4 E2E Test Rollback")
    print("=" * 40)

    if not TARGET_FILE.exists():
        print(f"ERROR: {TARGET_FILE} not found")
        return 1

    content = TARGET_FILE.read_text()

    if "def get_timestamp()" not in content:
        print("Nothing to rollback - function not present")
        return 0

    print(f"Found get_timestamp() in {TARGET_FILE.name}")
    print("Removing...")

    # Remove the function
    new_content = re.sub(FUNCTION_PATTERN, '\n', content, flags=re.DOTALL)

    if new_content == content:
        print("WARNING: Regex didn't match - manual removal may be needed")
        print("Look for 'def get_timestamp()' and remove it manually")
        return 1

    # Write back
    TARGET_FILE.write_text(new_content)
    print("Function removed successfully")

    return 0


if __name__ == "__main__":
    sys.exit(main())

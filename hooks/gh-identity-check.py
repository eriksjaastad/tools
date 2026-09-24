#!/usr/bin/env python3
"""
GitHub Identity Hook

Global PreToolUse hook for personal-account GitHub writes.
Agents use the installed `gha` shim. Direct legacy App-wrapper commands are blocked.

Location: ~/.claude/hooks/gh-identity-check.py
Applies to: All Claude Code projects

Exit codes:
  0 = allow command
  2 = BLOCK command (show stderr to Claude)
"""
import json
import re
import sys


# Write operations that must use the personal-account `gha` shim.
WRITE_PATTERNS = [
    r"gh\s+pr\s+create\b",
    r"gh\s+pr\s+comment\b",
    r"gh\s+pr\s+review\b",
    r"gh\s+pr\s+merge\b",
    r"gh\s+pr\s+close\b",
    r"gh\s+pr\s+edit\b",
    r"gh\s+pr\s+ready\b",
    r"gh\s+pr\s+reopen\b",
    r"gh\s+issue\s+create\b",
    r"gh\s+issue\s+comment\b",
    r"gh\s+issue\s+close\b",
    r"gh\s+issue\s+edit\b",
    r"gh\s+issue\s+reopen\b",
]

LEGACY_WRAPPER_COMMAND = re.compile(r"gh-agent\.sh", re.IGNORECASE)


def check_gh_identity(command: str) -> tuple[bool, str]:
    """
    Check if a bare `gh` command is used for write operations.
    Returns: (should_block, reason)
    """
    # Reject every literal legacy-wrapper reference. Shell launchers such as
    # `bash`, `env`, and `timeout` can all invoke it, and this hook cannot safely
    # prove a reference is read-only from the command text alone.
    legacy = LEGACY_WRAPPER_COMMAND.search(command)
    if legacy:
        return True, "gh-agent.sh"

    # Check if command matches any write operation pattern
    for pattern in WRITE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            # Extract the matched operation for the error message
            match = re.search(pattern, command, re.IGNORECASE)
            operation = match.group(0) if match else "gh write operation"
            return True, operation

    return False, ""


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Hook JSON Parse Error: {e}", file=sys.stderr)
        sys.exit(1)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # Only validate Bash commands
    if tool_name != "Bash" or not command:
        sys.exit(0)

    # Both bare gh and the retired wrapper require inspection.
    if "gh" not in command:
        sys.exit(0)

    should_block, operation = check_gh_identity(command)

    if should_block:
        error_msg = f"""
GH COMMAND BLOCKED BY IDENTITY HOOK

Unsupported GitHub command path `{operation}` detected.

Attempted: {command}

Use the installed personal-account `gha` shim for write operations:
  gha pr create ...
  gha pr comment ...
  gha issue create ...

`gha` resolves to the personal-account shim on PATH. App-role wrapper writes
must not be used for new work.

Read-only operations (gh pr view, gh pr checks, gh api) are fine with bare gh.
""".strip()
        print(error_msg, file=sys.stderr)
        sys.exit(2)  # Exit 2 = BLOCK

    sys.exit(0)


if __name__ == "__main__":
    main()

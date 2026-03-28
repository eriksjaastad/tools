#!/usr/bin/env python3
"""
GitHub Identity Hook

Global PreToolUse hook to enforce bot identity on gh write operations.
Agents must use `gha` (alias for gh-agent.sh --auto) instead of bare `gh`
for PR/issue write operations. This prevents PRs from appearing under
Erik's personal account instead of the project's bot identity.

Location: ~/.claude/hooks/gh-identity-check.py
Applies to: All Claude Code projects

Exit codes:
  0 = allow command
  2 = BLOCK command (show stderr to Claude)
"""
import json
import re
import sys


# Write operations that MUST use gha wrapper
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

# Wrapper scripts that set bot identity — these are safe
WRAPPER_PATTERNS = [
    r"gha\b",
    r"gh-agent\.sh",
    r"gh-claude\.sh",
    r"gh-antigravity\.sh",
]


def check_gh_identity(command: str) -> tuple[bool, str]:
    """
    Check if a bare `gh` command is used for write operations.
    Returns: (should_block, reason)
    """
    # If the command uses a known wrapper, allow it
    for wrapper in WRAPPER_PATTERNS:
        if re.search(wrapper, command):
            return False, ""

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

    # Quick exit: only check commands that contain "gh "
    if "gh " not in command and not command.startswith("gh"):
        sys.exit(0)

    should_block, operation = check_gh_identity(command)

    if should_block:
        error_msg = f"""
GH COMMAND BLOCKED BY IDENTITY HOOK

Bare `{operation}` detected — this will run under Erik's personal account.

Attempted: {command}

Use `gha` instead of `gh` for all write operations:
  gha pr create ...
  gha pr comment ...
  gha issue create ...

`gha` is an alias for `$HOME/projects/_tools/gh-agent.sh --auto` which
automatically sets the correct bot identity (GitHub App token + committer)
for the current project.

Read-only operations (gh pr view, gh pr checks, gh api) are fine with bare gh.
""".strip()
        print(error_msg, file=sys.stderr)
        sys.exit(2)  # Exit 2 = BLOCK

    sys.exit(0)


if __name__ == "__main__":
    main()

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
import shlex
import sys
from pathlib import Path


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


def legacy_wrapper_invocation(command: str) -> bool:
    """Recognize direct and common shell-launched wrapper executions."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        # A malformed command may execute an earlier segment. Keep the legacy
        # wrapper blocked when its invocation cannot be parsed reliably.
        return "gh-agent.sh" in command

    segments = []
    segment = []
    for token in tokens:
        if token and all(char in ";&|()" for char in token):
            if segment:
                segments.append(segment)
            segment = []
        else:
            segment.append(token)
    if segment:
        segments.append(segment)

    for words in segments:
        index = 0
        while index < len(words):
            word = words[index]
            if "=" in word and not word.startswith("/") and index == 0:
                index += 1  # Shell variable assignment before the command.
                continue
            if word in ("env", "/usr/bin/env"):
                index += 1
                while index < len(words):
                    option = words[index]
                    if option == "-u" and index + 1 < len(words):
                        index += 2
                    elif option.startswith("-") or ("=" in option and not option.startswith("/")):
                        index += 1
                    else:
                        break
                continue
            if word == "timeout" and index + 1 < len(words):
                index += 2  # duration
                continue
            if word in ("bash", "sh", "/bin/bash", "/bin/sh"):
                index += 1
                while index < len(words) and words[index].startswith("-"):
                    option = words[index]
                    index += 1
                    if option.startswith("-") and not option.startswith("--") and "c" in option[1:]:
                        if index < len(words) and legacy_wrapper_invocation(words[index]):
                            return True
                        break
                continue
            if word in ("command", "exec", "source", "."):
                index += 1
                if index < len(words) and words[index] == "-v":
                    break  # command -v only inspects PATH.
                continue
            if Path(word).name == "gh-agent.sh":
                return True
            break
    return False


def mutating_bare_api(command: str) -> bool:
    """Block bare gh api requests whose HTTP method can change server state."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return bool(re.search(r"\bgh\s+api\b", command))

    segment = []
    segments = []
    for token in tokens:
        if token and all(char in ";&|()" for char in token):
            if segment:
                segments.append(segment)
            segment = []
        else:
            segment.append(token)
    if segment:
        segments.append(segment)

    for words in segments:
        for index, word in enumerate(words[:-1]):
            if word in ("bash", "sh", "/bin/bash", "/bin/sh"):
                option_index = index + 1
                while option_index < len(words) and words[option_index].startswith("-"):
                    option = words[option_index]
                    option_index += 1
                    if option.startswith("-") and not option.startswith("--") and "c" in option[1:]:
                        if option_index < len(words) and mutating_bare_api(words[option_index]):
                            return True
                        break
            if word != "gh" or words[index + 1] != "api":
                continue
            args = words[index + 2:]
            method = None
            has_body = False
            for offset, arg in enumerate(args):
                if arg in ("-X", "--method") and offset + 1 < len(args):
                    method = args[offset + 1].upper()
                elif arg.startswith("--method="):
                    method = arg.partition("=")[2].upper()
                elif arg.startswith("-X") and len(arg) > 2:
                    method = arg[2:].upper()
                elif arg in ("-f", "-F", "--field", "--raw-field", "--input") or arg.startswith(("--field=", "--raw-field=", "--input=", "-f", "-F")):
                    has_body = True
            if method is not None:
                return method not in ("GET", "HEAD")
            if has_body:
                return True
    return False


def check_gh_identity(command: str) -> tuple[bool, str]:
    """
    Check if a bare `gh` command is used for write operations.
    Returns: (should_block, reason)
    """
    if legacy_wrapper_invocation(command):
        return True, "gh-agent.sh"
    if mutating_bare_api(command):
        return True, "gh api write operation"

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

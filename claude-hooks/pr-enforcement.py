#!/usr/bin/env python3
"""PR Enforcement Hook - PostToolUse

Fires after `gh pr create` commands to enforce PR quality standards:
1. Warns if no --label flag was included
2. Detects multi-concern PRs (mixed conventional commit types)
3. Reminds to run CI checks
"""
import json
import re
import subprocess
import sys


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Hook JSON Parse Error: {e}", file=sys.stderr)
        sys.exit(1)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if tool_name != "Bash" or "pr create" not in command:
        sys.exit(0)

    warnings = []

    # Check 1: label included?
    if "--label" not in command:
        warnings.append(
            "WARNING: PR created WITHOUT a label. "
            "Add one: gha pr edit <number> --add-label 'type:feat'"
        )

    # Check 2: multi-concern PR?
    try:
        result = subprocess.run(
            ["git", "log", "origin/main..HEAD", "--format=%s"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            messages = result.stdout.strip().split("\n")
            types_found = set()
            for msg in messages:
                match = re.match(
                    r"^(feat|fix|docs|chore|refactor|test|style|perf|ci|build)",
                    msg,
                )
                if match:
                    types_found.add(match.group(1))
            if len(types_found) > 1:
                warnings.append(
                    f"WARNING: Multi-concern PR detected: commit types "
                    f"[{', '.join(sorted(types_found))}]. "
                    f"Consider splitting into separate PRs."
                )
    except Exception:
        pass

    # Check 3: remind about CI checks
    if "pr checks" not in command and "--watch" not in command:
        warnings.append(
            "REMINDER: Run `gha pr checks <number> --watch` to wait for CI"
        )

    if warnings:
        print("\n".join(warnings), file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()

"""Repository hook coverage; installed user hooks are outside this test suite."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "hooks" / "gh-identity-check.py"
spec = importlib.util.spec_from_file_location("gh_identity_hook_test", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


@pytest.mark.parametrize("command", ["gha pr create", "gh-agent.sh manager pr create", "gh pr view 1", "gh issue list"])
def test_supported_commands_remain_allowed(command):
    assert hook.check_gh_identity(command) == (False, "")


@pytest.mark.parametrize("command", ["gh pr create", "gh pr review 1", "gh issue create"])
def test_bare_writes_are_blocked(command):
    blocked, reason = hook.check_gh_identity(command)
    assert blocked
    assert reason in command


def test_retired_wrapper_no_longer_exempts_bare_write():
    # The old allow-list matched anywhere in the command, including an argument.
    blocked, reason = hook.check_gh_identity("gh pr create --body gh-claude.sh")
    assert blocked
    assert reason == "gh pr create"
    assert not (REPO / "gh-claude.sh").exists()


@pytest.mark.parametrize("command,expected_code", [("gha pr create", 0), ("gh pr create --body gh-claude.sh", 2)])
def test_hook_json_entrypoint(command, expected_code):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    try:
        result = subprocess.run(
            [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True,
            text=True, check=True, timeout=10,
        )
    except subprocess.CalledProcessError as error:
        assert error.returncode == expected_code
        assert "GH COMMAND BLOCKED" in error.stderr
    else:
        assert expected_code == 0
        assert result.stdout == ""

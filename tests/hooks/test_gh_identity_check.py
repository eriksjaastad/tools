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


@pytest.mark.parametrize("command", ["gha pr create", "gh pr view 1", "gh issue list",
                                      "rg gh-agent.sh AGENTS.md", "cat gh-agent.sh",
                                      "command -v gh-agent.sh"])
def test_supported_commands_remain_allowed(command):
    assert hook.check_gh_identity(command) == (False, "")


@pytest.mark.parametrize("command", ["gh pr create", "gh pr review 1", "gh issue create",
                                      "gh-agent.sh manager pr create", "gh-agent.sh --auto issue create",
                                      "gh-agent.sh manager api -X PUT repos/example/pulls/74/merge",
                                      "bash ./gh-agent.sh manager api -X PUT repos/example/pulls/74/merge",
                                      "env GH_TOKEN=x ./gh-agent.sh --auto api -X POST repos/example/issues",
                                      "env -u GH_TOKEN bash ./gh-agent.sh --auto -- git push",
                                      "GH_TOKEN=x ./gh-agent.sh --auto pr create",
                                      "timeout 10 bash ./gh-agent.sh --auto -- git push",
                                      "bash -c './gh-agent.sh manager pr create'",
                                      "bash -lc './gh-agent.sh manager pr create'",
                                      "bash -e -c './gh-agent.sh manager pr create'",
                                      "source ./gh-agent.sh manager pr create",
                                      ". ./gh-agent.sh manager pr create",
                                      "./gh-agent.sh --auto pr view 1; echo 'unclosed",
                                      "./gh-agent.sh --auto -- git push",
                                      "gh pr create --body gha"])
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


@pytest.mark.parametrize("command", [
    "GH_TOKEN=x gh api -X POST repos/example/issues",
    "gh api --method PATCH repos/example/issues/1",
    "gh api -f title=test repos/example/issues",
    "gh api --raw-field title=test repos/example/issues",
    "gh api --input payload.json repos/example/issues",
    "bash -lc 'gh api -X DELETE repos/example/issues/1'",
])
def test_mutating_bare_api_is_blocked(command):
    assert hook.check_gh_identity(command) == (True, "gh api write operation")


@pytest.mark.parametrize("command", [
    "gh api repos/example/issues",
    "gh api -X GET search/issues -f q=test",
    "gh api --method=GET search/issues --field q=test",
    "rg 'gh api -X POST' AGENTS.md",
])
def test_read_only_api_is_allowed(command):
    assert hook.check_gh_identity(command) == (False, "")


@pytest.mark.parametrize("command,expected_code", [("gha pr create", 0), ("gh pr create --body gh-claude.sh", 2),
                                                   ("gh-agent.sh manager pr create", 2),
                                                   ("source ./gh-agent.sh manager pr create", 2),
                                                   ("GH_TOKEN=x gh api -X POST repos/example/issues", 2),
                                                   ("gh api -X GET search/issues -f q=test", 0),
                                                   ("./gh-agent.sh --auto -- git push", 2)])
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

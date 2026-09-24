"""Test coverage for claude-hooks/pr-enforcement.py"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "claude-hooks" / "pr-enforcement.py"


def run_hook_with_mocks(payload, git_stdout="feat: add feature\n", gh_stdout="false\n", gh_fails=False):
    """Helper to run the hook with mocked subprocess calls."""
    
    # Create a wrapper script that mocks git and gh commands
    wrapper = f'''#!/usr/bin/env python3
import sys
import json

# Mock the subprocess.run calls
original_run = __import__('subprocess').run

def mock_run(args, **kwargs):
    if args[0] == "git":
        result = type('obj', (), {{'stdout': {repr(git_stdout)}, 'returncode': 0}})()
        return result
    elif args[0] == "gh":
        if {gh_fails}:
            raise __import__('subprocess').CalledProcessError(1, args)
        result = type('obj', (), {{'stdout': {repr(gh_stdout)}, 'returncode': 0}})()
        return result
    return original_run(args, **kwargs)

__import__('subprocess').run = mock_run

# Load and run the actual hook
with open({repr(str(HOOK))}) as f:
    exec(f.read())
'''
    
    result = subprocess.run(
        [sys.executable, "-c", wrapper],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result


def test_hook_skips_non_bash_tools():
    """Test hook ignores non-Bash tools."""
    payload = {"tool_name": "Shell", "tool_input": {"command": "gha pr create"}}
    result = run_hook_with_mocks(payload)
    assert result.returncode == 0
    assert result.stderr == ""


def test_hook_skips_non_pr_create_commands():
    """Test hook ignores commands without 'pr create'."""
    payload = {"tool_name": "Bash", "tool_input": {"command": "gha pr view 123"}}
    result = run_hook_with_mocks(payload)
    assert result.returncode == 0
    assert result.stderr == ""


def test_private_repo_reminder():
    """Test that private repo triggers merge reminder."""
    payload = {"tool_name": "Bash", "tool_input": {"command": "gha pr create"}}
    result = run_hook_with_mocks(payload, gh_stdout="true\n")
    
    # Should succeed with private repo warning
    assert result.returncode == 0
    assert "Private repos have no GitHub allow-auto-merge on Free" in result.stderr
    assert "gha pr merge" in result.stderr
    assert "--match-head-commit" in result.stderr
    assert "Do not ping Erik solely for a merge click" in result.stderr


def test_public_repo_no_merge_reminder():
    """Test that public repo does not trigger merge reminder."""
    payload = {"tool_name": "Bash", "tool_input": {"command": "gha pr create"}}
    result = run_hook_with_mocks(payload, gh_stdout="false\n")
    
    # Should succeed without private repo warning
    assert result.returncode == 0
    assert "Private repos have no GitHub allow-auto-merge" not in result.stderr
    assert "REMINDER: Run `gha pr checks" in result.stderr


def test_repo_privacy_detection_failure_silent():
    """Test that privacy detection failure doesn't fail the hook."""
    payload = {"tool_name": "Bash", "tool_input": {"command": "gha pr create"}}
    result = run_hook_with_mocks(payload, gh_fails=True)
    
    # Should still succeed - privacy check failure is silently ignored
    assert result.returncode == 0
    assert "Private repos have no GitHub allow-auto-merge" not in result.stderr
    assert "REMINDER: Run `gha pr checks" in result.stderr


def test_multi_concern_pr_detected():
    """Test that multi-concern PRs are detected."""
    payload = {"tool_name": "Bash", "tool_input": {"command": "gha pr create"}}
    git_output = "feat: add feature\nfix: fix bug\n"
    result = run_hook_with_mocks(payload, git_stdout=git_output)
    
    assert result.returncode == 0
    assert "Multi-concern PR detected" in result.stderr
    assert "feat" in result.stderr
    assert "fix" in result.stderr

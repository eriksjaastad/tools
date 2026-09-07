"""Offline contracts for standalone inspection/startup entry points (#6981)."""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load(relative):
    spec = importlib.util.spec_from_file_location("remediation_target", ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def grepai(monkeypatch):
    module = load("ensure_grepai.py")
    monkeypatch.setattr(module.time, "sleep", Mock())
    return module


@pytest.mark.parametrize("failure", [
    FileNotFoundError("grepai missing"),
    subprocess.TimeoutExpired("grepai", 10),
    subprocess.CalledProcessError(1, "grepai"),
])
def test_failed_status_never_starts_daemon(grepai, monkeypatch, capsys, failure):
    run = Mock(side_effect=failure)
    monkeypatch.setattr(grepai.subprocess, "run", run)
    assert grepai.main() == 1
    assert run.call_count == 1
    assert run.call_args.args[0] == ["grepai", "watch", "--status"]
    assert run.call_args.kwargs["check"] is True
    assert run.call_args.kwargs["timeout"] == 10
    assert "check/start failed" in capsys.readouterr().err


@pytest.mark.parametrize("output", ["", "Status: unknown", "Status: running\nStatus: not running"])
def test_unrecognized_status_never_starts_daemon(grepai, monkeypatch, capsys, output):
    run = Mock(return_value=SimpleNamespace(stdout=output))
    monkeypatch.setattr(grepai.subprocess, "run", run)
    assert grepai.main() == 1
    assert run.call_count == 1
    assert "refusing to start" in capsys.readouterr().err


def test_already_running_is_success_without_start(grepai, monkeypatch):
    run = Mock(return_value=SimpleNamespace(stdout="Status: running\nPID: 42\n"))
    monkeypatch.setattr(grepai.subprocess, "run", run)
    assert grepai.main() == 0
    assert run.call_count == 1


@pytest.mark.parametrize("final_status,expected", [("Status: running", 0), ("Status: not running", 1)])
def test_confirmed_stop_starts_and_verifies(grepai, monkeypatch, final_status, expected):
    run = Mock(side_effect=[SimpleNamespace(stdout="Status: not running\n"), SimpleNamespace(), SimpleNamespace(stdout=final_status)])
    monkeypatch.setattr(grepai.subprocess, "run", run)
    assert grepai.main() == expected
    assert [call.args[0][-1] for call in run.call_args_list] == ["--status", "--background", "--status"]
    assert all(call.kwargs["check"] and call.kwargs["capture_output"] and call.kwargs["timeout"] for call in run.call_args_list)


def test_failed_start_is_nonzero(grepai, monkeypatch, capsys):
    run = Mock(side_effect=[SimpleNamespace(stdout="Status: not running"), subprocess.CalledProcessError(2, "grepai")])
    monkeypatch.setattr(grepai.subprocess, "run", run)
    assert grepai.main() == 1
    assert run.call_count == 2
    assert "check/start failed" in capsys.readouterr().err


@pytest.mark.parametrize("failure", [FileNotFoundError("git missing"), subprocess.TimeoutExpired("git", 5), subprocess.CalledProcessError(128, "git")])
def test_failed_pr_inspection_is_reported(monkeypatch, capsys, failure):
    module = load("claude-hooks/pr-enforcement.py")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "gha pr create --label chore"}})))
    run = Mock(side_effect=failure)
    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 1
    assert run.call_args.kwargs["check"] is True
    assert run.call_args.kwargs["timeout"] == 5
    output = capsys.readouterr().err
    assert "Multi-concern check unavailable" in output
    assert "REMINDER" in output
    assert "Multi-concern PR detected" not in output


@pytest.mark.parametrize("messages,mixed", [("fix: one\nfix: two", False), ("fix: one\ndocs: two", True), ("", False)])
def test_successful_pr_inspection_preserves_warnings(monkeypatch, capsys, messages, mixed):
    module = load("claude-hooks/pr-enforcement.py")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "gha pr create"}})))
    monkeypatch.setattr(module.subprocess, "run", Mock(return_value=SimpleNamespace(stdout=messages)))
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 0
    output = capsys.readouterr().err
    assert "WITHOUT a label" in output
    assert ("Multi-concern PR detected" in output) is mixed
    assert "unavailable" not in output

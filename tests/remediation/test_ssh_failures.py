"""Transport-free tests for expected idle timeouts versus failed SSH sessions."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]


class IdleTimeout(Exception):
    """Synthetic equivalent of pexpect.TIMEOUT."""


class EndOfFile(Exception):
    """Synthetic equivalent of pexpect.EOF."""


@pytest.fixture
def transport(monkeypatch):
    child = Mock()
    child.isalive.return_value = True
    child.expect.return_value = 0
    child.before = "answer\n"
    child.match.group.return_value = "0"
    pexpect = SimpleNamespace(TIMEOUT=IdleTimeout, EOF=EndOfFile, spawn=Mock(return_value=child))
    monkeypatch.setitem(sys.modules, "pexpect", pexpect)
    monkeypatch.setitem(sys.modules, "paramiko", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "yaml", SimpleNamespace())
    path = ROOT / "ssh_agent/src/ssh_mcp/ssh_ops.py"
    spec = importlib.util.spec_from_file_location("ssh_failure_contracts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cfg = {"hostname": "offline.invalid", "key_path": "synthetic-key", "username": "tester", "method": "cli_persistent"}
    monkeypatch.setattr(module, "load_hosts", lambda: {"test-host": cfg})
    return module, child, pexpect


def test_optional_banner_and_empty_buffer_timeouts_preserve_execution(transport):
    module, child, pexpect = transport
    child.expect.side_effect = [IdleTimeout("no banner"), 0]
    child.read_nonblocking.side_effect = IdleTimeout("no buffered bytes")
    assert module.run_ssh_command("test-host", "work") == ("answer", "", 0)
    child.sendline.assert_called_once()
    pexpect.spawn.assert_called_once()


@pytest.mark.parametrize("failure", [EndOfFile, OSError, RuntimeError])
def test_startup_failure_propagates_without_running_command(transport, failure):
    module, child, _ = transport
    child.expect.side_effect = failure("startup failed")
    with pytest.raises(failure, match="startup failed"):
        module.run_ssh_command("test-host", "work")
    child.sendline.assert_not_called()
    assert module.PERSISTENT_SHELLS == {}


@pytest.mark.parametrize("failure", [EndOfFile, OSError, RuntimeError])
def test_buffer_failure_propagates_before_command_is_sent(transport, failure):
    module, child, _ = transport
    child.read_nonblocking.side_effect = failure("session failed")
    with pytest.raises(failure, match="session failed"):
        module.run_ssh_command("test-host", "work")
    child.sendline.assert_not_called()


@pytest.mark.parametrize("completion", [1, 2, IdleTimeout("command timeout")])
def test_completion_failures_remain_explicit_error_results(transport, completion):
    module, child, _ = transport
    child.expect.side_effect = [0, completion]
    child.before = "partial output"
    stdout, stderr, exit_code = module.run_ssh_command("test-host", "work")
    assert stdout == ""
    assert "AGENT_ERROR" in stderr
    assert exit_code == -1


def test_nonzero_remote_status_is_preserved(transport):
    module, child, _ = transport
    child.match.group.return_value = "7"
    assert module.run_ssh_command("test-host", "work") == ("answer", "", 7)

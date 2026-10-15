"""Offline proof of explicit CLI failure sentinels."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from api_cost_tracker import tracker as cost_tracker
import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_script(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def posted(monkeypatch):
    """Records the real cost-tracker client would send. Replacing its send step keeps the
    network and the machine's buffer out of reach under any runner, not only pytest."""
    records = []
    monkeypatch.setattr(cost_tracker, "_send", lambda endpoint, payload: records.append((endpoint, payload)))
    return records


@pytest.fixture
def cli(monkeypatch, posted):
    module = load_script("claude_failure_contracts", "claude-cli/claude-cli.py")
    monkeypatch.setattr(module, "get_api_key", lambda: "offline")
    return module


def provider_failure(monkeypatch, failure):
    if failure == "dependency":
        monkeypatch.setitem(sys.modules, "anthropic", None)
    else:
        client = Mock()
        client.messages.create.side_effect = RuntimeError("synthetic provider failure")
        monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=Mock(return_value=client)))


@pytest.mark.parametrize("failure", ["dependency", "provider"])
def test_single_message_errors_exit_nonzero(cli, monkeypatch, capsys, failure):
    provider_failure(monkeypatch, failure)
    monkeypatch.setattr(sys, "argv", ["claude-cli", "hello"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    output = capsys.readouterr().out
    assert ("not installed" if failure == "dependency" else "synthetic provider failure") in output


@pytest.mark.parametrize("failure", ["dependency", "provider"])
def test_interactive_errors_are_reported_and_session_can_continue(cli, monkeypatch, capsys, failure):
    provider_failure(monkeypatch, failure)
    inputs = iter(["hello", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    cli.interactive_mode("offline")
    output = capsys.readouterr().out
    assert "couldn't get a response" in output
    assert "Goodbye" in output


def test_successful_response_is_preserved_and_its_cost_recorded(cli, posted, monkeypatch, capsys):
    client = Mock()
    client.messages.create.return_value = SimpleNamespace(
        model="claude-test",
        content=[SimpleNamespace(text="successful answer")],
        usage=SimpleNamespace(input_tokens=12, output_tokens=3),
    )
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=Mock(return_value=client)))
    monkeypatch.setattr(sys, "argv", ["claude-cli", "hello"])
    cli.main()
    assert "successful answer" in capsys.readouterr().out
    client.messages.create.assert_called_once()
    ((endpoint, payload),) = posted
    assert endpoint == "/track"
    assert (payload["provider"], payload["model"], payload["project"], payload["caller"]) == (
        "anthropic", "claude-test", "claude-cli", "claude_chat"
    )
    assert (payload["prompt_tokens"], payload["completion_tokens"]) == (12, 3)

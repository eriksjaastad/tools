"""Offline proof of explicit CLI failure sentinels and archived text fallback."""

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_script(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli(monkeypatch):
    monkeypatch.setitem(sys.modules, "api_trust_tracker", SimpleNamespace(track=Mock()))
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


def test_successful_response_is_preserved(cli, monkeypatch, capsys):
    client = Mock()
    client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(text="successful answer")])
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=Mock(return_value=client)))
    monkeypatch.setattr(sys, "argv", ["claude-cli", "hello"])
    cli.main()
    assert "successful answer" in capsys.readouterr().out
    client.messages.create.assert_called_once()


@pytest.fixture
def archive():
    return load_script("archived_claude_contracts", "_archive/multi-layer-delegation/multi-layer-delegation/adapters/claude_code.py")


@pytest.mark.parametrize("text", ["preserved free text", "{broken structured output", "[]", "null"])
def test_archived_optional_parsing_preserves_text_and_usage(archive, text):
    result = archive.parse_claude_output(json.dumps({"result": text, "cost_usd": 0.1, "input_tokens": 10, "output_tokens": 20}))
    assert result["result"] == text
    assert result["cost"] == {"api_cost_usd": 0.1, "input_tokens": 10, "output_tokens": 20}


def test_archived_structured_output_is_still_used(archive):
    structured = {"result": "deliverable", "artifacts": [{"type": "inline", "value": "work"}], "notes": "diagnostic"}
    assert archive.parse_claude_output(json.dumps({"result": json.dumps(structured)})) == structured


def test_archived_non_json_envelope_reports_fallback(archive):
    result = archive.parse_claude_output("free text envelope")
    assert result["result"] == "free text envelope"
    assert "not valid JSON" in result["notes"]

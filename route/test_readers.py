"""Offline usage-reader contracts: complete evidence or an explicit failure."""

import builtins
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROUTE_DIR = Path(__file__).resolve().parent


def load_reader(name):
    spec = importlib.util.spec_from_file_location(f"route_test_{name}", ROUTE_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def claude():
    return load_reader("claude_reader")


@pytest.fixture
def codex():
    return load_reader("codex_reader")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


def claude_cache(home, usage):
    return write_json(home / ".claude" / "stats-cache.json", {"modelUsage": usage})


def codex_metadata(timestamp="2026-09-06T12:00:00Z"):
    return {"type": "session_meta", "payload": {"id": "offline-session", "timestamp": timestamp, "cwd": "workspace/project"}}


def token_event(input_tokens=100, output_tokens=50):
    return {"type": "event_msg", "payload": {"type": "token_count", "info": {
        "total_token_usage": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                              "cached_input_tokens": 20, "reasoning_output_tokens": 5, "total_tokens": input_tokens + output_tokens},
    }}}


def codex_session(home, records=None, name="session.jsonl"):
    return write_jsonl(home / ".codex" / "sessions" / "2026" / name,
                       records if records is not None else [codex_metadata(), token_event()])


def codex_config(home, content='model = "gpt-5.5"\n'):
    path = home / ".codex" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def run_cli(home, *args, expected_code=0):
    try:
        result = subprocess.run(
            [sys.executable, str(ROUTE_DIR / "route"), *args],
            env={"HOME": str(home), "PATH": os.defpath},
            check=True, capture_output=True, text=True, timeout=10,
        )
    except subprocess.CalledProcessError as error:
        assert error.returncode == expected_code, error.stderr
        return error
    assert expected_code == 0, "CLI unexpectedly succeeded"
    return result


def test_claude_valid_totals_preserve_token_contract(claude, tmp_path):
    claude_cache(tmp_path, {"offline-model": {"inputTokens": 12, "outputTokens": 34,
                                             "cacheReadInputTokens": 5, "cacheCreationInputTokens": 6}})
    assert claude.get_token_totals() == {"offline-model": {
        "input_tokens": 12, "output_tokens": 34, "cache_read_tokens": 5, "cache_write_tokens": 6,
    }}


def test_explicit_empty_stats_is_valid_zero_usage(claude, tmp_path):
    claude_cache(tmp_path, {})
    assert claude.get_token_totals() == {}


def test_missing_stats_is_not_zero_usage(claude):
    with pytest.raises(FileNotFoundError):
        claude.get_token_totals()


@pytest.mark.parametrize("contents", ["{bad", "[]", "{}", '{"modelUsage": []}'])
def test_invalid_stats_cannot_produce_totals(claude, tmp_path, contents):
    path = claude_cache(tmp_path, {})
    path.write_text(contents)
    with pytest.raises((ValueError, TypeError)):
        claude.get_token_totals()


@pytest.mark.parametrize("usage", [{}, {"inputTokens": 1}, {"inputTokens": -1, "outputTokens": 2},
                                  {"inputTokens": True, "outputTokens": 2}, {"inputTokens": "1", "outputTokens": 2}])
def test_incomplete_or_invalid_stats_counters_raise(claude, tmp_path, usage):
    claude_cache(tmp_path, {"offline-model": usage})
    with pytest.raises(ValueError):
        claude.get_token_totals()


def test_claude_valid_session_counts_and_classification(claude, tmp_path):
    path = write_jsonl(tmp_path / ".claude" / "projects" / "project" / "session.jsonl", [
        {"message": {"role": "user", "content": "offline message"}},
        {"message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Write"},
                                                       {"type": "tool_use", "name": "Read"}]},
         "metadata": {"model": "offline-model"}},
    ])
    sessions = claude.read_sessions()
    assert len(sessions) == 1
    assert sessions[0] == {
        "session_id": "session", "project": "project", "timestamp": claude._get_session_mtime(path),
        "user_messages": 1, "assistant_messages": 1, "tool_calls": {"Write": 1, "Read": 1},
        "write_tools": 1, "read_tools": 1, "category": "CODING", "models_used": ["offline-model"],
    }


def test_claude_corrupt_record_cannot_produce_partial_session(claude, tmp_path):
    path = write_jsonl(tmp_path / "session.jsonl", [{"message": {"role": "user"}}])
    path.write_text(path.read_text() + "{sentinel-private-source\n")
    with pytest.raises(ValueError, match="Invalid Claude session JSON") as error:
        claude._parse_session_file(path)
    assert "sentinel-private-source" not in str(error.value)


@pytest.mark.parametrize("operation", ["stats", "session"])
def test_claude_read_failure_propagates(claude, tmp_path, monkeypatch, operation):
    path = write_jsonl(tmp_path / "session.jsonl", [])
    claude_cache(tmp_path, {})

    def unreadable(*args, **kwargs):
        raise PermissionError("Offline unreadable file")

    monkeypatch.setattr(builtins, "open", unreadable)
    with pytest.raises(PermissionError):
        if operation == "stats":
            claude.get_token_totals()
        else:
            claude._parse_session_file(path)


def test_claude_mtime_is_required(claude, tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise PermissionError("Offline missing mtime")

    monkeypatch.setattr(Path, "stat", unavailable)
    with pytest.raises(PermissionError):
        claude._parse_session_file(tmp_path / "session.jsonl")


@pytest.mark.parametrize("reader_name", ["claude_reader", "codex_reader"])
@pytest.mark.parametrize("requested_date", ["not-a-date", ""])
def test_invalid_requested_date_fails_even_when_source_missing(reader_name, requested_date):
    reader = load_reader(reader_name)
    with pytest.raises(ValueError):
        reader.read_sessions(requested_date)


def test_claude_epoch_date_filter_is_not_disabled(claude, tmp_path):
    path = write_jsonl(tmp_path / ".claude" / "projects" / "project" / "session.jsonl", [])
    os.utime(path, (0, 0))
    assert claude.read_sessions("1970-01-01T00:00:00+00:00") == []


@pytest.mark.parametrize("reader_name,folder", [("claude_reader", ".claude/projects"), ("codex_reader", ".codex/sessions")])
def test_missing_directory_and_empty_directory_are_distinct(reader_name, folder, tmp_path):
    reader = load_reader(reader_name)
    with pytest.raises(FileNotFoundError):
        reader.read_sessions()
    (tmp_path / folder).mkdir(parents=True)
    assert reader.read_sessions() == []


def test_unreadable_claude_directory_propagates(claude, tmp_path, monkeypatch):
    (tmp_path / ".claude" / "projects").mkdir(parents=True)

    def unavailable(*args, **kwargs):
        raise PermissionError("Offline unavailable directory")

    monkeypatch.setattr(Path, "iterdir", unavailable)
    with pytest.raises(PermissionError):
        claude.read_sessions()


def test_unreadable_codex_subdirectory_propagates(codex, tmp_path, monkeypatch):
    (tmp_path / ".codex" / "sessions").mkdir(parents=True)

    def unavailable(root, onerror):
        onerror(PermissionError("Offline unavailable directory"))

    monkeypatch.setattr(codex.os, "walk", unavailable)
    with pytest.raises(PermissionError):
        codex.read_sessions()


def test_codex_explicit_toml_model_uses_top_level_only(codex, tmp_path):
    codex_config(tmp_path, "model='gpt-5.5'\n[profiles.other]\nmodel='unrelated'\n")
    assert codex._get_codex_model() == "gpt-5.5"


@pytest.mark.parametrize("content", ["", "model=42", "model=' '", "model=[", "[profiles.other]\nmodel='unrelated'"])
def test_codex_missing_or_malformed_model_is_not_assumed(codex, tmp_path, content):
    codex_config(tmp_path, content)
    with pytest.raises(ValueError):
        codex._get_codex_model()


def test_codex_missing_model_file_is_not_assumed(codex):
    with pytest.raises(FileNotFoundError):
        codex._get_codex_model()


def test_codex_valid_cumulative_tokens_preserve_contract(codex, tmp_path):
    codex_config(tmp_path)
    codex_session(tmp_path, [codex_metadata(), token_event(10, 5), token_event(100, 50)])
    assert codex.get_token_totals() == {"gpt-5.5": {
        "input_tokens": 100, "output_tokens": 50, "cached_input_tokens": 20, "reasoning_tokens": 5,
    }}
    assert codex.read_sessions()[0]["project"] == "project"
    assert codex.read_sessions()[0]["total_tokens"] == 150


def test_codex_explicit_zero_token_event_is_valid_evidence(codex, tmp_path):
    codex_config(tmp_path)
    codex_session(tmp_path, [codex_metadata(), {"type": "event_msg", "payload": {"type": "token_count", "info": {
        "total_token_usage": {"input_tokens": 0, "output_tokens": 0},
    }}}])
    assert codex.get_token_totals()["gpt-5.5"]["input_tokens"] == 0


@pytest.mark.parametrize("contents", ["", "{bad", "[]", '{"type":"event_msg"}', '{"type":"session_meta","payload":null}'])
def test_codex_missing_or_corrupt_metadata_raises(codex, tmp_path, contents):
    path = codex_session(tmp_path)
    path.write_text(contents)
    with pytest.raises((ValueError, TypeError)):
        codex._parse_session_meta(path)


@pytest.mark.parametrize("timestamp", [None, 42, "not-a-date", "2026-09-06T12:00:00"])
@pytest.mark.parametrize("since", [None, "2026-09-01"])
def test_codex_invalid_timestamps_never_bypass_filter(codex, tmp_path, timestamp, since):
    codex_session(tmp_path, [codex_metadata(timestamp), token_event()])
    with pytest.raises(ValueError):
        codex.read_sessions(since)


def test_codex_date_filter_compares_aware_timestamps(codex, tmp_path):
    codex_config(tmp_path)
    codex_session(tmp_path, [codex_metadata("2026-09-06T01:00:00+02:00"), token_event()], name="before.jsonl")
    codex_session(tmp_path, [codex_metadata("2026-09-06T02:00:00+02:00"), token_event()], name="at.jsonl")
    sessions = codex.read_sessions("2026-09-06")
    assert len(sessions) == 1
    assert sessions[0]["timestamp"] == "2026-09-06T02:00:00+02:00"


def test_codex_missing_token_event_is_not_zero_usage(codex, tmp_path):
    codex_session(tmp_path, [codex_metadata()])
    with pytest.raises(ValueError, match="no token-count evidence"):
        codex.get_token_totals()


@pytest.mark.parametrize("suffix", ["{sentinel-private-source\n", json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": None}}),
                                   json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {}}}})])
def test_codex_broken_final_event_cannot_reuse_earlier_total(codex, tmp_path, suffix):
    path = codex_session(tmp_path)
    path.write_text(path.read_text() + suffix)
    with pytest.raises((ValueError, TypeError)) as error:
        codex._find_last_token_count(path)
    assert "sentinel-private-source" not in str(error.value)


def rate_limit_event():
    return {"type": "event_msg", "payload": {
        "type": "token_count", "info": None,
        "rate_limits": {"primary": {"used_percent": 5.0, "window_minutes": 300, "resets_at": 2000000000}},
    }}


@pytest.mark.parametrize("position", ["before", "between", "after"])
def test_codex_rate_limit_update_preserves_latest_usage(codex, tmp_path, position):
    records = [token_event(10, 5), token_event(100, 50)]
    records.insert({"before": 0, "between": 1, "after": 2}[position], rate_limit_event())
    codex_session(tmp_path, [codex_metadata(), *records])
    codex_config(tmp_path)
    assert codex.get_token_totals()["gpt-5.5"] == {
        "input_tokens": 100, "output_tokens": 50, "cached_input_tokens": 20, "reasoning_tokens": 5,
    }


def test_codex_rate_limits_without_usage_do_not_establish_zero(codex, tmp_path):
    codex_session(tmp_path, [codex_metadata(), rate_limit_event()])
    with pytest.raises(ValueError, match="no token-count evidence"):
        codex.read_sessions()


@pytest.mark.parametrize("limits", [None, [], {}, "not rate limits"])
def test_codex_null_info_requires_valid_rate_limit_metadata(codex, tmp_path, limits):
    event = rate_limit_event()
    event["payload"]["rate_limits"] = limits
    path = codex_session(tmp_path, [codex_metadata(), token_event(), event])
    with pytest.raises((TypeError, ValueError)):
        codex._find_last_token_count(path)


def test_codex_missing_info_is_not_a_rate_limit_update(codex, tmp_path):
    event = rate_limit_event()
    del event["payload"]["info"]
    path = codex_session(tmp_path, [codex_metadata(), token_event(), event])
    with pytest.raises((TypeError, ValueError)):
        codex._find_last_token_count(path)


@pytest.mark.parametrize("operation", ["config", "metadata", "usage"])
def test_codex_read_failures_propagate(codex, tmp_path, monkeypatch, operation):
    path = codex_session(tmp_path)
    codex_config(tmp_path)

    def unreadable(*args, **kwargs):
        raise PermissionError("Offline unreadable file")

    monkeypatch.setattr(builtins, "open", unreadable)
    with pytest.raises(PermissionError):
        if operation == "config":
            codex._get_codex_model()
        elif operation == "metadata":
            codex._parse_session_meta(path)
        else:
            codex._find_last_token_count(path)


@pytest.mark.parametrize("flag", ["--week", "--month"])
def test_cli_rejects_unavailable_summary_date_ranges(tmp_path, flag):
    result = run_cli(tmp_path, "summary", flag, expected_code=2)
    assert result.stdout == ""
    assert "aggregate totals" in result.stderr


def test_cli_valid_empty_evidence_reports_zero(tmp_path):
    claude_cache(tmp_path, {})
    (tmp_path / ".codex" / "sessions").mkdir(parents=True)
    result = run_cli(tmp_path, "summary", "--all")
    assert "TOTAL SHADOW COST: $0.00" in result.stdout
    assert result.stderr == ""


def test_cli_second_source_failure_cannot_print_partial_totals(tmp_path):
    claude_cache(tmp_path, {"claude-haiku-4-5-20251001": {"inputTokens": 100, "outputTokens": 20}})
    codex_session(tmp_path, [codex_metadata()])
    result = run_cli(tmp_path, "summary", expected_code=2)
    assert result.stdout == ""
    assert "no token-count evidence" in result.stderr


def test_cli_missing_stats_is_not_a_successful_zero(tmp_path):
    result = run_cli(tmp_path, "summary", expected_code=2)
    assert result.stdout == ""
    assert "unable to complete summary" in result.stderr


def test_cli_corrupt_session_does_not_print_partial_list(tmp_path):
    path = write_jsonl(tmp_path / ".claude" / "projects" / "project" / "session.jsonl", [])
    path.write_text("{sentinel-private-source")
    result = run_cli(tmp_path, "sessions", expected_code=2)
    assert result.stdout == ""
    assert "Invalid Claude session JSON" in result.stderr
    assert "sentinel-private-source" not in result.stderr

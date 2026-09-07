#!/usr/bin/env python3
"""
Codex CLI session reader module for route shadow pricing tool.

Reads Codex CLI session files from ~/.codex/sessions/**/*.jsonl
Extracts token usage from the last token_count event in each session.
"""

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import tomllib


def _get_codex_model() -> str:
    """
    Read the explicit top-level model from ~/.codex/config.toml.
    Missing, malformed, or unreadable configuration cannot establish pricing.
    """
    config_path = Path.home() / ".codex" / "config.toml"

    with open(config_path, "rb") as file:
        config = tomllib.load(file)
    model = config.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Codex configuration requires an explicit top-level model for pricing")
    return model


def _extract_project_from_cwd(cwd: str) -> str:
    """Extract the last path component from a cwd string."""
    if not cwd:
        return "unknown"
    return Path(cwd).name


def _read_records(session_file: Path):
    """Yield complete JSONL evidence; malformed records never become omissions."""
    with open(session_file, "r") as file:
        for number, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid Codex session JSON at {session_file}:{number}") from error
            if not isinstance(record, dict):
                raise TypeError(f"Codex session record must be an object at {session_file}:{number}")
            yield record


def _find_last_token_count(session_file: Path) -> dict:
    """
    Read a JSONL session file and find the LAST token_count event.
    Return the token_count info dict. Missing or partial usage evidence raises.
    """
    last_token_count = None

    for record in _read_records(session_file):
        if record.get("type") != "event_msg":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            raise TypeError(f"Codex event payload must be an object in {session_file}")
        if payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        if "info" in payload and info is None and isinstance(payload.get("rate_limits"), dict) and payload["rate_limits"]:
            # Native rate-limit updates share the token_count event name but
            # contain no new usage. They neither reset nor establish a total.
            continue
        if not isinstance(info, dict) or not isinstance(info.get("total_token_usage"), dict):
            raise TypeError(f"Codex token event has no cumulative usage object in {session_file}")
        usage = info["total_token_usage"]
        for required in ("input_tokens", "output_tokens"):
            if required not in usage:
                raise ValueError(f"Codex token event is missing {required} in {session_file}")
        for field in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"):
            value = usage.get(field, 0)
            if type(value) is not int or value < 0:
                raise ValueError(f"Codex token event requires a nonnegative integer for {field} in {session_file}")
        last_token_count = info
    if last_token_count is None:
        raise ValueError(f"Codex session has no token-count evidence in {session_file}")
    return last_token_count


def _parse_session_meta(session_file: Path) -> dict:
    """
    Read the first line of a JSONL session file to extract session_meta.
    Returns a dict with required session_id, timestamp, and cwd metadata.
    """
    with open(session_file, "r") as file:
        first_line = file.readline()
    try:
        record = json.loads(first_line)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid or missing Codex session metadata in {session_file}") from error
    if not isinstance(record, dict) or record.get("type") != "session_meta":
        raise ValueError(f"Codex session must start with session_meta in {session_file}")
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise TypeError(f"Codex session metadata payload must be an object in {session_file}")
    meta = {
        "session_id": payload.get("id"),
        "timestamp": payload.get("timestamp", record.get("timestamp")),
        "cwd": payload.get("cwd", "unknown"),
    }
    if any(not isinstance(value, str) or not value.strip() for value in meta.values()):
        raise ValueError(f"Codex session metadata requires string ID, timestamp, and cwd in {session_file}")
    timestamp = datetime.fromisoformat(meta["timestamp"].replace("Z", "+00:00"))
    if timestamp.utcoffset() is None:
        raise ValueError(f"Codex session timestamp requires a timezone in {session_file}")
    return meta


def _raise_walk_error(error):
    raise error


def read_sessions(since_date: str | None = None) -> list[dict]:
    """
    Read Codex session files from ~/.codex/sessions/**/*.jsonl

    For each session, find the LAST token_count event (it's cumulative).

    Args:
        since_date: Optional ISO format date string (e.g., "2026-02-15").
                   Only return sessions after this date.

    Returns:
        List of dicts with structure:
        {
            "session_id": str,
            "project": str (extracted from session_meta cwd),
            "timestamp": str (from session_meta),
            "model": str (from explicit top-level config),
            "input_tokens": int,
            "cached_input_tokens": int,
            "output_tokens": int,
            "reasoning_tokens": int,
            "total_tokens": int
        }
    """
    sessions = []
    sessions_dir = Path.home() / ".codex" / "sessions"

    # Parse since_date if provided
    since_datetime = None
    if since_date is not None:
        since_datetime = datetime.fromisoformat(since_date)
        # A requested calendar date has historically meant midnight UTC.
        if since_datetime.tzinfo is None:
            since_datetime = since_datetime.replace(tzinfo=timezone.utc)

    if not stat.S_ISDIR(sessions_dir.stat().st_mode):
        raise NotADirectoryError(f"Codex sessions path is not a directory: {sessions_dir}")
    paths = []
    for directory, _, filenames in os.walk(sessions_dir, onerror=_raise_walk_error):
        paths.extend(Path(directory) / name for name in filenames if name.endswith(".jsonl"))
    model = None
    for session_file in sorted(paths):
        # Extract session metadata (first line)
        meta = _parse_session_meta(session_file)
        # Check date filter
        if since_datetime:
            session_ts = datetime.fromisoformat(meta["timestamp"].replace("Z", "+00:00"))
            if session_ts < since_datetime:
                continue

        # Find the last token_count event
        token_info = _find_last_token_count(session_file)
        total_usage = token_info["total_token_usage"]
        if model is None:
            model = _get_codex_model()

        session_record = {
            "session_id": meta["session_id"],
            "project": _extract_project_from_cwd(meta["cwd"]),
            "timestamp": meta["timestamp"],
            "model": model,
            "input_tokens": total_usage.get("input_tokens", 0),
            "cached_input_tokens": total_usage.get("cached_input_tokens", 0),
            "output_tokens": total_usage.get("output_tokens", 0),
            "reasoning_tokens": total_usage.get("reasoning_output_tokens", 0),
            "total_tokens": total_usage.get("total_tokens", 0),
        }

        sessions.append(session_record)

    return sessions


def get_token_totals() -> dict:
    """
    Aggregate token usage across all Codex sessions by model.

    Returns:
        Dict with model IDs as keys:
        {
            "gpt-5.5": {
                "input_tokens": int,
                "output_tokens": int,
                "cached_input_tokens": int,
                "reasoning_tokens": int
            },
            ...
        }
    """
    totals = {}

    sessions = read_sessions()
    for session in sessions:
        model = session["model"]

        if model not in totals:
            totals[model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_input_tokens": 0,
                "reasoning_tokens": 0,
            }

        totals[model]["input_tokens"] += session["input_tokens"]
        totals[model]["output_tokens"] += session["output_tokens"]
        totals[model]["cached_input_tokens"] += session["cached_input_tokens"]
        totals[model]["reasoning_tokens"] += session["reasoning_tokens"]

    return totals


if __name__ == "__main__":
    # Quick summary for testing/debugging
    sessions = read_sessions()
    totals = get_token_totals()

    print(f"Found {len(sessions)} Codex sessions")
    print("Token totals by model:")

    for model, tokens in sorted(totals.items()):
        total = tokens["total_tokens"] if "total_tokens" in tokens else (
            tokens["input_tokens"] +
            tokens["cached_input_tokens"] +
            tokens["output_tokens"] +
            tokens["reasoning_tokens"]
        )
        print(f"  {model}:")
        print(f"    Input: {tokens['input_tokens']:,}")
        print(f"    Cached input: {tokens['cached_input_tokens']:,}")
        print(f"    Output: {tokens['output_tokens']:,}")
        print(f"    Reasoning: {tokens['reasoning_tokens']:,}")
        print(f"    Total: {total:,}")

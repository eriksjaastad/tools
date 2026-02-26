#!/usr/bin/env python3
"""
Codex CLI session reader module for route shadow pricing tool.

Reads Codex CLI session files from ~/.codex/sessions/**/*.jsonl
Extracts token usage from the last token_count event in each session.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


def _get_codex_model() -> str:
    """
    Read the model from ~/.codex/config.toml using simple string parsing.
    Returns the model value (e.g., "gpt-5.2-codex").
    Falls back to "gpt-5.2-codex" if not found or file doesn't exist.
    """
    config_path = Path.home() / ".codex" / "config.toml"

    if not config_path.exists():
        return "gpt-5.2-codex"

    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith('model = "'):
                    # Extract value between quotes: model = "value"
                    start = line.find('"') + 1
                    end = line.rfind('"')
                    if start > 0 and end > start:
                        return line[start:end]
    except (OSError, IOError):
        pass

    return "gpt-5.2-codex"


def _extract_project_from_cwd(cwd: str) -> str:
    """Extract the last path component from a cwd string."""
    if not cwd:
        return "unknown"
    return Path(cwd).name


def _find_last_token_count(session_file: Path) -> Optional[dict]:
    """
    Read a JSONL session file and find the LAST token_count event.
    Returns the token_count info dict or None if not found.
    """
    last_token_count = None

    try:
        with open(session_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Look for event_msg with type == "token_count"
                if (record.get("type") == "event_msg" and
                    record.get("payload", {}).get("type") == "token_count"):
                    info = record.get("payload", {}).get("info")
                    if info and info.get("total_token_usage"):
                        last_token_count = info
    except (OSError, IOError):
        pass

    return last_token_count


def _parse_session_meta(session_file: Path) -> Optional[dict]:
    """
    Read the first line of a JSONL session file to extract session_meta.
    Returns a dict with session_id, timestamp, and cwd, or None if not found.
    """
    try:
        with open(session_file, "r") as f:
            first_line = f.readline()
            if not first_line.strip():
                return None

            record = json.loads(first_line)
            if record.get("type") == "session_meta":
                payload = record.get("payload", {})
                return {
                    "session_id": payload.get("id", "unknown"),
                    "timestamp": payload.get("timestamp", record.get("timestamp")),
                    "cwd": payload.get("cwd", "unknown"),
                }
    except (OSError, IOError, json.JSONDecodeError):
        pass

    return None


def read_sessions(since_date: Optional[str] = None) -> list[dict]:
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
            "model": str (from config, default "gpt-5.2-codex"),
            "input_tokens": int,
            "cached_input_tokens": int,
            "output_tokens": int,
            "reasoning_tokens": int,
            "total_tokens": int
        }
    """
    sessions = []
    sessions_dir = Path.home() / ".codex" / "sessions"

    if not sessions_dir.exists():
        return sessions

    # Parse since_date if provided
    since_datetime = None
    if since_date:
        try:
            since_datetime = datetime.fromisoformat(since_date)
            # Make it UTC-aware for comparison with session timestamps
            if since_datetime.tzinfo is None:
                since_datetime = since_datetime.replace(tzinfo=timezone.utc)
        except ValueError:
            # Invalid date format, ignore filter
            pass

    model = _get_codex_model()

    # Find all .jsonl files in sessions directory recursively
    for session_file in sessions_dir.glob("**/*.jsonl"):
        # Extract session metadata (first line)
        meta = _parse_session_meta(session_file)
        if not meta:
            continue

        # Check date filter
        if since_datetime:
            try:
                session_ts = datetime.fromisoformat(
                    meta["timestamp"].replace("Z", "+00:00")
                )
                if session_ts < since_datetime:
                    continue
            except (ValueError, AttributeError):
                pass

        # Find the last token_count event
        token_info = _find_last_token_count(session_file)
        if not token_info:
            continue

        total_usage = token_info.get("total_token_usage", {})

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
            "gpt-5.2-codex": {
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
    print(f"Token totals by model:")

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

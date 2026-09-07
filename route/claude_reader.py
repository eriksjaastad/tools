#!/usr/bin/env python3
"""
Claude Code session reader module for the route CLI tool.

Reads AI CLI session data from:
1. ~/.claude/stats-cache.json — aggregated stats (may be stale)
2. ~/.claude/projects/*/*.jsonl — individual session transcripts (real-time)

Provides functions to extract session metadata, tool usage, and activity classification.
"""

import json
import stat
from datetime import datetime, timezone
from pathlib import Path


def read_stats_cache() -> dict:
    """
    Read the aggregated stats cache.

    Returns:
        dict with keys:
        - version: cache version
        - lastComputedDate: ISO date string
        - dailyActivity: list of daily activity records
        - dailyModelTokens: list of daily token records
        - modelUsage: dict of model usage totals
        - totalSessions: int
        - totalMessages: int

    Raises on missing, unreadable, malformed, or incomplete cache evidence.
    """
    cache_path = Path.home() / ".claude" / "stats-cache.json"

    with open(cache_path, "r") as f:
        cache = json.load(f)
    if not isinstance(cache, dict) or not isinstance(cache.get("modelUsage"), dict):
        raise TypeError("Claude stats cache requires a modelUsage object")
    return cache


def get_token_totals() -> dict:
    """
    Read model usage from stats cache and return token totals.

    Returns:
        dict with structure:
        {
            "model_id": {
                "input_tokens": int,
                "output_tokens": int,
                "cache_read_tokens": int,
                "cache_write_tokens": int
            }
        }

    Field mapping from stats-cache.json:
    - inputTokens -> input_tokens
    - outputTokens -> output_tokens
    - cacheReadInputTokens -> cache_read_tokens
    - cacheCreationInputTokens -> cache_write_tokens
    """
    cache = read_stats_cache()
    model_usage = cache["modelUsage"]

    result = {}
    for model_id, usage in model_usage.items():
        if not isinstance(model_id, str) or not model_id.strip() or not isinstance(usage, dict):
            raise ValueError("Claude model usage requires a model ID and token counters")
        for required in ("inputTokens", "outputTokens"):
            if required not in usage:
                raise ValueError(f"Claude model usage is missing {required}")
        for field in ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens"):
            value = usage.get(field, 0)
            if type(value) is not int or value < 0:
                raise ValueError(f"Claude model usage requires a nonnegative integer for {field}")
        result[model_id] = {
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
            "cache_read_tokens": usage.get("cacheReadInputTokens", 0),
            "cache_write_tokens": usage.get("cacheCreationInputTokens", 0),
        }

    return result


def _extract_project_name(session_path: Path) -> str:
    """
    Extract project name from session file path.

    Path format: ~/.claude/projects/-Users-eriksjaastad-projects-{PROJECT_NAME}/{session_id}.jsonl
    Returns: PROJECT_NAME
    """
    project_dir = session_path.parent.name
    # Format: -Users-eriksjaastad-projects-{PROJECT_NAME}
    prefix = "-Users-eriksjaastad-projects-"
    if project_dir.startswith(prefix):
        return project_dir[len(prefix):]
    return project_dir


def _get_session_mtime(session_path: Path) -> str:
    """Get required modification metadata used for ordering and date filtering."""
    mtime = session_path.stat().st_mtime
    # Keep the existing local, timezone-free display format after explicit conversion.
    return datetime.fromtimestamp(mtime, timezone.utc).astimezone().replace(tzinfo=None).isoformat()


def _read_records(session_path: Path):
    """Yield every JSONL record, rejecting corruption instead of partial counts."""
    with open(session_path, "r") as file:
        for number, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid Claude session JSON at {session_path}:{number}") from error
            if not isinstance(record, dict):
                raise TypeError(f"Claude session record must be an object at {session_path}:{number}")
            yield record


def _classify_session(
    write_tools: int,
    read_tools: int,
    tool_calls: dict,
) -> str:
    """
    Classify session activity based on tool usage patterns.

    Classification logic:
    - CODING: write_tools > 0 AND write_tools / total_tools > 0.2
    - RESEARCH: read_tools > total_tools * 0.5
    - TALKING: total_tools == 0 OR (write_tools == 0 AND total_tools < 5)
    - MIXED: everything else
    """
    total_tools = sum(tool_calls.values())

    if total_tools == 0:
        return "TALKING"

    if write_tools > 0 and (write_tools / total_tools) > 0.2:
        return "CODING"

    if read_tools > total_tools * 0.5:
        return "RESEARCH"

    if write_tools == 0 and total_tools < 5:
        return "TALKING"

    return "MIXED"


def _parse_session_file(session_path: Path) -> dict:
    """
    Parse a single JSONL session file.

    Returns a session dict; missing metadata and corrupt/unreadable files raise.
    """
    session_id = session_path.stem
    project = _extract_project_name(session_path)
    timestamp = _get_session_mtime(session_path)

    user_messages = 0
    assistant_messages = 0
    tool_calls = {}
    write_tools_set = {"Edit", "Write", "NotebookEdit"}
    read_tools_set = {"Read", "Glob", "Grep"}
    write_tools_count = 0
    read_tools_count = 0
    models_used = set()

    for obj in _read_records(session_path):
        if "message" not in obj:
            continue
        msg = obj["message"]
        if not isinstance(msg, dict):
            raise TypeError(f"Claude message must be an object in {session_path}")
        role = msg.get("role")
        if role == "user":
            user_messages += 1
        elif role == "assistant":
            assistant_messages += 1
            content = msg.get("content", [])
            if not isinstance(content, (list, str)):
                raise TypeError(f"Claude assistant content must be text or a list in {session_path}")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name")
                        if not isinstance(tool_name, str) or not tool_name:
                            raise ValueError(f"Claude tool call requires a name in {session_path}")
                        tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1
                        if tool_name in write_tools_set:
                            write_tools_count += 1
                        elif tool_name in read_tools_set:
                            read_tools_count += 1
        if "metadata" in obj and isinstance(obj["metadata"], dict):
            model = obj["metadata"].get("model")
            if model:
                if not isinstance(model, str):
                    raise ValueError(f"Claude model metadata must be a string in {session_path}")
                models_used.add(model)

    category = _classify_session(write_tools_count, read_tools_count, tool_calls)

    return {
        "session_id": session_id,
        "project": project,
        "timestamp": timestamp,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "tool_calls": tool_calls,
        "write_tools": write_tools_count,
        "read_tools": read_tools_count,
        "category": category,
        "models_used": sorted(models_used),
    }


def read_sessions(since_date: str | None = None) -> list:
    """
    Read individual session JSONL files from ~/.claude/projects/.

    Args:
        since_date: Optional ISO format date string (YYYY-MM-DD).
                   Only returns sessions modified after this date.

    Returns:
        List of session dicts, each containing:
        {
            "session_id": str,
            "project": str (extracted from path),
            "timestamp": str (file mtime),
            "user_messages": int,
            "assistant_messages": int,
            "tool_calls": dict[str, int] (tool name -> count),
            "write_tools": int (Edit + Write + NotebookEdit),
            "read_tools": int (Read + Glob + Grep),
            "category": "CODING" | "RESEARCH" | "TALKING" | "MIXED",
            "models_used": list[str] (from message metadata if available)
        }
    """
    projects_dir = Path.home() / ".claude" / "projects"

    # Parse since_date if provided
    since_timestamp = None
    if since_date is not None:
        since_dt = datetime.fromisoformat(since_date)
        since_timestamp = since_dt.timestamp()

    sessions = []

    # Explicit enumeration propagates directory-read failures; glob may omit them.
    for project_dir in sorted(projects_dir.iterdir()):
        if not stat.S_ISDIR(project_dir.stat().st_mode):
            continue
        for jsonl_path in sorted(project_dir.iterdir()):
            if jsonl_path.suffix != ".jsonl":
                continue
            if since_timestamp is not None and jsonl_path.stat().st_mtime <= since_timestamp:
                continue
            sessions.append(_parse_session_file(jsonl_path))

    return sessions


if __name__ == "__main__":
    # Quick summary when run directly
    print("=" * 60)
    print("Claude Code Session Reader - Summary")
    print("=" * 60)

    # Stats cache
    cache = read_stats_cache()
    if cache:
        print("\nStats Cache:")
        print(f"  Last computed: {cache.get('lastComputedDate', 'N/A')}")
        print(f"  Total sessions: {cache.get('totalSessions', 0)}")
        print(f"  Total messages: {cache.get('totalMessages', 0)}")
    else:
        print("\nStats Cache: Not available")

    # Token totals
    tokens = get_token_totals()
    if tokens:
        print("\nToken Usage by Model:")
        for model_id, usage in tokens.items():
            total_input = usage["input_tokens"] + usage["cache_read_tokens"]
            total_output = usage["output_tokens"] + usage["cache_write_tokens"]
            print(f"  {model_id}:")
            print(f"    Input: {usage['input_tokens']:,} + {usage['cache_read_tokens']:,} (cached)")
            print(f"    Output: {usage['output_tokens']:,} + {usage['cache_write_tokens']:,} (cached)")

    # Recent sessions
    sessions = read_sessions()
    if sessions:
        print(f"\nRecent Sessions: {len(sessions)}")

        # Group by category
        categories = {}
        for session in sessions:
            cat = session["category"]
            categories[cat] = categories.get(cat, 0) + 1

        print(f"  By category: {categories}")

        # Show top 3 projects by session count
        projects = {}
        for session in sessions:
            proj = session["project"]
            projects[proj] = projects.get(proj, 0) + 1

        top_projects = sorted(projects.items(), key=lambda x: x[1], reverse=True)[:3]
        print("  Top projects:")
        for proj, count in top_projects:
            print(f"    {proj}: {count} sessions")
    else:
        print("\nRecent Sessions: None found")

    print("\n" + "=" * 60)

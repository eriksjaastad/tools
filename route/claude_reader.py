#!/usr/bin/env python3
"""
Claude Code session reader module for the route CLI tool.

Reads AI CLI session data from:
1. ~/.claude/stats-cache.json — aggregated stats (may be stale)
2. ~/.claude/projects/*/*.jsonl — individual session transcripts (real-time)

Provides functions to extract session metadata, tool usage, and activity classification.
"""

import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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

    Returns empty dict if file doesn't exist or can't be parsed.
    """
    cache_path = Path.home() / ".claude" / "stats-cache.json"

    if not cache_path.exists():
        logger.warning(f"Stats cache not found at {cache_path}")
        return {}

    try:
        with open(cache_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to read stats cache: {e}")
        return {}


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
    model_usage = cache.get("modelUsage", {})

    result = {}
    for model_id, usage in model_usage.items():
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
    """Get file modification time as ISO format string."""
    try:
        mtime = session_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).isoformat()
    except (OSError, ValueError):
        return ""


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


def _parse_session_file(session_path: Path) -> Optional[dict]:
    """
    Parse a single JSONL session file.

    Returns session dict or None if file is corrupt/unreadable.
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

    try:
        with open(session_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(f"Corrupt JSON in {session_path}: {line[:100]}")
                    continue

                # Count messages
                if "message" in obj:
                    msg = obj["message"]
                    role = msg.get("role")

                    if role == "user":
                        user_messages += 1
                    elif role == "assistant":
                        assistant_messages += 1

                    # Extract tool calls from assistant content blocks
                    if role == "assistant":
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_use":
                                    tool_name = block.get("name")
                                    if tool_name:
                                        tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1

                                        if tool_name in write_tools_set:
                                            write_tools_count += 1
                                        elif tool_name in read_tools_set:
                                            read_tools_count += 1

                    # Extract model info from metadata if available
                    if "metadata" in obj and isinstance(obj["metadata"], dict):
                        model = obj["metadata"].get("model")
                        if model:
                            models_used.add(model)

    except IOError as e:
        logger.warning(f"Failed to read session file {session_path}: {e}")
        return None

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
        "models_used": sorted(list(models_used)),
    }


def read_sessions(since_date: Optional[str] = None) -> list:
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

    if not projects_dir.exists():
        logger.warning(f"Projects directory not found at {projects_dir}")
        return []

    # Parse since_date if provided
    since_timestamp = None
    if since_date:
        try:
            since_dt = datetime.fromisoformat(since_date)
            since_timestamp = since_dt.timestamp()
        except ValueError:
            logger.warning(f"Invalid date format for since_date: {since_date}")
            return []

    sessions = []

    # Find all .jsonl files in project directories
    for jsonl_path in projects_dir.glob("*/*.jsonl"):
        # Check if file is newer than since_date
        if since_timestamp:
            try:
                mtime = jsonl_path.stat().st_mtime
                if mtime <= since_timestamp:
                    continue
            except OSError:
                logger.warning(f"Failed to get mtime for {jsonl_path}")
                continue

        session = _parse_session_file(jsonl_path)
        if session:
            sessions.append(session)

    return sessions


if __name__ == "__main__":
    # Quick summary when run directly
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Claude Code Session Reader - Summary")
    print("=" * 60)

    # Stats cache
    cache = read_stats_cache()
    if cache:
        print(f"\nStats Cache:")
        print(f"  Last computed: {cache.get('lastComputedDate', 'N/A')}")
        print(f"  Total sessions: {cache.get('totalSessions', 0)}")
        print(f"  Total messages: {cache.get('totalMessages', 0)}")
    else:
        print("\nStats Cache: Not available")

    # Token totals
    tokens = get_token_totals()
    if tokens:
        print(f"\nToken Usage by Model:")
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
        print(f"  Top projects:")
        for proj, count in top_projects:
            print(f"    {proj}: {count} sessions")
    else:
        print("\nRecent Sessions: None found")

    print("\n" + "=" * 60)

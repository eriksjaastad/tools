"""Claude CLI environment adapter."""

import os
import sys
from pathlib import Path

from .base import EnvironmentAdapter

class ClaudeCLIAdapter(EnvironmentAdapter):
    """Adapter for Claude Code CLI environment."""

    name = "claude-cli"

    @classmethod
    def detect(cls) -> bool:
        """Detect by CLAUDE_SESSION_ID env var."""
        return bool(os.getenv("CLAUDE_SESSION_ID"))

    def get_config_path(self) -> Path:
        """Config at ~/.claude/"""
        return Path.home() / ".claude"

    def get_session_id(self) -> str | None:
        return os.getenv("CLAUDE_SESSION_ID")

    def trigger(self, message: str) -> bool:
        """Direct output to stdout."""
        print(message)
        sys.stdout.flush()
        return True

    def read_response(self, timeout: float = 30.0) -> str | None:
        """Claude CLI doesn't support async response reading."""
        return None

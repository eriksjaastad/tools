"""Cursor IDE environment adapter."""

import os
import subprocess
import json
from pathlib import Path

from .base import EnvironmentAdapter

class CursorAdapter(EnvironmentAdapter):
    """Adapter for Cursor IDE environment."""

    name = "cursor"

    @classmethod
    def detect(cls) -> bool:
        """Detect by CURSOR_* env vars or config existence."""
        if any(k.startswith("CURSOR_") for k in os.environ):
            return True
        return (Path.home() / ".cursor" / "mcp.json").exists()

    def get_config_path(self) -> Path:
        """Config at ~/.cursor/mcp.json"""
        return Path.home() / ".cursor" / "mcp.json"

    def trigger(self, message: str) -> bool:
        """Trigger via cursor-agent chat command."""
        try:
            result = subprocess.run(
                ["cursor-agent", "chat", message],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def read_response(self, timeout: float = 30.0) -> str | None:
        """Cursor responses come via MCP, not direct read."""
        return None

    def load_mcp_config(self) -> dict:
        """Load the Cursor MCP configuration."""
        config_path = self.get_config_path()
        if config_path.exists():
            return json.loads(config_path.read_text())
        return {}

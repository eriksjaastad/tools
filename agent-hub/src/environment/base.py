"""Base class for environment adapters."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from enum import Enum

class Environment(Enum):
    CLAUDE_CLI = "claude_cli"
    CURSOR = "cursor"
    ANTIGRAVITY = "antigravity"
    UNKNOWN = "unknown"

class EnvironmentAdapter(ABC):
    """Abstract base class for environment adapters."""

    name: str = "unknown"

    @classmethod
    @abstractmethod
    def detect(cls) -> bool:
        """Return True if this environment is active."""
        pass

    @abstractmethod
    def get_config_path(self) -> Path:
        """Return path to MCP config for this environment."""
        pass

    @abstractmethod
    def trigger(self, message: str) -> bool:
        """
        Trigger/notify this environment.
        Returns True if successful.
        """
        pass

    @abstractmethod
    def read_response(self, timeout: float = 30.0) -> str | None:
        """
        Read response from environment (if applicable).
        Returns None if no response or not supported.
        """
        pass

    def get_session_id(self) -> str | None:
        """Get current session ID if available."""
        return None


def detect_environment() -> EnvironmentAdapter:
    """
    Detect the current environment and return appropriate adapter.

    Priority: Claude CLI > Cursor > Anti-Gravity > Unknown
    """
    from .claude_cli import ClaudeCLIAdapter
    from .cursor import CursorAdapter
    from .antigravity import AntigravityAdapter

    for adapter_class in [ClaudeCLIAdapter, CursorAdapter, AntigravityAdapter]:
        if adapter_class.detect():
            return adapter_class()

    # Fallback - return Claude CLI adapter as default
    return ClaudeCLIAdapter()

def get_adapter() -> EnvironmentAdapter:
    """Convenience wrapper for detect_environment."""
    return detect_environment()

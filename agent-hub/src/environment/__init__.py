from .base import EnvironmentAdapter, detect_environment, Environment, get_adapter
from .claude_cli import ClaudeCLIAdapter
from .cursor import CursorAdapter
from .antigravity import AntigravityAdapter

__all__ = [
    "EnvironmentAdapter",
    "detect_environment",
    "ClaudeCLIAdapter",
    "CursorAdapter",
    "AntigravityAdapter",
    "Environment",
    "get_adapter",
]

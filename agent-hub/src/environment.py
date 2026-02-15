"""
Environment Detection - Adapters for Claude CLI, Cursor, and Anti-Gravity.
"""

import os
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class Environment(Enum):
    CLAUDE_CLI = "claude_cli"
    CURSOR = "cursor"
    ANTIGRAVITY = "antigravity"
    UNKNOWN = "unknown"

class EnvironmentAdapter:
    """Base adapter class."""
    def notify(self, message: str):
        pass
    def trigger_agent(self, prompt: str):
        pass
    def get_mcp_config_path(self) -> Path:
        return Path("~/.mcp.json").expanduser()

class ClaudeCLIAdapter(EnvironmentAdapter):
    def notify(self, message: str):
        print(f"\n[Claude CLI] {message}")
    
    def trigger_agent(self, prompt: str):
        logger.info("Sub-agent trigger not supported in Claude CLI (already in session)")
    
    def get_mcp_config_path(self) -> Path:
        return Path("~/.claude/mcp.json").expanduser()

class CursorAdapter(EnvironmentAdapter):
    def notify(self, message: str):
        print(f"\n[Cursor] {message}")
    
    def trigger_agent(self, prompt: str):
        import subprocess
        logger.info(f"Triggering cursor-agent with prompt: {prompt[:50]}...")
        try:
            subprocess.run(["cursor-agent", "chat", prompt], check=False, timeout=30)
        except subprocess.TimeoutExpired:
            logger.warning("cursor-agent timed out after 30 seconds")
    
    def get_mcp_config_path(self) -> Path:
        return Path("~/.cursor/mcp.json").expanduser()

class AntigravityAdapter(EnvironmentAdapter):
    def __init__(self, handoff_dir: str = "_handoff"):
        self.handoff_dir = Path(handoff_dir)
        self.handoff_dir.mkdir(parents=True, exist_ok=True)

    def notify(self, message: str):
        notif_file = self.handoff_dir / "notifications.md"
        with open(notif_file, "a") as f:
            f.write(f"- {message}\n")
    
    def trigger_agent(self, prompt: str):
        import json
        pending_file = self.handoff_dir / "pending_tasks.json"
        task = {"prompt": prompt, "timestamp": os.getpid()}
        with open(pending_file, "a") as f:
            f.write(json.dumps(task) + "\n")
    
    def get_mcp_config_path(self) -> Path:
        return Path("~/.antigravity/mcp.json").expanduser()

def detect_environment() -> Environment:
    """
    FR-5.1: Detect environment via env vars and filesystem.
    """
    if os.getenv("CLAUDE_SESSION_ID"):
        return Environment.CLAUDE_CLI
    if os.getenv("CURSOR_SESSION") or Path(".cursor").exists():
        return Environment.CURSOR
    if os.getenv("ANTIGRAVITY_SESSION"):
        return Environment.ANTIGRAVITY
    return Environment.UNKNOWN

def get_adapter() -> EnvironmentAdapter:
    """
    FR-5.2: Return appropriate adapter for current environment.
    """
    env = detect_environment()
    if env == Environment.CLAUDE_CLI:
        return ClaudeCLIAdapter()
    if env == Environment.CURSOR:
        return CursorAdapter()
    if env == Environment.ANTIGRAVITY:
        return AntigravityAdapter()
    return ClaudeCLIAdapter() # Default fallback

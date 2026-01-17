"""
Configuration loader for Floor Manager skill.
Reads from skill.json, environment variables, and runtime overrides.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class FloorManagerConfig:
    agent_id: str = "floor_manager"
    hub_path: Path = None
    mcp_server_path: Path = None
    handoff_dir: Path = Path("_handoff")
    heartbeat_interval: int = 30
    message_poll_interval: int = 5

    # Limits
    max_rebuttals: int = 2
    max_review_cycles: int = 5
    cost_ceiling_usd: float = 0.50
    global_timeout_hours: int = 4

    @classmethod
    def load(cls, skill_root: Path = None) -> "FloorManagerConfig":
        """
        Load config with priority:
        1. Environment variables (highest)
        2. skill.json
        3. Defaults (lowest)
        """
        config = cls()

        # Find skill.json
        if skill_root is None:
            skill_root = Path(__file__).parent.parent

        skill_json = skill_root / "skill.json"
        
        # Default paths to use if nothing else is found
        default_hub_path = "/Users/eriksjaastad/projects/_tools/claude-mcp/dist/server.js"
        default_mcp_path = "/Users/eriksjaastad/projects/_tools/ollama-mcp/dist/server.js"

        if skill_json.exists():
            try:
                with open(skill_json) as f:
                    manifest = json.load(f)
                    cfg = manifest.get("config", {})

                    for key, spec in cfg.items():
                        if hasattr(config, key):
                            val = spec.get("default")
                            # Handle ${VAR} placeholders in skill.json
                            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                                env_var = val[2:-1]
                                val = os.getenv(env_var)
                            
                            if val is not None:
                                if key in ["hub_path", "handoff_dir"]:
                                    setattr(config, key, Path(val))
                                else:
                                    setattr(config, key, val)
            except Exception:
                pass

        # Environment overrides and specific defaults
        config.hub_path = Path(os.getenv(
            "HUB_SERVER_PATH",
            str(config.hub_path or default_hub_path)
        ))
        config.mcp_server_path = Path(os.getenv(
            "MCP_SERVER_PATH",
            str(config.mcp_server_path or default_mcp_path)
        ))
        config.handoff_dir = Path(os.getenv("HANDOFF_DIR", str(config.handoff_dir)))
        config.agent_id = os.getenv("FLOOR_MANAGER_ID", config.agent_id)

        return config

    def validate(self) -> list[str]:
        """Returns list of validation errors, empty if valid."""
        errors = []

        if self.hub_path is None or not self.hub_path.exists():
            errors.append(f"Hub server not found: {self.hub_path}")
        if self.mcp_server_path is None or not self.mcp_server_path.exists():
            errors.append(f"MCP server not found: {self.mcp_server_path}")

        return errors


# Global config instance
_config: Optional[FloorManagerConfig] = None

def get_config() -> FloorManagerConfig:
    global _config
    if _config is None:
        _config = FloorManagerConfig.load()
    return _config

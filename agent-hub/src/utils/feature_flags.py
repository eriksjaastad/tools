"""Feature flag utilities for safe rollout."""

import os

def is_enabled(flag_name: str) -> bool:
    """Check if a feature flag is enabled via environment variable."""
    env_var = f"UAS_{flag_name.upper()}"
    value = os.getenv(env_var, "").lower()
    return value in ("1", "true", "yes")

# Convenience functions for specific flags
def use_ollama_http() -> bool:
    return is_enabled("OLLAMA_HTTP")

def use_persistent_mcp() -> bool:
    return is_enabled("PERSISTENT_MCP")

def use_adaptive_polling() -> bool:
    return is_enabled("ADAPTIVE_POLL")

def use_litellm_routing() -> bool:
    return is_enabled("LITELLM_ROUTING")

def use_sqlite_bus() -> bool:
    return is_enabled("SQLITE_BUS")

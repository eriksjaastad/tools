#!/usr/bin/env python3
"""Health check for Floor Manager skill."""

import sys
import os
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure we can import src
from src.config import get_config
from src.mcp_client import MCPClient
from src.hub_client import HubClient

def main():
    config = get_config()

    print("=== Floor Manager Health Check ===")

    # Check config
    errors = config.validate()
    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return 1
    print("[OK] Configuration valid")

    # Check hub connection
    try:
        with MCPClient(config.hub_path) as mcp:
            hub = HubClient(mcp)
            if hub.connect("health_check"):
                print("[OK] MCP Hub connection")
            else:
                print("[FAIL] MCP Hub connection")
                return 1
    except Exception as e:
        print(f"[FAIL] MCP Hub: {e}")
        return 1

    # Check Ollama connection
    try:
        with MCPClient(config.mcp_server_path) as mcp:
            # Just verify we can connect/start
            print("[OK] Ollama MCP connection")
    except Exception as e:
        print(f"[FAIL] Ollama MCP: {e}")
        return 1

    print("\nAll checks passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())

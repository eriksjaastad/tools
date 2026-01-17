#!/bin/bash
# Start Agent Hub with MCP message listener

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HUB_PATH="${HUB_SERVER_PATH:-/Users/eriksjaastad/projects/_tools/claude-mcp/dist/server.js}"

echo "=== Agent Hub Startup ==="

# 1. Check if hub is already running
if ! pgrep -f "claude-mcp" > /dev/null; then
    echo "Starting MCP Hub..."
    node "$HUB_PATH" &
    sleep 2
fi

# 2. Verify hub is responsive
python3 -c "
import sys
import os
from pathlib import Path
# Add project root to path for imports
sys.path.append('$PROJECT_ROOT')
from src.hub_client import HubClient
from src.mcp_client import MCPClient

with MCPClient(Path('$HUB_PATH')) as mcp:
    hub = HubClient(mcp)
    if hub.connect('startup_check'):
        print('Hub: OK')
    else:
        sys.exit(1)
" || {
    echo "Error: Hub not responsive"
    exit 1
}

# 3. Start message listener
echo "Starting Message Listener..."
cd "$PROJECT_ROOT"
# Use -m to run as module so absolute imports work
PYTHONPATH=. python3 -m src.listener

echo "Agent Hub stopped."

#!/bin/bash
# Pre-installation checks for Floor Manager skill

set -e

echo "=== Floor Manager Pre-Install Check ==="

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
# bc might not be installed, use python for comparison
IS_PYTHON_OK=$(python3 -c "print(1 if float('$PYTHON_VERSION') >= 3.10 else 0)")

if [[ "$IS_PYTHON_OK" -eq 0 ]]; then
    echo "Error: Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi
echo "Python: OK ($PYTHON_VERSION)"

# Check for required MCP servers
if [ -z "$HUB_SERVER_PATH" ]; then
    echo "Warning: HUB_SERVER_PATH not set"
fi

if [ -z "$MCP_SERVER_PATH" ]; then
    echo "Warning: MCP_SERVER_PATH not set"
fi

echo "Pre-install checks passed."

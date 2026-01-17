#!/bin/bash
# Post-installation setup for Floor Manager skill

set -e

echo "=== Floor Manager Post-Install Setup ==="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Create handoff directory
mkdir -p "$PROJECT_ROOT/_handoff"

# Make scripts executable
chmod +x "$PROJECT_ROOT/scripts/"*.sh

echo "Post-install setup complete."
echo ""
echo "To start the Floor Manager:"
echo "  cd $PROJECT_ROOT && ./scripts/start_agent_hub.sh"

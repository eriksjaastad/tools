#!/bin/bash

# uninstall-hooks.sh
# Removes pre-commit hook from a project
# Usage: ./uninstall-hooks.sh [project-directory]

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get project directory (default to current directory)
PROJECT_DIR="${1:-.}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

echo "Uninstalling governance hooks from: $PROJECT_DIR"

# Check if it's a git repository
if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo -e "${RED}Error: $PROJECT_DIR is not a git repository${NC}" >&2
    exit 1
fi

# Path to pre-commit hook
HOOK_FILE="$PROJECT_DIR/.git/hooks/pre-commit"

# Check if hook exists
if [ ! -f "$HOOK_FILE" ]; then
    echo -e "${YELLOW}No pre-commit hook found${NC}"
    exit 0
fi

# Check if it's our hook (contains "governance")
if grep -q "governance" "$HOOK_FILE" 2>/dev/null; then
    # Use trash if available, otherwise rm
    if command -v trash &> /dev/null; then
        trash "$HOOK_FILE"
        echo -e "${GREEN}✓ Pre-commit hook moved to trash${NC}"
    else
        rm "$HOOK_FILE"
        echo -e "${GREEN}✓ Pre-commit hook removed${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Pre-commit hook exists but doesn't appear to be a governance hook${NC}"
    echo "File: $HOOK_FILE"
    echo "Not removing it automatically. Please review and remove manually if needed."
    exit 1
fi

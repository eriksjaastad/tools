#!/bin/bash

# uninstall-hooks.sh
# Removes the governance pre-commit and pre-push hooks from a project
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

STATUS=0

# remove_hook <hook name> <marker>: remove the hook only when it carries the
# governance marker. pre-commit keeps the original loose "governance" marker so
# hooks installed by older versions are still recognized; pre-push (#7841) is
# matched on the exact installer line, since projects may have their own.
remove_hook() {
    local name="$1" marker="$2"
    local hook_file="$PROJECT_DIR/.git/hooks/$name"

    if [ ! -f "$hook_file" ]; then
        echo -e "${YELLOW}No $name hook found${NC}"
        return
    fi

    if grep -q "$marker" "$hook_file" 2>/dev/null; then
        # Use trash if available, otherwise rm
        if command -v trash &> /dev/null; then
            trash "$hook_file"
            echo -e "${GREEN}✓ $name hook moved to trash${NC}"
        else
            rm "$hook_file"
            echo -e "${GREEN}✓ $name hook removed${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ $name hook exists but doesn't appear to be a governance hook${NC}"
        echo "File: $hook_file"
        echo "Not removing it automatically. Please review and remove manually if needed."
        STATUS=1
    fi
}

remove_hook pre-commit "governance"
remove_hook pre-push "installed by governance system"
exit $STATUS

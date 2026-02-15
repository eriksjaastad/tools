#!/bin/bash

# install-hooks.sh
# Installs pre-commit hook that runs governance checks
# Usage: ./install-hooks.sh [project-directory]

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get the directory where this script is located
GOVERNANCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Get project directory (default to current directory)
PROJECT_DIR="${1:-.}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

echo "Installing governance hooks in: $PROJECT_DIR"

# Check if it's a git repository
if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo -e "${RED}Error: $PROJECT_DIR is not a git repository${NC}" >&2
    echo "Initialize git first: git init" >&2
    exit 1
fi

# Create hooks directory if it doesn't exist
HOOKS_DIR="$PROJECT_DIR/.git/hooks"
mkdir -p "$HOOKS_DIR"

# Path to pre-commit hook
HOOK_FILE="$HOOKS_DIR/pre-commit"

# Create the pre-commit hook (note: no quotes around EOF so $GOVERNANCE_DIR expands)
cat > "$HOOK_FILE" << EOF
#!/bin/bash
# Pre-commit hook installed by governance system
# Runs governance checks on staged files

# Path to governance-check.sh (set at install time)
GOVERNANCE_CHECK="$GOVERNANCE_DIR/governance-check.sh"

if [ ! -f "\$GOVERNANCE_CHECK" ]; then
    echo "Error: governance-check.sh not found at \$GOVERNANCE_CHECK" >&2
    exit 1
fi

# Run governance checks
exec "\$GOVERNANCE_CHECK"
EOF

# Make the hook executable
chmod +x "$HOOK_FILE"

echo -e "${GREEN}✓ Pre-commit hook installed successfully!${NC}"
echo ""
echo "The hook will run the following validators on each commit:"
echo "  - secrets-scanner.py (blocks API keys and secrets)"
echo "  - absolute-path-check.py (blocks hardcoded absolute paths)"
echo "  - agent-sync (ensures AGENTS.md, .cursorrules, CLAUDE.md stay in sync)"
echo ""
echo "Governance directory: $GOVERNANCE_DIR"
echo "Hook installed at: $HOOK_FILE"

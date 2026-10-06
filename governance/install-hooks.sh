#!/bin/bash

# install-hooks.sh
# Installs the pre-commit hook and the pre-push backstop that run governance checks
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

# With core.hooksPath set (locally, or globally as on these machines), Git
# never runs .git/hooks, so an install there would do nothing. This installer
# owns only .git/hooks: it refuses, writes nothing, and makes no claim about the
# hooks it does not own; that directory's owner wires the checks in. `git
# config` exits 1 when unset; any other failure is an error, not "unset".
set +e
ACTIVE_HOOKS="$(git -C "$PROJECT_DIR" config --type=path --get core.hooksPath)"
CONFIG_STATUS=$?
set -e
if [ $CONFIG_STATUS -ne 0 ] && [ $CONFIG_STATUS -ne 1 ]; then
    echo -e "${RED}Error: could not read core.hooksPath (git config exit $CONFIG_STATUS)${NC}" >&2
    exit 1
fi
if [ -n "$ACTIVE_HOOKS" ]; then
    echo -e "${RED}Not installed: core.hooksPath is set to $ACTIVE_HOOKS, so Git ignores .git/hooks here.${NC}" >&2
    echo "Nothing was written. The hooks in that directory must run the checks themselves" >&2
    echo "(a change for that directory's owner):" >&2
    echo "  pre-commit: bash \"$GOVERNANCE_DIR/governance-check.sh\"" >&2
    echo "  pre-push:   \"\$HOME/.local/bin/uv\" run --no-project \"$GOVERNANCE_DIR/push-range-check.py\" \"\$@\"" >&2
    exit 1
fi

# Create hooks directory if it doesn't exist
HOOKS_DIR="$PROJECT_DIR/.git/hooks"
mkdir -p "$HOOKS_DIR"

# Path to pre-commit hook
HOOK_FILE="$HOOKS_DIR/pre-commit"
PUSH_HOOK_FILE="$HOOKS_DIR/pre-push"

# A project's own pre-push hook is never overwritten. Refuse before writing
# anything, so a refused install leaves no half-installed governance hooks.
if [ -e "$PUSH_HOOK_FILE" ] && ! grep -q "installed by governance system" "$PUSH_HOOK_FILE" 2>/dev/null; then
    echo -e "${RED}Error: $PUSH_HOOK_FILE exists and is not a governance hook${NC}" >&2
    echo "Merge the governance push check into it by hand, then re-run:" >&2
    echo "  \"\$HOME/.local/bin/uv\" run --no-project \"$GOVERNANCE_DIR/push-range-check.py\" \"\$@\"" >&2
    exit 1
fi

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

# Create the pre-push backstop (#7841): checks every commit the push would
# publish, including cherry-picks, rebase replays and --no-verify commits that
# pre-commit never saw. Git's ref lines arrive on stdin and pass through exec.
cat > "$PUSH_HOOK_FILE" << EOF
#!/bin/bash
# Pre-push hook installed by governance system
# Runs governance checks on every commit the push would publish

PUSH_CHECK="$GOVERNANCE_DIR/push-range-check.py"

if [ ! -f "\$PUSH_CHECK" ]; then
    echo "Error: push-range-check.py not found at \$PUSH_CHECK" >&2
    exit 1
fi

exec "\$HOME/.local/bin/uv" run --no-project "\$PUSH_CHECK" "\$@"
EOF

chmod +x "$PUSH_HOOK_FILE"

echo -e "${GREEN}✓ Pre-commit hook installed successfully!${NC}"
echo -e "${GREEN}✓ Pre-push hook installed successfully!${NC}"
echo ""
echo "The hook will run the following validators on each commit:"
echo "  - secrets-scanner.py (blocks API keys and secrets)"
echo "  - absolute-path-check.py (blocks hardcoded absolute paths)"
echo "  - api-wrapper-check.py (blocks raw API calls that bypass cost tracking)"
echo ""
echo "CLAUDE.md/AGENTS.md sync is NOT a commit hook. agent-runtime-config's"
echo "runtime-doctor generates the AGENTS.md mirror, and 'runtime-doctor monitor'"
echo "reports drift."
echo ""
echo "Governance directory: $GOVERNANCE_DIR"
echo "Hooks installed at: $HOOK_FILE and $PUSH_HOOK_FILE"

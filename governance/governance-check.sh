#!/bin/bash

# governance-check.sh
# Master script that runs all validators on staged files
# Exit codes:
#   0: All validators passed
#   1: One or more validators failed

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATORS_DIR="$SCRIPT_DIR/validators"

# Check if uv is available
if ! command -v "$HOME/.local/bin/uv" &> /dev/null; then
    echo -e "${RED}Error: uv not found at $HOME/.local/bin/uv${NC}" >&2
    echo "Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

# Get list of staged files
# If files are passed as arguments, use those; otherwise get from git
if [ $# -gt 0 ]; then
    STAGED_FILES=("$@")
else
    # Get staged files from git (compatible with older bash)
    STAGED_FILES=()
    while IFS= read -r file; do
        STAGED_FILES+=("$file")
    done < <(git diff --cached --name-only --diff-filter=ACM)
fi

# Exit early if no files to check
if [ ${#STAGED_FILES[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ No files to check${NC}"
    exit 0
fi

echo -e "${YELLOW}Checking ${#STAGED_FILES[@]} file(s)...${NC}"

# Track overall pass/fail
OVERALL_STATUS=0

# Array of validators to run
VALIDATORS=(
    "secrets-scanner.py"
    "absolute-path-check.py"
)

# Run each validator
for validator in "${VALIDATORS[@]}"; do
    VALIDATOR_PATH="$VALIDATORS_DIR/$validator"
    
    if [ ! -f "$VALIDATOR_PATH" ]; then
        echo -e "${YELLOW}⚠ Validator not found: $validator (skipping)${NC}"
        continue
    fi
    
    echo -n "Running $validator... "
    
    # Run validator with uv, passing all staged files
    if "$HOME/.local/bin/uv" run "$VALIDATOR_PATH" "${STAGED_FILES[@]}" 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
    else
        VALIDATOR_EXIT_CODE=$?
        echo -e "${RED}✗ FAIL${NC}"
        OVERALL_STATUS=1
        
        # The validator should have already printed error details to stderr
        echo -e "${RED}Validator $validator failed with exit code $VALIDATOR_EXIT_CODE${NC}" >&2
    fi
done

# Summary
echo ""
if [ $OVERALL_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ All governance checks passed${NC}"
else
    echo -e "${RED}✗ Governance checks failed - commit blocked${NC}" >&2
fi

exit $OVERALL_STATUS

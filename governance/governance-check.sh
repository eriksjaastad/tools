#!/bin/bash

# governance-check.sh
# Runs every validator in VALIDATORS on the staged files (what pre-commit
# does), or with file arguments on those paths. The whole-file validators
# read the files on disk; source-deletion-check.py and silent-failure-check.py
# always check staged changes only, so for them the arguments just narrow
# that set (source-deletion-check.py matches only repository-relative paths).
# The global pre-commit and pre-merge-commit hooks call it (wiring:
# governance/README.md); push-range-check.py runs these validators per
# commit at pre-push, from its own FILE_VALIDATORS and COMMIT_VALIDATORS.
# Exit codes:
#   0: All validators passed
#   1: One or more validators failed
#
# Secrets are checked by gitleaks, the standard scanner (#8363), with the shared
# governance/gitleaks.toml over the same staged files; it judges a value by how
# it is used (an assignment's name, a known token prefix), not by its shape.
# Without gitleaks the check fails: install it with `brew install gitleaks`.
#
# Adding a validator: list it in VALIDATORS below, with any extra arguments
# in validator_args, and in push-range-check.py, under FILE_VALIDATORS (called
# with file paths) or COMMIT_VALIDATORS (called with --commit SHA).
# push-range-check.py runs it with its own Python, so use the standard
# library only. This script runs each as `uv run --no-project` from the repository
# being committed, so uv never creates or syncs that repository's .venv
# (#7647).

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
    STAGED_LIST=$(mktemp)
    trap 'rm -f "$STAGED_LIST"' EXIT
    if ! git diff --cached --name-only -z --diff-filter=ACMRT > "$STAGED_LIST"; then
        echo "Error: could not discover staged files" >&2
        exit 1
    fi
    STAGED_FILES=()
    while IFS= read -r -d '' file; do
        STAGED_FILES+=("$file")
    done < "$STAGED_LIST"
fi

# Exit early if no files to check
if [ ${#STAGED_FILES[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ No files to check${NC}"
    exit 0
fi

echo -e "${YELLOW}Checking ${#STAGED_FILES[@]} file(s)...${NC}"

# Track overall pass/fail
OVERALL_STATUS=0

# absolute-path-check.py judges files against the STAGED .absolute-path-ignore
# (empty when none is staged), as push-range-check.py passes each pushed
# commit's own copy, so both gates read the list being committed. Only a
# regular file is a list; push-range-check.py refuses anything else too.
IGNORE_LIST=$(mktemp)
trap 'rm -f "${STAGED_LIST:-}" "$IGNORE_LIST"' EXIT
IGNORE_ENTRY=$(git ls-files -s -- ".absolute-path-ignore")
case "$IGNORE_ENTRY" in
    "") ;;
    100644*$'\t'.absolute-path-ignore|100755*$'\t'.absolute-path-ignore)
        git cat-file blob ":.absolute-path-ignore" > "$IGNORE_LIST" ;;
    *)
        echo -e "${RED}.absolute-path-ignore must be a regular file${NC}" >&2
        exit 1 ;;
esac

# Secrets: gitleaks over the staged files, linked under their repository-relative
# names (read from disk, like the whole-file validators). Its .gitleaksignore is
# read from this directory, never from the repository, so a repo cannot add one.
echo -n "Running gitleaks... "
if ! command -v gitleaks >/dev/null 2>&1; then
    echo -e "${RED}✗ FAIL${NC}"
    echo -e "${RED}gitleaks is not installed (brew install gitleaks); secrets cannot be checked${NC}" >&2
    OVERALL_STATUS=1
else
    SECRETS_DIR=$(mktemp -d)
    trap 'rm -rf "${STAGED_LIST:-}" "$IGNORE_LIST" "$SECRETS_DIR"' EXIT
    for f in "${STAGED_FILES[@]}"; do
        [ -f "$f" ] || continue
        case "$f" in /*) src="$f" ;; *) src="$PWD/$f" ;; esac
        mkdir -p "$SECRETS_DIR/$(dirname "$f")"
        ln -s "$src" "$SECRETS_DIR/$f"
    done
    if gitleaks dir "$SECRETS_DIR" --follow-symlinks --config "$SCRIPT_DIR/gitleaks.toml" \
            --gitleaks-ignore-path "$SCRIPT_DIR" --no-banner --redact --verbose --log-level warn 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo -e "${RED}gitleaks found a likely secret (value redacted above)${NC}" >&2
        OVERALL_STATUS=1
    fi
fi

# Array of validators to run
VALIDATORS=(
    "absolute-path-check.py"
    "api-wrapper-check.py"
    "source-deletion-check.py"
    "silent-failure-check.py"
)

# Extra arguments for validators that need them. silent-failure-check.py
# checks only added or edited lines of the staged blobs (#6900): existing
# findings on untouched lines are the portfolio remediation backlog, not a
# reason to block an unrelated commit.
validator_args() {
    case "$1" in
        silent-failure-check.py) echo "--staged" ;;
        absolute-path-check.py) echo "--ignore-file $IGNORE_LIST" ;;
    esac
}

# Ecosystem-level validators (not file-based). Empty since 2026-09-01.
#
# "agent-sync" was removed (#6681). It pointed at a sync script that never
# existed. Every
# commit that staged an AGENTS.md printed a yellow "Skipped (sync script
# not found...)" and left OVERALL_STATUS untouched, so the run still ended
# "All governance checks passed". The auto-generation everyone believed was
# running had never run once, and that is why AGENTS.md files were expected
# to appear automatically and never did.
#
# It is deleted rather than repaired because its trigger was also backwards:
# it fired on staged AGENTS.md and called that "the source of truth", but
# AGENTS.md was then the GENERATED side and CLAUDE.md the source.
# Regenerating from the output would have been worse than doing nothing.
#
# Since agent-runtime-config #8283 (2026-10-14) there is nothing to sync:
# AGENTS.md is each project's one instructions file and CLAUDE.md a symlink
# to it. instruction-writer refreshes its shared blocks, and
# 'runtime-doctor monitor' reports a broken layout.
ECOSYSTEM_VALIDATORS=()

# Run each validator
for validator in "${VALIDATORS[@]}"; do
    VALIDATOR_PATH="$VALIDATORS_DIR/$validator"
    
    if [ ! -f "$VALIDATOR_PATH" ]; then
        echo -e "${RED}Validator not found: $validator${NC}" >&2
        OVERALL_STATUS=1
        continue
    fi
    
    echo -n "Running $validator... "
    
    # Run validator with uv, passing all staged files. --no-project keeps uv
    # from treating the repo being committed as the project: without it, a
    # validator lacking a PEP 723 block made uv create or sync that repo's
    # .venv, which then shadowed the real interpreter in fresh worktrees (#7647).
    # Unquoted on purpose: validator_args prints zero or more plain flags.
    # shellcheck disable=SC2046
    if "$HOME/.local/bin/uv" run --no-project "$VALIDATOR_PATH" $(validator_args "$validator") "${STAGED_FILES[@]}" 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
    else
        VALIDATOR_EXIT_CODE=$?
        echo -e "${RED}✗ FAIL${NC}"
        OVERALL_STATUS=1
        
        # The validator should have already printed error details to stderr
        echo -e "${RED}Validator $validator failed with exit code $VALIDATOR_EXIT_CODE${NC}" >&2
    fi
done

# Run ecosystem-level validators (not file-based).
# None are currently defined. The loop is kept so adding one is a one-line
# change to ECOSYSTEM_VALIDATORS above; the length guard is required because
# `set -u` treats "${ARR[@]}" on an empty array as an unbound variable on
# bash 3.2 (macOS system bash), which printed an error on every commit.
if [ ${#ECOSYSTEM_VALIDATORS[@]} -gt 0 ]; then
    for validator in "${ECOSYSTEM_VALIDATORS[@]}"; do
        case "$validator" in
            *)
                echo -e "${YELLOW}⚠ Unknown ecosystem validator: $validator${NC}" >&2
                OVERALL_STATUS=1
                ;;
        esac
    done
fi

# Summary
echo ""
if [ $OVERALL_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ All governance checks passed${NC}"
else
    echo -e "${RED}✗ Governance checks failed - commit blocked${NC}" >&2
fi

exit $OVERALL_STATUS

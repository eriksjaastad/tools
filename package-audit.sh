#!/bin/bash
set -euo pipefail

# package-audit.sh — Safe wrapper for pip install / uv add
#
# Checks requested packages against banned-packages.txt before installing.
# Usage:
#   package-audit.sh pip install <packages...>
#   package-audit.sh uv add <packages...>
#   package-audit.sh uv pip install <packages...>

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BANNED_FILE="$SCRIPT_DIR/banned-packages.txt"

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

if [[ $# -lt 2 ]]; then
    echo -e "${RED}Usage: package-audit.sh <pip|uv> <install|add|pip install> [packages...]${NC}" >&2
    exit 1
fi

if [[ ! -f "$BANNED_FILE" ]]; then
    echo -e "${YELLOW}WARNING: banned-packages.txt not found at $BANNED_FILE${NC}" >&2
    echo -e "${YELLOW}Proceeding without ban check.${NC}" >&2
    exec "$@"
fi

# Extract package names from command args (skip flags like -r, --upgrade, etc.)
extract_packages() {
    local skip_next=false
    for arg in "$@"; do
        if $skip_next; then
            skip_next=false
            continue
        fi
        case "$arg" in
            -r|--requirement|-c|--constraint|-e|--editable|-i|--index-url|--extra-index-url|--find-links|-t|--target|--prefix)
                skip_next=true
                continue
                ;;
            -*)
                continue
                ;;
            *)
                echo "$arg" | sed 's/[><=!].*//' | tr '[:upper:]' '[:lower:]'
                ;;
        esac
    done
}

# Check if a package name appears in the banned list
# Returns the matching line from banned-packages.txt, or empty string
check_banned() {
    local pkg_name="$1"
    while IFS= read -r line; do
        # Skip comments and blank lines
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

        # Extract just the package name portion (before version specifiers and comments)
        local entry_spec="${line%%#*}"
        entry_spec="$(echo "$entry_spec" | xargs)"
        [[ -z "$entry_spec" ]] && continue

        local entry_name
        entry_name="$(echo "$entry_spec" | sed 's/[><=!].*//' | tr '[:upper:]' '[:lower:]')"

        if [[ "$pkg_name" == "$entry_name" ]]; then
            echo "$line"
            return 0
        fi
    done < "$BANNED_FILE"
    return 1
}

# Determine which args are packages (skip the command prefix like "pip install")
cmd_args=("$@")
pkg_start=0

case "${cmd_args[0]}" in
    pip|pip3)
        pkg_start=2
        ;;
    uv)
        case "${cmd_args[1]}" in
            add)
                pkg_start=2
                ;;
            pip)
                pkg_start=3
                ;;
            *)
                echo -e "${RED}Unsupported uv subcommand: ${cmd_args[1]}${NC}" >&2
                exit 1
                ;;
        esac
        ;;
    *)
        echo -e "${RED}Unsupported package manager: ${cmd_args[0]}${NC}" >&2
        exit 1
        ;;
esac

packages=($(extract_packages "${cmd_args[@]:$pkg_start}"))

if [[ ${#packages[@]} -eq 0 ]]; then
    echo -e "${YELLOW}No packages detected in arguments. Passing through.${NC}" >&2
    exec "$@"
fi

# Check each package against banned list
blocked_count=0
for pkg in "${packages[@]}"; do
    ban_line="$(check_banned "$pkg" || true)"
    if [[ -n "$ban_line" ]]; then
        if [[ $blocked_count -eq 0 ]]; then
            echo "" >&2
            echo -e "${RED}========================================${NC}" >&2
            echo -e "${RED}  BLOCKED: Banned package(s) detected   ${NC}" >&2
            echo -e "${RED}========================================${NC}" >&2
            echo "" >&2
        fi
        echo -e "${RED}  $ban_line${NC}" >&2
        echo "" >&2
        blocked_count=$((blocked_count + 1))
    fi
done

if [[ $blocked_count -gt 0 ]]; then
    echo -e "${RED}Install aborted. Edit $BANNED_FILE to update the ban list.${NC}" >&2
    exit 1
fi

# Warn if no lockfile present in current directory
if [[ ! -f "uv.lock" && ! -f "poetry.lock" && ! -f "Pipfile.lock" && ! -f "requirements.txt" ]]; then
    echo -e "${YELLOW}WARNING: No lockfile found in $(pwd).${NC}" >&2
    echo -e "${YELLOW}Consider using 'uv lock' or pinning versions to ensure reproducible builds.${NC}" >&2
fi

echo -e "${GREEN}Package audit passed. Proceeding with install...${NC}" >&2
exec "$@"

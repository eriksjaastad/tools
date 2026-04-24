#!/usr/bin/env bash
# set-repo-bot-identity — configure the current git repo to commit AND push
# as a bot without needing the `gha -- git` wrapper.
#
# Writes three repo-local settings to .git/config:
#   user.name           — the bot's login with [bot] suffix
#   user.email          — <numeric-user-id>+<botname>@users.noreply.github.com
#   credential.helper   — shell function that mints a fresh bot token per
#                         git network operation (push/fetch/clone).
#
# Usage (from inside a git repo):
#   ./set-repo-bot-identity.sh architect     # cross-repo role
#   ./set-repo-bot-identity.sh manager       # project-scoped role (most repos)
#   ./set-repo-bot-identity.sh auxesis-coder # autonomous API code-dev (restricted)
#
# After this runs, plain `git commit` + `git push` work as the bot on this
# machine. No `gha -- git` wrapping needed. `gha` remains the right wrapper
# for gh operations (`gha pr create`, etc.).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOKEN_SCRIPT="$SCRIPT_DIR/github-app-token.py"

if [[ ! -f "$TOKEN_SCRIPT" ]]; then
    echo "Error: token generator not found at $TOKEN_SCRIPT" >&2
    exit 1
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "Error: not inside a git repo (cd into the repo first)" >&2
    exit 1
fi

IDENTITY="${1:-}"

if [[ -z "$IDENTITY" ]]; then
    echo "Usage: $(basename "$0") <identity>" >&2
    echo "" >&2
    echo "Canonical identities (2026-04-24):" >&2
    echo "  architect     — cross-repo planning/review" >&2
    echo "  auxesis-coder — autonomous API code-dev (explicit only, scope-restricted)" >&2
    echo "  manager       — project-scoped execution" >&2
    echo "" >&2
    echo "Legacy identities are still accepted until Phase G cleanup." >&2
    exit 1
fi

# Resolve bot display name and email via the token script.
BOTNAME=$(uv run --with PyJWT --with cryptography "$TOKEN_SCRIPT" "$IDENTITY" --botname)
EMAIL=$(uv run --with PyJWT --with cryptography "$TOKEN_SCRIPT" "$IDENTITY" --email)

if [[ -z "$BOTNAME" || -z "$EMAIL" ]]; then
    echo "Error: failed to resolve botname or email for identity '$IDENTITY'." >&2
    exit 1
fi

# The credential helper runs fresh per git network op. It invokes the token
# script with the identity baked in at setup time so push/fetch never need
# GH_TOKEN in the environment.
HELPER="!f() { echo username=x-access-token; echo \"password=\$(uv run --with PyJWT --with cryptography $TOKEN_SCRIPT $IDENTITY)\"; }; f"

git config --local user.name "$BOTNAME"
git config --local user.email "$EMAIL"

# Reset credential.helper list then add ours. The empty-string entry tells git
# to clear any inherited helpers (e.g. system-wide osxkeychain from Xcode's
# git-core/gitconfig) — without this, osxkeychain answers first with Erik's
# cached personal credentials, and our bot helper never runs at push time.
git config --local --unset-all credential.helper || true
git config --local --add credential.helper ""
git config --local --add credential.helper "$HELPER"

REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
echo "✓ ${REPO_NAME}: identity set to ${BOTNAME}"
echo "   user.email         = ${EMAIL}"
echo "   credential.helper  = <shell function that mints fresh bot token per call>"

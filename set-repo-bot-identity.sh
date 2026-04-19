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
#   ./set-repo-bot-identity.sh                    # auto-detect identity from cwd
#   ./set-repo-bot-identity.sh project-tracker    # explicit identity
#   ./set-repo-bot-identity.sh claude             # for ~/.claude/ and similar
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
    echo "Valid identities (per IDENTITY_MAP in github-app-token.py):" >&2
    echo "  claude, gemini, codex," >&2
    echo "  ai-memory, smart-invoice-workflow, hypocrisynow," >&2
    echo "  project-tracker, tax-organizer, _tools, muffinpanrecipes," >&2
    echo "  synth-insight-labs, cortana-personal-ai" >&2
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
git config --local credential.helper "$HELPER"

REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
echo "✓ ${REPO_NAME}: identity set to ${BOTNAME}"
echo "   user.email         = ${EMAIL}"
echo "   credential.helper  = <shell function that mints fresh bot token per call>"

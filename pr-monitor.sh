#!/bin/bash
# pr-monitor.sh — check all open PRs for failed reviews, alert on Slack if found
# Authenticates as Architect[bot] (cross-repo monitoring is an Architect role)

REPO="eriksjaastad/data-vault-factory"
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"

# Get a fresh GitHub App token
GH_TOKEN=$(uv run --with PyJWT --with cryptography "$TOOLS_DIR/github-app-token.py" architect 2>/dev/null)
if [ -z "$GH_TOKEN" ]; then
  # Fallback to default gh auth if app token fails
  unset GH_TOKEN
fi

export GH_TOKEN

open_prs=$(gh pr list --repo $REPO --json number,title --jq '.[].number' 2>/dev/null)

for pr in $open_prs; do
  status=$(gh pr checks $pr --repo $REPO 2>&1)
  if echo "$status" | grep -q "fail"; then
    title=$(gh pr view $pr --repo $REPO --json title --jq '.title' 2>/dev/null)
    echo "🚨 PR #$pr failed auto-review: \"$title\"" >&2
  fi
done

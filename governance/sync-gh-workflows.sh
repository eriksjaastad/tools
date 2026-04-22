#!/usr/bin/env bash
# sync-gh-workflows.sh — install the canonical PR label workflow, remove
# obsolete claude-review wrappers, and handle the one scoped default-branch
# rename agreed on 2026-04-21.
#
# Usage:
#   sync-gh-workflows.sh --dry-run install-pr-label-check
#   sync-gh-workflows.sh --apply   install-pr-label-check
#   sync-gh-workflows.sh --apply   install-pr-label-check --all-active
#   sync-gh-workflows.sh --dry-run delete-dead-claude-review
#   sync-gh-workflows.sh --apply   delete-dead-claude-review ai-journal
#   sync-gh-workflows.sh --dry-run rename-default-branch
#
# Default mode is --dry-run. If no repos are provided, each action uses its
# canonical rollout target set.

set -euo pipefail

OWNER="eriksjaastad"
MODE="dry-run"
ACTION=""
USE_ALL_ACTIVE=0
ACTIVE_DAYS="${ACTIVE_DAYS:-30}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKFLOW_SOURCE="$SCRIPT_DIR/../.github/workflows/pr-label-check.yml"
WORKFLOW_PATH=".github/workflows/pr-label-check.yml"
DEAD_WRAPPER_PATH=".github/workflows/claude-review.yml"
DEAD_WRAPPER_REF="eriksjaastad/tools/.github/workflows/claude-review-reusable.yml@main"
FAILURES=0

PR_LABEL_ROLLOUT_REPOS=(
  "project-tracker"
  "tools"
  "claude-user-config"
  "auxesis"
  "mcp-trust-gateway"
  "ai-journal"
  "holoscape"
  "trading-copilot"
  "mcp-trust-scanner"
  "discovery-lab-v2"
  "mcp-trust-console"
  "ai-memory"
  "leadgen-data-products"
  "x402-gateway"
  "tollpath"
  "mcp-trust-registry"
  "mcp-trust-policy"
  "mcp-trust-platform"
  "auxesis-research-labs"
  "cortana-personal-ai"
  "muffinpanrecipes"
  "project-scaffolding"
  "Smart-Invoice-Follow-Up-Workflow"
  "Flo-Fi"
  "audit-agent"
  "hypocrisynow"
  "ai-memory-replay"
  "image-workflow"
  "analyze-youtube-videos"
  "tax-organizer"
  "model-updater"
)

DEAD_CLAUDE_REVIEW_REPOS=(
  "ai-journal"
  "ai-memory"
  "ai-memory-replay"
  "analyze-youtube-videos"
  "audit-agent"
  "cortana-personal-ai"
  "Flo-Fi"
  "holoscape"
  "hypocrisynow"
  "market-research"
  "model-updater"
  "muffinpanrecipes"
  "Portfolio-ai"
  "project-scaffolding"
  "project-tracker"
  "tax-organizer"
  "trading-copilot"
)

BRANCH_RENAMES=(
  "eriksjaastad:master:main"
)

usage() {
  local exit_code="${1:-1}"
  cat <<'EOF'
sync-gh-workflows.sh — install the canonical PR label workflow, remove
obsolete claude-review wrappers, and handle the scoped default-branch
rename agreed on 2026-04-21.

Usage:
  sync-gh-workflows.sh --dry-run install-pr-label-check
  sync-gh-workflows.sh --apply   install-pr-label-check
  sync-gh-workflows.sh --apply   install-pr-label-check --all-active
  sync-gh-workflows.sh --dry-run delete-dead-claude-review
  sync-gh-workflows.sh --apply   delete-dead-claude-review ai-journal
  sync-gh-workflows.sh --dry-run rename-default-branch

Actions:
  install-pr-label-check
  delete-dead-claude-review
  rename-default-branch

Flags:
  --dry-run      Report only (default)
  --apply        Make GitHub changes
  --all-active   For install-pr-label-check only, target non-archived repos
                 pushed within ACTIVE_DAYS (default 30) instead of the baked-in
                 2026-04-21 rollout list
EOF
  exit "$exit_code"
}

require_action() {
  case "$ACTION" in
    install-pr-label-check|delete-dead-claude-review|rename-default-branch) ;;
    *) echo "Error: missing or unknown action" >&2; usage ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="dry-run"; shift ;;
    --apply) MODE="apply"; shift ;;
    --all-active) USE_ALL_ACTIVE=1; shift ;;
    -h|--help) usage 0 ;;
    -*)
      echo "Unknown flag: $1" >&2
      usage
      ;;
    *)
      if [[ -z "$ACTION" ]]; then
        ACTION="$1"
      else
        TARGETS_INPUT="${TARGETS_INPUT:+$TARGETS_INPUT"$'\n'"}$1"
      fi
      shift
      ;;
  esac
done

require_action

if [[ "$ACTION" != "install-pr-label-check" && "$USE_ALL_ACTIVE" == "1" ]]; then
  echo "Error: --all-active is only valid for install-pr-label-check" >&2
  exit 1
fi

if [[ ! -f "$WORKFLOW_SOURCE" ]]; then
  echo "Error: canonical workflow source not found: $WORKFLOW_SOURCE" >&2
  exit 1
fi

WORKFLOW_SOURCE_B64="$(base64 < "$WORKFLOW_SOURCE" | tr -d '\n')"

get_active_repos() {
  gh repo list "$OWNER" --limit 100 --json name,pushedAt,isArchived | \
    "$HOME/.local/bin/uv" run python3 -c "
import sys, json
from datetime import datetime, timezone
days = $ACTIVE_DAYS
repos = json.load(sys.stdin)
now = datetime.now(timezone.utc)
out = []
for r in repos:
    if r.get('isArchived'):
        continue
    pushed = datetime.fromisoformat(r['pushedAt'].replace('Z', '+00:00'))
    if (now - pushed).days < days:
        out.append(r['name'])
print('\n'.join(out))
"
}

resolve_targets() {
  if [[ -n "${TARGETS_INPUT:-}" ]]; then
    printf '%s\n' "$TARGETS_INPUT"
    return
  fi

  case "$ACTION" in
    install-pr-label-check)
      if [[ "$USE_ALL_ACTIVE" == "1" ]]; then
        get_active_repos
      else
        printf '%s\n' "${PR_LABEL_ROLLOUT_REPOS[@]}"
      fi
      ;;
    delete-dead-claude-review)
      printf '%s\n' "${DEAD_CLAUDE_REVIEW_REPOS[@]}"
      ;;
    rename-default-branch)
      printf '%s\n' "${BRANCH_RENAMES[@]}"
      ;;
  esac
}

decode_base64() {
  local content="$1"
  local normalized
  normalized="$(printf '%s' "$content" | tr -d '\n')"
  printf '%s' "$normalized" | base64 -d 2>/dev/null || \
    printf '%s' "$normalized" | base64 -D 2>/dev/null
}

repo_json() {
  gh api "repos/$OWNER/$1" 2>/dev/null
}

run_standardize() {
  local repo="$1"
  if [[ "$MODE" == "dry-run" ]]; then
    echo "    - would run governance/standardize-gh-repo.sh --apply $repo"
    return
  fi

  if "$SCRIPT_DIR/standardize-gh-repo.sh" --apply "$repo"; then
    echo "    ✓ standardized repo settings"
  else
    echo "    ! failed to standardize repo settings"
    FAILURES=$((FAILURES + 1))
  fi
}

install_pr_label_check() {
  local repo="$1"
  local slug="$OWNER/$repo"
  local info default_branch file_json existing_b64 existing_sha cmd

  if ! info=$(repo_json "$repo"); then
    echo "[$repo] ERROR: cannot fetch repo"
    FAILURES=$((FAILURES + 1))
    return
  fi

  default_branch=$(echo "$info" | jq -r '.default_branch')
  existing_b64=""
  existing_sha=""

  if file_json=$(gh api "repos/$slug/contents/$WORKFLOW_PATH" 2>/dev/null); then
    existing_b64=$(echo "$file_json" | jq -r '.content // ""' | tr -d '\n')
    existing_sha=$(echo "$file_json" | jq -r '.sha // ""')
  fi

  if [[ "$existing_b64" == "$WORKFLOW_SOURCE_B64" ]]; then
    echo "[$repo] ✓ $WORKFLOW_PATH already canonical"
    return
  fi

  if [[ -n "$existing_sha" ]]; then
    echo "[$repo] update $WORKFLOW_PATH on $default_branch"
  else
    echo "[$repo] create $WORKFLOW_PATH on $default_branch"
  fi

  if [[ "$MODE" == "dry-run" ]]; then
    echo "    - would upsert canonical pr-label-check workflow"
    run_standardize "$repo"
    return
  fi

  cmd=(
    gh api -X PUT "repos/$slug/contents/$WORKFLOW_PATH"
    -f "message=Install pr-label-check workflow"
    -f "content=$WORKFLOW_SOURCE_B64"
    -f "branch=$default_branch"
  )
  if [[ -n "$existing_sha" ]]; then
    cmd+=(-f "sha=$existing_sha")
  fi

  if "${cmd[@]}" >/dev/null 2>&1; then
    echo "    ✓ workflow synced"
    run_standardize "$repo"
  else
    echo "    ! failed to sync workflow"
    FAILURES=$((FAILURES + 1))
  fi
}

delete_dead_claude_review() {
  local repo="$1"
  local slug="$OWNER/$repo"
  local info default_branch file_json existing_sha decoded

  if ! info=$(repo_json "$repo"); then
    echo "[$repo] ERROR: cannot fetch repo"
    FAILURES=$((FAILURES + 1))
    return
  fi

  default_branch=$(echo "$info" | jq -r '.default_branch')
  if ! file_json=$(gh api "repos/$slug/contents/$DEAD_WRAPPER_PATH" 2>/dev/null); then
    echo "[$repo] ✓ $DEAD_WRAPPER_PATH already absent"
    return
  fi

  existing_sha=$(echo "$file_json" | jq -r '.sha // ""')
  decoded="$(decode_base64 "$(echo "$file_json" | jq -r '.content // ""')")"
  if ! printf '%s' "$decoded" | grep -q "$DEAD_WRAPPER_REF"; then
    echo "[$repo] skip $DEAD_WRAPPER_PATH: file does not match dead wrapper signature"
    return
  fi

  echo "[$repo] delete $DEAD_WRAPPER_PATH from $default_branch"
  if [[ "$MODE" == "dry-run" ]]; then
    echo "    - would delete wrapper referencing $DEAD_WRAPPER_REF"
    return
  fi

  if gh api -X DELETE "repos/$slug/contents/$DEAD_WRAPPER_PATH" \
      -f "message=Delete dead claude-review wrapper" \
      -f "sha=$existing_sha" \
      -f "branch=$default_branch" >/dev/null 2>&1; then
    echo "    ✓ wrapper deleted"
  else
    echo "    ! failed to delete wrapper"
    FAILURES=$((FAILURES + 1))
  fi
}

rename_default_branch() {
  local spec="$1"
  local repo from_branch to_branch slug info current_default

  repo="${spec%%:*}"
  from_branch="${spec#*:}"
  to_branch="${from_branch#*:}"
  from_branch="${from_branch%%:*}"
  slug="$OWNER/$repo"

  if ! info=$(repo_json "$repo"); then
    echo "[$repo] ERROR: cannot fetch repo"
    FAILURES=$((FAILURES + 1))
    return
  fi

  current_default=$(echo "$info" | jq -r '.default_branch')
  if [[ "$current_default" == "$to_branch" ]]; then
    echo "[$repo] ✓ default branch already $to_branch"
    if [[ "$MODE" == "apply" ]]; then
      run_standardize "$repo"
    fi
    return
  fi

  if [[ "$current_default" != "$from_branch" ]]; then
    echo "[$repo] skip rename: expected default branch $from_branch but found $current_default"
    FAILURES=$((FAILURES + 1))
    return
  fi

  echo "[$repo] rename default branch $current_default -> $to_branch"
  if [[ "$MODE" == "dry-run" ]]; then
    echo "    - would rename branch $from_branch to $to_branch"
    run_standardize "$repo"
    return
  fi

  if ! gh api -X POST "repos/$slug/branches/$from_branch/rename" \
      -f "new_name=$to_branch" >/dev/null 2>&1; then
    echo "    ! failed to rename $from_branch to $to_branch"
    FAILURES=$((FAILURES + 1))
    return
  fi

  if ! gh api -X PATCH "repos/$slug" -f "default_branch=$to_branch" >/dev/null 2>&1; then
    echo "    ! branch renamed but failed to set default_branch pointer to $to_branch"
    FAILURES=$((FAILURES + 1))
    return
  fi
  echo "    ✓ branch renamed"
  run_standardize "$repo"
}

TARGETS="$(resolve_targets)"
TARGET_COUNT=$(printf '%s\n' "$TARGETS" | sed '/^$/d' | wc -l | tr -d ' ')

echo "=== sync-gh-workflows.sh ==="
echo "Mode:   $MODE"
echo "Action: $ACTION"
echo "Owner:  $OWNER"
echo "Repos:  $TARGET_COUNT"
echo ""

while IFS= read -r target; do
  [[ -z "$target" ]] && continue
  case "$ACTION" in
    install-pr-label-check) install_pr_label_check "$target" ;;
    delete-dead-claude-review) delete_dead_claude_review "$target" ;;
    rename-default-branch) rename_default_branch "$target" ;;
  esac
done <<< "$TARGETS"

echo ""
if [[ "$FAILURES" -gt 0 ]]; then
  echo "Done with $FAILURES failure(s)."
  exit 1
fi

echo "Done. Mode was: $MODE"

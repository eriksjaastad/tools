#!/usr/bin/env bash
# sync-gh-workflows.sh — remove obsolete claude-review wrappers and handle
# the one scoped default-branch rename agreed on 2026-04-21.
#
# Usage:
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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEAD_WRAPPER_PATH=".github/workflows/claude-review.yml"
DEAD_WRAPPER_REF="eriksjaastad/tools/.github/workflows/claude-review-reusable.yml@main"
FAILURES=0

DEAD_CLAUDE_REVIEW_REPOS=(
  "ai-journal"
  "ai-memory"
  "ai-memory-replay"
  "analyze-youtube-videos"
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
sync-gh-workflows.sh — remove obsolete claude-review wrappers and handle
the scoped default-branch rename agreed on 2026-04-21.

Usage:
  sync-gh-workflows.sh --dry-run delete-dead-claude-review
  sync-gh-workflows.sh --apply   delete-dead-claude-review ai-journal
  sync-gh-workflows.sh --dry-run rename-default-branch

Actions:
  delete-dead-claude-review
  rename-default-branch

Flags:
  --dry-run      Report only (default)
  --apply        Make GitHub changes
EOF
  exit "$exit_code"
}

require_action() {
  case "$ACTION" in
    delete-dead-claude-review|rename-default-branch) ;;
    *) echo "Error: missing or unknown action" >&2; usage ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="dry-run"; shift ;;
    --apply) MODE="apply"; shift ;;
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

ARCHIVED_QUERY_LIMIT=500

drop_archived_repos() {
  # Filter archived repos out of a baked-in list, on stdin, one name per line.
  #
  # The canonical arrays below are hand-maintained, and archiving a repo and
  # editing this script are two unrelated actions with different triggers -- so
  # the lists drift. The archived-repo filter prevents obsolete targets from
  # causing unnecessary writes or obscure errors.
  #
  # Every skip is LOGGED. A filter that silently shrinks a list is worse than
  # the stale list it replaces: the run looks clean and you never learn the
  # entry is dead.
  local names archived
  names="$(cat)"
  [[ -n "$names" ]] || return 0

  # Check gh's exit status explicitly. Swallowing it with `|| true` would make
  # "the query failed" and "nothing is archived" the same silent code path, so a
  # transient auth or network blip would disable this filter with no trace --
  # the run would look clean while writing to archived repos anyway.
  local repo_json
  if ! repo_json="$(gh repo list "$OWNER" --limit "$ARCHIVED_QUERY_LIMIT" \
      --json name,isArchived 2>/dev/null)"; then
    echo "WARNING: could not list repos for '$OWNER' -- archived filter DISABLED," >&2
    echo "         passing all targets through unfiltered. Writes to archived repos" >&2
    echo "         will fail individually rather than being skipped." >&2
    printf '%s\n' "$names"
    return 0
  fi

  # `gh repo list --limit N` truncates silently with nothing on stderr. If we got
  # exactly N back, repos beyond the cutoff are invisible and would be treated as
  # active. Say so rather than quietly returning a wrong answer.
  local repo_count
  repo_count="$(jq 'length' <<< "$repo_json")"
  if [[ "$repo_count" -ge "$ARCHIVED_QUERY_LIMIT" ]]; then
    echo "WARNING: repo list hit the --limit $ARCHIVED_QUERY_LIMIT ceiling; results may be" >&2
    echo "         truncated and archived repos past the cutoff will not be skipped." >&2
  fi

  archived="$(jq -r '.[] | select(.isArchived) | .name' <<< "$repo_json")"

  if [[ -z "$archived" ]]; then
    echo "note: no archived repos found for '$OWNER'; nothing filtered" >&2
    printf '%s\n' "$names"
    return 0
  fi

  local name
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    if grep -qxF "$name" <<< "$archived"; then
      echo "[$name] skip: archived, no write attempted" >&2
    else
      printf '%s\n' "$name"
    fi
  done <<< "$names"
}

resolve_targets() {
  if [[ -n "${TARGETS_INPUT:-}" ]]; then
    printf '%s\n' "$TARGETS_INPUT"
    return
  fi

  case "$ACTION" in
    delete-dead-claude-review)
      printf '%s\n' "${DEAD_CLAUDE_REVIEW_REPOS[@]}" | drop_archived_repos
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

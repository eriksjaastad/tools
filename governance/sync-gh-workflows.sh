#!/usr/bin/env bash
# sync-gh-workflows.sh — remove obsolete claude-review wrappers and handle
# the one scoped default-branch rename agreed on 2026-04-21.
#
# File mutations go through a branch-and-PR flow. This script never commits
# to a default branch: it creates a short-lived branch, changes the file
# there through the GitHub contents API, and opens a pull request.
#
# All GitHub operations use the `gha` personal-identity shim. `gha` clears
# inherited GH_TOKEN/GITHUB_TOKEN and uses Erik's personal `gh` login; bare
# `gh` would fall through to whatever token the environment carries.
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
SYNC_BRANCH="tools-sync/delete-dead-claude-review"
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
  delete-dead-claude-review   Open a branch+PR that deletes the dead wrapper
  rename-default-branch       Rename the scoped default branch (settings only)

Flags:
  --dry-run      Report only (default)
  --apply        Make GitHub changes (still always through a PR for file edits)

GitHub operations resolve the `gha` personal-identity shim from PATH.
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

# Resolve the managed identity shim before any GitHub call. Never fall back
# to bare `gh`: that would silently authenticate as whatever token the
# environment carries, which is the failure this shim exists to prevent.
resolve_gha() {
  if ! GHA=$(command -v gha); then
    echo "ERROR: 'gha' personal-identity shim not found on PATH." >&2
    echo "       Refusing to run GitHub operations without the managed identity." >&2
    exit 1
  fi
}
resolve_gha

gha_bounded() {
  python3 "$SCRIPT_DIR/gha-bounded.py" "${GHA_TIMEOUT_SECONDS:-20}" "$GHA" "$@"
}

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
  if ! repo_json="$(gha_bounded repo list "$OWNER" --limit "$ARCHIVED_QUERY_LIMIT" \
      --json name,isArchived 2>/dev/null)"; then
    echo "WARNING: could not list repos for '$OWNER' -- archived filter DISABLED," >&2
    echo "         passing all targets through unfiltered. Writes to archived repos" >&2
    echo "         will be skipped per-repo instead of being attempted." >&2
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
  gha_bounded api "repos/$OWNER/$1" 2>/dev/null
}

# A missing resource is expected on first run. Other API failures must never
# be reported as an already-absent file or branch.
api_get_optional() {
  local response
  if response=$(gha_bounded api "$1" 2>&1); then
    printf '%s' "$response"
    return 0
  fi
  if [[ "$response" == *"(HTTP 404)"* ]]; then
    return 4
  fi
  echo "GitHub lookup failed for $1: $response" >&2
  return 1
}

repo_archived() {
  # Print "true" only when the fetched repo JSON says so. A fetch failure or a
  # malformed payload is a failure, not an active repo: callers check the exit
  # status of the fetch itself before trusting this.
  jq -r '.archived // false' <<< "$1"
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

delete_file_on_branch() {
  # GitHub contents API DELETE scoped to a branch. $1 slug, $2 path, $3 sha, $4 branch.
  gha_bounded api -X DELETE "repos/$1/contents/$2" \
    -f "message=Delete dead claude-review wrapper" \
    -f "sha=$3" \
    -f "branch=$4" >/dev/null 2>&1
}

delete_dead_claude_review() {
  local repo="$1"
  local slug="$OWNER/$repo"
  local info default_branch archived file_json existing_sha encoded decoded
  local branch_file_json branch_sha branch_encoded branch_decoded ref_json default_ref default_sha
  local compare_json branch_has_deletion
  local pr_json pr_number pr_url

  if ! info=$(repo_json "$repo"); then
    echo "[$repo] ERROR: cannot fetch repo"
    FAILURES=$((FAILURES + 1))
    return
  fi

  if ! default_branch=$(jq -er '.default_branch | select(type == "string" and length > 0)' <<< "$info") || \
      ! archived=$(jq -r 'if (.archived | type) == "boolean" then .archived else error("missing archived flag") end' <<< "$info"); then
    echo "[$repo] ERROR: malformed repository metadata"
    FAILURES=$((FAILURES + 1))
    return
  fi
  if [[ "$archived" == "true" ]]; then
    echo "[$repo] skip: archived, no write attempted"
    return
  fi
  if [[ -z "$default_branch" || "$default_branch" == "null" ]]; then
    echo "[$repo] ERROR: repo has no default branch"
    FAILURES=$((FAILURES + 1))
    return
  fi

  if file_json=$(api_get_optional "repos/$slug/contents/$DEAD_WRAPPER_PATH?ref=$default_branch"); then
    :
  else
    local lookup_status=$?
    if [[ "$lookup_status" -eq 4 ]]; then
      echo "[$repo] ✓ $DEAD_WRAPPER_PATH already absent on $default_branch"
    else
      echo "[$repo] ERROR: cannot verify $DEAD_WRAPPER_PATH on $default_branch"
      FAILURES=$((FAILURES + 1))
    fi
    return
  fi

  if ! existing_sha=$(jq -er '.sha | select(type == "string" and length > 0)' <<< "$file_json") || \
      ! encoded=$(jq -er '.content | select(type == "string" and length > 0)' <<< "$file_json") || \
      ! decoded=$(decode_base64 "$encoded"); then
    echo "[$repo] ERROR: malformed wrapper response"
    FAILURES=$((FAILURES + 1))
    return
  fi
  if ! printf '%s' "$decoded" | grep -q "$DEAD_WRAPPER_REF"; then
    echo "[$repo] skip $DEAD_WRAPPER_PATH: file does not match dead wrapper signature"
    return
  fi

  echo "[$repo] plan: branch-and-PR delete of $DEAD_WRAPPER_PATH ($default_branch)"

  if [[ "$MODE" == "dry-run" ]]; then
    echo "    - would create branch $SYNC_BRANCH from $default_branch"
    echo "    - would delete wrapper via contents API on branch $SYNC_BRANCH"
    echo "    - would open PR $SYNC_BRANCH -> $default_branch"
    return
  fi

  # Idempotency gate 1: an open PR from our branch means the change is already
  # staged for review; do not create a second PR or rewrite the branch.
  if ! pr_json=$(gha_bounded pr list --repo "$slug" --head "$SYNC_BRANCH" --state open \
      --json number,url 2>/dev/null); then
    echo "    ! cannot list open PRs for branch $SYNC_BRANCH"
    FAILURES=$((FAILURES + 1))
    return
  fi
  if ! pr_number=$(jq -er 'if type == "array" then (.[0].number // "") else error("not an array") end' <<< "$pr_json"); then
    echo "    ! malformed open-PR response"
    FAILURES=$((FAILURES + 1))
    return
  fi
  if [[ -n "$pr_number" ]]; then
    echo "    ✓ PR already open: #$pr_number"
    return
  fi

  # Idempotency gate 2: reuse an existing branch from a previous interrupted
  # run. If the file is already gone on that branch, open the PR; otherwise
  # finish the deletion on the branch first.
  if ref_json=$(api_get_optional "repos/$slug/git/ref/heads/$SYNC_BRANCH"); then
    echo "    - branch $SYNC_BRANCH already exists; reusing"
    if ! compare_json=$(gha_bounded api "repos/$slug/compare/$default_branch...$SYNC_BRANCH" 2>/dev/null) || \
        ! jq -e --arg path "$DEAD_WRAPPER_PATH" \
          '(.files | type) == "array" and (.ahead_by | type) == "number" and
           .ahead_by <= 1 and all(.files[]; .filename == $path and .status == "removed")' \
          <<< "$compare_json" >/dev/null; then
      echo "    ! existing branch has unrelated or unverifiable changes; preserve it"
      FAILURES=$((FAILURES + 1))
      return
    fi
    branch_has_deletion=$(jq -r '[.files[] | select(.status == "removed")] | length' <<< "$compare_json")
    if branch_file_json=$(api_get_optional "repos/$slug/contents/$DEAD_WRAPPER_PATH?ref=$SYNC_BRANCH"); then
      if [[ "$branch_has_deletion" != "0" ]] || \
          ! branch_sha=$(jq -er '.sha | select(type == "string" and length > 0)' <<< "$branch_file_json") || \
          ! branch_encoded=$(jq -er '.content | select(type == "string" and length > 0)' <<< "$branch_file_json") || \
          ! branch_decoded=$(decode_base64 "$branch_encoded") || \
          ! printf '%s' "$branch_decoded" | grep -q "$DEAD_WRAPPER_REF"; then
        echo "    ! existing branch workflow differs from the dead wrapper; preserve it"
        FAILURES=$((FAILURES + 1))
        return
      fi
      if ! delete_file_on_branch "$slug" "$DEAD_WRAPPER_PATH" "$branch_sha" "$SYNC_BRANCH"; then
        echo "    ! failed to delete wrapper on existing branch $SYNC_BRANCH"
        FAILURES=$((FAILURES + 1))
        return
      fi
      echo "    ✓ wrapper deleted on existing branch $SYNC_BRANCH"
    else
      local branch_file_status=$?
      if [[ "$branch_file_status" -ne 4 || "$branch_has_deletion" != "1" ]]; then
        echo "    ! cannot verify wrapper on $SYNC_BRANCH"
        FAILURES=$((FAILURES + 1))
        return
      fi
      echo "    ✓ wrapper already absent on $SYNC_BRANCH"
    fi
  else
    local ref_status=$?
    if [[ "$ref_status" -ne 4 ]]; then
      echo "    ! cannot verify whether $SYNC_BRANCH exists"
      FAILURES=$((FAILURES + 1))
      return
    fi
    # Create the branch from the default branch's current head.
    if ! default_ref=$(gha_bounded api "repos/$slug/git/ref/heads/$default_branch" 2>/dev/null); then
      echo "    ! cannot resolve default branch ref $default_branch"
      FAILURES=$((FAILURES + 1))
      return
    fi
    default_sha=$(echo "$default_ref" | jq -r '.object.sha // ""')
    if [[ -z "$default_sha" ]]; then
      echo "    ! default branch ref has no sha"
      FAILURES=$((FAILURES + 1))
      return
    fi
    if ! gha_bounded api -X POST "repos/$slug/git/refs" \
        -f "ref=refs/heads/$SYNC_BRANCH" \
        -f "sha=$default_sha" >/dev/null 2>&1; then
      echo "    ! failed to create branch $SYNC_BRANCH"
      FAILURES=$((FAILURES + 1))
      return
    fi
    echo "    ✓ created branch $SYNC_BRANCH"

    if ! delete_file_on_branch "$slug" "$DEAD_WRAPPER_PATH" "$existing_sha" "$SYNC_BRANCH"; then
      echo "    ! failed to delete wrapper on branch $SYNC_BRANCH"
      FAILURES=$((FAILURES + 1))
      return
    fi
    echo "    ✓ wrapper deleted on branch $SYNC_BRANCH"
  fi

  if ! pr_url=$(gha_bounded pr create --repo "$slug" --head "$OWNER:$SYNC_BRANCH" \
      --base "$default_branch" \
      --title "Remove dead claude-review workflow" \
      --body "Deletes $DEAD_WRAPPER_PATH, which references the retired $DEAD_WRAPPER_REF reusable workflow.

Created by governance/sync-gh-workflows.sh (branch-and-PR sync)." 2>/dev/null); then
    echo "    ! branch updated but failed to open PR"
    FAILURES=$((FAILURES + 1))
    return
  fi
  echo "    ✓ PR opened: $pr_url"
}

rename_default_branch() {
  local spec="$1"
  local repo from_branch to_branch slug info current_default archived

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

  archived=$(repo_archived "$info")
  if [[ "$archived" == "true" ]]; then
    echo "[$repo] skip: archived, no write attempted"
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

  if ! gha_bounded api -X POST "repos/$slug/branches/$from_branch/rename" \
      -f "new_name=$to_branch" >/dev/null 2>&1; then
    echo "    ! failed to rename $from_branch to $to_branch"
    FAILURES=$((FAILURES + 1))
    return
  fi

  if ! gha_bounded api -X PATCH "repos/$slug" -f "default_branch=$to_branch" >/dev/null 2>&1; then
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
echo "GHA:    $GHA"
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

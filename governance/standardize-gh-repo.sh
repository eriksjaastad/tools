#!/usr/bin/env bash
# standardize-gh-repo.sh — enforce canonical GitHub repo settings across
# eriksjaastad/* repos. Codifies what the README claims is true everywhere
# but actually wasn't (e.g. delete_branch_on_merge was off on
# claude-user-config, surfaced after PR #8 in 2026-04-21).
#
# Canonical settings (agreed 2026-04-21):
#   delete_branch_on_merge = true
#   allow_squash_merge     = false   (overkill, we want preserved SHAs)
#   allow_merge_commit     = true    (default merge method)
#   allow_rebase_merge     = true
#   default_branch         = main
#   labels                 = canonical 11 (feature enhancement bug chore
#                            refactor docs test hotfix security perf ci)
#   branch protection on main (when missing):
#     - require PR before merge
#     - preserve any existing required checks and review settings
#
# All GitHub operations use the `gha` personal-identity shim. `gha` clears
# inherited GH_TOKEN/GITHUB_TOKEN and uses Erik's personal `gh` login.
#
# Usage:
#   standardize-gh-repo.sh --dry-run <repo>          # single repo, report only
#   standardize-gh-repo.sh --apply   <repo>          # single repo, make changes
#   standardize-gh-repo.sh --dry-run --all-active    # all repos pushed <30d
#   standardize-gh-repo.sh --apply   --all-active    # apply across all active
#
# Default mode is --dry-run if neither flag given. Never makes a change
# without --apply.

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# NOTE: -e omitted intentionally — per-repo gha api calls can fail on edge
# cases (empty repos, missing main, permissions) and we want to skip the
# bad repo and continue, not abort the entire sweep. Failures are counted
# and reported; --apply exits nonzero if any write fails.

OWNER="eriksjaastad"
MODE="dry-run"
TARGET=""
ACTIVE_DAYS="${ACTIVE_DAYS:-30}"
APPLY_FAILURES=0

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

CANONICAL_LABELS=(
  "feature:#5319E7"
  "enhancement:#a2eeef"
  "bug:#d73a4a"
  "chore:#C2E0C6"
  "refactor:#006B75"
  "docs:#5319E7"
  "test:#D93F0B"
  "hotfix:#D93F0B"
  "security:#E99695"
  "perf:#F9D0C4"
  "ci:#1D76DB"
)

usage() {
  sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="dry-run"; shift ;;
    --apply)   MODE="apply"; shift ;;
    --all-active) TARGET="__all__"; shift ;;
    -h|--help) usage ;;
    -*) echo "Unknown flag: $1" >&2; usage ;;
    *)  TARGET="$1"; shift ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "Error: must specify <repo> or --all-active" >&2
  usage
fi

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

# Fetch repo list once. For --all-active, list active repos; for single, use as-is.
if [[ "$TARGET" == "__all__" ]]; then
  if ! REPOS=$(gha_bounded repo list "$OWNER" --limit 100 --json name,pushedAt,isArchived | \
    python3 -c "
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
print('\n'.join(sorted(out)))
"); then
    echo "ERROR: cannot list active repositories" >&2
    exit 1
  fi
else
  REPOS="$TARGET"
fi

REPO_COUNT=$(echo "$REPOS" | wc -l | tr -d ' ')
echo "=== standardize-gh-repo.sh ==="
echo "Mode:   $MODE"
echo "Owner:  $OWNER"
echo "GHA:    $GHA"
echo "Repos:  $REPO_COUNT"
echo ""

# ---------------------------------------------------------------------------
# Per-repo logic. Reports current vs canonical, applies if MODE=apply.
# ---------------------------------------------------------------------------

check_repo() {
  local repo="$1"
  local slug="$OWNER/$repo"
  local changes=()
  local failures_before="$APPLY_FAILURES"

  # 1. Fetch current settings.
  local settings
  if ! settings=$(gha_bounded api "repos/$slug" 2>/dev/null); then
    echo "[$repo] ERROR: cannot fetch repo (missing? no access?)"
    APPLY_FAILURES=$((APPLY_FAILURES + 1))
    return
  fi

  local cur_archived
  if ! cur_archived=$(jq -r 'if (.archived | type) == "boolean" then .archived else error("missing archived flag") end' <<< "$settings"); then
    echo "[$repo] ERROR: malformed repository metadata"
    APPLY_FAILURES=$((APPLY_FAILURES + 1))
    return
  fi
  if [[ "$cur_archived" == "true" ]]; then
    echo "[$repo] skip: archived, no write attempted"
    return
  fi

  local cur_delete cur_squash cur_merge cur_rebase cur_default cur_private
  cur_delete=$(echo "$settings" | jq -r '.delete_branch_on_merge')
  cur_squash=$(echo "$settings" | jq -r '.allow_squash_merge')
  cur_merge=$(echo "$settings" | jq -r '.allow_merge_commit')
  cur_rebase=$(echo "$settings" | jq -r '.allow_rebase_merge')
  cur_default=$(echo "$settings" | jq -r '.default_branch')
  cur_private=$(echo "$settings" | jq -r '.private')

  [[ "$cur_delete"  != "true"  ]] && changes+=("delete_branch_on_merge: $cur_delete -> true")
  [[ "$cur_squash"  != "false" ]] && changes+=("allow_squash_merge: $cur_squash -> false")
  [[ "$cur_merge"   != "true"  ]] && changes+=("allow_merge_commit: $cur_merge -> true")
  [[ "$cur_rebase"  != "true"  ]] && changes+=("allow_rebase_merge: $cur_rebase -> true")
  [[ "$cur_default" != "main"  ]] && changes+=("default_branch: $cur_default -> main (NOT auto-changed; manual)")

  # 2. Labels — ensure canonical 11 exist (don't delete others).
  local existing_labels
  local labels_readable=1
  if ! existing_labels=$(gha_bounded api "repos/$slug/labels" --paginate -q '.[].name' 2>/dev/null); then
    echo "    ! cannot list labels; skipping label enforcement"
    APPLY_FAILURES=$((APPLY_FAILURES + 1))
    existing_labels=""
    labels_readable=0
  fi
  local missing_labels=()
  if [[ "$labels_readable" == "1" ]]; then
    for entry in "${CANONICAL_LABELS[@]}"; do
      local name="${entry%%:*}"
      if ! echo "$existing_labels" | grep -qx "$name"; then
        missing_labels+=("$name")
      fi
    done
  fi
  if [[ ${#missing_labels[@]} -gt 0 ]]; then
    changes+=("missing labels: ${missing_labels[*]}")
  fi

  # 3. Branch protection on main — create only when absent. Existing protection
  # may require unrelated checks; never replace its status contexts or reviews.
  local has_main=""
  local protection_status="not-checked"
  # Branch protection requires a paid plan for private repos. Skip with
  # warning rather than failing apply — the repo-level settings (auto-delete,
  # merge methods, labels) still get applied.
  if [[ "$cur_private" == "true" ]]; then
    changes+=("WARNING: private repo — branch protection skipped (requires GitHub Pro)")
    has_main="none"
  else
    local main_response
    if main_response=$(api_get_optional "repos/$slug/branches/main"); then
      if ! has_main=$(jq -er '.name | select(type == "string")' <<< "$main_response"); then
        echo "    ! malformed main branch response"
        APPLY_FAILURES=$((APPLY_FAILURES + 1))
      fi
    else
      local main_status=$?
      if [[ "$main_status" -eq 4 ]]; then
        has_main="none"
      else
        echo "    ! cannot verify main branch"
        APPLY_FAILURES=$((APPLY_FAILURES + 1))
      fi
    fi
  fi
  if [[ "$has_main" == "main" ]]; then
    local current_protection
    if current_protection=$(api_get_optional "repos/$slug/branches/main/protection"); then
      if [[ "$current_protection" == "{}" ]]; then
        echo "    ! malformed branch protection response"
        APPLY_FAILURES=$((APPLY_FAILURES + 1))
        protection_status="unreadable"
      else
        protection_status="present"
      fi
    else
      local protection_read_status=$?
      if [[ "$protection_read_status" -eq 4 ]]; then
        protection_status="missing"
      else
        echo "    ! cannot read branch protection; skipping protection enforcement"
        APPLY_FAILURES=$((APPLY_FAILURES + 1))
        protection_status="unreadable"
      fi
    fi
    if [[ "$protection_status" == "missing" ]]; then
      changes+=("branch protection on main: NONE -> enforce")
    fi
  fi

  # 4. Report or apply.
  if [[ ${#changes[@]} -eq 0 ]]; then
    if [[ "$APPLY_FAILURES" -gt "$failures_before" ]]; then
      echo "[$repo] inspection incomplete"
    else
      echo "[$repo] ✓ already canonical"
    fi
    return
  fi

  echo "[$repo] $((${#changes[@]})) change(s):"
  for c in "${changes[@]}"; do
    echo "    - $c"
  done

  if [[ "$MODE" == "apply" ]]; then
    # Apply repo-level settings.
    if ! gha_bounded api -X PATCH "repos/$slug" \
      -f delete_branch_on_merge=true \
      -f allow_squash_merge=false \
      -f allow_merge_commit=true \
      -f allow_rebase_merge=true >/dev/null 2>&1; then
      echo "    ! failed to apply repo settings"
      APPLY_FAILURES=$((APPLY_FAILURES + 1))
    fi

    # Apply missing labels.
    if [[ "$labels_readable" == "1" ]]; then
      for entry in "${CANONICAL_LABELS[@]}"; do
        local name="${entry%%:*}"
        local color="${entry##*:#}"
        if ! echo "$existing_labels" | grep -qx "$name"; then
          if ! gha_bounded api "repos/$slug/labels" -f "name=$name" -f "color=$color" >/dev/null 2>&1; then
            echo "    ! failed to create label: $name"
            APPLY_FAILURES=$((APPLY_FAILURES + 1))
          fi
        fi
      done
    fi

    # Branch protection — only update if main exists and protection is missing.
    if [[ "$has_main" == "main" ]] && [[ "$protection_status" == "missing" ]]; then
      if ! gha_bounded api -X PUT "repos/$slug/branches/main/protection" \
        --input - >/dev/null 2>&1 <<EOF
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 0, "dismiss_stale_reviews": false, "require_code_owner_reviews": false },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": false
}
EOF
      then
        echo "    ! failed to set branch protection"
        APPLY_FAILURES=$((APPLY_FAILURES + 1))
      fi
    fi
    if [[ "$APPLY_FAILURES" -eq "$failures_before" ]]; then
      echo "    ✓ applied"
    else
      echo "    ! apply incomplete"
    fi
  fi
}

# Iterate.
for repo in $REPOS; do
  check_repo "$repo"
done

echo ""
echo "Done. Mode was: $MODE"
if [[ "$APPLY_FAILURES" -gt 0 ]]; then
  echo "$APPLY_FAILURES inspection/apply failure(s)."
  exit 1
fi
[[ "$MODE" == "dry-run" ]] && echo "Re-run with --apply to make changes."
exit 0

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
#   branch protection on main:
#     - require PR before merge
#     - require status checks: check-label (when the pr-label-check
#       workflow is wired up in the repo)
#     - no human-review requirement
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
# NOTE: -e omitted intentionally — per-repo gh api calls can fail on edge
# cases (empty repos, missing main, permissions) and we want to skip the
# bad repo and continue, not abort the entire sweep.

OWNER="eriksjaastad"
MODE="dry-run"
TARGET=""
ACTIVE_DAYS="${ACTIVE_DAYS:-30}"

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

REQUIRED_CHECKS=("check-label")

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

# Fetch repo list once. For --all-active, list active repos; for single, use as-is.
if [[ "$TARGET" == "__all__" ]]; then
  REPOS=$(gh repo list "$OWNER" --limit 100 --json name,pushedAt,isArchived | \
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
print('\n'.join(sorted(out)))
")
else
  REPOS="$TARGET"
fi

REPO_COUNT=$(echo "$REPOS" | wc -l | tr -d ' ')
echo "=== standardize-gh-repo.sh ==="
echo "Mode:   $MODE"
echo "Owner:  $OWNER"
echo "Repos:  $REPO_COUNT"
echo ""

# ---------------------------------------------------------------------------
# Per-repo logic. Reports current vs canonical, applies if MODE=apply.
# ---------------------------------------------------------------------------

check_repo() {
  local repo="$1"
  local slug="$OWNER/$repo"
  local changes=()

  # 1. Fetch current settings.
  local settings
  if ! settings=$(gh api "repos/$slug" 2>/dev/null); then
    echo "[$repo] ERROR: cannot fetch repo (missing? no access?)"
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
  existing_labels=$(gh api "repos/$slug/labels" --paginate -q '.[].name' 2>/dev/null || echo "")
  local missing_labels=()
  for entry in "${CANONICAL_LABELS[@]}"; do
    local name="${entry%%:*}"
    if ! echo "$existing_labels" | grep -qx "$name"; then
      missing_labels+=("$name")
    fi
  done
  if [[ ${#missing_labels[@]} -gt 0 ]]; then
    changes+=("missing labels: ${missing_labels[*]}")
  fi

  # 3. Branch protection on main — only enforce if main exists.
  #
  # Detect which canonical checks are actually wired up in this repo's
  # workflows. We fetch each workflow file's content ONCE and grep all check
  # names against that single blob, instead of re-fetching per-check or
  # re-doing the whole detection in the apply phase. At 43 repos x ~5 workflows
  # x 2 check names x 2 phases (old shape), this was ~860 API calls per sweep
  # — enough to hit GitHub's 80 req/min secondary limit silently, since
  # errors were suppressed by 2>/dev/null.
  local -a workflow_paths=()
  while IFS= read -r p; do
    [[ -n "$p" ]] && workflow_paths+=("$p")
  done < <(gh api "repos/$slug/actions/workflows" -q '.workflows[].path' 2>/dev/null)

  local all_workflow_content=""
  if [[ ${#workflow_paths[@]} -gt 0 ]]; then
    for path in "${workflow_paths[@]}"; do
      local encoded
      encoded=$(gh api "repos/$slug/contents/$path" -q '.content // ""' 2>/dev/null || echo "")
      [[ -n "$encoded" ]] && all_workflow_content+=$'\n'$(echo "$encoded" | base64 -d 2>/dev/null || echo "")
    done
  fi

  # Build the list of REQUIRED_CHECKS that are actually referenced in workflow
  # files. Reused below for both the detection report and the apply payload.
  local -a PRESENT_CHECKS=()
  for chk in "${REQUIRED_CHECKS[@]}"; do
    if echo "$all_workflow_content" | grep -q "$chk"; then
      PRESENT_CHECKS+=("$chk")
    fi
  done

  if [[ ${#PRESENT_CHECKS[@]} -eq 0 ]]; then
    changes+=("WARNING: no check-label workflow installed — protection enforced with empty contexts; copy .github/workflows/pr-label-check.yml from the tools repo")
  fi

  local has_main
  has_main=$(gh api "repos/$slug/branches/main" 2>/dev/null | jq -r '.name // "none"')
  local protection_status="not-checked"
  # Branch protection requires a paid plan for private repos. Skip with
  # warning rather than failing apply — the repo-level settings (auto-delete,
  # merge methods, labels) still get applied.
  if [[ "$cur_private" == "true" ]]; then
    changes+=("WARNING: private repo — branch protection skipped (requires GitHub Pro)")
    has_main="none"
  fi
  if [[ "$has_main" == "main" ]]; then
    local current_protection
    current_protection=$(gh api "repos/$slug/branches/main/protection" 2>/dev/null || echo "{}")
    if [[ "$current_protection" == "{}" ]] || echo "$current_protection" | grep -q '"message":"Branch not protected"'; then
      changes+=("branch protection on main: NONE -> enforce")
      protection_status="missing"
    else
      # Compare required checks: what IS required vs what SHOULD be required
      # (PRESENT_CHECKS, already computed above).
      local cur_checks
      cur_checks=$(echo "$current_protection" | jq -r '.required_status_checks.contexts // [] | .[]' 2>/dev/null | sort -u)
      local needed_sorted=""
      [[ ${#PRESENT_CHECKS[@]} -gt 0 ]] && needed_sorted=$(printf '%s\n' "${PRESENT_CHECKS[@]}" | sort -u | xargs)
      local cur_sorted=""
      [[ -n "$cur_checks" ]] && cur_sorted=$(echo "$cur_checks" | xargs)
      if [[ "$needed_sorted" != "$cur_sorted" ]]; then
        changes+=("required checks on main: [$cur_sorted] -> [$needed_sorted]")
      fi
      protection_status="present"
    fi
  fi

  # 4. Report or apply.
  if [[ ${#changes[@]} -eq 0 ]]; then
    echo "[$repo] ✓ already canonical"
    return
  fi

  echo "[$repo] $((${#changes[@]})) change(s):"
  for c in "${changes[@]}"; do
    echo "    - $c"
  done

  if [[ "$MODE" == "apply" ]]; then
    # Apply repo-level settings.
    gh api -X PATCH "repos/$slug" \
      -f delete_branch_on_merge=true \
      -f allow_squash_merge=false \
      -f allow_merge_commit=true \
      -f allow_rebase_merge=true >/dev/null

    # Apply missing labels.
    for entry in "${CANONICAL_LABELS[@]}"; do
      local name="${entry%%:*}"
      local color="${entry##*:#}"
      if ! echo "$existing_labels" | grep -qx "$name"; then
        gh api "repos/$slug/labels" -f "name=$name" -f "color=$color" >/dev/null 2>&1 || \
          echo "    ! failed to create label: $name"
      fi
    done

    # Branch protection — only update if main exists.
    if [[ "$has_main" == "main" ]] && [[ "$protection_status" != "not-checked" ]]; then
      # Build the contexts list from PRESENT_CHECKS (already computed above
      # — no re-fetching of workflow content).
      local checks_payload="[]"
      if [[ ${#PRESENT_CHECKS[@]} -gt 0 ]]; then
        local -a quoted=()
        for chk in "${PRESENT_CHECKS[@]}"; do quoted+=("\"$chk\""); done
        local joined
        joined=$(IFS=,; echo "${quoted[*]}")
        checks_payload="[$joined]"
      fi

      gh api -X PUT "repos/$slug/branches/main/protection" \
        --input - <<EOF >/dev/null 2>&1 || echo "    ! failed to set branch protection"
{
  "required_status_checks": { "strict": false, "contexts": $checks_payload },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 0, "dismiss_stale_reviews": false, "require_code_owner_reviews": false },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": false
}
EOF
    fi
    echo "    ✓ applied"
  fi
}

# Iterate.
for repo in $REPOS; do
  check_repo "$repo"
done

echo ""
echo "Done. Mode was: $MODE"
[[ "$MODE" == "dry-run" ]] && echo "Re-run with --apply to make changes."

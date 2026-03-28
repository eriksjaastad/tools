#!/bin/bash
# morning-briefing.sh — Quick status of all projects across both machines
# Run: morning-briefing (after aliasing) or bash _tools/morning-briefing.sh

set -uo pipefail

PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/projects}"
MINI_HOST="eriksjaastad@eriks-mac-mini.local"
MINI_PROJECTS="$HOME/projects"
PT_CLI="$PROJECTS_ROOT/project-tracker/pt"
HOURS_RECENT=48

# Colors for terminal
BOLD="\033[1m"
DIM="\033[2m"
RED="\033[31m"
YELLOW="\033[33m"
GREEN="\033[32m"
CYAN="\033[36m"
RESET="\033[0m"

now_epoch=$(date +%s)
cutoff_epoch=$((now_epoch - HOURS_RECENT * 3600))

scan_projects() {
    local root="$1"
    local label="$2"
    local found=0

    for dir in "$root"/*/; do
        [ -d "$dir/.git" ] || continue
        project_name=$(basename "$dir")

        # Skip hidden/underscore dirs
        [[ "$project_name" == .* || "$project_name" == _* ]] && continue

        # Get last commit info
        last_commit_epoch=$(git -C "$dir" log -1 --format="%at" 2>/dev/null || echo "0")
        last_commit_rel=$(git -C "$dir" log -1 --format="%ar" 2>/dev/null || echo "unknown")
        last_commit_author=$(git -C "$dir" log -1 --format="%an" 2>/dev/null || echo "unknown")
        last_commit_msg=$(git -C "$dir" log -1 --format="%s" 2>/dev/null | cut -c1-60 || echo "")

        # Check for dirty state
        dirty_count=$(git -C "$dir" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
        unpushed=$(git -C "$dir" log --oneline '@{upstream}..HEAD' 2>/dev/null | wc -l | tr -d ' ')

        # Determine if this project is worth showing
        is_recent=false
        [ "$last_commit_epoch" -gt "$cutoff_epoch" ] && is_recent=true
        has_dirty=false
        [ "$dirty_count" -gt 0 ] && has_dirty=true
        has_unpushed=false
        [ "$unpushed" -gt 0 ] && has_unpushed=true

        if ! $is_recent && ! $has_dirty && ! $has_unpushed; then
            continue
        fi

        found=1

        # Build status indicator
        status=""
        if $has_dirty; then
            status="${RED}${dirty_count} uncommitted${RESET}"
        else
            status="${GREEN}clean${RESET}"
        fi

        if $has_unpushed; then
            status="$status ${YELLOW}(${unpushed} unpushed)${RESET}"
        fi

        printf "  %-24s %b  %-14s \033[2m%s\033[0m\n" "$project_name" "$status" "$last_commit_rel" "$last_commit_author"
        if $has_dirty || $has_unpushed; then
            printf "  %-24s \033[2m%s\033[0m\n" "" "$last_commit_msg"
        fi
    done

    [ "$found" -eq 0 ] && printf "  \033[2m(no recent activity)\033[0m\n"
}

scan_mini() {
    # Run a self-contained script on the Mini via SSH
    ssh -o ConnectTimeout=5 "$MINI_HOST" bash -s "$MINI_PROJECTS" "$cutoff_epoch" 2>/dev/null << 'REMOTE_SCRIPT'
root="$1"
cutoff="$2"
now_epoch=$(date +%s)

for dir in "$root"/*/; do
    [ -d "$dir/.git" ] || continue
    name=$(basename "$dir")
    [[ "$name" == .* || "$name" == _* ]] && continue

    last_epoch=$(git -C "$dir" log -1 --format="%at" 2>/dev/null || echo "0")
    last_rel=$(git -C "$dir" log -1 --format="%ar" 2>/dev/null || echo "unknown")
    last_author=$(git -C "$dir" log -1 --format="%an" 2>/dev/null || echo "unknown")
    last_msg=$(git -C "$dir" log -1 --format="%s" 2>/dev/null | cut -c1-60 || echo "")

    dirty=$(git -C "$dir" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    unpushed=$(git -C "$dir" log --oneline '@{upstream}..HEAD' 2>/dev/null | wc -l | tr -d ' ')

    is_recent=0; [ "$last_epoch" -gt "$cutoff" ] && is_recent=1
    has_dirty=0; [ "$dirty" -gt 0 ] && has_dirty=1
    has_unpushed=0; [ "$unpushed" -gt 0 ] && has_unpushed=1

    [ "$is_recent" -eq 0 ] && [ "$has_dirty" -eq 0 ] && [ "$has_unpushed" -eq 0 ] && continue

    echo "${name}|${dirty}|${unpushed}|${last_rel}|${last_author}|${last_msg}"
done
REMOTE_SCRIPT
}

# ─── Header ───
echo ""
printf "${BOLD}=== Morning Briefing $(date '+%Y-%m-%d %H:%M') ===${RESET}\n"
echo ""

# ─── Laptop ───
printf "${BOLD}${CYAN}LAPTOP${RESET} ${DIM}($PROJECTS_ROOT)${RESET}\n"
scan_projects "$PROJECTS_ROOT" "laptop"
echo ""

# ─── Mac Mini ───
printf "${BOLD}${CYAN}MAC MINI${RESET} ${DIM}(${MINI_HOST})${RESET}\n"
mini_output=$(scan_mini 2>&1) || true

if [ -z "$mini_output" ]; then
    echo "  ${DIM}(unreachable or no recent activity)${RESET}"
else
    while IFS='|' read -r name dirty unpushed last_rel last_author last_msg; do
        status=""
        if [ "$dirty" -gt 0 ]; then
            status="${RED}${dirty} uncommitted${RESET}"
        else
            status="${GREEN}clean${RESET}"
        fi
        if [ "$unpushed" -gt 0 ]; then
            status="$status ${YELLOW}(${unpushed} unpushed)${RESET}"
        fi
        printf "  %-24s %b  %-14s ${DIM}%s${RESET}\n" "$name" "$status" "$last_rel" "$last_author"
    done <<< "$mini_output"
fi
echo ""

# ─── Kanban ───
printf "${BOLD}${CYAN}KANBAN${RESET} ${DIM}(In Progress + Review)${RESET}\n"
if [ -x "$PT_CLI" ]; then
    in_progress=$("$PT_CLI" tasks -s "In Progress" 2>/dev/null | tail -n +3 | head -20) || true
    in_review=$("$PT_CLI" tasks -s "Review" 2>/dev/null | tail -n +3 | head -20) || true

    if [ -n "$in_progress" ]; then
        echo "$in_progress" | while read -r line; do
            [ -n "$line" ] && printf "  ${YELLOW}▶${RESET} %s\n" "$line"
        done
    fi
    if [ -n "$in_review" ]; then
        echo "$in_review" | while read -r line; do
            [ -n "$line" ] && printf "  ${CYAN}◉${RESET} %s\n" "$line"
        done
    fi
    if [ -z "$in_progress" ] && [ -z "$in_review" ]; then
        echo "  ${DIM}(no tasks in flight)${RESET}"
    fi
else
    echo "  ${DIM}(pt CLI not found)${RESET}"
fi

echo ""
printf "${DIM}Showing projects with activity in last ${HOURS_RECENT}h or uncommitted changes${RESET}\n"
echo ""

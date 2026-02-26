#!/usr/bin/env bash
# GrepAI search logging wrapper
# Source this file in your shell profile to log all grepai search calls.
# Usage: source "$PROJECTS_ROOT/_tools/grepai-wrapper.sh"

grepai() {
  local result exit_code
  result=$(command grepai "$@" 2>&1)
  exit_code=$?

  if [[ "$1" == "search" ]]; then
    local query="$2" project ts paths
    project=$(basename "$(pwd)")
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    paths=$(echo "$result" | "$HOME/.local/bin/uv" run python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(json.dumps([r['file'] for r in data.get('results', [])]))
except: print('[]')
" 2>/dev/null || echo '[]')
    local log_dir="${PROJECTS_ROOT:-$HOME/projects}/_tools/grepai-logs"
    mkdir -p "$log_dir"
    echo "{\"ts\":\"$ts\",\"project\":\"$project\",\"query\":\"$query\",\"results\":$paths}" \
      >> "$log_dir/ai_search_log.jsonl"
  fi

  echo "$result"
  return $exit_code
}

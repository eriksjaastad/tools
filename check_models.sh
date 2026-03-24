#!/bin/bash
set -euo pipefail

if [[ "${MODEL_HEALTH_INNER:-0}" != "1" ]]; then
  exec doppler run --project openclaw --config dev -- env MODEL_HEALTH_INNER=1 /bin/bash "$0" "$@"
fi

PATH="/opt/homebrew/bin:/usr/bin:/bin"
STATE_FILE="$HOME/.openclaw/workspace/model_health.json"
TMP_STATE="$(mktemp)"
CHECKED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
STATUS_LINES=""

check_ollama() {
  local body
  body="$(curl -fsS http://127.0.0.1:11434/api/tags)"
  echo "$body" | jq -e '.models[]?.name | select(. == "qwen3.5:35b")' >/dev/null
}

check_anthropic() {
  local prefix="$1"
  local body
  body="$(curl -fsS https://api.anthropic.com/v1/models \
    -H "x-api-key: ${ANTHROPIC_API_KEY}" \
    -H "anthropic-version: 2023-06-01")"
  echo "$body" | jq -e --arg prefix "$prefix" '.data[]?.id | select(startswith($prefix))' >/dev/null
}

check_openai() {
  local body
  body="$(curl -fsS https://api.openai.com/v1/models \
    -H "Authorization: Bearer ${OPENAI_API_KEY}")"
  echo "$body" | jq -e '.data[]?.id | select(. == "gpt-4o")' >/dev/null
}

check_gemini() {
  local body
  body="$(curl -fsS "https://generativelanguage.googleapis.com/v1beta/models?key=${GEMINI_API_KEY}")"
  echo "$body" | jq -e '.models[]?.name | select(. == "models/gemini-2.5-flash" or . == "models/gemini-2.5-flash-latest")' >/dev/null
}

check_xai() {
  local body
  body="$(curl -fsS https://api.x.ai/v1/models \
    -H "Authorization: Bearer ${XAI_API_KEY}")"
  echo "$body" | jq -e '.data[]?.id | select(startswith("grok-3-mini"))' >/dev/null
}

record_status() {
  local model="$1"
  local state="$2"
  STATUS_LINES="${STATUS_LINES}${model}"$'\t'"${state}"$'\n'
  printf '%s %s\n' "$model" "$(tr '[:lower:]' '[:upper:]' <<<"$state")"
}

run_check() {
  local model="$1"
  shift
  if "$@"; then
    record_status "$model" "ok"
  else
    record_status "$model" "fail"
  fi
}

run_check "ollama/qwen3.5:35b" check_ollama
run_check "anthropic/claude-haiku-4-5" check_anthropic "claude-haiku-4-5"
run_check "openai/gpt-4o" check_openai
run_check "google/gemini-2.5-flash" check_gemini
run_check "xai/grok-3-mini" check_xai
run_check "anthropic/claude-sonnet-4-6" check_anthropic "claude-sonnet-4-6"

{
  printf '{\n'
  printf '  "last_checked": "%s"' "$CHECKED_AT"
  while IFS=$'\t' read -r model state; do
    [[ -z "$model" ]] && continue
    printf ',\n  "%s": "%s"' "$model" "$state"
  done < <(printf '%s' "$STATUS_LINES" | sort)
  printf '\n}\n'
} > "$TMP_STATE"

mv "$TMP_STATE" "$STATE_FILE"

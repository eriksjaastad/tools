#!/bin/bash
set -euo pipefail

if [[ "${MODEL_HEALTH_INNER:-0}" != "1" ]]; then
  exec doppler run --project synth-insight-labs --config dev -- env MODEL_HEALTH_INNER=1 /bin/bash "$0" "$@"
fi

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}"
mkdir -p "$STATE_DIR"
STATE_FILE="$STATE_DIR/model_health.json"
TMP_STATE="$(mktemp)"
CHECKED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
STATUS_LINES=""
CURL_TIMEOUT=(--connect-timeout 5 --max-time 30)

check_ollama() {
  local model="$1"
  local body
  body="$(curl -fsS "${CURL_TIMEOUT[@]}" http://127.0.0.1:11434/api/tags)"
  echo "$body" | jq -e --arg model "$model" '.models[]?.name | select(. == $model)' >/dev/null
}

check_anthropic() {
  local prefix="$1"
  local body
  body="$(curl -fsS "${CURL_TIMEOUT[@]}" https://api.anthropic.com/v1/models \
    -H "x-api-key: ${ANTHROPIC_API_KEY}" \
    -H "anthropic-version: 2023-06-01")"
  echo "$body" | jq -e --arg prefix "$prefix" '.data[]?.id | select(startswith($prefix))' >/dev/null
}

check_openai() {
  local model="$1"
  local body
  body="$(curl -fsS "${CURL_TIMEOUT[@]}" https://api.openai.com/v1/models \
    -H "Authorization: Bearer ${OPENAI_API_KEY}")"
  echo "$body" | jq -e --arg model "$model" '.data[]?.id | select(. == $model)' >/dev/null
}

check_gemini() {
  local model="$1"
  local body
  body="$(curl -fsS "${CURL_TIMEOUT[@]}" "https://generativelanguage.googleapis.com/v1beta/models?key=${GOOGLE_API_KEY}")"
  echo "$body" | jq -e --arg model "$model" '.models[]?.name | select(. == ("models/" + $model) or . == ("models/" + $model + "-latest"))' >/dev/null
}

check_openrouter() {
  local model="$1"
  local body
  body="$(curl -fsS "${CURL_TIMEOUT[@]}" https://openrouter.ai/api/v1/models \
    -H "Authorization: Bearer ${OPENROUTER_API_KEY}")"
  echo "$body" | jq -e --arg model "$model" '.data[]?.id | select(. == $model)' >/dev/null
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

run_check "ollama/coding:current" check_ollama "coding:current"
run_check "anthropic/claude-opus-4-8" check_anthropic "claude-opus-4-8"
run_check "anthropic/claude-haiku-4-5" check_anthropic "claude-haiku-4-5"
run_check "openai/gpt-5.5" check_openai "gpt-5.5"
run_check "google/gemini-2.5-flash" check_gemini "gemini-2.5-flash"
# xAI direct is invalid; Grok is routed through OpenRouter now.
run_check "openrouter/x-ai/grok-4.3" check_openrouter "x-ai/grok-4.3"

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

#!/bin/bash
set -euo pipefail

if [[ "${MODEL_REGISTRY_INNER:-0}" != "1" ]]; then
  exec doppler run --project openclaw --config dev -- env MODEL_REGISTRY_INNER=1 /bin/bash "$0" "$@"
fi

PATH="/opt/homebrew/bin:/usr/bin:/bin"
TOOLS_MD="$HOME/.openclaw/workspace/TOOLS.md"

EXPECTED_MODELS="$(python3 - <<'PY'
import re
from pathlib import Path
text = Path(Path.home() / ".openclaw" / "workspace" / "TOOLS.md").read_text()
patterns = [
    r'`((?:anthropic|openai|google|xai|ollama)/[^`]+)`',
    r'\*\*((?:anthropic|openai|google|xai|ollama)/[^*]+)\*\*',
]
models = set()
for pattern in patterns:
    models.update(re.findall(pattern, text))
models = sorted(models)
for model in models:
    print(model)
PY
)"

ANTHROPIC_MODELS="$(curl -fsS https://api.anthropic.com/v1/models \
  -H "x-api-key: ${ANTHROPIC_API_KEY}" \
  -H "anthropic-version: 2023-06-01" | jq -r '.data[]?.id')"
OPENAI_MODELS="$(curl -fsS https://api.openai.com/v1/models \
  -H "Authorization: Bearer ${OPENAI_API_KEY}" | jq -r '.data[]?.id')"
GEMINI_MODELS="$(curl -fsS "https://generativelanguage.googleapis.com/v1beta/models?key=${GEMINI_API_KEY}" | jq -r '.models[]?.name | sub("^models/"; "")')"
XAI_MODELS="$(curl -fsS https://api.x.ai/v1/models \
  -H "Authorization: Bearer ${XAI_API_KEY}" | jq -r '.data[]?.id')"
OLLAMA_MODELS="$(curl -fsS http://127.0.0.1:11434/api/tags | jq -r '.models[]?.name')"

has_match() {
  local expected="$1"
  local available="$2"
  if grep -Fxq "$expected" <<<"$available"; then
    return 0
  fi
  grep -Eq "^${expected}([:-].*)?$" <<<"$available"
}

echo "Checking model registry against $TOOLS_MD"
echo

missing=0
while IFS= read -r model; do
  [[ -z "$model" ]] && continue
  provider="${model%%/*}"
  model_id="${model#*/}"
  case "$provider" in
    anthropic) available="$ANTHROPIC_MODELS" ;;
    openai) available="$OPENAI_MODELS" ;;
    google) available="$GEMINI_MODELS" ;;
    xai) available="$XAI_MODELS" ;;
    ollama) available="$OLLAMA_MODELS" ;;
    *)
      echo "SKIP $model unknown provider"
      continue
      ;;
  esac

  if has_match "$model_id" "$available"; then
    echo "OK   $model"
  else
    echo "MISS $model"
    missing=1
  fi
done <<<"$EXPECTED_MODELS"

exit "$missing"

#!/bin/bash
# Floor Manager Task Pickup Hook for Cursor
# Triggers when a new TASK_*.md file is created in _handoff/
# NOTE: We use node instead of jq to extract values to avoid external dependencies.

# Read the JSON payload from Cursor
PAYLOAD=$(cat)

# Extract file_path using Node.js
FILE_PATH=$(echo "$PAYLOAD" | node -e "try { console.log(JSON.parse(require('fs').readFileSync(0, 'utf8')).file_path || ''); } catch(e) { console.log(''); }")

# Check if this is a new task file in _handoff/
if [[ "$FILE_PATH" == *"_handoff/TASK_"*.md ]]; then
  # Return a followup message to trigger Floor Manager
  cat << 'EOF'
{
  "followup_message": "A new task has arrived in _handoff/. Run `python scripts/handoff_info.py` to see the task details, then execute it following Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md. Dispatch to a Worker using ollama_agent_run, route the submission to Claude for review via request_draft_review, and apply or reject based on the verdict."
}
EOF
else
  echo '{}'
fi

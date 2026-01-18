#!/bin/bash
# Floor Manager Task Pickup Hook for Cursor
# Triggers when a new TASK_*.md file is created in _handoff/

# Read the JSON payload from Cursor
PAYLOAD=$(cat)
FILE_PATH=$(echo "$PAYLOAD" | jq -r '.file_path')

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

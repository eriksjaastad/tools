#!/bin/bash
# oc-monitor.sh - Comprehensive OpenClaw Status Monitor

echo "🦞 OpenClaw Global Status"
echo "========================="
openclaw status
echo ""

echo "⏰ Cron Scheduler"
echo "-----------------"
openclaw cron list
echo ""

echo "📋 Last Patrol Result (floor-manager-patrol)"
echo "-------------------------------------------"
# Capture both stdout and stderr, then extract JSON
TEMP_FILE=$(mktemp)
openclaw cron runs --id floor-manager-patrol --limit 1 > "$TEMP_FILE" 2>&1
# Extract content starting from the first '{' and ending at the last '}'
sed -n '/^{/,/^}/p' "$TEMP_FILE" | jq -r '.entries[0].summary'
rm "$TEMP_FILE"
echo ""

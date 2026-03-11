#!/bin/bash
# oc-auth-watchdog.sh - OpenClaw Auth Watchdog
# Detects OAuth token refresh failures for openai-codex

LOG_FILE="$HOME/.openclaw/logs/gateway.err.log"
STATE_FILE="/tmp/oc_auth_watchdog_state"
ALERT_LOG="$HOME/.openclaw/logs/auth_watchdog.log"
DEDUPE_TIME=3600 # 60 minutes

get_timestamp() {
    TZ="America/Los_Angeles" date "+%Y-%m-%d %H:%M:%S %Z"
}

# Collect status data safely
MODELS_STATUS=$(openclaw models status 2>&1 || true)
STATUS_ALL=$(openclaw status --all 2>&1 || true)
LOGS=$(tail -n 200 "$LOG_FILE" 2>/dev/null || true)
AGENT_PING=$(timeout 10 openclaw agent --agent main -m "health ping" 2>&1 || true)

COMBINED_OUTPUT="$MODELS_STATUS\n$STATUS_ALL\n$LOGS\n$AGENT_PING"

ALERT=0
ERROR_LINE=""

# Evaluate alert conditions
if echo "$COMBINED_OUTPUT" | grep -q "OAuth token refresh failed for openai-codex"; then
    ALERT=1
    ERROR_LINE=$(echo "$COMBINED_OUTPUT" | grep "OAuth token refresh failed for openai-codex" | head -n 1 | xargs)
elif echo "$COMBINED_OUTPUT" | grep -q "refresh_token_reused"; then
    ALERT=1
    ERROR_LINE=$(echo "$COMBINED_OUTPUT" | grep "refresh_token_reused" | head -n 1 | xargs)
elif echo "$COMBINED_OUTPUT" | grep -q "\[openai-codex\] Token refresh failed: 401"; then
    ALERT=1
    ERROR_LINE=$(echo "$COMBINED_OUTPUT" | grep "\[openai-codex\] Token refresh failed: 401" | head -n 1 | xargs)
elif echo "$AGENT_PING" | grep -iE -q "auth|refresh error"; then
    ALERT=1
    ERROR_LINE=$(echo "$AGENT_PING" | grep -iE "auth|refresh error" | head -n 1 | xargs)
fi

CURRENT_TIME=$(date +%s)

if [ "$ALERT" -eq 1 ]; then
    LAST_ALERT_TIME=0
    if [ -f "$STATE_FILE" ]; then
        LAST_ALERT_TIME=$(cat "$STATE_FILE")
    fi
    TIME_DIFF=$((CURRENT_TIME - LAST_ALERT_TIME))
    
    # Trigger if it's the first time or 60 minutes have passed
    if [ "$LAST_ALERT_TIME" -eq 0 ] || [ "$TIME_DIFF" -ge "$DEDUPE_TIME" ]; then
        TIMESTAMP=$(get_timestamp)
        LAST_LOGS=$(tail -n 5 "$LOG_FILE" 2>/dev/null || true)
        
        ALERT_MSG="🚨 OPENCLAW AUTH FAILURE 🚨
Time: $TIMESTAMP
Error: $ERROR_LINE

Last 5 log lines:
$LAST_LOGS

Suggested Fix: openclaw configure --section model"

        # Write to alert log
        echo "$ALERT_MSG" >> "$ALERT_LOG"
        
        # Send macOS push notification
        osascript -e "display notification \"$ERROR_LINE\" with title \"OpenClaw Auth Failed (openai-codex)\""
        
        # Update dedupe state
        echo "$CURRENT_TIME" > "$STATE_FILE"
        
        # Print to stdout for manual runs
        echo -e "$ALERT_MSG"
    fi
else
    # System is healthy
    if [ -f "$STATE_FILE" ]; then
        # It was failing before, now it recovered
        rm "$STATE_FILE"
        RECOVERY_MSG="✅ OpenClaw Auth recovered. Time: $(get_timestamp)"
        echo "$RECOVERY_MSG" >> "$ALERT_LOG"
        osascript -e 'display notification "OpenClaw Auth is healthy again." with title "OpenClaw Auth Watchdog"'
        echo "$RECOVERY_MSG"
    fi
fi

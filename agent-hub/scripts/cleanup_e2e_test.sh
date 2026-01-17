#!/bin/bash
# Cleanup after E2E test

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HANDOFF_DIR="$PROJECT_ROOT/_handoff"
ARCHIVE_DIR="$HANDOFF_DIR/archive/e2e_test_$(date +%Y%m%d_%H%M%S)"

echo "=== E2E Test Cleanup ==="

# Create archive directory
mkdir -p "$ARCHIVE_DIR"

# Move test artifacts
for f in TEST_PROPOSAL.md TASK_CONTRACT.json JUDGE_REPORT.md JUDGE_REPORT.json; do
    if [ -f "$HANDOFF_DIR/$f" ]; then
        mv "$HANDOFF_DIR/$f" "$ARCHIVE_DIR/"
        echo "Archived: $f"
    fi
done

# Keep transition.ndjson but copy to archive
if [ -f "$HANDOFF_DIR/transition.ndjson" ]; then
    cp "$HANDOFF_DIR/transition.ndjson" "$ARCHIVE_DIR/"
    echo "Copied: transition.ndjson"
fi

echo ""
echo "Archived to: $ARCHIVE_DIR"
echo "Cleanup complete."

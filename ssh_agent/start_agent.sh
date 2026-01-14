#!/bin/bash
###############################################################################
# Start SSH Agent
#
# This agent lets Claude run SSH commands on the RunPod
# by writing to queue/requests.jsonl and reading from
# queue/results.jsonl
###############################################################################

cd "$(dirname "$0")"

echo "📡 Starting SSH Agent..."
echo ""
echo "Claude can now run SSH commands on RunPod!"
echo "The agent will poll queue/requests.jsonl for new commands."
echo ""
echo "Press Ctrl+C to stop the agent."
echo ""

# Check if venv exists and use it
if [ -f "venv/bin/activate" ]; then
    echo "🐍 Using virtual environment..."
    source venv/bin/activate
fi

# Run the agent
python3 agent.py


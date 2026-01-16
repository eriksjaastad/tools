# SSH Agent for Claude

Central SSH tool located in `_tools/ssh_agent`. It allows AI agents to run commands on remote hosts via a JSON queue.

## Setup (One-Time)

```bash
# Install dependencies
cd _tools/ssh_agent
pip install -r requirements.txt

# Start the agent (in a separate terminal)
./start_agent.sh
```

The agent will keep running, watching for new commands in the `queue/` directory.

## How Claude Uses It

Claude writes JSON commands to `queue/requests.jsonl` and reads results from `queue/results.jsonl`.

## Configuration

Edit `ssh_hosts.yaml` to add hosts.

## Testing

```bash
# Test a simple command
echo '{"id":"test1","host":"runpod","command":"pwd","reason":"test"}' >> queue/requests.jsonl

# Check results
tail -1 queue/results.jsonl
```

## Components
- [[agent.py|SSH Agent Core]] - Python script that processes the command queue.
- [[ssh_hosts.yaml|SSH Hosts Config]] - YAML configuration for remote host connection details.
- [[queue/.agent_state.json|Agent State]] - Internal persistence for tracking queue progress.

## Notes

- Agent polls every 1 second for new requests
- Supports both RSA and ED25519 SSH keys
- Auto-expands `~` in key paths
- For RunPod, reads the POD_ID from `../.pod_id` automatically

## Related Documentation

- [[cloud_gpu_setup]] - cloud GPU
- [[queue_processing_guide]] - queue/workflow
- [[ai_model_comparison]] - AI models
- [[testing_strategy]] - testing/QA

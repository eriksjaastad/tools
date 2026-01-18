import json
import subprocess
import os
import sys
import time
from pathlib import Path

def dispatch_task(task_path: Path, model: str, max_iterations: int = 10):
    """
    Dispatches a task to ollama_agent_run via ollama-mcp server.
    """
    root_dir = Path(__file__).parent.parent.parent
    ollama_mcp_dir = root_dir / "ollama-mcp"
    server_js = ollama_mcp_dir / "dist" / "server.js"

    if not server_js.exists():
        print(f"Error: MCP server not found at {server_js}")
        sys.exit(1)

    # Read task content
    with open(task_path, 'r') as f:
        task_content = f.read()

    # Prepare prompt
    task_id = "PHASE_0_P1_LITELLM_REFS"
    prompt = f"""TASK_ID: {task_id}

TASK DETAILS:
{task_content}

FILE STATUS (Files already created as empty stubs):
- references/litellm/README.md
- references/litellm/ROUTING_PATTERNS.md
- references/litellm/FALLBACK_PATTERNS.md
- references/litellm/COOLDOWN_PATTERNS.md

PREVIOUS ATTEMPT STATUS:
- FAILED: All files had hallucinated API patterns (e.g., 'CooldownManager').
- REJECTED: Cooldown documentation was incorrect and empty.

CORRECT PATTERNS TO USE (From official LiteLLM docs):

1. Router & Load Balancing:
```python
from litellm import Router
model_list = [
    {{"model_name": "tier1", "litellm_params": {{"model": "ollama/qwen2.5-coder:14b"}}}},
    {{"model_name": "tier2", "litellm_params": {{"model": "gemini/gemini-1.5-flash"}}}},
    {{"model_name": "tier3", "litellm_params": {{"model": "claude-3-5-sonnet-20240620"}}}}
]
router = Router(model_list=model_list, routing_strategy="least-busy")
```
Strategies: 'simple-shuffle', 'least-busy', 'latency-based', 'weighted-shuffle'.

2. Fallbacks:
```python
router = Router(
    model_list=model_list,
    fallbacks=[{{"tier1": ["tier2", "tier3"]}}],
    context_window_fallbacks=[{{"tier1": ["tier3"]}}]
)
```

3. Cooldowns:
```python
router = Router(
    model_list=model_list,
    allowed_fails=3,
    cooldown_time=60
)
```

INSTRUCTIONS:
1. Use 'ollama_request_draft' for EACH file.
2. Use 'ollama_write_draft' to fill them with COMPREHENSIVE documentation using the CORRECT patterns above.
3. README.md: Include links to https://docs.litellm.com/ and summary of these 3 features.
4. Use 'ollama_submit_draft' for EACH file.

BE COMPREHENSIVE. Don't stop until all 4 files are fully documented."""

    # Start MCP server
    process = subprocess.Popen(
        ["node", str(server_js)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ollama_mcp_dir),
        text=True,
        bufsize=1
    )

    # Give it a moment to start
    time.sleep(2)
    
    # Call ollama_agent_run
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "ollama_agent_run",
            "arguments": {
                "prompt": prompt,
                "model": model,
                "timeout_ms": 600000, # 10 minutes
                "task_id": task_id, # pass task_id if supported
                "max_iterations": max_iterations
            }
        }
    }

    print(f"Dispatching task {task_path.name} to {model}...")
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()

    # Wait for response and log stderr in background
    print("Waiting for response (check terminal for logs)...")
    
    while True:
        # Check stderr for progress
        line = process.stderr.readline()
        if line:
            print(f"[LOG] {line.strip()}")
        
        # Check stdout for response
        if process.poll() is not None:
             break
        
        # We can't easily do non-blocking read on both in a simple script
        # but the agent loop prints to stderr, so we'll see it.
        
    response_str = process.stdout.read()
    if response_str:
        try:
            response = json.loads(response_str)
            if "error" in response:
                print(f"Error from MCP: {response['error']}")
            else:
                print("Task dispatch successful.")
                print("Worker Result Summary:")
                print(json.dumps(response.get("result", {}), indent=2))
        except json.JSONDecodeError:
            print(f"Malformed response from server: {response_str}")

    process.terminate()
    process.wait()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python dispatch_task.py <task_file> <model> [max_iterations]")
        sys.exit(1)
    
    task_file = Path(sys.argv[1])
    model_name = sys.argv[2]
    max_iters = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    dispatch_task(task_file, model_name, max_iters)

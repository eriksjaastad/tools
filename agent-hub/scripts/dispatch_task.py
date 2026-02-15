"""
Dispatch a task to a local Ollama worker via the Go MCP server.

Usage:
    python scripts/dispatch_task.py <task_file.md> <role> [max_iterations]

Roles: coder, reviewer, implementer, embedder
       (or any Ollama model alias like "coding:current")

The role is resolved through config/routing.yaml role_aliases,
then validated against installed Ollama models before dispatch.
"""

import json
import subprocess
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent dir so we can import config.models
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.models import resolve_role, validate_routing_config


def dispatch_task(task_path: Path, role: str, max_iterations: int = 15):
    """
    Dispatches a task to agent_loop via ollama-mcp-go server.

    Args:
        task_path: Path to the task markdown file.
        role: Role name ("coder", "reviewer") or model alias ("coding:current").
        max_iterations: Max agent loop iterations.
    """
    agent_hub_dir = Path(__file__).parent.parent
    root_dir = agent_hub_dir.parent
    server_bin = root_dir / "ollama-mcp-go" / "bin" / "server"

    if not server_bin.exists():
        print(f"Error: MCP server not found at {server_bin}")
        sys.exit(1)

    # Resolve role to model name
    model = resolve_role(role)
    if model != role:
        print(f"Resolved role '{role}' -> '{model}'")

    # Preflight: validate models are actually installed
    errors = validate_routing_config()
    if errors:
        print("Preflight check failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    # Read task content
    with open(task_path, 'r') as f:
        task_content = f.read()

    task_id = task_path.name.replace(".md", "")

    # Prepare prompt
    prompt = f"""TASK_ID: {task_id}

TASK DETAILS:
{task_content}

INSTRUCTIONS:
1. Read the task objective and target files carefully.
2. You MUST use tools to perform the task. Text-only responses will be ignored.
3. To call a tool, you MUST use this EXACT format:
   <tool_call>{{"name": "tool_name", "arguments": {{"arg1": "val1"}}}}</tool_call>
4. EXAMPLES:
   - To read a file: <tool_call>{{"name": "draft_read", "arguments": {{"path": "filename.py"}}}}</tool_call>
   - To write a file: <tool_call>{{"name": "draft_write", "arguments": {{"path": "filename.py", "content": "..."}}}}</tool_call>
5. You are working in a sandbox. All paths should be relative to the root.

GOAL: Complete the objective stated in the task details. Perform the edits now.
"""

    # Start MCP server
    process = subprocess.Popen(
        [str(server_bin)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(root_dir),
        text=True,
        bufsize=1,
        env={**os.environ, "SANDBOX_ROOT": str(root_dir), "LOG_LEVEL": "info"}
    )

    # Give it a moment to start
    time.sleep(1)

    # Call agent_loop
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "agent_loop",
            "arguments": {
                "prompt": prompt,
                "model": model,
                "max_iterations": max_iterations,
                "task_id": task_id
            }
        }
    }

    print(f"Dispatching task {task_path.name} to {model} via Go MCP...")
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()

    # Wait for response and log stderr in background
    print("Waiting for response (check terminal for logs)...")

    # Read response
    response_str = ""
    while True:
        line = process.stdout.readline()
        if line:
            response_str += line
            if '"result":' in line or '"error":' in line:
                break

        # Also check stderr
        err_line = process.stderr.readline()
        if err_line:
            print(f"[LOG] {err_line.strip()}")

        if process.poll() is not None:
             break

    if response_str:
        try:
            response = json.loads(response_str)
            if "error" in response:
                print(f"Error from MCP: {response['error']}")
            else:
                print("Task execution loop finished.")
                print("Worker Result Summary:")
                res = response.get("result", {})
                if isinstance(res, dict):
                    print(f"Iterations: {res.get('iterations')}")
                    print(f"Tools Called: {res.get('tool_calls_made')}")
                    response_text = res.get("response") or ""
                    preview = response_text[:500] if response_text else "(none)"
                    print(f"Final Response: {preview}...")

                    # Append to task file
                    with open(task_path, "a") as f:
                        f.write(f"\n\n## Worker Output ({datetime.now().isoformat()})\n\n")
                        f.write(res.get("response") or "No response")
                        f.write(f"\n\n---\n**Stats:** {res.get('iterations')} iterations, {res.get('tool_calls_made')} tool calls.\n")
                else:
                    print(json.dumps(res, indent=2))
        except json.JSONDecodeError:
            print(f"Malformed response from server: {response_str}")

    process.terminate()
    process.wait()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python dispatch_task.py <task_file> <role> [max_iterations]")
        print()
        print("Roles: coder, reviewer, implementer, embedder")
        print("       (or any Ollama alias like 'coding:current')")
        sys.exit(1)

    task_file = Path(sys.argv[1])
    role_name = sys.argv[2]
    max_iters = int(sys.argv[3]) if len(sys.argv) > 3 else 15

    dispatch_task(task_file, role_name, max_iters)

"""
Dispatch a task to a local Ollama worker via the Go MCP server.

Usage:
    python scripts/dispatch_task.py <task_file.md> <role> [--max-iterations N] [--project-root PATH]

Roles: coder, reviewer, implementer, embedder
       (or any Ollama model alias like "coding:current")

The role is resolved through config/routing.yaml role_aliases,
then validated against installed Ollama models before dispatch.

When --project-root is specified, the worker can read files from the target
project via draft_read, and the sandbox is expanded to cover both the tools
directory and the project directory.
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


def dispatch_task(task_path: Path, role: str, max_iterations: int = 15, project_root: Path = None):
    """
    Dispatches a task to agent_loop via ollama-mcp-go server.

    Args:
        task_path: Path to the task markdown file.
        role: Role name ("coder", "reviewer") or model alias ("coding:current").
        max_iterations: Max agent loop iterations.
        project_root: Path to the target project directory. When set, the worker
                      can read files from this project via draft_read.
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

    # Resolve project root
    resolved_project_root = None
    if project_root is not None:
        resolved_project_root = project_root.resolve()
        if not resolved_project_root.is_dir():
            print(f"Error: Project root does not exist: {resolved_project_root}")
            sys.exit(1)
        print(f"Project root: {resolved_project_root}")

    # Prepare prompt
    project_context = ""
    if resolved_project_root:
        project_context = f"""6. PROJECT ROOT: {resolved_project_root}
   All file paths are relative to this project directory.
   Use draft_read with relative paths (e.g., "pyproject.toml", "src/main.py") to read project files.
"""
    else:
        project_context = "5. You are working in a sandbox. All paths should be relative to the root.\n"

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
{project_context}
GOAL: Complete the objective stated in the task details. Perform the edits now.
"""

    # Compute sandbox root: must cover both tools dir and project root
    sandbox_root = root_dir
    if resolved_project_root:
        sandbox_root = Path(os.path.commonpath([str(root_dir), str(resolved_project_root)]))
        print(f"Sandbox root expanded to: {sandbox_root}")

    # Start MCP server
    process = subprocess.Popen(
        [str(server_bin)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(root_dir),
        text=True,
        bufsize=1,
        env={**os.environ, "SANDBOX_ROOT": str(sandbox_root), "LOG_LEVEL": "info"}
    )

    # Give it a moment to start
    time.sleep(1)

    # Perform MCP handshake
    # 1. Send initialize request
    init_request = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "agent-hub-dispatcher",
                "version": "1.0.0"
            }
        }
    }
    
    print("Sending MCP initialize request...")
    process.stdin.write(json.dumps(init_request) + "\n")
    process.stdin.flush()
    
    # Wait for initialize response
    init_response = process.stdout.readline()
    if init_response:
        try:
            init_data = json.loads(init_response)
            print(f"✓ Initialize response received")
        except json.JSONDecodeError:
            print(f"✗ Failed to parse initialize response: {init_response}")
    
    # 2. Send initialized notification
    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
    
    print("Sending initialized notification...")
    process.stdin.write(json.dumps(initialized_notification) + "\n")
    process.stdin.flush()
    
    # Small delay to ensure notification is processed
    time.sleep(0.1)

    # Call agent_loop
    arguments = {
        "prompt": prompt,
        "model": model,
        "max_iterations": max_iterations,
        "task_id": task_id
    }
    if resolved_project_root:
        arguments["project_root"] = str(resolved_project_root)

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "agent_loop",
            "arguments": arguments
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
        print(f"\n[DEBUG] Raw response: {response_str[:500]}...")
        try:
            response = json.loads(response_str)
            print(f"[DEBUG] Parsed response keys: {response.keys()}")
            
            if "error" in response:
                print(f"Error from MCP: {response['error']}")
            else:
                print("Task execution loop finished.")
                print("Worker Result Summary:")
                res = response.get("result", {})
                print(f"[DEBUG] Result type: {type(res)}")
                print(f"[DEBUG] Result content: {json.dumps(res, indent=2)[:1000]}")
                
                if isinstance(res, dict):
                    print(f"Iterations: {res.get('iterations')}")
                    print(f"Tools Called: {res.get('tool_calls_made')}")
                    response_text = res.get("response") or ""
                    preview = response_text[:500] if response_text else "(none)"
                    print(f"Final Response: {preview}...")

                    # Append to task file
                    print(f"\n[DEBUG] Appending to task file: {task_path}")
                    with open(task_path, "a") as f:
                        f.write(f"\n\n## Worker Output ({datetime.now().isoformat()})\n\n")
                        f.write(res.get("response") or "No response")
                        f.write(f"\n\n---\n**Stats:** {res.get('iterations')} iterations, {res.get('tool_calls_made')} tool calls.\n")
                    print(f"[DEBUG] Successfully appended to {task_path}")
                    
                    # Validate drafts and notify Floor Manager
                    print(f"\n[VALIDATION] Checking drafts for task {task_id}...")
                    try:
                        # Import and run validation
                        sys.path.insert(0, str(Path(__file__).parent))
                        from validate_draft import validate_drafts, write_notification
                        
                        validation_result = validate_drafts(task_id)
                        
                        if validation_result["valid"]:
                            print(f"✅ Validation passed: {validation_result['draft_count']} draft(s), {validation_result['total_bytes']} bytes")
                            notification_file = write_notification(task_id, validation_result)
                            print(f"📬 Floor Manager notified: {notification_file}")
                            print(f"\n🎉 Task {task_id} ready for Floor Manager review!")
                        else:
                            print(f"⚠️  Validation issues found:")
                            for issue in validation_result["issues"]:
                                print(f"  - {issue}")
                            notification_file = write_notification(task_id, validation_result)
                            print(f"📬 Floor Manager notified (needs attention): {notification_file}")
                    except Exception as e:
                        print(f"⚠️  Validation failed with error: {e}")
                        print("Continuing anyway - Floor Manager can review manually")
                        
                else:
                    print(f"[WARNING] Unexpected result type: {type(res)}")
                    print(json.dumps(res, indent=2))
        except json.JSONDecodeError as e:
            print(f"Malformed response from server: {response_str}")
            print(f"[DEBUG] JSON decode error: {e}")

    process.terminate()
    process.wait()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Dispatch a task to a local Ollama worker via Go MCP server."
    )
    parser.add_argument("task_file", type=Path, help="Path to the task markdown file")
    parser.add_argument("role", help="Role name (coder, reviewer) or model alias (coding:current)")
    parser.add_argument("--max-iterations", type=int, default=15, help="Max agent loop iterations (default: 15)")
    parser.add_argument("--project-root", type=Path, default=None,
                        help="Path to target project directory (for tasks that modify external projects)")
    args = parser.parse_args()

    dispatch_task(args.task_file, args.role, args.max_iterations, args.project_root)

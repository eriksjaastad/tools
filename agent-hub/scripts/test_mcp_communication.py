import subprocess
import json
import time
import os
import sys
import argparse
from typing import List, Dict, Any, Optional

def log(msg: str, verbose: bool = False):
    if verbose:
        print(f"[DEBUG] {msg}")

def run_test(name: str, test_fn):
    try:
        success, message = test_fn()
        if success:
            print(f"[PASS] {name}: {message}")
            return True
        else:
            print(f"[FAIL] {name}: {message}")
            return False
    except Exception as e:
        print(f"[FAIL] {name}: Exception: {str(e)}")
        return False

class MCPServerProcess:
    def __init__(self, command: List[str], cwd: str, verbose: bool = False):
        self.command = command
        self.cwd = cwd
        self.verbose = verbose
        self.process = None

    def start(self):
        log(f"Starting server: {' '.join(self.command)} in {self.cwd}", self.verbose)
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            text=True,
            bufsize=1
        )
        # Give it a moment to start
        time.sleep(1)
        if self.process.poll() is not None:
            stderr = self.process.stderr.read()
            raise Exception(f"Server failed to start. Exit code: {self.process.returncode}, stderr: {stderr}")

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": method
        }
        if params:
            request["params"] = params
        
        request_str = json.dumps(request)
        log(f"Sending: {request_str}", self.verbose)
        
        self.process.stdin.write(request_str + "\n")
        self.process.stdin.flush()
        
        response_str = self.process.stdout.readline()
        log(f"Received: {response_str}", self.verbose)
        
        if not response_str:
            # Check stderr
            stderr = ""
            while True:
                line = self.process.stderr.readline()
                if not line: break
                stderr += line
            raise Exception(f"No response from server. Stderr: {stderr}")
            
        return json.loads(response_str)

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process.kill()

EXPECTED_CLAUDE_TOOLS = [
    "claude_judge_review",
    "request_draft_review",
    "submit_review_verdict",
    "claude_validate_proposal",
    "claude_security_audit",
    "claude_resolve_conflict",
    "claude_health",
    "hub_connect",
    "hub_send_message",
    "hub_receive_messages",
    "hub_heartbeat",
    "hub_send_answer",
    "hub_get_all_messages",
]

EXPECTED_OLLAMA_TOOLS = [
    "ollama_list_models",
    "ollama_run",
    "ollama_run_many",
    "ollama_request_draft",
    "ollama_write_draft",
    "ollama_read_draft",
    "ollama_submit_draft",
    "ollama_agent_run",
]

def main():
    parser = argparse.ArgumentParser(description="MCP Communication E2E Test")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    claude_mcp_dir = os.path.join(root_dir, "claude-mcp")
    ollama_mcp_dir = os.path.join(root_dir, "ollama-mcp")
    agent_hub_dir = os.path.join(root_dir, "agent-hub")
    handoff_dir = os.path.join(claude_mcp_dir, "_handoff")
    hub_state_path = os.path.join(handoff_dir, "hub_state.json")

    print("=== MCP Communication E2E Test ===")
    
    total_tests = 0
    passed_tests = 0
    
    claude_server = None
    ollama_server = None

    try:
        # 1. Test claude-mcp
        claude_server = MCPServerProcess(["node", "dist/server.js"], claude_mcp_dir, args.verbose)
        claude_server.start()
        
        # Test tools/list
        def test_claude_list():
            resp = claude_server.call("tools/list")
            tools = resp.get("result", {}).get("tools", [])
            tool_names = [t["name"] for t in tools]
            missing = [t for t in EXPECTED_CLAUDE_TOOLS if t not in tool_names]
            if missing:
                return False, f"Missing Claude tools: {missing}"
            return True, f"All {len(EXPECTED_CLAUDE_TOOLS)} expected Claude tools present"
        
        total_tests += 1
        if run_test("claude-mcp", test_claude_list): passed_tests += 1

        # Test hub_connect
        def test_claude_connect():
            resp = claude_server.call("tools/call", {
                "name": "hub_connect",
                "arguments": {"agent_id": "test_agent", "role": "tester"}
            })
            if "result" in resp and not resp.get("error"):
                return True, "hub_connect successful"
            return False, f"hub_connect failed: {resp.get('error')}"

        total_tests += 1
        if run_test("claude-mcp", test_claude_connect): passed_tests += 1

        # Test hub_send_message
        def test_claude_send():
            resp = claude_server.call("tools/call", {
                "name": "hub_send_message",
                "arguments": {
                    "to_id": "test_agent",
                    "from_id": "test_agent",
                    "message": "hello test",
                    "msg_type": "PROPOSAL_READY"
                }
            })
            if "result" in resp and not resp.get("error"):
                return True, "hub_send_message successful"
            return False, f"hub_send_message failed: {resp.get('error')}"

        total_tests += 1
        if run_test("claude-mcp", test_claude_send): passed_tests += 1

        # Test hub_receive_messages
        def test_claude_receive():
            resp = claude_server.call("tools/call", {
                "name": "hub_receive_messages",
                "arguments": {"agent_id": "test_agent"}
            })
            if "result" in resp and not resp.get("error"):
                return True, "hub_receive_messages returns empty list"
            return False, f"hub_receive_messages failed: {resp.get('error')}"

        total_tests += 1
        if run_test("claude-mcp", test_claude_receive): passed_tests += 1

        # Verify hub_state.json
        def test_hub_state_file():
            if os.path.exists(hub_state_path):
                return True, "hub_state.json created"
            return False, "hub_state.json not found"

        total_tests += 1
        if run_test("claude-mcp", test_hub_state_file): passed_tests += 1

        # 2. Test ollama-mcp
        ollama_server = MCPServerProcess(["node", "dist/server.js"], ollama_mcp_dir, args.verbose)
        ollama_server.start()
        
        def test_ollama_list():
            resp = ollama_server.call("tools/list")
            tools = resp.get("result", {}).get("tools", [])
            tool_names = [t["name"] for t in tools]
            missing = [t for t in EXPECTED_OLLAMA_TOOLS if t not in tool_names]
            if missing:
                return False, f"Missing Ollama tools: {missing}"
            return True, f"All {len(EXPECTED_OLLAMA_TOOLS)} expected Ollama tools present"

        total_tests += 1
        if run_test("ollama-mcp", test_ollama_list): passed_tests += 1

        # 3. Test hook detection
        def test_hook_trigger():
            hook_script = os.path.join(agent_hub_dir, ".cursor", "hooks", "floor_manager_pickup.sh")
            if not os.path.exists(hook_script):
                return False, f"Hook script not found at {hook_script}"
            
            payload = json.dumps({"file_path": "_handoff/TASK_test.md"})
            proc = subprocess.run(
                [hook_script],
                input=payload,
                capture_output=True,
                text=True,
                cwd=agent_hub_dir
            )
            
            if proc.returncode != 0:
                return False, f"Hook script failed with code {proc.returncode}: {proc.stderr}"
            
            resp = json.loads(proc.stdout)
            if "followup_message" in resp:
                return True, "floor_manager_pickup.sh triggers on TASK file"
            return False, f"Hook did not return followup_message: {proc.stdout}"

        total_tests += 1
        if run_test("hook", test_hook_trigger): passed_tests += 1

    finally:
        if claude_server:
            claude_server.stop()
        if ollama_server:
            ollama_server.stop()
        
        # Cleanup
        if os.path.exists(hub_state_path):
            os.remove(hub_state_path)

    print(f"=== {passed_tests}/{total_tests} tests passed ===")
    
    if passed_tests == total_tests:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

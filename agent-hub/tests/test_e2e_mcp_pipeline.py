"""
E2E test: Verify MCP servers can communicate.
Run: pytest tests/test_e2e_mcp_pipeline.py -v
"""
import subprocess
import json
import time
import os
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
OLLAMA_BIN = ROOT / "ollama-mcp-go" / "bin" / "server"
CLAUDE_BIN = ROOT / "claude-mcp-go" / "bin" / "claude-mcp-go"

@pytest.fixture
def ollama_server():
    """Start ollama-mcp-go server."""
    proc = subprocess.Popen(
        [str(OLLAMA_BIN)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "SANDBOX_ROOT": str(ROOT)}
    )
    time.sleep(1)
    yield proc
    proc.terminate()
    proc.wait()

@pytest.fixture
def claude_server():
    """Start claude-mcp-go server."""
    proc = subprocess.Popen(
        [str(CLAUDE_BIN)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "HUB_STATE_DIR": str(ROOT / "agent-hub" / "_handoff")}
    )
    time.sleep(1)
    yield proc
    proc.terminate()
    proc.wait()

def mcp_call(proc, method, params=None):
    """Send MCP request and get response."""
    request = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        request["params"] = params
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())

class TestOllamaMCP:
    def test_server_starts(self, ollama_server):
        assert ollama_server.poll() is None

    def test_tools_list(self, ollama_server):
        resp = mcp_call(ollama_server, "tools/list")
        tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
        assert "ollama_run" in tools
        assert "agent_loop" in tools
        assert "draft_read" in tools
        assert "draft_write" in tools
        assert "ollama_list_models" in tools

class TestClaudeMCP:
    def test_server_starts(self, claude_server):
        assert claude_server.poll() is None

    def test_tools_list(self, claude_server):
        resp = mcp_call(claude_server, "tools/list")
        tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
        assert "hub_connect" in tools
        assert "hub_send_message" in tools
        assert "request_draft_review" in tools

class TestHubMessaging:
    def test_connect_and_send(self, claude_server):
        # Connect
        resp = mcp_call(claude_server, "tools/call", {
            "name": "hub_connect",
            "arguments": {"agent_id": "test", "role": "tester"}
        })
        assert "error" not in resp

        # Send message
        resp = mcp_call(claude_server, "tools/call", {
            "name": "hub_send_message",
            "arguments": {
                "to_id": "test",
                "from_id": "test",
                "message": "ping",
                "msg_type": "PROPOSAL_READY"
            }
        })
        assert "error" not in resp

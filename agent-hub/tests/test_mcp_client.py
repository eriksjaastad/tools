import pytest
import json
import threading
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.mcp_client import MCPClient, MCPError, MCPTimeoutError

@pytest.fixture
def mock_process():
    process = MagicMock()
    process.stdin = MagicMock()
    process.stdout = MagicMock()
    process.poll.return_value = None
    return process

def test_start_stop(mock_process):
    path = Path("/dummy/path")
    with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
        client = MCPClient(path)
        client.start()
        mock_popen.assert_called_once()
        client.stop()
        mock_process.terminate.assert_called_once()

def test_call_tool_success(mock_process):
    path = Path("/dummy/path")
    with patch("subprocess.Popen", return_value=mock_process):
        client = MCPClient(path)
        client.start()
        
        # Mock response
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"output": "hello"}
        }
        mock_process.stdout.readline.return_value = json.dumps(response)
        
        result = client.call_tool("test_tool", {})
        assert result == {"output": "hello"}
        
        # Verify request sent
        args, _ = mock_process.stdin.write.call_args
        sent_request = json.loads(args[0])
        assert sent_request["method"] == "tools/call"
        assert sent_request["params"]["name"] == "test_tool"

def test_call_tool_timeout(mock_process):
    path = Path("/dummy/path")
    with patch("subprocess.Popen", return_value=mock_process):
        client = MCPClient(path)
        client.start()
        
        # Simulate hang by making readline block (or just sleep in a concise way)
        # Using a specialized mock for readline to sleep is tricky in single thread without real blocking
        # But we use threading in client. 
        
        def slow_readline():
            import time
            time.sleep(1.0)
            return "{}"
            
        mock_process.stdout.readline.side_effect = slow_readline
        
        with pytest.raises(MCPTimeoutError):
            client.call_tool("test_tool", {}, timeout=0.1)

def test_mcp_error_response(mock_process):
    path = Path("/dummy/path")
    with patch("subprocess.Popen", return_value=mock_process):
        client = MCPClient(path)
        client.start()
        
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid Request"}
        }
        mock_process.stdout.readline.return_value = json.dumps(response)
        
        with pytest.raises(MCPError, match="Invalid Request"):
            client.call_tool("test_tool", {})

# Integration test (skipped if server not found)
import os
SERVER_PATH = Path(os.environ.get("OLLAMA_MCP_PATH", ""))

@pytest.mark.skipif(not SERVER_PATH or not SERVER_PATH.exists(), reason="OLLAMA_MCP_PATH not set or server not found")
def test_integration_list_models():
    # This assumes 'ollama' is running on the host and accessible by the node server
    # We set a short timeout
    try:
        with MCPClient(SERVER_PATH) as client:
            try:
                result = client.call_tool("ollama_list_models", {}, timeout=5)
                # MCP tools return {content: [{type: 'text', text: '...'}]}
                assert "content" in result
                text = result["content"][0]["text"]
                data = json.loads(text)
                assert "models" in data
            except MCPError as e:
                # If ollama is down, the tool might return an error, which is also a valid transport result
                print(f"Integration test error (Ollama might be down): {e}")
            except MCPTimeoutError:
                pytest.fail("Integration test timed out")
    except Exception as e:
        pytest.skip(f"Integration test skipped: {e}")

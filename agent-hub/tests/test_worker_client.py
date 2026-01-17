import pytest
from unittest.mock import MagicMock
from pathlib import Path
from src.worker_client import WorkerClient
from src.mcp_client import MCPTimeoutError

@pytest.fixture
def mock_mcp():
    mcp = MagicMock()
    return mcp

@pytest.fixture
def contract():
    return {
        "task_id": "TEST-1",
        "project": "TEST",
        "specification": {
            "requirements": ["Do x"],
            "source_files": [],
            "target_file": "output.py"
        },
        "roles": {
            "implementer": "mock-impl",
            "local_reviewer": "mock-rev"
        },
        "limits": {
            "timeout_minutes": {"implementer": 1, "local_review": 1}
        }
    }

def test_implement_task_success(mock_mcp, contract, tmp_path):
    # Setup
    worker = WorkerClient(mock_mcp)
    
    # Mock MCP response
    code = "print('hello')"
    response_text = f"Here is the code:\n```python\n{code}\n```"
    mock_mcp.call_tool.return_value = {
        "content": [{"type": "text", "text": response_text}]
    }
    
    # Change CWD to tmp_path so atomic_write works there?
    # Actually worker_client uses atomic_write which uses Path objects.
    # The contract target_file is relative. 
    # We should run this test in a way that respects tmp_path for file writing.
    # We can patch safe_read/atomic_write or just ensure target_file is absolute.
    
    output_file = tmp_path / "output.py"
    contract["specification"]["target_file"] = str(output_file)
    
    result = worker.implement_task(contract)
    
    assert result["success"] is True
    assert result["files_changed"] == [str(output_file)]
    assert output_file.read_text().strip() == "print('hello')"

def test_implement_task_stall_empty(mock_mcp, contract):
    worker = WorkerClient(mock_mcp)
    mock_mcp.call_tool.return_value = {"content": [{"type": "text", "text": "   "}]}
    
    result = worker.implement_task(contract)
    assert result["success"] is False
    assert result["stall_reason"] == "empty_output"

def test_implement_task_stall_malformed(mock_mcp, contract):
    worker = WorkerClient(mock_mcp)
    mock_mcp.call_tool.return_value = {"content": [{"type": "text", "text": "No code block here"}]}
    
    result = worker.implement_task(contract)
    assert result["success"] is False
    assert result["stall_reason"] == "malformed_output"

def test_implement_task_timeout(mock_mcp, contract):
    worker = WorkerClient(mock_mcp)
    mock_mcp.call_tool.side_effect = MCPTimeoutError("Timeout")
    
    result = worker.implement_task(contract)
    assert result["success"] is False
    assert result["stall_reason"] == "timeout"

def test_run_local_review_critical(mock_mcp, contract):
    worker = WorkerClient(mock_mcp)
    
    json_resp = '{"verdict": "FAIL", "critical": true, "issues": ["secret found"]}'
    mock_mcp.call_tool.return_value = {
        "content": [{"type": "text", "text": json_resp}]
    }
    
    result = worker.run_local_review(contract, ["dummy.py"])
    
    assert result["passed"] is False
    assert result["critical"] is True
    assert "secret found" in result["issues"]

def test_check_health(mock_mcp):
    worker = WorkerClient(mock_mcp)
    
    # Healthy
    mock_mcp.call_tool.return_value = {"content": []}
    assert worker.check_ollama_health() is True
    
    # Unhealthy
    mock_mcp.call_tool.side_effect = MCPTimeoutError()
    assert worker.check_ollama_health() is False

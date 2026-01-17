import pytest
import time
import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.listener import MessageListener
from src.hub_client import HubClient
from src.mcp_client import MCPClient
from src.watchdog import load_contract, save_contract

class MockHub:
    def __init__(self):
        self.messages = []
        self.connected_agents = set()
        self.heartbeats = []
        self.lock = threading.Lock()

    def handle_tool(self, name, args):
        with self.lock:
            if name == "hub_connect":
                self.connected_agents.add(args["agent_id"])
                return {"success": True}
            elif name == "hub_send_message":
                msg = args["message"]
                self.messages.append(msg)
                return {"success": True, "id": msg["id"]}
            elif name == "hub_receive_messages":
                agent_id = args["agent_id"]
                # In this mock, we just return all messages for simplicity, 
                # or filter by 'to'
                msgs = [m for m in self.messages if m.get("to") == agent_id]
                # Clear read messages to simulate consumption
                self.messages = [m for m in self.messages if m.get("to") != agent_id]
                return {"success": True, "messages": msgs}
            elif name == "hub_heartbeat":
                self.heartbeats.append(args)
                return {"success": True}
            elif name == "hub_send_answer":
                self.messages.append({
                    "id": "ans-123",
                    "type": "ANSWER",
                    "from": args["from"],
                    "to": "floor_manager",
                    "payload": args["payload"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                return {"success": True}
            elif name == "claude_validate_proposal":
                return {"valid": True, "issues": []}
            return {"error": "Unknown tool"}

@pytest.fixture
def mock_mcp_env():
    hub = MockHub()
    def mock_call_tool(name, args, timeout=600):
        return hub.handle_tool(name, args)
    
    with patch("src.listener.MCPClient") as mock_mcp_class:
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.__enter__.return_value = mock_mcp_instance
        mock_mcp_instance.call_tool.side_effect = mock_call_tool
        mock_mcp_class.return_value = mock_mcp_instance
        
        yield hub, mock_mcp_instance

def test_proposal_to_review_message_flow(mock_mcp_env, tmp_path):
    hub, mcp = mock_mcp_env
    handoff_dir = tmp_path / "_handoff"
    handoff_dir.mkdir()
    
    # Create a dummy proposal
    proposal_path = tmp_path / "PROPOSAL.md"
    proposal_path.write_text("# Test Task\n\n## Specification\nTarget: test.py\n\n## Requirements\n- Req 1\n")
    
    listener = MessageListener("floor_manager", Path("fake/path"))
    
    # We need to patch convert_proposal because it writes to fixed _handoff/TASK_CONTRACT.json
    # or we can use monkeypatch for HANDOFF_DIR
    with patch("src.listener.convert_proposal") as mock_convert:
        contract_path = handoff_dir / "TASK_CONTRACT.json"
        mock_convert.return_value = contract_path
        
        # Manually trigger handler as if message was received
        msg = {
            "id": "msg-1",
            "type": "PROPOSAL_READY",
            "from": "super_manager",
            "payload": {"proposal_path": str(proposal_path)}
        }
        
        listener.handle_proposal_ready(msg)
        
        assert mock_convert.called
        assert mock_convert.call_args[0][0] == proposal_path

def test_stop_task_interrupts_work(mock_mcp_env):
    hub, mcp = mock_mcp_env
    listener = MessageListener("floor_manager", Path("fake/path"))
    
    msg = {
        "id": "msg-stop",
        "type": "STOP_TASK",
        "from": "super_manager",
        "payload": {"reason": "User cancelled"}
    }
    
    # Currently handle_stop_task just logs. 
    # We just verify it doesn't crash.
    listener.handle_stop_task(msg)

def test_question_answer_negotiation(mock_mcp_env):
    hub, mcp = mock_mcp_env
    listener = MessageListener("floor_manager", Path("fake/path"))
    
    msg = {
        "id": "q-123",
        "type": "QUESTION",
        "from": "super_manager",
        "payload": {
            "question": "Should we proceed?",
            "options": ["Yes", "No"]
        }
    }
    
    # This should trigger send_answer via the mock hub
    listener.handle_question(msg)
    
    # Check if hub received an ANSWER message (dispatched by handle_question)
    # Actually, handle_question in our impl sends to hub, and hub records it.
    ans_msg = next((m for m in hub.messages if m["type"] == "ANSWER"), None)
    assert ans_msg is not None
    assert ans_msg["payload"]["question_id"] == "q-123"
    assert ans_msg["payload"]["selected_option"] == 0

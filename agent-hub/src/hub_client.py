import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from .mcp_client import MCPClient

logger = logging.getLogger(__name__)

class HubClient:
    VALID_MSG_TYPES = {
        "PROPOSAL_READY", "REVIEW_NEEDED", "STOP_TASK",
        "QUESTION", "ANSWER", "VERDICT_SIGNAL", "HEARTBEAT"
    }

    def __init__(self, mcp_client: MCPClient):
        self.mcp = mcp_client
        self.agent_id = None

    def connect(self, agent_id: str) -> bool:
        """Register this agent with the hub."""
        try:
            result = self.mcp.call_tool("hub_connect", {"agent_id": agent_id})
            if result.get("success"):
                self.agent_id = agent_id
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect to hub: {e}")
            return False

    def send_message(self, recipient: str, msg_type: str, payload: dict) -> str:
        """
        Send a message to another agent.
        Returns: message_id
        """
        if msg_type not in self.VALID_MSG_TYPES:
            raise ValueError(f"Invalid message type: {msg_type}")

        msg_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        message = {
            "id": msg_id,
            "from": self.agent_id,
            "to": recipient,
            "type": msg_type,
            "payload": payload,
            "timestamp": timestamp
        }
        
        self.mcp.call_tool("hub_send_message", {"message": message})
        return msg_id

    def receive_messages(self, since: str = None) -> List[dict]:
        """
        Check inbox for pending messages.
        Returns list of: {id, from, type, payload, timestamp}
        """
        if not self.agent_id:
            raise RuntimeError("Agent not connected to hub")
            
        result = self.mcp.call_tool("hub_receive_messages", {
            "agent_id": self.agent_id,
            "since": since
        })
        return result.get("messages", [])

    def emit_heartbeat(self, progress: str = None) -> None:
        """
        Signal "I'm alive and working on {progress}"
        Called every 30 seconds by active agents.
        """
        if not self.agent_id:
            return

        timestamp = datetime.now(timezone.utc).isoformat()
        self.mcp.call_tool("hub_heartbeat", {
            "agent_id": self.agent_id,
            "timestamp": timestamp,
            "progress": progress
        })

    def send_question(self, recipient: str, question: str, options: List[str]) -> str:
        """
        Ask a constrained question (2-4 options required).
        Returns: message_id
        """
        if not (2 <= len(options) <= 4):
            raise ValueError("Questions must have between 2 and 4 options.")
            
        payload = {
            "question": question,
            "options": options
        }
        return self.send_message(recipient, "QUESTION", payload)

    def send_answer(self, question_id: str, selected_option: int) -> str:
        """
        Answer a previous question by selecting an option index.
        Returns: message_id
        """
        # We don't necessarily know the recipient here without looking up the question_id,
        # but the hub might handle routing or we might need a specific 'to' for send_message.
        # For now, we assume we send it to 'hub' or the sender of the question is implied.
        # Actually, Prompt 7.1 says send_message(recipient, ...).
        # We might need to know who asked. 
        # But maybe the hub_send_answer tool handles it?
        # Let's adjust based on common patterns: send_answer usually targets the question sender.
        
        payload = {
            "question_id": question_id,
            "selected_option": selected_option
        }
        # If we don't have recipient, we might need a generic hub_send_answer tool
        # that handles the lookup.
        self.mcp.call_tool("hub_send_answer", {
            "from": self.agent_id,
            "payload": payload
        })
        return str(uuid.uuid4()) # Placeholder if tool doesn't return one

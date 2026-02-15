import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from .mcp_client import MCPClient
from .utils import feature_flags
from . import mcp_connection_pool

logger = logging.getLogger(__name__)

class HubClient:
    VALID_MSG_TYPES = {
        "PROPOSAL_READY", "REVIEW_NEEDED", "STOP_TASK",
        "QUESTION", "ANSWER", "VERDICT_SIGNAL", "HEARTBEAT"
    }

    def __init__(self, mcp_client: Any):
        """
        Initialize HubClient.
        Args:
            mcp_client: Can be an MCPClient instance (legacy) or a Path to the hub server.
        """
        from pathlib import Path
        if isinstance(mcp_client, (str, Path)):
            self.hub_path = Path(mcp_client)
            self.mcp = None
        else:
            self.mcp = mcp_client
            self.hub_path = getattr(mcp_client, "server_path", None)
            
        self.agent_id = None

    def _get_mcp(self) -> MCPClient:
        """Get the appropriate MCP client based on feature flags."""
        if feature_flags.use_persistent_mcp():
            if not self.hub_path:
                raise ValueError("Hub path unknown, cannot use persistent MCP")
            return mcp_connection_pool.get_pool().get_client("hub", self.hub_path)
        
        if not self.mcp:
            raise ValueError("No MCP client provided and persistent MCP disabled")
        return self.mcp

    def connect(self, agent_id: str) -> bool:
        """Register this agent with the hub."""
        try:
            result = self._get_mcp().call_tool("hub_connect", {"agent_id": agent_id})
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
        Raises: RuntimeError if send fails
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
        
        result = self._get_mcp().call_tool("hub_send_message", {"message": message})
        # Check if the send was successful
        if not result or not result.get("success", True):
            error_msg = result.get("error", "Unknown error") if result else "No response from hub"
            raise RuntimeError(f"Failed to send message: {error_msg}")
        
        return msg_id

    def receive_messages(self, since: str = None) -> List[dict]:
        """
        Check inbox for pending messages.
        Returns list of: {id, from, type, payload, timestamp}
        """
        if not self.agent_id:
            raise RuntimeError("Agent not connected to hub")
            
        result = self._get_mcp().call_tool("hub_receive_messages", {
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
        self._get_mcp().call_tool("hub_heartbeat", {
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
        payload = {
            "question_id": question_id,
            "selected_option": selected_option
        }
        self._get_mcp().call_tool("hub_send_answer", {
            "from": self.agent_id,
            "payload": payload
        })
        return str(uuid.uuid4())

    # ===== Subagent Protocol Methods =====

    def ask_parent(self, question: str, run_id: str | None = None) -> str:
        """
        Worker asks a question and waits for parent response.
        Returns message_id that can be used to check for answer.
        """
        from .state_adapter import get_state_adapter

        effective_run_id = run_id or self.agent_id or "default"
        adapter = get_state_adapter()
        return adapter.ask_parent(
            run_id=effective_run_id,
            subagent_id=self.agent_id or "unknown",
            question=question
        )

    def check_answer(self, message_id: str) -> str | None:
        """
        Check if a question has been answered.
        Returns the answer string, or None if still pending.
        """
        from .state_adapter import get_state_adapter

        adapter = get_state_adapter()
        return adapter.check_answer(message_id)

    def get_pending_questions(self, run_id: str | None = None) -> List[dict]:
        """
        Get all pending questions for this run.
        Used by parent/manager to see what workers need.
        """
        from .state_adapter import get_state_adapter

        adapter = get_state_adapter()
        return adapter.get_pending_questions(run_id)

    def reply_to_worker(self, message_id: str, answer: str) -> bool:
        """
        Parent replies to a worker's question.
        Returns True if successful.
        """
        from .state_adapter import get_state_adapter

        adapter = get_state_adapter()
        return adapter.reply_to_worker(message_id, answer)

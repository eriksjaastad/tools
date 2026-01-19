"""
Bidirectional Messaging - Ask/Reply protocol for agent communication.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from .message_bus import MessageBus

logger = logging.getLogger(__name__)

class BidirectionalMessenger:
    """
    FR-3.1: Protocol for workers to ask clarifying questions.
    """

    def __init__(self, message_bus: MessageBus):
        self.bus = message_bus

    def ask_parent(self, from_agent: str, to_agent: str, question: str, context: Optional[Dict] = None, run_id: Optional[str] = None) -> str:
        """
        Worker asks parent for clarification.
        """
        payload = {
            "question": question,
            "context": context or {},
            "asked_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id
        }
        msg_id = self.bus.send_message(
            msg_type="QUESTION",
            from_agent=from_agent,
            to_agent=to_agent,
            payload=payload
        )
        logger.info(f"Question sent ({msg_id}): {question[:50]}...")
        return msg_id

    def reply_to_worker(self, from_agent: str, to_agent: str, message_id: str, answer: str) -> str:
        """
        Parent provides answer to worker's question.
        """
        payload = {
            "question_id": message_id,
            "answer": answer,
            "answered_at": datetime.now(timezone.utc).isoformat()
        }
        # Mark the original question as read (handled)
        self.bus.mark_read(message_id)
        
        # Send the answer message
        reply_id = self.bus.send_message(
            msg_type="ANSWER",
            from_agent=from_agent,
            to_agent=to_agent,
            payload=payload
        )
        logger.info(f"Reply sent for {message_id}")
        return reply_id

    def check_answer(self, agent_id: str, message_id: str) -> Optional[str]:
        """
        Worker checks if answer is available for their question.
        """
        messages = self.bus.get_messages(to_agent=agent_id)
        for msg in messages:
            if msg["type"] == "ANSWER" and msg["payload"].get("question_id") == message_id:
                self.bus.mark_read(msg["id"])
                return msg["payload"]["answer"]
        return None

    def get_pending_questions(self, agent_id: str, run_id: Optional[str] = None) -> List[Dict]:
        """
        Parent retrieves unanswered questions.
        """
        messages = self.bus.get_messages(to_agent=agent_id)
        candidates = [msg for msg in messages if msg["type"] == "QUESTION"]
        
        if run_id:
            candidates = [msg for msg in candidates if msg["payload"].get("run_id") == run_id]
            
        return candidates

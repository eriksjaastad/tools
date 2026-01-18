"""
State Adapter - Abstract interface for hub state management.

Allows switching between file-based (legacy) and SQLite (new) backends.
Feature flag: UAS_SQLITE_BUS
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from .utils import feature_flags

logger = logging.getLogger(__name__)


class StateAdapter(ABC):
    """Abstract base class for state storage backends."""

    @abstractmethod
    def ask_parent(self, run_id: str, subagent_id: str, question: str) -> str:
        """Submit a question. Returns message_id."""
        pass

    @abstractmethod
    def reply_to_worker(self, message_id: str, answer: str) -> bool:
        """Answer a question. Returns success."""
        pass

    @abstractmethod
    def check_answer(self, message_id: str) -> str | None:
        """Check for answer. Returns answer or None."""
        pass

    @abstractmethod
    def get_pending_questions(self, run_id: str | None = None) -> list[dict]:
        """Get pending questions."""
        pass

    @abstractmethod
    def send_message(self, sender: str, recipient: str, msg_type: str, payload: dict) -> str:
        """Send a hub message. Returns message_id."""
        pass

    @abstractmethod
    def receive_messages(self, agent_id: str, since: str | None = None) -> list[dict]:
        """Receive messages for an agent."""
        pass

    @abstractmethod
    def record_heartbeat(self, agent_id: str, progress: str | None = None) -> None:
        """Record agent heartbeat."""
        pass


class SQLiteStateAdapter(StateAdapter):
    """SQLite-backed state adapter (new, recommended)."""

    def __init__(self, db_path: Path | str | None = None):
        from .message_bus import MessageBus
        self._bus = MessageBus(db_path)

    def ask_parent(self, run_id: str, subagent_id: str, question: str) -> str:
        return self._bus.ask_parent(run_id, subagent_id, question)

    def reply_to_worker(self, message_id: str, answer: str) -> bool:
        return self._bus.reply_to_worker(message_id, answer)

    def check_answer(self, message_id: str) -> str | None:
        return self._bus.check_answer(message_id)

    def get_pending_questions(self, run_id: str | None = None) -> list[dict]:
        return self._bus.get_pending_questions(run_id)

    def send_message(self, sender: str, recipient: str, msg_type: str, payload: dict) -> str:
        return self._bus.send_hub_message(sender, recipient, msg_type, payload)

    def receive_messages(self, agent_id: str, since: str | None = None) -> list[dict]:
        return self._bus.receive_hub_messages(agent_id, since)

    def record_heartbeat(self, agent_id: str, progress: str | None = None) -> None:
        self._bus.record_heartbeat(agent_id, progress)


class LegacyFileStateAdapter(StateAdapter):
    """
    File-based state adapter (legacy, for backwards compatibility).

    Uses JSON files for storage. NOT recommended for production due to
    concurrency issues, but useful for tests and simple cases.
    """

    def __init__(self, state_dir: Path | str | None = None):
        self.state_dir = Path(state_dir) if state_dir else Path("data/state")
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self._messages_file = self.state_dir / "messages.json"
        self._questions_file = self.state_dir / "questions.json"
        self._heartbeats_file = self.state_dir / "heartbeats.json"

        # Initialize files if they don't exist
        for f in [self._messages_file, self._questions_file, self._heartbeats_file]:
            if not f.exists():
                f.write_text("[]" if f != self._heartbeats_file else "{}")

    def _read_json(self, path: Path) -> Any:
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return [] if "questions" in str(path) or "messages" in str(path) else {}

    def _write_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, indent=2))

    def ask_parent(self, run_id: str, subagent_id: str, question: str) -> str:
        import uuid
        questions = self._read_json(self._questions_file)

        message_id = str(uuid.uuid4())
        questions.append({
            "message_id": message_id,
            "run_id": run_id,
            "subagent_id": subagent_id,
            "question": question,
            "answer": None,
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        self._write_json(self._questions_file, questions)
        return message_id

    def reply_to_worker(self, message_id: str, answer: str) -> bool:
        questions = self._read_json(self._questions_file)

        for q in questions:
            if q["message_id"] == message_id and q["status"] == "PENDING":
                q["answer"] = answer
                q["status"] = "ANSWERED"
                self._write_json(self._questions_file, questions)
                return True

        return False

    def check_answer(self, message_id: str) -> str | None:
        questions = self._read_json(self._questions_file)

        for q in questions:
            if q["message_id"] == message_id:
                if q["status"] == "ANSWERED":
                    q["status"] = "RETRIEVED"
                    self._write_json(self._questions_file, questions)
                    return q["answer"]
                return None

        return None

    def get_pending_questions(self, run_id: str | None = None) -> list[dict]:
        questions = self._read_json(self._questions_file)
        pending = [q for q in questions if q["status"] == "PENDING"]

        if run_id:
            pending = [q for q in pending if q["run_id"] == run_id]

        return pending

    def send_message(self, sender: str, recipient: str, msg_type: str, payload: dict) -> str:
        import uuid
        messages = self._read_json(self._messages_file)

        msg_id = str(uuid.uuid4())
        messages.append({
            "id": msg_id,
            "from": sender,
            "to": recipient,
            "type": msg_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "read": False
        })

        self._write_json(self._messages_file, messages)
        return msg_id

    def receive_messages(self, agent_id: str, since: str | None = None) -> list[dict]:
        messages = self._read_json(self._messages_file)

        result = []
        for msg in messages:
            if msg["to"] == agent_id and not msg["read"]:
                if since and msg["timestamp"] <= since:
                    continue
                msg["read"] = True
                result.append(msg)

        self._write_json(self._messages_file, messages)
        return result

    def record_heartbeat(self, agent_id: str, progress: str | None = None) -> None:
        heartbeats = self._read_json(self._heartbeats_file)
        heartbeats[agent_id] = {
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "progress": progress
        }
        self._write_json(self._heartbeats_file, heartbeats)


def get_state_adapter(db_path: Path | str | None = None) -> StateAdapter:
    """
    Get the appropriate state adapter based on feature flags.

    Set UAS_SQLITE_BUS=1 to use SQLite backend.
    """
    if feature_flags.is_enabled("SQLITE_BUS"):
        logger.info("Using SQLite state adapter")
        return SQLiteStateAdapter(db_path)
    else:
        logger.info("Using legacy file state adapter")
        return LegacyFileStateAdapter()

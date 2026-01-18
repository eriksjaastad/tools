"""
SQLite Message Bus for bi-directional agent communication.

Replaces file-based hub_state.json with reliable SQLite storage.
"""

import sqlite3
import uuid
import logging
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from contextlib import contextmanager
from enum import Enum

logger = logging.getLogger(__name__)

# Default database location
DEFAULT_DB_PATH = Path("data/hub.db")


class MessageStatus(Enum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    RETRIEVED = "RETRIEVED"
    EXPIRED = "EXPIRED"


class MessageBus:
    """
    SQLite-backed message bus for agent communication.

    Usage:
        bus = MessageBus()

        # Worker asks a question
        msg_id = bus.ask_parent(run_id="task-123", subagent_id="worker-1", question="How should I handle errors?")

        # Parent checks for pending questions
        pending = bus.get_pending_questions(run_id="task-123")

        # Parent replies
        bus.reply_to_worker(message_id=msg_id, answer="Use try/except with logging")

        # Worker retrieves answer
        answer = bus.check_answer(message_id=msg_id)
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS subagent_messages (
        message_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        subagent_id TEXT NOT NULL,
        question TEXT NOT NULL,
        answer TEXT,
        status TEXT DEFAULT 'PENDING',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_run_id ON subagent_messages(run_id);
    CREATE INDEX IF NOT EXISTS idx_status ON subagent_messages(status);
    CREATE INDEX IF NOT EXISTS idx_subagent_id ON subagent_messages(subagent_id);

    CREATE TABLE IF NOT EXISTS hub_messages (
        id TEXT PRIMARY KEY,
        sender TEXT NOT NULL,
        recipient TEXT NOT NULL,
        msg_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        read INTEGER DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_recipient ON hub_messages(recipient, read);

    CREATE TABLE IF NOT EXISTS agent_heartbeats (
        agent_id TEXT PRIMARY KEY,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        progress TEXT
    );
    """

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level="IMMEDIATE"  # Prevents write conflicts
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ===== Subagent Protocol Methods =====

    def ask_parent(self, run_id: str, subagent_id: str, question: str) -> str:
        """
        Worker asks a question. Returns message_id.
        Creates a PENDING message that the parent can answer.
        """
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO subagent_messages
                   (message_id, run_id, subagent_id, question, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'PENDING', ?, ?)""",
                (message_id, run_id, subagent_id, question, now, now)
            )

        logger.info(f"Worker {subagent_id} asked: {question[:50]}...")
        return message_id

    def reply_to_worker(self, message_id: str, answer: str) -> bool:
        """
        Parent provides an answer to a pending question.
        Returns True if successful.
        """
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                """UPDATE subagent_messages
                   SET answer = ?, status = 'ANSWERED', updated_at = ?
                   WHERE message_id = ? AND status = 'PENDING'""",
                (answer, now, message_id)
            )
            success = cursor.rowcount > 0

        if success:
            logger.info(f"Replied to message {message_id}")
        else:
            logger.warning(f"No pending message found with id {message_id}")

        return success

    def check_answer(self, message_id: str) -> str | None:
        """
        Worker checks if their question has been answered.
        Returns the answer if available, None if still pending.
        Moves status to RETRIEVED on successful retrieval.
        """
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT answer, status FROM subagent_messages WHERE message_id = ?",
                (message_id,)
            ).fetchone()

            if not row:
                return None

            if row["status"] == "ANSWERED":
                conn.execute(
                    """UPDATE subagent_messages
                       SET status = 'RETRIEVED', updated_at = ?
                       WHERE message_id = ?""",
                    (now, message_id)
                )
                return row["answer"]

            return None

    def get_pending_questions(self, run_id: str | None = None) -> list[dict]:
        """
        Get all pending questions, optionally filtered by run_id.
        """
        with self._get_connection() as conn:
            if run_id:
                rows = conn.execute(
                    """SELECT message_id, run_id, subagent_id, question, created_at
                       FROM subagent_messages
                       WHERE status = 'PENDING' AND run_id = ?
                       ORDER BY created_at ASC""",
                    (run_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT message_id, run_id, subagent_id, question, created_at
                       FROM subagent_messages
                       WHERE status = 'PENDING'
                       ORDER BY created_at ASC"""
                ).fetchall()

        return [dict(row) for row in rows]

    # ===== Hub Message Methods (existing functionality) =====

    def send_hub_message(self, sender: str, recipient: str, msg_type: str, payload: dict) -> str:
        """Send a message through the hub."""
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO hub_messages (id, sender, recipient, msg_type, payload, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (msg_id, sender, recipient, msg_type, json.dumps(payload), now)
            )

        return msg_id

    def receive_hub_messages(self, agent_id: str, since: str | None = None) -> list[dict]:
        """Receive messages for an agent."""
        with self._get_connection() as conn:
            if since:
                rows = conn.execute(
                    """SELECT id, sender, recipient, msg_type, payload, timestamp
                       FROM hub_messages
                       WHERE recipient = ? AND read = 0 AND timestamp > ?
                       ORDER BY timestamp ASC""",
                    (agent_id, since)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, sender, recipient, msg_type, payload, timestamp
                       FROM hub_messages
                       WHERE recipient = ? AND read = 0
                       ORDER BY timestamp ASC""",
                    (agent_id,)
                ).fetchall()

            # Mark as read
            msg_ids = [row["id"] for row in rows]
            if msg_ids:
                placeholders = ",".join("?" * len(msg_ids))
                conn.execute(
                    f"UPDATE hub_messages SET read = 1 WHERE id IN ({placeholders})",
                    msg_ids
                )

        return [
            {
                "id": row["id"],
                "from": row["sender"],
                "to": row["recipient"],
                "type": row["msg_type"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["timestamp"]
            }
            for row in rows
        ]

    def record_heartbeat(self, agent_id: str, progress: str | None = None) -> None:
        """Record an agent heartbeat."""
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO agent_heartbeats (agent_id, last_seen, progress)
                   VALUES (?, ?, ?)""",
                (agent_id, now, progress)
            )

    def get_agent_status(self) -> list[dict]:
        """Get status of all known agents."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT agent_id, last_seen, progress FROM agent_heartbeats ORDER BY last_seen DESC"
            ).fetchall()

        return [dict(row) for row in rows]

    def expire_old_messages(self, max_age_hours: int = 24) -> int:
        """Mark old PENDING messages as EXPIRED. Returns count."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                """UPDATE subagent_messages
                   SET status = 'EXPIRED'
                   WHERE status = 'PENDING' AND created_at < ?""",
                (cutoff,)
            )
            return cursor.rowcount


# Global instance
_message_bus: MessageBus | None = None

def get_message_bus(db_path: Path | str | None = None) -> MessageBus:
    """Get the global message bus instance."""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus(db_path)
    return _message_bus

"""
Message Bus - SQLite-backed communication hub.
"""

import sqlite3
import json
import logging
import uuid
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/hub.db")

# Global singleton
_instance: Optional["MessageBus"] = None

def get_message_bus(db_path: Path | str | None = None) -> "MessageBus":
    global _instance
    if _instance is None:
        _instance = MessageBus(db_path)
    return _instance

class MessageBus:
    """
    FR-3.2: SQLite-backed message bus.
    Reliable, persistent, and concurrent.
    """

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            db_path = os.getenv("UAS_DB_PATH", DEFAULT_DB_PATH)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._migrate_if_needed()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            
            # messages table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
              id TEXT PRIMARY KEY,
              type TEXT NOT NULL,
              from_agent TEXT NOT NULL,
              to_agent TEXT NOT NULL,
              payload TEXT,  -- JSON
              timestamp TEXT NOT NULL,
              read INTEGER DEFAULT 0
            );
            """)
            
            # subagent_messages table (FR-3.2)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS subagent_messages (
                message_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                subagent_id TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # heartbeats table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS heartbeats (
              agent_id TEXT PRIMARY KEY,
              progress TEXT,
              timestamp TEXT NOT NULL
            );
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_agent);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);")
            conn.commit()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate_if_needed(self):
        """
        Migrate from file-based hub_state.json if it exists and DB is empty.
        """
        state_file = Path("hub_state.json")
        if not state_file.exists():
            return

        with self._get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            if count > 0:
                return

            logger.info("Migrating from hub_state.json to SQLite...")
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
                    messages = state.get("messages", [])
                    for msg in messages:
                        conn.execute(
                            "INSERT OR IGNORE INTO messages (id, type, from_agent, to_agent, payload, timestamp, read) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (msg.get("id"), msg.get("type"), msg.get("from"), msg.get("to"), json.dumps(msg.get("payload")), msg.get("timestamp"), 1)
                        )
                logger.info(f"Migrated {len(messages)} messages.")
            except Exception as e:
                logger.error(f"Migration failed: {e}")

    def ask_parent(self, run_id: str, subagent_id: str, question: str) -> str:
        msg_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO subagent_messages (message_id, run_id, subagent_id, question, status) VALUES (?, ?, ?, ?, ?)",
                (msg_id, run_id, subagent_id, question, "PENDING")
            )
            conn.commit()
        return msg_id

    def reply_to_worker(self, message_id: str, answer: str) -> bool:
        with self._get_connection() as conn:
            res = conn.execute(
                "UPDATE subagent_messages SET answer = ?, status = 'ANSWERED' WHERE message_id = ? AND status = 'PENDING'",
                (answer, message_id)
            )
            conn.commit()
            return res.rowcount > 0

    def check_answer(self, message_id: str) -> str | None:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT answer FROM subagent_messages WHERE message_id = ? AND status = 'ANSWERED'",
                (message_id,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE subagent_messages SET status = 'RETRIEVED' WHERE message_id = ?",
                    (message_id,)
                )
                conn.commit()
                return row["answer"]
        return None

    def get_pending_questions(self, run_id: str | None = None) -> List[Dict]:
        with self._get_connection() as conn:
            if run_id:
                cursor = conn.execute(
                    "SELECT * FROM subagent_messages WHERE run_id = ? AND status = 'PENDING'",
                    (run_id,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM subagent_messages WHERE status = 'PENDING'"
                )
            return [dict(r) for r in cursor.fetchall()]

    def send_hub_message(self, from_agent: str, to_agent: str, msg_type: str, payload: Dict) -> str:
        return self.send_message(msg_type, from_agent, to_agent, payload)

    def receive_hub_messages(self, agent_id: str, since: Optional[str] = None) -> List[Dict]:
        messages = self.get_messages(agent_id, since)
        for msg in messages:
            self.mark_read(msg["id"])
        return messages

    def record_heartbeat(self, agent_id: str, progress: str):
        self.update_heartbeat(agent_id, progress)

    def send_message(self, msg_type: str, from_agent: str, to_agent: str, payload: Dict) -> str:
        msg_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (id, type, from_agent, to_agent, payload, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, msg_type, from_agent, to_agent, json.dumps(payload), timestamp)
            )
            conn.commit()
        return msg_id

    def get_messages(self, to_agent: str, since: Optional[str] = None) -> List[Dict]:
        query = "SELECT * FROM messages WHERE to_agent = ? AND read = 0"
        params = [to_agent]
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        
        results = []
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            for row in cursor:
                msg = dict(row)
                msg["payload"] = json.loads(msg["payload"])
                # Alias id to message_id for compatibility
                msg["message_id"] = msg["id"]
                results.append(msg)
        return results

    def mark_read(self, message_id: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE messages SET read = 1 WHERE id = ?", (message_id,))
            conn.commit()

    def update_heartbeat(self, agent_id: str, progress: str):
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO heartbeats (agent_id, progress, timestamp) VALUES (?, ?, ?)",
                (agent_id, progress, timestamp)
            )
            conn.commit()

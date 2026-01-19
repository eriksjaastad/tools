"""
SQLite Message Bus - Persistent, concurrent-safe message storage.
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/hub.db")

class MessageBus:
    """
    FR-3.2: SQLite-backed message bus.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._migrate_if_needed()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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

    def _migrate_if_needed(self):
        """
        Migrate from file-based hub_state.json if it exists and DB is empty.
        """
        state_file = Path("hub_state.json")
        if not state_file.exists():
            return

        with sqlite3.connect(self.db_path) as conn:
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

    def send_message(self, msg_type: str, from_agent: str, to_agent: str, payload: Dict) -> str:
        import uuid
        msg_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (id, type, from_agent, to_agent, payload, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, msg_type, from_agent, to_agent, json.dumps(payload), timestamp)
            )
        return msg_id

    def get_messages(self, to_agent: str, since: Optional[str] = None) -> List[Dict]:
        query = "SELECT * FROM messages WHERE to_agent = ? AND read = 0"
        params = [to_agent]
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        
        results = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            for row in cursor:
                msg = dict(row)
                msg["payload"] = json.loads(msg["payload"])
                results.append(msg)
        return results

    def mark_read(self, message_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE messages SET read = 1 WHERE id = ?", (message_id,))

    def update_heartbeat(self, agent_id: str, progress: str):
        timestamp = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO heartbeats (agent_id, progress, timestamp) VALUES (?, ?, ?)",
                (agent_id, progress, timestamp)
            )

    def get_heartbeats(self) -> Dict[str, Dict]:
        results = {}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM heartbeats")
            for row in cursor:
                results[row["agent_id"]] = dict(row)
        return results

import sqlite3
import logging
from typing import List, Dict, Optional
from .config import TRACKER_DB

logger = logging.getLogger("librarian-mcp")

class TrackerDB:
    def __init__(self, db_path: str = str(TRACKER_DB)):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_project(self, name: str) -> Optional[Dict]:
        if not self.conn: self.connect()
        cursor = self.conn.execute("SELECT * FROM projects WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_projects(self) -> List[Dict]:
        if not self.conn: self.connect()
        cursor = self.conn.execute("SELECT * FROM projects")
        return [dict(row) for row in cursor.fetchall()]

    def search_projects(self, query: str) -> List[Dict]:
        if not self.conn: self.connect()
        search_pattern = f"%{query}%"
        cursor = self.conn.execute(
            "SELECT * FROM projects WHERE name LIKE ? OR description LIKE ?",
            (search_pattern, search_pattern)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_dependencies(self, project: str) -> Dict[str, List[str]]:
        if not self.conn: self.connect()
        
        # Upstream: what this project depends on
        cursor = self.conn.execute(
            "SELECT dependency FROM service_dependencies WHERE project = ?",
            (project,)
        )
        upstream = [row["dependency"] for row in cursor.fetchall()]
        
        # Downstream: what depends on this project
        cursor = self.conn.execute(
            "SELECT project FROM service_dependencies WHERE dependency = ?",
            (project,)
        )
        downstream = [row["project"] for row in cursor.fetchall()]
        
        return {
            "upstream": upstream,
            "downstream": downstream
        }

    def get_ai_agents(self, project: Optional[str] = None) -> List[Dict]:
        if not self.conn: self.connect()
        if project:
            cursor = self.conn.execute("SELECT * FROM ai_agents WHERE project = ?", (project,))
        else:
            cursor = self.conn.execute("SELECT * FROM ai_agents")
        return [dict(row) for row in cursor.fetchall()]

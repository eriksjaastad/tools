import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger("librarian-mcp")

MAX_CACHED = int(os.environ.get("LIBRARIAN_MAX_CACHED", "10000"))

class MemoryDB:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.environ.get("LIBRARIAN_MEMORY_DB_PATH", str(Path.home() / ".librarian" / "memory.db"))
        
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE NOT NULL,
                    query_text TEXT NOT NULL,
                    answer TEXT,
                    ask_count INTEGER DEFAULT 1,
                    first_asked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_asked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cached_at TIMESTAMP,
                    compute_time_ms INTEGER,
                    cache_hits INTEGER DEFAULT 0,
                    confidence REAL,
                    tier TEXT DEFAULT 'cold'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_query_hash ON query_memory(query_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tier ON query_memory(tier)")
            conn.commit()

    def get_query_stats(self, query_hash: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT * FROM query_memory WHERE query_hash = ?", (query_hash,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def lookup_exact(self, query_hash: str) -> Optional[Dict[str, Any]]:
        """Exact match lookup. Returns record if found and not stale."""
        stats = self.get_query_stats(query_hash)
        if stats and stats["answer"]:
            if not self.is_stale(stats):
                return stats
            else:
                # Mark as stale / clear answer
                self.clear_cache(query_hash)
        return None

    def clear_cache(self, query_hash: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE query_memory SET answer = NULL, cached_at = NULL, tier = 'cold' WHERE query_hash = ?", (query_hash,))
            conn.commit()

    def record_query(self, query_text: str, query_hash: str, compute_time_ms: int = 0):
        with self._get_conn() as conn:
            stats = self.get_query_stats(query_hash)
            if stats:
                conn.execute("""
                    UPDATE query_memory 
                    SET ask_count = ask_count + 1, 
                        last_asked = CURRENT_TIMESTAMP,
                        compute_time_ms = ?
                    WHERE query_hash = ?
                """, (compute_time_ms, query_hash))
            else:
                conn.execute("""
                    INSERT INTO query_memory (query_text, query_hash, compute_time_ms)
                    VALUES (?, ?, ?)
                """, (query_text, query_hash, compute_time_ms))
            conn.commit()

    def update_answer(self, query_hash: str, answer: str, tier: str = 'warm'):
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE query_memory 
                SET answer = ?, tier = ?, cached_at = CURRENT_TIMESTAMP
                WHERE query_hash = ?
            """, (answer, tier, query_hash))
            conn.commit()

    def record_hit(self, query_hash: str):
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE query_memory 
                SET cache_hits = cache_hits + 1,
                    last_asked = CURRENT_TIMESTAMP
                WHERE query_hash = ?
            """, (query_hash,))
            conn.commit()

    def get_hit_count(self, query_hash: str) -> int:
        stats = self.get_query_stats(query_hash)
        return stats["ask_count"] if stats else 0

    def promote_tier(self, query_hash: str):
        stats = self.get_query_stats(query_hash)
        if not stats: return
        
        count = stats["ask_count"]
        current_tier = stats["tier"]
        
        new_tier = current_tier
        if count >= 10:
            new_tier = "core"
        elif count >= 4:
            new_tier = "hot"
        elif count >= 2:
            new_tier = "warm"
            
        if new_tier != current_tier:
            with self._get_conn() as conn:
                conn.execute("UPDATE query_memory SET tier = ? WHERE query_hash = ?", (new_tier, query_hash))
                conn.commit()
            logger.info(f"Promoted query {query_hash[:8]} to {new_tier}")

    def is_stale(self, stats: Dict[str, Any]) -> bool:
        """Check if cached answer has expired based on tier."""
        if not stats.get("cached_at") or not stats.get("answer"):
            return True
            
        ttls = {
            "cold": 24,
            "warm": 72,
            "hot": 168,
            "core": 720 # 30 days
        }
        
        ttl_hours = ttls.get(stats["tier"], 24)
        try:
            cached_at = datetime.fromisoformat(stats["cached_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            try:
                # Handle SQLite CURRENT_TIMESTAMP format (YYYY-MM-DD HH:MM:SS)
                cached_at = datetime.strptime(stats["cached_at"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                return True
            
        age = datetime.utcnow() - cached_at
        return (age.total_seconds() / 3600) > ttl_hours

    def get_all_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM query_memory").fetchone()[0]
            by_tier = conn.execute("SELECT tier, COUNT(*) FROM query_memory GROUP BY tier").fetchall()
            hits = conn.execute("SELECT SUM(cache_hits), SUM(ask_count) FROM query_memory").fetchone()
            avg_comp = conn.execute("SELECT AVG(compute_time_ms) FROM query_memory WHERE compute_time_ms > 0").fetchone()[0]
            
            return {
                "total_memories": total,
                "by_tier": {row[0]: row[1] for row in by_tier},
                "cache_hit_rate": (hits[0] / hits[1]) if hits and hits[1] else 0,
                "avg_compute_time_ms": avg_comp or 0
            }

    def forget_query(self, query_hash: str):
        self.clear_cache(query_hash)

    def forget_topic(self, topic: str):
        with self._get_conn() as conn:
            pattern = f"%{topic}%"
            conn.execute("UPDATE query_memory SET answer = NULL, cached_at = NULL, tier = 'cold' WHERE query_text LIKE ?", (pattern,))
            conn.commit()

    def evict_if_needed(self):
        """Evict oldest warm/cold entries if over limit."""
        with self._get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM query_memory WHERE answer IS NOT NULL").fetchone()[0]
            if count > MAX_CACHED:
                # Evict enough to get back under limit plus a small buffer (10% of MAX_CACHED)
                buffer = max(1, MAX_CACHED // 10)
                to_evict = count - MAX_CACHED + buffer
                conn.execute("""
                    DELETE FROM query_memory WHERE id IN (
                        SELECT id FROM query_memory
                        WHERE answer IS NOT NULL AND tier IN ('cold', 'warm')
                        ORDER BY last_asked ASC
                        LIMIT ?
                    )
                """, (to_evict,))
                conn.commit()
                logger.info(f"Evicted {to_evict} stale memories")

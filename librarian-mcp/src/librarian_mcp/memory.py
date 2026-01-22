import logging
import os
import sqlite3
import json
import numpy as np
from typing import List, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger("librarian-mcp")

class MemoryStore:
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            storage_path = os.environ.get("LIBRARIAN_CHROMA_PATH", str(Path.home() / ".librarian" / "vectors.db"))
        
        # Ensure we use a db file if it was pointing to a directory
        if os.path.isdir(storage_path):
            self.db_path = os.path.join(storage_path, "vectors.db")
        else:
            self.db_path = storage_path
            
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        logger.info(f"MemoryStore (Lite) initialized at {self.db_path}")

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def add_search_result(self, query: str, answer: str, embedding: List[float], metadata: Dict[str, Any]):
        """
        Store a query/answer pair with its embedding in SQLite.
        """
        import uuid
        import numpy as np
        doc_id = str(uuid.uuid4())
        
        # Convert embedding to numpy blob for storage
        emb_array = np.array(embedding, dtype=np.float32)
        emb_blob = emb_array.tobytes()
        
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO embeddings (id, query, answer, embedding, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_id, query, answer, emb_blob, json.dumps(metadata)))
            conn.commit()
        logger.debug(f"Stored semantic cache for query: {query[:50]}...")

    def search_similar(self, embedding: List[float], threshold: float = 0.25) -> Optional[Dict[str, Any]]:
        """
        Search for similar queries using cosine distance in SQLite + Numpy.
        threshold: 0.25 (75% similarity)
        """
        target_emb = np.array(embedding, dtype=np.float32)
        
        best_match = None
        min_distance = 2.0 # Max cosine distance is 2.0
        
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT query, answer, embedding, metadata FROM embeddings")
            for row in cursor:
                query_text, answer, emb_blob, meta_json = row
                
                # Load embedding from blob
                db_emb = np.frombuffer(emb_blob, dtype=np.float32)
                
                # Compute Cosine Distance
                # distance = 1 - cosine_similarity
                # cos_sim = (A . B) / (||A|| ||B||)
                norm_a = np.linalg.norm(target_emb)
                norm_b = np.linalg.norm(db_emb)
                
                if norm_a == 0 or norm_b == 0:
                    distance = 2.0
                else:
                    cos_sim = np.dot(target_emb, db_emb) / (norm_a * norm_b)
                    distance = 1.0 - cos_sim
                
                if distance < threshold and distance < min_distance:
                    min_distance = distance
                    best_match = {
                        "query": query_text,
                        "answer": answer,
                        "distance": float(distance),
                        "metadata": json.loads(meta_json) if meta_json else {}
                    }
        
        return best_match

    def delete_by_query(self, query: str):
        """Remove a specific query from memory."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM embeddings WHERE query = ?", (query,))
            conn.commit()

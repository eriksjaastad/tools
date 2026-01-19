import logging
import requests
from typing import List, Optional

logger = logging.getLogger("librarian-mcp")

class EmbeddingService:
    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.ollama_host = ollama_host
        self.model = "nomic-embed-text"

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using Ollama's embeddings endpoint.
        """
        try:
            url = f"{self.ollama_host}/api/embeddings"
            results = []
            
            # Ollama /api/embeddings handles one at a time usually, 
            # or sometimes a list depending on version. 
            # To be safe and compatible, we'll loop if needed or try batch.
            
            payload = {
                "model": self.model,
                "prompt": texts[0] if len(texts) == 1 else texts # Some versions take list
            }
            
            # NOTE: For now we implement a simple single-query version 
            # used for the L2 cache lookup.
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if "embedding" in data:
                return [data["embedding"]]
            elif "embeddings" in data:
                return data["embeddings"]
            
            return []
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []

    def get_single_embedding(self, text: str) -> Optional[List[float]]:
        """Convienience method for single text."""
        res = self.get_embeddings([text])
        return res[0] if res else None

"""
AI Router - Cost-optimized routing between local Ollama and cloud AI models

Automatically routes requests to:
- Local (free): llama3.2 via Ollama
- Cheap cloud: gpt-4o-mini
- Expensive cloud: gpt-4o

With automatic escalation on failures or poor responses.
"""

from .router import AIRouter, AIResult, Tier

__all__ = ["AIRouter", "AIResult", "Tier"]
__version__ = "1.0.0"


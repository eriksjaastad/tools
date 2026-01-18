"""
Ollama HTTP Client - Direct API access with connection pooling.

Replaces subprocess spawning for 10x faster inference.
Feature flag: UAS_OLLAMA_HTTP
"""

import os
import httpx
import json
from typing import Generator
from . import cost_logger
from .utils import timing

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "5m")

# Connection pool - reused across calls
_client: httpx.Client | None = None

def get_client() -> httpx.Client:
    """Get or create the shared HTTP client with connection pooling."""
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=OLLAMA_BASE_URL,
            timeout=httpx.Timeout(OLLAMA_TIMEOUT),
            limits=httpx.Limits(max_keepalive_connections=5),
        )
    return _client

def chat(
    model: str,
    messages: list[dict],
    stream: bool = False,
    keep_alive: str | None = None,
) -> dict | Generator[dict, None, None]:
    """
    Send chat completion request to Ollama.

    Args:
        model: Model name (e.g., "llama3.2:1b")
        messages: List of {"role": "...", "content": "..."} dicts
        stream: If True, yields chunks as they arrive
        keep_alive: Override default keep_alive (e.g., "5m", "0", "-1")

    Returns:
        Full response dict if stream=False, generator if stream=True
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "keep_alive": keep_alive or OLLAMA_KEEP_ALIVE,
    }

    client = get_client()

    if stream:
        # Note: Cost logging for streaming is more complex, 
        # usually handled by the caller or a wrapper.
        return _stream_response(client, payload)
    else:
        with timing.measure_latency() as t:
            try:
                response = client.post("/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                
                # Log success
                cost_logger.log_model_call(
                    model=model,
                    tokens_in=data.get("prompt_eval_count", 0),
                    tokens_out=data.get("eval_count", 0),
                    latency_ms=t["latency_ms"],
                    success=True
                )
                return data
            except Exception as e:
                # Log failure
                cost_logger.log_model_call(
                    model=model,
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=t["latency_ms"],
                    success=False,
                    error=str(e)
                )
                raise

def _stream_response(client: httpx.Client, payload: dict) -> Generator[dict, None, None]:
    """Stream response chunks from Ollama."""
    with client.stream("POST", "/api/chat", json=payload) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                yield json.loads(line)

def list_models() -> list[dict]:
    """List available models."""
    client = get_client()
    response = client.get("/api/tags")
    response.raise_for_status()
    return response.json().get("models", [])

def is_model_loaded(model: str) -> bool:
    """Check if a model is currently loaded in memory."""
    client = get_client()
    response = client.get("/api/ps")
    response.raise_for_status()
    running = response.json().get("models", [])
    # Partial matching or exact? API usually returns exact but with :tag
    # We'll check for both
    return any(m.get("name") == model or m.get("name", "").split(":")[0] == model.split(":")[0] for m in running)

def unload_model(model: str) -> None:
    """Unload a model from memory (for memory pressure scenarios)."""
    chat(model, [{"role": "user", "content": ""}], keep_alive="0")

def close() -> None:
    """Close the HTTP client (call on shutdown)."""
    global _client
    if _client:
        _client.close()
        _client = None

"""Calls one model with one prompt. LiteLLM for cloud, httpx for Ollama."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx

from .registry import ModelEntry


@dataclass
class CallResult:
    """Result of a single model call."""

    model_id: str
    response: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    error: str | None = None


# ── Ollama client (connection pooled) ─────────────────────────────────────────

_ollama_client: httpx.Client | None = None


def _get_ollama_client() -> httpx.Client:
    global _ollama_client
    if _ollama_client is None:
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        _ollama_client = httpx.Client(
            base_url=host,
            timeout=httpx.Timeout(120.0),
            limits=httpx.Limits(max_keepalive_connections=5),
        )
    return _ollama_client


def _call_ollama(model: ModelEntry, prompt: str, timeout_seconds: int) -> CallResult:
    """Call Ollama via direct HTTP."""
    # Strip "ollama/" prefix for the API call
    model_name = model.id.removeprefix("ollama/")
    client = _get_ollama_client()
    # Local models need extra time for cold loads (model swap into GPU memory)
    effective_timeout = max(timeout_seconds, 120)
    client.timeout = httpx.Timeout(float(effective_timeout))

    start = time.perf_counter()
    try:
        r = client.post(
            "/api/chat",
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "keep_alive": "5m",
            },
        )
        r.raise_for_status()
        data = r.json()
        latency_ms = int((time.perf_counter() - start) * 1000)

        return CallResult(
            model_id=model.id,
            response=data.get("message", {}).get("content", ""),
            latency_ms=latency_ms,
            tokens_in=data.get("prompt_eval_count", 0),
            tokens_out=data.get("eval_count", 0),
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return CallResult(
            model_id=model.id,
            response="",
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            error=str(e),
        )


def _call_litellm(model: ModelEntry, prompt: str, timeout_seconds: int) -> CallResult:
    """Call cloud model via LiteLLM."""
    import litellm

    start = time.perf_counter()
    try:
        response = litellm.completion(
            model=model.id,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout_seconds,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        content = response.choices[0].message.content or ""
        usage = response.usage

        return CallResult(
            model_id=model.id,
            response=content,
            latency_ms=latency_ms,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return CallResult(
            model_id=model.id,
            response="",
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            error=str(e),
        )


# ── Public API ────────────────────────────────────────────────────────────────


def call_model(model: ModelEntry, prompt: str, timeout_seconds: int = 30) -> CallResult:
    """Call a model with a prompt. Routes to Ollama or LiteLLM based on provider."""
    if model.provider == "ollama":
        return _call_ollama(model, prompt, timeout_seconds)
    return _call_litellm(model, prompt, timeout_seconds)


def close():
    """Clean up HTTP clients."""
    global _ollama_client
    if _ollama_client:
        _ollama_client.close()
        _ollama_client = None

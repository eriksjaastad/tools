"""Calls one model with one prompt. LiteLLM for cloud, httpx for Ollama."""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path

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
    artifact: bytes | None = None
    artifact_mime_type: str | None = None


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


def _read_image(path: Path) -> tuple[str, bytes]:
    """Read one bounded local image for a multimodal model request."""
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise ValueError(f"image is not a file: {path}")
        size = resolved.stat().st_size
        if size > 25 * 1024 * 1024:
            raise ValueError(f"image exceeds 25 MiB request limit: {path}")
        mime_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        if not mime_type.startswith("image/"):
            raise ValueError(f"unsupported image MIME type for {path}: {mime_type}")
        return mime_type, resolved.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read image {path}: {exc}") from exc


def _litellm_content(prompt: str, image_paths: list[Path]) -> str | list[dict]:
    if not image_paths:
        return prompt
    content: list[dict] = [{"type": "text", "text": prompt}]
    for path in image_paths:
        mime_type, payload = _read_image(path)
        encoded = base64.b64encode(payload).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
            }
        )
    return content


def _call_ollama(
    model: ModelEntry,
    prompt: str,
    timeout_seconds: int,
    image_paths: list[Path],
) -> CallResult:
    """Call Ollama via direct HTTP."""
    # Strip "ollama/" prefix for the API call
    model_name = model.id.removeprefix("ollama/")
    client = _get_ollama_client()
    # Local models need extra time for cold loads (model swap into GPU memory)
    effective_timeout = max(timeout_seconds, 120)
    client.timeout = httpx.Timeout(float(effective_timeout))

    start = time.perf_counter()
    try:
        message: dict = {"role": "user", "content": prompt}
        if image_paths:
            message["images"] = [
                base64.b64encode(_read_image(path)[1]).decode("ascii")
                for path in image_paths
            ]
        r = client.post(
            "/api/chat",
            json={
                "model": model_name,
                "messages": [message],
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
    except Exception as e:  # noqa: BLE001 - provider failures become run evidence
        latency_ms = int((time.perf_counter() - start) * 1000)
        return CallResult(
            model_id=model.id,
            response="",
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            error=str(e),
        )


def _call_litellm(
    model: ModelEntry,
    prompt: str,
    timeout_seconds: int,
    image_paths: list[Path],
    parameters: dict[str, object],
) -> CallResult:
    """Call cloud model via LiteLLM."""
    import litellm

    start = time.perf_counter()
    try:
        response = litellm.completion(
            model=model.id,
            messages=[
                {"role": "user", "content": _litellm_content(prompt, image_paths)}
            ],
            timeout=timeout_seconds,
            **parameters,
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
    except Exception as e:  # noqa: BLE001 - LiteLLM errors are not uniform
        latency_ms = int((time.perf_counter() - start) * 1000)
        return CallResult(
            model_id=model.id,
            response="",
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            error=str(e),
        )


def _call_stability(model: ModelEntry, prompt: str, timeout_seconds: int) -> CallResult:
    """Call Stability's image endpoint and retain the returned artifact bytes."""
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        return CallResult(
            model_id=model.id,
            response="",
            latency_ms=0,
            tokens_in=0,
            tokens_out=0,
            error="STABILITY_API_KEY is not configured",
        )

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=httpx.Timeout(float(timeout_seconds))) as client:
            response = client.post(
                "https://api.stability.ai/v2beta/stable-image/generate/core",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "image/*",
                },
                data={"prompt": prompt, "output_format": "png", "aspect_ratio": "1:1"},
                files={"none": ("", b"")},
            )
            response.raise_for_status()
        return CallResult(
            model_id=model.id,
            response="",
            latency_ms=int((time.perf_counter() - start) * 1000),
            tokens_in=0,
            tokens_out=0,
            artifact=response.content,
            artifact_mime_type=response.headers.get("content-type", "image/png").split(
                ";"
            )[0],
        )
    except Exception as exc:  # noqa: BLE001 - provider failures become run evidence
        return CallResult(
            model_id=model.id,
            response="",
            latency_ms=int((time.perf_counter() - start) * 1000),
            tokens_in=0,
            tokens_out=0,
            error=str(exc),
        )


# ── Public API ────────────────────────────────────────────────────────────────


def call_model(
    model: ModelEntry,
    prompt: str,
    timeout_seconds: int = 30,
    *,
    image_paths: list[Path] | None = None,
    parameters: dict[str, object] | None = None,
) -> CallResult:
    """Call a model with a prompt. Routes to Ollama or LiteLLM based on provider."""
    image_paths = image_paths or []
    parameters = parameters or {}
    if model.provider == "ollama":
        return _call_ollama(model, prompt, timeout_seconds, image_paths)
    if model.provider == "stability-ai":
        if image_paths:
            return CallResult(
                model_id=model.id,
                response="",
                latency_ms=0,
                tokens_in=0,
                tokens_out=0,
                error="image-generation seats do not accept input images",
            )
        return _call_stability(model, prompt, timeout_seconds)
    return _call_litellm(model, prompt, timeout_seconds, image_paths, parameters)


def close():
    """Clean up HTTP clients."""
    global _ollama_client
    if _ollama_client:
        _ollama_client.close()
        _ollama_client = None

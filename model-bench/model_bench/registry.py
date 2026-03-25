"""Model registry — which models to benchmark, pricing, and judge config."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Try to import pricing from route tool for cost estimates
_ROUTE_PRICING_AVAILABLE = False
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "route"))
    from pricing import get_model_pricing, compute_shadow_cost

    _ROUTE_PRICING_AVAILABLE = True
except ImportError:
    pass


@dataclass
class ModelEntry:
    """A model available for benchmarking."""

    id: str  # LiteLLM model ID or Ollama model name
    display_name: str
    provider: str  # "ollama", "anthropic", "openai", "google"
    tier: str  # "local", "cheap", "mid"
    enabled: bool = True
    # For cost estimation — per 1M tokens. Overridden by route/pricing.py if available.
    input_cost_per_1m: float = 0.0
    output_cost_per_1m: float = 0.0


# ── Models to benchmark ──────────────────────────────────────────────────────

MODELS: list[ModelEntry] = [
    # Local (free) — Ollama aliases
    ModelEntry(
        id="ollama/coding:current",
        display_name="coding:current (Qwen2.5-Coder 14B)",
        provider="ollama",
        tier="local",
    ),
    # ModelEntry(
    #     id="ollama/reviewing:current",
    #     display_name="reviewing:current (Qwen2.5-Coder 32B)",
    #     provider="ollama",
    #     tier="local",
    # ),  # Too big for laptop — enable on Mac Mini
    ModelEntry(
        id="ollama/reasoning:current",
        display_name="reasoning:current (Llama3.2 Vision 11B)",
        provider="ollama",
        tier="local",
    ),
    # Cheap cloud
    ModelEntry(
        id="claude-haiku-4-5-20251001",
        display_name="Haiku 4.5",
        provider="anthropic",
        tier="cheap",
        input_cost_per_1m=0.80,
        output_cost_per_1m=4.00,
    ),
    ModelEntry(
        id="gpt-4.1-mini",
        display_name="GPT-4.1 Mini",
        provider="openai",
        tier="cheap",
        input_cost_per_1m=0.40,
        output_cost_per_1m=1.60,
    ),
    ModelEntry(
        id="gemini/gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        provider="google",
        tier="cheap",
        input_cost_per_1m=0.15,
        output_cost_per_1m=0.60,
    ),
    # Mid cloud
    ModelEntry(
        id="gemini/gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider="google",
        tier="mid",
        input_cost_per_1m=1.25,
        output_cost_per_1m=10.00,
    ),
]

# ── Judge config ──────────────────────────────────────────────────────────────

JUDGE_MODEL = "claude-opus-4-6"  # Via Claude Code subscription — no API cost


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_enabled_models() -> list[ModelEntry]:
    """Return all enabled models."""
    return [m for m in MODELS if m.enabled]


def get_models_by_ids(ids: list[str]) -> list[ModelEntry]:
    """Return models matching the given IDs (exact or partial match)."""
    result = []
    for model_id in ids:
        for m in MODELS:
            # Match on full ID or display name (case-insensitive)
            if model_id == m.id or model_id.lower() in m.id.lower() or model_id.lower() in m.display_name.lower():
                if m not in result:
                    result.append(m)
    return result


def estimate_cost(model: ModelEntry, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a model call."""
    if model.provider == "ollama":
        return 0.0

    # Try route/pricing.py first for accurate data
    if _ROUTE_PRICING_AVAILABLE:
        cost = compute_shadow_cost(
            model_id=model.id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        if cost > 0:
            return cost

    # Fallback to registry-level pricing
    return (input_tokens / 1e6) * model.input_cost_per_1m + (output_tokens / 1e6) * model.output_cost_per_1m


def is_ollama_available() -> bool:
    """Check if Ollama is reachable."""
    import httpx

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        r = httpx.get(f"{host}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def list_ollama_models() -> list[str]:
    """Return names of locally installed Ollama models."""
    import httpx

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        r = httpx.get(f"{host}/api/tags", timeout=5.0)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []

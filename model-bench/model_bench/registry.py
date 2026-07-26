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
    from pricing import compute_shadow_cost, get_model_pricing

    _ROUTE_PRICING_AVAILABLE = True
except ImportError:
    _ROUTE_PRICING_AVAILABLE = False


@dataclass
class ModelEntry:
    """A model available for benchmarking."""

    id: str  # LiteLLM model ID or Ollama model name
    display_name: str
    provider: str  # "ollama", "anthropic", "openai", "google", "xai"
    tier: str  # "local", "cheap", "mid"
    enabled: bool = True
    # For cost estimation — per 1M tokens. Overridden by route/pricing.py if available.
    input_cost_per_1m: float = 0.0
    output_cost_per_1m: float = 0.0
    capabilities: frozenset[str] = field(
        default_factory=lambda: frozenset({"json_mode", "long_context"})
    )


# ── Models to benchmark ──────────────────────────────────────────────────────

MODELS: list[ModelEntry] = [
    # Cheap cloud
    ModelEntry(
        id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        provider="openai",
        tier="cheap",
        input_cost_per_1m=0.15,
        output_cost_per_1m=0.60,
        capabilities=frozenset({"json_mode", "long_context", "vision"}),
    ),
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
        capabilities=frozenset({"json_mode", "long_context", "vision"}),
    ),
    ModelEntry(
        id="gemini/gemini-3.5-flash",
        display_name="Gemini 3.5 Flash",
        provider="google",
        tier="cheap",
        input_cost_per_1m=1.50,
        output_cost_per_1m=9.00,
        capabilities=frozenset({"json_mode", "long_context", "vision"}),
    ),
    ModelEntry(
        # Routed via OpenRouter (was xai/ direct — the xAI-direct key in auxesis:prd
        # is invalid; OpenRouter's key covers all cheap models with one credential).
        # xAI aliases for this model: grok-code-fast-1 / grok-code-fast.
        id="openrouter/x-ai/grok-build-0.1",
        display_name="Grok Build 0.1",
        provider="openrouter",
        tier="cheap",
        input_cost_per_1m=1.00,
        output_cost_per_1m=2.00,
    ),
    ModelEntry(
        id="openrouter/deepseek/deepseek-v3.2",
        display_name="DeepSeek V3.2 (open-weight)",
        provider="openrouter",
        tier="cheap",
        input_cost_per_1m=0.23,
        output_cost_per_1m=0.34,
    ),
    ModelEntry(
        id="openrouter/qwen/qwen3-coder",
        display_name="Qwen3-Coder (open-weight)",
        provider="openrouter",
        tier="cheap",
        input_cost_per_1m=0.22,
        output_cost_per_1m=1.80,
    ),
    # Mid cloud
    ModelEntry(
        id="gemini/gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider="google",
        tier="mid",
        input_cost_per_1m=1.25,
        output_cost_per_1m=10.00,
        capabilities=frozenset({"json_mode", "long_context", "vision"}),
    ),
    ModelEntry(
        id="openrouter/z-ai/glm-5.2",
        display_name="GLM-5.2 (Z.ai, open-weight)",
        provider="openrouter",
        tier="mid",
        input_cost_per_1m=1.40,
        output_cost_per_1m=4.40,
    ),
    ModelEntry(
        id="openrouter/x-ai/grok-4.3",
        display_name="Grok 4.3 (xAI, current flagship)",
        provider="openrouter",
        tier="mid",
        input_cost_per_1m=1.25,
        output_cost_per_1m=2.50,
    ),
    # Frontier — the top-tier reference line (what the cheap models are measured against)
    ModelEntry(
        id="claude-opus-4-8",
        display_name="Opus 4.8 (Anthropic frontier)",
        provider="anthropic",
        tier="frontier",
        input_cost_per_1m=5.00,
        output_cost_per_1m=25.00,
        capabilities=frozenset({"json_mode", "long_context", "vision"}),
    ),
    ModelEntry(
        id="gpt-5.5",
        display_name="GPT-5.5 (OpenAI, daily driver)",
        provider="openai",
        tier="frontier",
        input_cost_per_1m=5.00,
        output_cost_per_1m=30.00,
        capabilities=frozenset({"json_mode", "long_context", "vision"}),
    ),
]

# ── Judge config ──────────────────────────────────────────────────────────────

JUDGE_MODEL = os.getenv("MODEL_BENCH_JUDGE_MODEL", "gpt-5.5")


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
            matches = (
                model_id == m.id
                or model_id.lower() in m.id.lower()
                or model_id.lower() in m.display_name.lower()
            )
            if matches and m not in result:
                result.append(m)
    return result


def resolve_models(ids: list[str]) -> list[ModelEntry]:
    """Resolve each requested selector to exactly one enabled registry model."""
    resolved: list[ModelEntry] = []
    for selector in ids:
        normalized = selector.casefold()
        exact = [
            model
            for model in get_enabled_models()
            if normalized in {model.id.casefold(), model.display_name.casefold()}
        ]
        matches = exact or [
            model
            for model in get_enabled_models()
            if normalized in model.id.casefold()
            or normalized in model.display_name.casefold()
        ]
        if not matches:
            raise ValueError(f"unknown model selector: {selector!r}")
        if len(matches) > 1:
            raise ValueError(
                f"ambiguous model selector {selector!r}; matches "
                f"{sorted(model.id for model in matches)}"
            )
        if matches[0] not in resolved:
            resolved.append(matches[0])
    return resolved


def get_models_for_capabilities(required: list[str] | set[str]) -> list[ModelEntry]:
    """Return enabled candidates that provide every model-native capability."""
    required_set = set(required)
    return [m for m in get_enabled_models() if required_set <= m.capabilities]


def model_from_pin(
    pin: dict,
    *,
    required_capabilities: list[str] | set[str] = (),
) -> ModelEntry:
    """Build an incumbent model entry without changing the project-owned pin.

    Existing registry entries are reused when their provider/model identity
    matches. Otherwise the exact project pin is adapted to LiteLLM's provider
    prefixes. A project's incumbent is assumed to provide the capabilities its
    own seat declares; whether the local/provider transport is reachable is a
    separate run-time concern recorded in the result.
    """
    provider = str(pin["provider"]).strip().lower()
    model = str(pin["model"]).strip()

    for entry in MODELS:
        if entry.provider == provider and (
            entry.id == model
            or entry.id.removeprefix(f"{provider}/") == model
            or entry.id.endswith(f"/{model}")
        ):
            return entry

    if provider == "google" and not model.startswith("gemini/"):
        model_id = f"gemini/{model}"
    elif provider in {
        "ollama",
        "xai",
        "stability-ai",
        "mlx_lm",
    } and not model.startswith(f"{provider}/"):
        model_id = f"{provider}/{model}"
    else:
        model_id = model

    return ModelEntry(
        id=model_id,
        display_name=f"{model} (current pin)",
        provider=provider,
        tier="incumbent",
        capabilities=frozenset(required_capabilities),
    )


def estimate_cost(model: ModelEntry, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a model call."""
    if model.provider == "ollama":
        return 0.0

    # Try route/pricing.py first for accurate data
    if _ROUTE_PRICING_AVAILABLE and get_model_pricing(model.id) is not None:
        return compute_shadow_cost(
            model_id=model.id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # Fallback to registry-level pricing
    if model.input_cost_per_1m <= 0 and model.output_cost_per_1m <= 0:
        raise ValueError(f"pricing is unavailable for {model.id}")
    return (input_tokens / 1e6) * model.input_cost_per_1m + (
        output_tokens / 1e6
    ) * model.output_cost_per_1m


def is_ollama_available() -> bool:
    """Check if Ollama is reachable."""
    import httpx

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        r = httpx.get(f"{host}/api/tags", timeout=3.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def list_ollama_models() -> list[str]:
    """Return names of locally installed Ollama models."""
    import httpx

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        r = httpx.get(f"{host}/api/tags", timeout=5.0)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return []

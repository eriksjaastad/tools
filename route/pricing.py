#!/usr/bin/env python3
"""
Shadow pricing engine for the route CLI.

Loads model registry and computes shadow costs for AI CLI sessions.
Shadow cost represents what the usage would have cost at pay-per-token rates.
"""

import json
from pathlib import Path
from typing import Optional


# Module-level registry cache
_registry: Optional[dict] = None


def load_registry(path: str | None = None) -> dict:
    """
    Load model registry from JSON file.

    Args:
        path: Path to model_registry.json. If None, uses model_registry.json
              in the same directory as this module.

    Returns:
        Parsed registry dictionary with 'models' and 'subscriptions' keys.

    Raises:
        FileNotFoundError: If registry file not found.
        json.JSONDecodeError: If registry JSON is malformed.
    """
    global _registry

    if path is None:
        path = Path(__file__).parent / "model_registry.json"
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Model registry not found at {path}")

    with open(path, "r") as f:
        _registry = json.load(f)

    return _registry


def _ensure_registry_loaded() -> dict:
    """Ensure registry is loaded, loading it if necessary."""
    global _registry
    if _registry is None:
        load_registry()
    return _registry


def get_model_pricing(model_id: str) -> Optional[dict]:
    """
    Look up pricing for a model ID.

    Args:
        model_id: Model identifier (e.g., "claude-opus-4-6").

    Returns:
        Dictionary with keys: input_usd, cached_input_usd, output_usd, provider.
        Returns None if model not found.
    """
    registry = _ensure_registry_loaded()

    for model in registry.get("models", []):
        if model.get("model_id") == model_id:
            pricing = model.get("pricing_per_1M", {}).copy()
            pricing["provider"] = model.get("provider", "unknown")
            return pricing

    return None


def compute_shadow_cost(
    model_id: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """
    Compute shadow cost in USD for token usage.

    Shadow cost represents the pay-per-token cost that would apply to this usage.

    Args:
        model_id: Model identifier (e.g., "claude-opus-4-6").
        input_tokens: Number of input tokens (non-cached).
        output_tokens: Number of output tokens.
        cache_read_tokens: Number of cache read tokens (reads from prompt cache).
        cache_write_tokens: Number of cache write tokens (writes to prompt cache).

    Returns:
        Total shadow cost in USD. Returns 0.0 if model not found.

    Formula:
        cost = (input_tokens / 1e6) * input_rate
             + (output_tokens / 1e6) * output_rate
             + (cache_read_tokens / 1e6) * cached_input_rate
             + (cache_write_tokens / 1e6) * cache_write_rate

        For Anthropic models: cache_write_rate = input_rate * 1.25
        For other providers: cache_write_rate = input_rate (default, no premium)
    """
    pricing = get_model_pricing(model_id)
    if pricing is None:
        return 0.0

    # Handle None/zero values
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    cache_read_tokens = cache_read_tokens or 0
    cache_write_tokens = cache_write_tokens or 0

    input_rate = pricing.get("input_usd", 0.0)
    cached_input_rate = pricing.get("cached_input_usd", 0.0)
    output_rate = pricing.get("output_usd", 0.0)
    provider = pricing.get("provider", "unknown")

    # Cache write rate: 125% for Anthropic, 100% for others
    if provider == "anthropic":
        cache_write_rate = input_rate * 1.25
    else:
        cache_write_rate = input_rate

    cost = (
        (input_tokens / 1e6) * input_rate
        + (output_tokens / 1e6) * output_rate
        + (cache_read_tokens / 1e6) * cached_input_rate
        + (cache_write_tokens / 1e6) * cache_write_rate
    )

    return cost


def compute_subscription_value(subscription_name: str, shadow_cost: float) -> dict:
    """
    Compare shadow cost to subscription price.

    Args:
        subscription_name: Name of subscription (e.g., "claude_max").
        shadow_cost: Shadow cost of session in USD.

    Returns:
        Dictionary with keys:
            - subscription: Subscription name
            - monthly_cost: Monthly subscription cost in USD
            - shadow_cost: Shadow cost in USD
            - multiplier: How many times the monthly cost was used (shadow_cost / monthly_cost)
            - savings: Negative value if saving money, positive if over cost

    Raises:
        KeyError: If subscription not found in registry.
    """
    registry = _ensure_registry_loaded()
    subscriptions = registry.get("subscriptions", {})

    if subscription_name not in subscriptions:
        raise KeyError(f"Subscription '{subscription_name}' not found in registry")

    sub = subscriptions[subscription_name]
    monthly_cost = sub.get("cost_usd_monthly", 0.0)

    multiplier = shadow_cost / monthly_cost if monthly_cost > 0 else float("inf")
    savings = shadow_cost - monthly_cost  # Negative if saving money

    return {
        "subscription": subscription_name,
        "monthly_cost": monthly_cost,
        "shadow_cost": shadow_cost,
        "multiplier": multiplier,
        "savings": savings,
    }


def format_cost(usd: float) -> str:
    """
    Format USD amount as a string.

    Args:
        usd: Amount in USD.

    Returns:
        Formatted string like "$0.02", "$1.45", "$7,015.00".
    """
    if usd < 0:
        return f"-${abs(usd):,.2f}"
    return f"${usd:,.2f}"


if __name__ == "__main__":
    # Demonstrate computing shadow costs
    print("Shadow Pricing Engine Demo")
    print("=" * 60)

    # Load registry
    registry = load_registry()
    print(f"\nLoaded registry with {len(registry['models'])} models")
    print(f"Subscriptions: {', '.join(registry['subscriptions'].keys())}\n")

    # Example 1: Claude Opus session
    print("Example 1: Claude Opus 4.6 Session")
    print("-" * 60)
    model_id = "claude-opus-4-6"
    input_tokens = 250_000
    output_tokens = 50_000
    cache_read_tokens = 100_000
    cache_write_tokens = 75_000

    shadow_cost = compute_shadow_cost(
        model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )

    print(f"Model: {model_id}")
    print(f"  Input tokens: {input_tokens:,}")
    print(f"  Output tokens: {output_tokens:,}")
    print(f"  Cache read tokens: {cache_read_tokens:,}")
    print(f"  Cache write tokens: {cache_write_tokens:,}")
    print(f"  Shadow cost: {format_cost(shadow_cost)}")

    # Compare to subscription
    sub_value = compute_subscription_value("claude_max", shadow_cost)
    print(f"\nSubscription: {sub_value['subscription']}")
    print(f"  Monthly cost: {format_cost(sub_value['monthly_cost'])}")
    print(f"  Session value: {format_cost(sub_value['shadow_cost'])}")
    print(f"  Multiplier: {sub_value['multiplier']:.2f}x monthly")
    print(f"  Savings: {format_cost(sub_value['savings'])}")

    # Example 2: Haiku session (cheap model)
    print("\n\nExample 2: Claude Haiku 4.5 Session")
    print("-" * 60)
    model_id = "claude-haiku-4-5"
    input_tokens = 1_000_000
    output_tokens = 100_000
    cache_read_tokens = 0
    cache_write_tokens = 0

    shadow_cost = compute_shadow_cost(
        model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    print(f"Model: {model_id}")
    print(f"  Input tokens: {input_tokens:,}")
    print(f"  Output tokens: {output_tokens:,}")
    print(f"  Shadow cost: {format_cost(shadow_cost)}")

    # Example 3: Model not in registry
    print("\n\nExample 3: Unknown Model")
    print("-" * 60)
    cost = compute_shadow_cost("unknown-model-xyz", input_tokens=100_000)
    print(f"Model: unknown-model-xyz")
    print(f"  Input tokens: 100,000")
    print(f"  Shadow cost: {format_cost(cost)} (model not found)")

    # Example 4: Zero tokens
    print("\n\nExample 4: Zero Tokens")
    print("-" * 60)
    cost = compute_shadow_cost("claude-opus-4-6")
    print(f"Model: claude-opus-4-6")
    print(f"  Shadow cost: {format_cost(cost)} (no usage)")

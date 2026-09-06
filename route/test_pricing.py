from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model-bench"))
sys.path.insert(0, str(ROOT / "route"))

from model_bench.registry import MODELS
from pricing import compute_shadow_cost, get_model_pricing, load_registry


@pytest.fixture(autouse=True)
def registry():
    """Every test uses the checked-in registry, independent of module cache state."""
    return load_registry(ROOT / "route" / "model_registry.json")


def test_cloud_benchmark_models_have_route_pricing():
    missing = [
        model.id
        for model in MODELS
        if model.provider != "ollama" and get_model_pricing(model.id) is None
    ]

    assert missing == []


# Standard input, cached read, output USD/MTok verified against the provider
# sources in README.md on 2026-09-06. These expectations are independent of
# registry contents, so a typo or blanket cache discount cannot bless itself.
VERIFIED_RATES = [
    ("claude-opus-4-8", 5, 0.5, 25),
    ("gpt-5.5", 5, 0.5, 30),
    ("claude-haiku-4-5-20251001", 1, 0.1, 5),
    ("gpt-4.1-mini", 0.4, 0.1, 1.6),
    ("gemini/gemini-2.5-flash", 0.3, 0.03, 2.5),
    ("gemini/gemini-2.5-pro", 1.25, 0.125, 10),
    ("openrouter/x-ai/grok-4.3", 1.25, 0.2, 2.5),
    ("openrouter/x-ai/grok-build-0.1", 1, 0.2, 2),
    ("openrouter/z-ai/glm-5.2", 0.966, 0.1932, 3.036),
    ("openrouter/deepseek/deepseek-v3.2", 0.269, 0.1345, 0.4),
    ("openrouter/qwen/qwen3-coder", 0.3, 0.1, 1),
    ("gpt-4o-mini", 0.15, 0.075, 0.6),
    ("gemini/gemini-3.5-flash", 1.5, 0.15, 9),
    ("claude-opus-5", 5, 0.5, 25),
    ("claude-sonnet-5", 2, 0.2, 10),
]


@pytest.mark.parametrize("model_id,input_rate,cache_rate,output_rate", VERIFIED_RATES)
def test_verified_standard_and_cache_rates(model_id, input_rate, cache_rate, output_rate):
    assert compute_shadow_cost(model_id, input_tokens=1_000_000) == pytest.approx(input_rate)
    assert compute_shadow_cost(model_id, cache_read_tokens=1_000_000) == pytest.approx(cache_rate)
    assert compute_shadow_cost(model_id, output_tokens=1_000_000) == pytest.approx(output_rate)


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("claude-opus-4-8", 2.01875),
        ("claude-opus-5", 2.01875),
        ("claude-sonnet-5", 0.8075),
        ("claude-haiku-4-5-20251001", 0.40375),
    ],
)
def test_anthropic_mixed_usage_includes_five_minute_cache_write_premium(model_id, expected):
    # 125K ordinary input + 40K output + 100K cache reads + 55K new cache tokens.
    assert compute_shadow_cost(
        model_id,
        input_tokens=125_000,
        output_tokens=40_000,
        cache_read_tokens=100_000,
        cache_write_tokens=55_000,
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("gpt-4o-mini", 0.0585),
        ("gpt-4.1-mini", 0.146),
        ("gemini/gemini-3.5-flash", 0.645),
        ("openrouter/x-ai/grok-build-0.1", 0.28),
    ],
)
def test_other_providers_mixed_usage_uses_input_rate_for_writes(model_id, expected):
    assert compute_shadow_cost(
        model_id,
        input_tokens=125_000,
        output_tokens=40_000,
        cache_read_tokens=100_000,
        cache_write_tokens=55_000,
    ) == pytest.approx(expected)


@pytest.mark.parametrize("model_id", [rates[0] for rates in VERIFIED_RATES])
def test_zero_usage_is_free(model_id):
    assert compute_shadow_cost(model_id) == 0.0


def test_optional_missing_usage_remains_zero():
    assert compute_shadow_cost(
        "claude-sonnet-5", input_tokens=None, output_tokens=None,
        cache_read_tokens=None, cache_write_tokens=None,
    ) == 0.0


def test_unknown_model_behavior_is_unchanged():
    assert get_model_pricing("unknown-model-xyz") is None
    assert compute_shadow_cost(
        "unknown-model-xyz", input_tokens=1_000_000, output_tokens=1_000_000,
        cache_read_tokens=1_000_000, cache_write_tokens=1_000_000,
    ) == 0.0

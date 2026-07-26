from __future__ import annotations

import pytest

from model_bench.registry import (
    ModelEntry,
    estimate_cost,
    get_models_for_capabilities,
    model_from_pin,
    resolve_models,
)


def test_capability_filter_requires_every_model_native_capability() -> None:
    vision = get_models_for_capabilities({"vision", "json_mode"})
    assert vision
    assert all({"vision", "json_mode"} <= model.capabilities for model in vision)
    assert all("image_generation" not in model.capabilities for model in vision)
    assert get_models_for_capabilities({"image_generation"}) == []


def test_model_from_pin_preserves_exact_incumbent_identity() -> None:
    incumbent = model_from_pin(
        {
            "provider": "stability-ai",
            "model": "stable-image-core",
        },
        required_capabilities={"image_generation"},
    )

    assert incumbent.id == "stability-ai/stable-image-core"
    assert incumbent.provider == "stability-ai"
    assert incumbent.tier == "incumbent"
    assert incumbent.capabilities == frozenset({"image_generation"})


def test_model_from_pin_reuses_matching_registry_entry() -> None:
    incumbent = model_from_pin(
        {"provider": "anthropic", "model": "claude-opus-4-8"},
        required_capabilities={"long_context"},
    )

    assert incumbent.id == "claude-opus-4-8"
    assert incumbent.display_name == "Opus 4.8 (Anthropic frontier)"


def test_model_from_google_pin_reuses_prefixed_priced_entry() -> None:
    incumbent = model_from_pin(
        {"provider": "google", "model": "gemini-3.5-flash"},
        required_capabilities={"long_context"},
    )

    assert incumbent.id == "gemini/gemini-3.5-flash"
    assert incumbent.tier == "cheap"
    assert incumbent.input_cost_per_1m > 0


def test_strict_model_resolution_rejects_ambiguous_partial_selector() -> None:
    with pytest.raises(ValueError, match="ambiguous model selector"):
        resolve_models(["gemini"])


def test_strict_model_resolution_accepts_exact_id() -> None:
    assert [model.id for model in resolve_models(["gemini/gemini-3.5-flash"])] == [
        "gemini/gemini-3.5-flash"
    ]


def test_unknown_cloud_pricing_is_not_silently_reported_as_free() -> None:
    unknown = ModelEntry(
        id="unknown-cloud-model",
        display_name="unknown",
        provider="unknown",
        tier="incumbent",
    )

    with pytest.raises(ValueError, match="pricing is unavailable"):
        estimate_cost(unknown, 100, 20)

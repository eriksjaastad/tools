from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import httpx
import pytest
from typer.testing import CliRunner

from model_bench import registry

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


@pytest.mark.parametrize("payload", [{}, [], {"models": None}, {"models": {}}, {"models": [None]}, {"models": [{}]}, {"models": [{"name": ""}]}, {"models": [{"name": 42}]}])
def test_invalid_ollama_inventory_cannot_be_empty(monkeypatch, payload):
    response = httpx.Response(200, json=payload, request=httpx.Request("GET", "http://offline.invalid/api/tags"))
    monkeypatch.setattr(httpx, "get", Mock(return_value=response))
    with pytest.raises(ValueError, match="Ollama inventory"):
        registry.list_ollama_models()


@pytest.mark.parametrize("payload,names", [({"models": []}, []), ({"models": [{"name": "local:latest"}]}, ["local:latest"])])
def test_verified_ollama_inventory(monkeypatch, payload, names):
    response = httpx.Response(200, json=payload, request=httpx.Request("GET", "http://offline.invalid/api/tags"))
    get = Mock(return_value=response)
    monkeypatch.setattr(httpx, "get", get)
    assert registry.list_ollama_models() == names
    assert get.call_args.kwargs["timeout"] == 5.0


@pytest.mark.parametrize("failure", [httpx.ConnectError("offline"), httpx.ReadTimeout("timeout")])
def test_inventory_transport_failure_propagates_but_availability_is_false(monkeypatch, failure):
    monkeypatch.setattr(httpx, "get", Mock(side_effect=failure))
    assert registry.is_ollama_available() is False
    with pytest.raises(type(failure)):
        registry.list_ollama_models()


def test_inventory_http_error_propagates(monkeypatch):
    response = httpx.Response(503, request=httpx.Request("GET", "http://offline.invalid/api/tags"))
    monkeypatch.setattr(httpx, "get", Mock(return_value=response))
    assert registry.is_ollama_available() is False
    with pytest.raises(httpx.HTTPStatusError):
        registry.list_ollama_models()


def test_inventory_invalid_json_is_not_an_empty_inventory(monkeypatch):
    response = httpx.Response(200, content=b"not JSON", request=httpx.Request("GET", "http://offline.invalid/api/tags"))
    monkeypatch.setattr(httpx, "get", Mock(return_value=response))
    with pytest.raises(ValueError):
        registry.list_ollama_models()


@pytest.fixture
def offline_cli(monkeypatch):
    # The production CLI imports dotenv at module load. Replace it before
    # loading the CLI so these offline tests never read the real .env file.
    dotenv = ModuleType("dotenv")
    dotenv.load_dotenv = Mock()
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)
    path = Path(registry.__file__).with_name("cli.py")
    spec = importlib.util.spec_from_file_location("model_bench.offline_cli_test", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(registry, "MODELS", [ModelEntry("ollama/local", "local", "ollama", "incumbent")])
    return module


def test_cli_distinguishes_offline_from_missing_model(monkeypatch, offline_cli):
    monkeypatch.setattr(httpx, "get", Mock(side_effect=httpx.ConnectError("offline")))
    result = CliRunner().invoke(offline_cli.app, ["models"])
    assert result.exit_code == 0
    assert "Ollama offline" in result.output
    assert "Not installed" not in result.output


def test_failed_cli_listing_cannot_claim_not_installed(monkeypatch, offline_cli):
    monkeypatch.setattr(registry, "is_ollama_available", lambda: True)
    monkeypatch.setattr(httpx, "get", Mock(side_effect=httpx.ReadTimeout("listing failed")))
    result = CliRunner().invoke(offline_cli.app, ["models"])
    assert result.exit_code != 0
    assert isinstance(result.exception, httpx.ReadTimeout)
    assert "Not installed" not in result.output


def test_confirmed_empty_cli_inventory_can_say_not_installed(monkeypatch, offline_cli):
    response = httpx.Response(200, json={"models": []}, request=httpx.Request("GET", "http://offline.invalid/api/tags"))
    monkeypatch.setattr(httpx, "get", Mock(return_value=response))
    result = CliRunner().invoke(offline_cli.app, ["models"])
    assert result.exit_code == 0
    assert "Not installed" in result.output

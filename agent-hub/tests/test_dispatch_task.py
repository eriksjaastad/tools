"""
Unit tests for role resolution in dispatch_task.py.

These tests use a fixture routing.yaml — no Ollama required.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root so we can import config.models
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.models import resolve_role, get_tier_models, get_role_aliases


@pytest.fixture
def mock_routing_config():
    """Mock routing.yaml content for tests."""
    return {
        "role_aliases": {
            "coder": "coding:current",
            "reviewer": "coding:current",
            "implementer": "coding:current",
            "embedder": "embedding:current",
        },
        "model_tiers": {
            "local": {
                "models": ["ollama/coding:current", "ollama/llama3.2-vision:11b"],
                "cost_per_1k_tokens": 0.0,
            },
            "cheap": {
                "models": ["gemini/gemini-2.0-flash"],
                "cost_per_1k_tokens": 0.0001,
            },
            "premium": {
                "models": ["anthropic/claude-3-5-sonnet-20241022"],
                "cost_per_1k_tokens": 0.003,
            },
        },
    }


class TestResolveRole:
    """Test role alias resolution."""

    def test_coder_resolves(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            assert resolve_role("coder") == "coding:current"

    def test_reviewer_resolves(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            assert resolve_role("reviewer") == "coding:current"

    def test_embedder_resolves(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            assert resolve_role("embedder") == "embedding:current"

    def test_case_insensitive(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            assert resolve_role("CODER") == "coding:current"
            assert resolve_role("Coder") == "coding:current"

    def test_unknown_role_passthrough(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            assert resolve_role("some-model:7b") == "some-model:7b"

    def test_strips_ollama_prefix(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            assert resolve_role("ollama/coding:current") == "coding:current"

    def test_ollama_alias_passthrough(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            assert resolve_role("coding:current") == "coding:current"

    def test_full_model_tag_passthrough(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            assert resolve_role("qwen2.5-coder:32b-instruct-q3_K_L") == "qwen2.5-coder:32b-instruct-q3_K_L"


class TestGetTierModels:
    """Test tier model extraction."""

    def test_local_tier(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            models = get_tier_models("local")
            assert "coding:current" in models
            assert "llama3.2-vision:11b" in models

    def test_cheap_tier(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            models = get_tier_models("cheap")
            assert "gemini-2.0-flash" in models

    def test_unknown_tier_returns_empty(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            assert get_tier_models("nonexistent") == []

    def test_strips_provider_prefix(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            models = get_tier_models("local")
            # Should not have ollama/ prefix
            assert not any(m.startswith("ollama/") for m in models)


class TestGetRoleAliases:
    """Test role alias retrieval."""

    def test_returns_all_aliases(self, mock_routing_config):
        with patch("config.models._load_routing", return_value=mock_routing_config):
            aliases = get_role_aliases()
            assert "coder" in aliases
            assert "reviewer" in aliases
            assert "embedder" in aliases

    def test_empty_if_no_aliases(self):
        with patch("config.models._load_routing", return_value={"model_tiers": {}}):
            aliases = get_role_aliases()
            assert aliases == {}

"""Tests for configuration validator."""

import pytest
import os
from src.config_validator import ConfigValidator, validate_config


class TestConfigValidator:
    """Test configuration validation."""

    def test_valid_defaults(self, monkeypatch):
        """Default configuration should be valid."""
        # Clear any existing env vars
        for key in list(os.environ.keys()):
            if key.startswith("UAS_"):
                monkeypatch.delenv(key, raising=False)

        result = validate_config()
        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_budget_value(self, monkeypatch):
        """Invalid budget values should error."""
        monkeypatch.setenv("UAS_SESSION_BUDGET", "not-a-number")

        result = validate_config()
        assert result.valid is False
        assert any("UAS_SESSION_BUDGET" in e.field for e in result.errors)

    def test_budget_out_of_range(self, monkeypatch):
        """Out of range budget should error."""
        monkeypatch.setenv("UAS_SESSION_BUDGET", "10000")

        result = validate_config()
        assert result.valid is False
        assert any("out of range" in e.message for e in result.errors)

    def test_session_exceeds_daily_warning(self, monkeypatch):
        """Session > daily should warn."""
        monkeypatch.setenv("UAS_SESSION_BUDGET", "10.0")
        monkeypatch.setenv("UAS_DAILY_BUDGET", "5.0")

        result = validate_config()
        # This is a warning, not an error
        assert any("exceeds daily" in w.message for w in result.warnings)

    def test_invalid_url(self, monkeypatch):
        """Invalid URL should error."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "not-a-url")

        result = validate_config()
        assert result.valid is False
        assert any("Invalid URL" in e.message for e in result.errors)

    def test_invalid_failure_limit(self, monkeypatch):
        """Invalid failure limit should error."""
        monkeypatch.setenv("UAS_ROUTER_FAILURE_LIMIT", "0")

        result = validate_config()
        assert result.valid is False

    def test_feature_flag_warning(self, monkeypatch):
        """Conflicting feature flags should warn."""
        monkeypatch.setenv("UAS_LITELLM_ROUTING", "1")
        monkeypatch.setenv("UAS_SQLITE_BUS", "0")

        result = validate_config()
        assert any("SQLite bus disabled" in w.message for w in result.warnings)

    def test_validation_result_str(self):
        """ValidationResult should have readable string output."""
        from src.config_validator import ValidationResult, ValidationError

        # Create result directly with errors and warnings
        result = ValidationResult(
            valid=False,
            errors=[ValidationError("TEST", "Test error", "Fix it")],
            warnings=[ValidationError("TEST2", "Test warning")]
        )
        output = str(result)

        assert "Errors:" in output
        assert "Test error" in output
        assert "Warnings:" in output

    def test_valid_config_str(self, monkeypatch):
        """Valid config should have simple string output."""
        for key in list(os.environ.keys()):
            if key.startswith("UAS_"):
                monkeypatch.delenv(key, raising=False)

        result = validate_config()
        assert "valid" in str(result).lower()

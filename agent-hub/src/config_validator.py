"""
Configuration Validator - Validate UAS configuration.

Provides:
- Environment variable validation
- Configuration file validation
- Helpful error messages
"""

import os
import logging
from dataclasses import dataclass
from typing import Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """A configuration validation error."""
    field: str
    message: str
    suggestion: str | None = None

    def __str__(self) -> str:
        result = f"{self.field}: {self.message}"
        if self.suggestion:
            result += f"\n  Suggestion: {self.suggestion}"
        return result


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]

    def __str__(self) -> str:
        if self.valid and not self.warnings:
            return "Configuration valid"

        lines = []
        if self.errors:
            lines.append("Errors:")
            for e in self.errors:
                lines.append(f"  - {e}")

        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")

        return "\n".join(lines)


class ConfigValidator:
    """
    Validates UAS configuration.

    Usage:
        validator = ConfigValidator()
        result = validator.validate()

        if not result.valid:
            print(result)
            sys.exit(1)
    """

    # Valid ranges
    BUDGET_MIN = 0.01
    BUDGET_MAX = 1000.0
    TIMEOUT_MIN = 1.0
    TIMEOUT_MAX = 600.0
    FAILURE_LIMIT_MIN = 1
    FAILURE_LIMIT_MAX = 100

    def __init__(self):
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []

    def _add_error(self, field: str, message: str, suggestion: str | None = None):
        self.errors.append(ValidationError(field, message, suggestion))

    def _add_warning(self, field: str, message: str, suggestion: str | None = None):
        self.warnings.append(ValidationError(field, message, suggestion))

    def _validate_float_env(
        self,
        name: str,
        min_val: float,
        max_val: float,
        default: float,
    ) -> float | None:
        """Validate a float environment variable."""
        value = os.getenv(name)
        if value is None:
            return default

        try:
            float_val = float(value)
            if float_val < min_val or float_val > max_val:
                self._add_error(
                    name,
                    f"Value {float_val} out of range [{min_val}, {max_val}]",
                    f"Set to a value between {min_val} and {max_val}"
                )
                return None
            return float_val
        except ValueError:
            self._add_error(
                name,
                f"Invalid float value: '{value}'",
                f"Set to a numeric value like '{default}'"
            )
            return None

    def _validate_int_env(
        self,
        name: str,
        min_val: int,
        max_val: int,
        default: int,
    ) -> int | None:
        """Validate an integer environment variable."""
        value = os.getenv(name)
        if value is None:
            return default

        try:
            int_val = int(value)
            if int_val < min_val or int_val > max_val:
                self._add_error(
                    name,
                    f"Value {int_val} out of range [{min_val}, {max_val}]",
                    f"Set to a value between {min_val} and {max_val}"
                )
                return None
            return int_val
        except ValueError:
            self._add_error(
                name,
                f"Invalid integer value: '{value}'",
                f"Set to a whole number like '{default}'"
            )
            return None

    def _validate_bool_env(self, name: str) -> bool | None:
        """Validate a boolean environment variable."""
        value = os.getenv(name, "").lower()
        if value in ("", "0", "false", "no"):
            return False
        if value in ("1", "true", "yes"):
            return True

        self._add_warning(
            name,
            f"Unexpected value '{value}', treating as false",
            "Use '1' or '0' for boolean flags"
        )
        return False

    def _validate_path_env(self, name: str, must_exist: bool = False) -> Path | None:
        """Validate a path environment variable."""
        value = os.getenv(name)
        if value is None:
            return None

        path = Path(value)
        if must_exist and not path.exists():
            self._add_error(
                name,
                f"Path does not exist: {path}",
                "Create the path or update the variable"
            )
            return None

        return path

    def _validate_url_env(self, name: str, default: str) -> str:
        """Validate a URL environment variable."""
        value = os.getenv(name, default)

        if not value.startswith(("http://", "https://")):
            self._add_error(
                name,
                f"Invalid URL: '{value}'",
                "URL must start with http:// or https://"
            )
            return default

        return value

    def validate_budget_config(self) -> None:
        """Validate budget-related configuration."""
        session = self._validate_float_env(
            "UAS_SESSION_BUDGET",
            self.BUDGET_MIN, self.BUDGET_MAX, 1.0
        )
        daily = self._validate_float_env(
            "UAS_DAILY_BUDGET",
            self.BUDGET_MIN, self.BUDGET_MAX, 5.0
        )

        if session and daily and session > daily:
            self._add_warning(
                "UAS_SESSION_BUDGET",
                f"Session budget (${session}) exceeds daily budget (${daily})",
                "Session budget is typically lower than daily budget"
            )

    def validate_circuit_breaker_config(self) -> None:
        """Validate circuit breaker configuration."""
        self._validate_int_env(
            "UAS_ROUTER_FAILURE_LIMIT",
            self.FAILURE_LIMIT_MIN, self.FAILURE_LIMIT_MAX, 5
        )
        self._validate_int_env(
            "UAS_SQLITE_FAILURE_LIMIT",
            self.FAILURE_LIMIT_MIN, self.FAILURE_LIMIT_MAX, 3
        )
        self._validate_int_env(
            "UAS_OLLAMA_FAILURE_LIMIT",
            self.FAILURE_LIMIT_MIN, self.FAILURE_LIMIT_MAX, 3
        )

    def validate_ollama_config(self) -> None:
        """Validate Ollama configuration."""
        self._validate_url_env("OLLAMA_BASE_URL", "http://localhost:11434")
        self._validate_float_env(
            "UAS_HEALTH_CHECK_TIMEOUT",
            self.TIMEOUT_MIN, self.TIMEOUT_MAX, 5.0
        )

    def validate_feature_flags(self) -> None:
        """Validate feature flags and check for conflicts."""
        sqlite_bus = self._validate_bool_env("UAS_SQLITE_BUS")
        litellm_routing = self._validate_bool_env("UAS_LITELLM_ROUTING")

        # Warnings for recommended combinations
        if litellm_routing and not sqlite_bus:
            self._add_warning(
                "UAS_SQLITE_BUS",
                "LiteLLM routing enabled but SQLite bus disabled",
                "Enable UAS_SQLITE_BUS=1 for full functionality"
            )

    def validate(self) -> ValidationResult:
        """
        Run all validations.

        Returns:
            ValidationResult with errors and warnings
        """
        self.errors = []
        self.warnings = []

        self.validate_budget_config()
        self.validate_circuit_breaker_config()
        self.validate_ollama_config()
        self.validate_feature_flags()

        return ValidationResult(
            valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )


def validate_config() -> ValidationResult:
    """Convenience function to validate configuration."""
    return ConfigValidator().validate()


def require_valid_config() -> None:
    """Validate configuration and raise if invalid."""
    result = validate_config()
    if not result.valid:
        raise ValueError(f"Invalid configuration:\n{result}")

    if result.warnings:
        for w in result.warnings:
            logger.warning(f"Config warning: {w}")

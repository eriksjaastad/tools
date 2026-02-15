"""
Integration tests for model routing validation.

These tests require Ollama to be running and validate that:
1. All models in routing.yaml are actually installed
2. Role aliases resolve to installed models
3. No hardcoded stale model names remain in source code

Run with: pytest tests/test_routing_validation.py -v
Skip in CI: pytest -m "not integration"
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.models import (
    get_installed_models,
    get_tier_models,
    get_role_aliases,
    resolve_role,
    validate_routing_config,
)

# Stale model names that should NEVER appear in source code.
# Add patterns here when models are removed/replaced.
STALE_MODEL_PATTERNS = [
    "qwen2.5-coder:14b",
    "qwen2.5-coder:7b",
    "deepseek-r1:7b",
    "deepseek-r1:14b",
    "deepseek-r1:32b",
    "deepseek-r1-distill-qwen:32b",
    "deepseek-r1-distill:32b",
    "llama3.2:1b",
]

PROJECT_ROOT = Path(__file__).parent.parent


def _ollama_available() -> bool:
    """Check if Ollama is running."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, timeout=5, check=False
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


needs_ollama = pytest.mark.skipif(
    not _ollama_available(), reason="Ollama not running"
)


@needs_ollama
class TestLocalModelsInstalled:
    """Validate that all local-tier models in routing.yaml are installed."""

    def test_all_local_models_installed(self):
        installed = get_installed_models()
        local_models = get_tier_models("local")

        missing = [m for m in local_models if m not in installed]
        assert not missing, (
            f"Models in routing.yaml local tier not installed in Ollama: {missing}\n"
            f"Installed: {sorted(installed)}"
        )

    def test_all_role_aliases_resolve_to_installed(self):
        installed = get_installed_models()
        aliases = get_role_aliases()

        for role, target in aliases.items():
            assert target in installed, (
                f"Role '{role}' -> '{target}' not installed in Ollama.\n"
                f"Installed: {sorted(installed)}"
            )

    def test_validate_routing_config_clean(self):
        errors = validate_routing_config()
        assert not errors, f"Routing config validation errors: {errors}"


class TestNoStaleModelNames:
    """Grep source code for hardcoded model names that no longer exist."""

    def test_no_stale_models_in_src(self):
        """No stale model names in src/ directory."""
        self._check_directory(PROJECT_ROOT / "src")

    def test_no_stale_models_in_scripts(self):
        """No stale model names in scripts/ directory."""
        self._check_directory(PROJECT_ROOT / "scripts")

    def test_no_stale_models_in_config_models(self):
        """No stale model names in config/models.py."""
        self._check_file(PROJECT_ROOT / "config" / "models.py")

    def _check_directory(self, directory: Path):
        if not directory.exists():
            pytest.skip(f"{directory} does not exist")

        violations = []
        for py_file in directory.glob("*.py"):
            content = py_file.read_text()
            for pattern in STALE_MODEL_PATTERNS:
                if pattern in content:
                    violations.append(f"{py_file.name}: contains '{pattern}'")

        assert not violations, (
            f"Hardcoded stale model names found:\n" + "\n".join(f"  - {v}" for v in violations)
        )

    def _check_file(self, filepath: Path):
        if not filepath.exists():
            pytest.skip(f"{filepath} does not exist")

        content = filepath.read_text()
        violations = []
        for pattern in STALE_MODEL_PATTERNS:
            if pattern in content:
                violations.append(f"contains '{pattern}'")

        assert not violations, (
            f"{filepath.name} has hardcoded stale model names:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestResolveRoleIntegration:
    """Test that resolve_role works against the real routing.yaml."""

    def test_coder_resolves_to_something(self):
        result = resolve_role("coder")
        assert result, "coder role resolved to empty string"
        assert ":" in result, f"Expected Ollama alias format (name:tag), got '{result}'"

    def test_all_roles_resolve(self):
        aliases = get_role_aliases()
        for role in aliases:
            result = resolve_role(role)
            assert result, f"Role '{role}' resolved to empty string"

"""
Centralized model resolution for Agent Hub.

Single source of truth for mapping role names to Ollama model aliases.
All model references flow through here — no hardcoded model names elsewhere.

Resolution chain:
    role ("coder") → routing.yaml alias ("coding:current") → Ollama alias → actual model

Usage:
    from config.models import resolve_role, get_installed_models, validate_routing_config

    model = resolve_role("coder")          # "coding:current"
    models = get_installed_models()        # {"coding:current", "embedding:current", ...}
    errors = validate_routing_config()     # [] if everything checks out
"""

import subprocess
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

CONFIG_DIR = Path(__file__).parent
ROUTING_PATH = CONFIG_DIR / "routing.yaml"


def _load_routing() -> dict:
    """Load routing.yaml config."""
    if not HAS_YAML:
        raise RuntimeError("PyYAML required but not installed. Run: pip install pyyaml")
    if not ROUTING_PATH.exists():
        raise FileNotFoundError(f"routing.yaml not found at {ROUTING_PATH}")
    with open(ROUTING_PATH) as f:
        return yaml.safe_load(f)


def resolve_role(name: str) -> str:
    """
    Resolve a role name or model reference to an Ollama model name.

    Accepts:
        - Role aliases: "coder", "reviewer", "implementer", "embedder"
        - Ollama aliases: "coding:current", "embedding:current"
        - Prefixed names: "ollama/coding:current" (prefix stripped)
        - Raw model tags: "qwen2.5-coder:32b" (passed through)

    Returns:
        Resolved model name for Ollama.
    """
    config = _load_routing()
    aliases = config.get("role_aliases", {})

    # Check role alias (case-insensitive)
    if name.lower() in aliases:
        return aliases[name.lower()]

    # Strip ollama/ prefix if present
    if name.startswith("ollama/"):
        return name[len("ollama/"):]

    return name


def get_role_aliases() -> dict[str, str]:
    """Return the role_aliases dict from routing.yaml."""
    config = _load_routing()
    return config.get("role_aliases", {})


def get_tier_models(tier: str) -> list[str]:
    """
    Get model list for a tier, with provider prefixes stripped.

    Args:
        tier: "local", "cheap", or "premium"

    Returns:
        List of model names (e.g., ["coding:current", "llama3.2-vision:11b"])
    """
    config = _load_routing()
    tier_config = config.get("model_tiers", {}).get(tier, {})
    raw_models = tier_config.get("models", [])
    # Strip provider prefix for Ollama models
    return [m.split("/", 1)[-1] if "/" in m else m for m in raw_models]


def get_installed_models() -> set[str]:
    """
    Query Ollama for installed models.

    Returns:
        Set of model name strings (e.g., {"coding:current", "llama3.2-vision:11b"})
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return set()

        models = set()
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:  # Skip header
            if line.strip():
                parts = line.split()
                if parts:
                    models.add(parts[0])
        return models
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()


def validate_routing_config() -> list[str]:
    """
    Validate that all models in routing.yaml are actually available.

    Returns:
        List of error strings. Empty list = everything is valid.
    """
    errors = []

    try:
        config = _load_routing()
    except Exception as e:
        return [f"Cannot load routing.yaml: {e}"]

    installed = get_installed_models()
    if not installed:
        return ["Cannot reach Ollama or no models installed"]

    # Check local tier models (Ollama models must be installed)
    local_models = get_tier_models("local")
    for model in local_models:
        if model not in installed:
            errors.append(f"Local model '{model}' in routing.yaml not installed in Ollama")

    # Check role aliases resolve to installed models
    aliases = config.get("role_aliases", {})
    for role, target in aliases.items():
        if target not in installed:
            errors.append(f"Role alias '{role}' -> '{target}' not installed in Ollama")

    return errors

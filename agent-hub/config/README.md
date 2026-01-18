# Configuration Directory

This directory contains the central configuration for the **Unified Agent System**.

## Getting Started

1. Copy the `.example` files to active yaml files:
   ```bash
   cp routing.yaml.example routing.yaml
   cp feature_flags.yaml.example feature_flags.yaml
   ```
2. Edit the active files to match your local setup (e.g., Ollama URL, API keys).
3. **Note:** `.yaml` files (without the .example suffix) are ignored by Git to prevent leaking local environment specifics.

## Configuration Files

- **`routing.yaml`:** Defines model tiers, fallback chains, and provider-specific URLs/timeouts.
- **`feature_flags.yaml`:** Controls the incremental rollout of system features.

## Environment Overrides
Most configuration values can be overridden via environment variables. For feature flags, the override pattern is defined in the `env_override` field of each flag (e.g., `UAS_LITELLM_ROUTING=1`).

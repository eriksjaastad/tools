# Feature Flag Policy: Unified Agent System

Feature flags are the primary mechanism for the safe, incremental rollout of new architectural components. They allow us to test high-risk changes (like switching from CLI to HTTP or implementing a new message bus) without breaking the existing stable core.

## Why We Use Feature Flags
1. **Safe Rollout:** Enable features for specific runs or developers before global activation.
2. **Instant Rollback:** Disable a failing feature via environment variable without a code change.
3. **A/B Testing:** Compare logic (e.g., standard polling vs. adaptive polling).
4. **Decoupling Deployment:** Deploy code anytime; activate the feature when ready.

## Naming Conventions
- **Config Key:** `snake_case` (e.g., `litellm_routing`).
- **Env Override:** `UAS_` prefix followed by upper case (e.g., `UAS_LITELLM_ROUTING`).

## Flag Lifecycle
1. **Disabled:** New code path is merged but inactive.
2. **Enabled in Dev:** Active in local environments for testing.
3. **Enabled in Prod:** Active for all users.
4. **Hardcoded:** The old code path is removed; the feature is now the standard.
5. **Removed:** The flag is deleted from the YAML and the code check is removed.

## Implementation Pattern (Python)
Always use a utility function to check flag status to ensure the environment override takes precedence.

```python
import os
import yaml

def is_feature_enabled(flag_name: str) -> bool:
    """Check if feature flag is enabled (env override or config)."""
    try:
        # Load config
        with open("config/feature_flags.yaml") as f:
            flags = yaml.safe_load(f)
    except FileNotFoundError:
        return False

    flag = flags.get(flag_name, {})

    # Environment override takes precedence
    env_var = flag.get("env_override")
    if env_var and os.getenv(env_var):
        return os.getenv(env_var).lower() in ("1", "true", "yes")

    return flag.get("enabled", False)
```

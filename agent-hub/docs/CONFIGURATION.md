# UAS Configuration Guide

## Feature Flags

All feature flags follow the pattern `UAS_*` and can be set to `1` (enabled) or `0` (disabled).

### Enabling All UAS Features

```bash
export UAS_OLLAMA_HTTP=1
export UAS_PERSISTENT_MCP=1
export UAS_ADAPTIVE_POLL=1
export UAS_LITELLM_ROUTING=1
export UAS_SQLITE_BUS=1
```

### Minimal Setup (Local Development)

```bash
export UAS_SQLITE_BUS=1
export UAS_SESSION_BUDGET=10.00
```

## Model Tiers

| Tier | Models | Cost/1M tokens | Use Case |
|------|--------|----------------|----------|
| Local (Free) | `local-fast`, `local-coder`, `local-reasoning` | $0 | Most tasks |
| Cloud (Cheap) | `cloud-fast` | ~$0.10 | Fallback |
| Cloud (Premium) | `cloud-premium` | ~$3.00 | Complex reasoning |

## Fallback Chains

Default chains by task type:

| Task Type | Chain |
|-----------|-------|
| `default` | local-fast → cloud-fast → cloud-premium |
| `code` | local-coder → cloud-fast → cloud-premium |
| `reasoning` | local-reasoning → cloud-fast → cloud-premium |

---

*See API_REFERENCE.md for full environment variable list*

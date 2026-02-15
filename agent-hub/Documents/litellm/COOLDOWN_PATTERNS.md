# Cooldown Patterns

Cooldowns act as circuit breakers, preventing the router from repeatedly hitting a known-failing or overloaded model.

## What Cooldown Does
When a model exceeds a failure threshold, the `Router` temporarily marks it as "unavailable" for a set duration. This prevent "thundering herd" issues and allows providers (like local Ollama instances) time to recover.

## Key Parameters
- **`allowed_fails`:** Number of failures allowed within a minute before cooldown triggers (Default: 0 - immediate cooldown).
- **`cooldown_time`:** How long (in seconds) the model stays in the "bad" list (Default: 60s).

## Implementation Pattern

```python
from litellm import Router

model_list = [...] # defined in ROUTING_PATTERNS.md

router = Router(
    model_list=model_list,
    allowed_fails=3,      # Allow 3 strikes before cooling down
    cooldown_time=300,    # 5-minute cooldown for failing providers
    set_verbose=True
)

# Checking status programmatically
unhealthy_models = router.get_unhealthy_deployments()
if any(m['model_name'] == 'tier1' for m in unhealthy_models):
    print("Local worker is cooling down...")
```

## Production Scaling
For multi-instance deployments, LiteLLM supports using **Redis** to sync cooldown status across different application processes.

```python
router = Router(
    model_list=model_list,
    redis_host="localhost",
    redis_port=6379,
    enable_pre_call_checks=True # Check Redis status before every call
)
```

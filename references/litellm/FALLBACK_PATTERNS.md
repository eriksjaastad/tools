# Fallback Patterns

Fallbacks ensure that our agents remain operational even when a specific provider is down, rate-limited, or overloaded.

## Error Types that Trigger Fallbacks
LiteLLM automatically catches and maps provider-specific errors:
- `RateLimitError` (HTTP 429)
- `ServiceUnavailableError` (HTTP 503)
- `ContentPolicyViolationError` (Safety filters)
- `Timeout` (Latency exceeded)

## Fallback Configuration
The `fallbacks` parameter in the `Router` defines the chain of succession.

```python
from litellm import Router

model_list = [...] # defined in ROUTING_PATTERNS.md

router = Router(
    model_list=model_list,
    fallbacks=[
        {"tier1": ["tier2", "tier3"]},  # If Ollama fails, try Gemini, then Claude
        {"tier2": ["tier3"]}           # If Gemini fails, escalate to Claude
    ],
    context_window_fallbacks=[
        {"tier1": ["tier3"]}           # Use premium models if context exceeds local capacity
    ]
)

# Implementation
response = router.completion(
    model="tier1", # Target model
    messages=messages,
    fallbacks=["tier2", "tier3"] # Explicitly override or use router defaults
)
```

## Advanced Fallback Logic
- **`context_window_fallbacks`:** Essential for local models with smaller context windows (e.g., 8k-16k) falling back to cloud models with 128k+ windows.
- **Ordered Chain:** The router respects the list order in the `fallbacks` dictionary.

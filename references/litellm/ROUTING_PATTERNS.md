# Routing Patterns

The `litellm.Router` is the heart of our provider abstraction. It allows us to group models by performance tiers and distribute requests based on capacity and latency.

## Basic Concepts
- **Model List:** A standardized list of dictionaries containing `model_name` (our internal alias) and `litellm_params` (the actual provider configuration).
- **Routing Strategy:** Determines how the router selects among available models in a group.

## 3-Tier Model Configuration
We map our internal tiers to specific providers:
- **Tier 1:** Local workers (Ollama)
- **Tier 2:** Cheap cloud (Gemini Flash)
- **Tier 3:** Premium cloud (Claude Sonnet 3.5)

## Implementation Pattern

```python
from litellm import Router

# Define our model inventory
model_list = [
    {
        "model_name": "tier1",
        "litellm_params": {
            "model": "ollama/qwen2.5-coder:14b",
            "api_base": "http://localhost:11434"
        }
    },
    {
        "model_name": "tier2",
        "litellm_params": {
            "model": "gemini/gemini-1.5-flash",
            "api_key": "os.environ/GEMINI_API_KEY"
        }
    },
    {
        "model_name": "tier3",
        "litellm_params": {
            "model": "claude-3-5-sonnet-20240620",
            "api_key": "os.environ/ANTHROPIC_API_KEY"
        }
    }
]

# Initialize the router
router = Router(
    model_list=model_list,
    routing_strategy="least-busy", # Options: 'simple-shuffle', 'least-busy', 'latency-based', 'weighted-shuffle'
    set_verbose=False
)

# Usage in application
# response = router.completion(model="tier1", messages=[{"role": "user", "content": "..."}])
```

## Load Balancing Strategies
- **`simple-shuffle`:** Basic random distribution (good for free Ollama clusters).
- **`least-busy`:** Tracks active requests in-memory (best for local hardware constraints).
- **`latency-based`:** Prioritizes models with faster historical response times.
- **`weighted-shuffle`:** Allows proportional traffic distribution.

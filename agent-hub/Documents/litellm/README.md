# LiteLLM Reference Vault

This directory contains foundational documentation and code patterns for the **Unified Agent System**. We use the `litellm` Python library (direct implementation, NOT the proxy) for model abstraction, routing, and resilience.

## Core Features in Use

- **[Router](ROUTING_PATTERNS.md):** Unified model management with load balancing.
- **[Fallbacks](FALLBACK_PATTERNS.md):** Automatic model switching on failure or rate limits.
- **[Cooldowns](COOLDOWN_PATTERNS.md):** Circuit breaking for failing or overloaded providers.
- **Model Aliasing:** Using our own tier names (Tier 1/2/3) to decouple logic from specific providers.

## Official Documentation
- [LiteLLM Home](https://docs.litellm.com/)
- [LiteLLM Router Docs](https://docs.litellm.com/docs/routing)
- [LiteLLM GitHub](https://github.com/BerriAI/litellm)

## Scope
We prioritize the **Library/SDK** approach over the Proxy server to minimize latency and architectural complexity in our agent loops.

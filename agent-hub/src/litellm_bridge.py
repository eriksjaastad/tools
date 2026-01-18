"""
LiteLLM Bridge - Routing layer with fallbacks and cooldowns.

Translates MCP-style calls to LiteLLM router.
Feature flag: UAS_LITELLM_ROUTING
"""

import os
import logging
import time
from typing import Any
from pathlib import Path

import litellm
from litellm import Router

from . import cost_logger
from .utils import timing

logger = logging.getLogger(__name__)

# Model tier definitions (matches config/routing.yaml)
DEFAULT_MODEL_LIST = [
    # Tier 1: Free (Ollama)
    {
        "model_name": "local-fast",
        "litellm_params": {
            "model": "ollama/llama3.2:1b",
            "api_base": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        },
    },
    {
        "model_name": "local-coder",
        "litellm_params": {
            "model": "ollama/qwen2.5-coder:14b",
            "api_base": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        },
    },
    {
        "model_name": "local-reasoning",
        "litellm_params": {
            "model": "ollama/deepseek-r1-distill-qwen:32b",
            "api_base": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        },
    },
    # Tier 2: Cheap (Gemini)
    {
        "model_name": "cloud-fast",
        "litellm_params": {
            "model": "gemini/gemini-2.0-flash",
            "api_key": os.getenv("GEMINI_API_KEY"),
        },
    },
    # Tier 3: Premium (Claude)
    {
        "model_name": "cloud-premium",
        "litellm_params": {
            "model": "claude-3-5-sonnet-20241022",
            "api_key": os.getenv("ANTHROPIC_API_KEY"),
        },
    },
]

# Fallback chains
FALLBACK_CHAINS = {
    "default": ["local-fast", "cloud-fast", "cloud-premium"],
    "code": ["local-coder", "cloud-fast", "cloud-premium"],
    "reasoning": ["local-reasoning", "cloud-premium"],
}

# Cooldown settings
COOLDOWN_TIME = int(os.getenv("UAS_COOLDOWN_SECONDS", "60"))
ALLOWED_FAILS = int(os.getenv("UAS_ALLOWED_FAILS", "3"))


from .budget_manager import get_budget_manager
from .degradation import get_degradation_manager


class BudgetExceededError(Exception):
    """Raised when budget limits prevent model calls."""
    pass


class LiteLLMBridge:
    """
    Bridge between MCP tool calls and LiteLLM router.

    Usage:
        bridge = LiteLLMBridge()
        response = bridge.chat(
            messages=[{"role": "user", "content": "Hello"}],
            task_type="code"  # Uses code fallback chain
        )
    """

    def __init__(self, model_list: list[dict] | None = None):
        self.model_list = model_list or DEFAULT_MODEL_LIST
        self._router: Router | None = None
        self._cooldowns: dict[str, float] = {}  # model -> cooldown_until timestamp
        self._fail_counts: dict[str, int] = {}  # model -> consecutive failures

    def _get_router(self) -> Router:
        """Lazy-init the LiteLLM router."""
        if self._router is None:
            self._router = Router(
                model_list=self.model_list,
                routing_strategy="simple-shuffle",
                num_retries=0,  # We handle retries ourselves via fallback chain
            )
        return self._router

    def _is_cooled_down(self, model: str) -> bool:
        """Check if model is in cooldown."""
        if model not in self._cooldowns:
            return False
        return time.time() < self._cooldowns[model]

    def _record_failure(self, model: str) -> None:
        """Record a failure and potentially trigger cooldown."""
        self._fail_counts[model] = self._fail_counts.get(model, 0) + 1
        if self._fail_counts[model] >= ALLOWED_FAILS:
            self._cooldowns[model] = time.time() + COOLDOWN_TIME
            logger.warning(f"Model {model} entering cooldown for {COOLDOWN_TIME}s")

    def _record_success(self, model: str) -> None:
        """Record success and reset failure count."""
        self._fail_counts[model] = 0

    def _get_fallback_chain(self, task_type: str) -> list[str]:
        """Get the fallback chain for a task type."""
        return FALLBACK_CHAINS.get(task_type, FALLBACK_CHAINS["default"])

    def chat(
        self,
        messages: list[dict],
        task_type: str = "default",
        preferred_model: str | None = None,
        require_budget_check: bool = True,
        **kwargs
    ) -> dict[str, Any]:
        """
        Send a chat completion with automatic fallback.

        Args:
            messages: Chat messages
            task_type: Type of task (default, code, reasoning)
            preferred_model: Specific model to try first
            require_budget_check: If True, check budget before cloud calls
            **kwargs: Additional args passed to litellm

        Returns:
            Response dict with model, content, usage, etc.

        Raises:
            BudgetExceededError: If no affordable models available
            RuntimeError: If all models fail
        """
        budget = get_budget_manager()
        degradation = get_degradation_manager()
        chain = self._get_fallback_chain(task_type)

        # Check degradation before attempting local models
        if degradation.is_degraded():
            # Filter out local models from chain
            chain = [m for m in chain if not m.startswith("local-")]
            if not chain:
                chain = [degradation.get_fallback_model()]
            logger.info(f"Degraded mode: using chain {chain}")

        if preferred_model and preferred_model in chain:
            # Move preferred to front
            chain = [preferred_model] + [m for m in chain if m != preferred_model]

        # Estimate token counts for budget check
        estimated_tokens_in = sum(len(m.get("content", "")) // 4 for m in messages)
        estimated_tokens_out = 500  # Conservative estimate

        last_error = None
        skipped_for_budget = []

        for model in chain:
            if self._is_cooled_down(model):
                logger.debug(f"Skipping {model} (in cooldown)")
                continue

            # Pre-flight budget check
            if require_budget_check:
                can_afford, reason = budget.can_afford(
                    model=model,
                    estimated_tokens_in=estimated_tokens_in,
                    estimated_tokens_out=estimated_tokens_out,
                )
                if not can_afford:
                    logger.warning(f"Skipping {model}: {reason}")
                    skipped_for_budget.append((model, reason))
                    continue

            with timing.measure_latency() as t:
                try:
                    router = self._get_router()
                    response = router.completion(
                        model=model,
                        messages=messages,
                        **kwargs
                    )

                    # Extract response data
                    content = response.choices[0].message.content
                    usage = response.usage

                    # Log success to cost logger
                    cost_logger.log_model_call(
                        model=model,
                        tokens_in=usage.prompt_tokens if usage else 0,
                        tokens_out=usage.completion_tokens if usage else 0,
                        latency_ms=t["latency_ms"],
                        success=True,
                        task_type=task_type,
                    )

                    # Record status to budget manager
                    budget.record_cost(
                        model=model,
                        tokens_in=usage.prompt_tokens if usage else 0,
                        tokens_out=usage.completion_tokens if usage else 0,
                        task_type=task_type,
                        was_fallback=model != chain[0],
                    )

                    self._record_success(model)

                    return {
                        "model": model,
                        "content": content,
                        "usage": {
                            "prompt_tokens": usage.prompt_tokens if usage else 0,
                            "completion_tokens": usage.completion_tokens if usage else 0,
                        },
                        "latency_ms": t["latency_ms"],
                        "fallback_used": model != chain[0],
                    }

                except Exception as e:
                    logger.warning(f"Model {model} failed: {e}")
                    last_error = e
                    self._record_failure(model)

                    # Log failure
                    cost_logger.log_model_call(
                        model=model,
                        tokens_in=0,
                        tokens_out=0,
                        latency_ms=t["latency_ms"],
                        success=False,
                        error=str(e),
                        task_type=task_type,
                    )

        # If we get here and skipped models for budget, raise specific error
        if skipped_for_budget and last_error is None:
            raise BudgetExceededError(
                f"All cloud models skipped due to budget: {skipped_for_budget}"
            )

        # All models failed
        raise RuntimeError(f"All models in chain {chain} failed. Last error: {last_error}")


    def get_cooldown_status(self) -> dict[str, Any]:
        """Get current cooldown status for all models."""
        now = time.time()
        return {
            model: {
                "in_cooldown": self._is_cooled_down(model),
                "fail_count": self._fail_counts.get(model, 0),
                "cooldown_remaining": max(0, self._cooldowns.get(model, 0) - now),
            }
            for model in set(m["model_name"] for m in self.model_list)
        }


# Global bridge instance
_bridge: LiteLLMBridge | None = None

def get_bridge() -> LiteLLMBridge:
    """Get the global bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = LiteLLMBridge()
    return _bridge

def route_chat(
    messages: list[dict],
    task_type: str = "default",
    **kwargs
) -> dict[str, Any]:
    """Convenience function to route a chat request."""
    return get_bridge().chat(messages, task_type, **kwargs)

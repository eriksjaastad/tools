"""
Model Router - Intelligent tier selection and fallback execution.
Uses LiteLLM for provider abstraction.
"""

import os
import yaml
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

import litellm

logger = logging.getLogger(__name__)

@dataclass
class ModelSelection:
    model: str
    tier: str
    fallback_chain: List[str]

class Router:
    """
    Handles model selection based on task complexity and manages fallbacks.
    """

    def __init__(self, config_path: str = "config/routing.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.cooldown_cache: Dict[str, float] = {}
        self.cooldown_seconds = self.config.get("cooldown_seconds", 300)

    def _load_config(self) -> Dict:
        if not self.config_path.exists():
            logger.warning(f"Config not found at {self.config_path}, using defaults")
            return {}
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def route(self, task_type: str, complexity: str, input_tokens: int = 0) -> ModelSelection:
        """
        FR-2.1: Select appropriate tier based on matrix.
        """
        routing_info = self.config.get("task_routing", {})
        tier = routing_info.get(task_type, {}).get(complexity, "local")
        
        # Get models for this tier
        tier_config = self.config.get("model_tiers", {}).get(tier, {})
        models = tier_config.get("models", [])
        if not models:
            raise ValueError(f"No models configured for tier '{tier}' in routing.yaml")
        
        # Simple selection: first available model in tier
        model = models[0]
        
        # Define fallback chain
        # local -> cheap -> premium
        chain = []
        if tier == "local":
            chain = ["cheap", "premium"]
        elif tier == "cheap":
            chain = ["premium"]
        
        fallback_models = []
        for fb_tier in chain:
            fb_models = self.config.get("model_tiers", {}).get(fb_tier, {}).get("models", [])
            if fb_models:
                fallback_models.append(fb_models[0])
                
        return ModelSelection(model=model, tier=tier, fallback_chain=fallback_models)

    def is_model_cooled_down(self, model: str) -> bool:
        if model not in self.cooldown_cache:
            return True
        return time.time() > self.cooldown_cache[model]

    def add_to_cooldown(self, model: str):
        self.cooldown_cache[model] = time.time() + self.cooldown_seconds
        logger.warning(f"Model {model} added to cooldown for {self.cooldown_seconds}s")

    def execute_with_fallback(self, selection: ModelSelection, prompt: str, system: Optional[str] = None) -> Any:
        """
        FR-2.2: Try models in chain until success.
        """
        models_to_try = [selection.model] + selection.fallback_chain
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt, model in enumerate(models_to_try):
            if not self.is_model_cooled_down(model):
                logger.debug(f"Skipping {model} due to cooldown")
                continue

            try:
                logger.info(f"Attempting {model} (Attempt {attempt+1})")
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    # We could add more litellm params here
                )
                
                # Log success would be done by the integration layer or cost_logger
                return response
            
            except Exception as e:
                logger.error(f"Model {model} failed: {e}")
                self.add_to_cooldown(model)
                last_error = e
                
                # Log fallback event
                fb_event = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "original_model": selection.model,
                    "failed_model": model,
                    "failed_reason": str(e),
                    "fallback_model": models_to_try[attempt+1] if attempt+1 < len(models_to_try) else None,
                    "attempt": attempt + 1
                }
                self._log_fallback(fb_event)

        raise RuntimeError(f"All models in fallback chain failed. Last error: {last_error}")

    def _log_fallback(self, event: Dict):
        # Implementation could write to a specific fallback log or audit log
        logger.warning(f"Fallback Event: {event}")

from datetime import datetime, timezone

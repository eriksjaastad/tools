"""
AI Router - Smart routing between local and cloud AI models

Routes requests based on complexity heuristics, with automatic escalation
on failures or poor responses.
"""

from __future__ import annotations

import os
import time
import json
import fcntl
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Literal, Optional, Dict

from openai import OpenAI  # modern SDK
import anthropic
from google import genai

Tier = Literal["local", "cheap", "expensive", "auto"]


@dataclass
class ModelInfo:
    """Metadata for an AI model including context window"""
    name: str
    context_window: int
    provider: Literal["local", "openai", "anthropic", "google"]
    description: Optional[str] = None


# Context windows: Use SAFE limits for local models (actual VRAM-constrained values)
# Cloud models can use full context, local models should be conservative
MODEL_CONFIG = {
    # Local models - conservative limits to avoid OOM on consumer GPUs
    "llama3.2:3b": ModelInfo("llama3.2:3b", 8192, "local", "Small but capable local model"),
    "llama3.2:latest": ModelInfo("llama3.2:latest", 8192, "local"),
    "deepseek-r1:14b": ModelInfo("deepseek-r1:14b", 16384, "local", "Reasoning model"),
    "qwen3:4b": ModelInfo("qwen3:4b", 8192, "local"),
    "qwen3:14b": ModelInfo("qwen3:14b", 16384, "local"),
    
    # OpenAI Cloud models
    "gpt-4o-mini": ModelInfo("gpt-4o-mini", 128000, "openai", "Cheap cloud model"),
    "gpt-4o": ModelInfo("gpt-4o", 128000, "openai", "Powerful cloud model"),
    "o1-mini": ModelInfo("o1-mini", 128000, "openai", "Reasoning cloud model"),
    
    # Anthropic Cloud models
    "claude-3-5-sonnet-20241022": ModelInfo("claude-3-5-sonnet-20241022", 200000, "anthropic", "High-quality strategic model"),
    "claude-3-5-haiku-20241022": ModelInfo("claude-3-5-haiku-20241022", 200000, "anthropic", "Fast cloud model"),
    "claude-3-opus-20240229": ModelInfo("claude-3-opus-20240229", 200000, "anthropic", "Most powerful Claude model"),
    
    # Google Cloud models
    "gemini-2.0-flash-exp": ModelInfo("gemini-2.0-flash-exp", 1000000, "google", "Large context middle-tier reasoning"),
    "gemini-1.5-flash": ModelInfo("gemini-1.5-flash", 1000000, "google", "Fast large context model"),
}

# Cost per 1M tokens in USD
MODEL_COSTS = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o1-mini": {"input": 3.00, "output": 12.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash-exp": {"input": 0.0, "output": 0.0},
}

EXPENSIVE_MODELS = {
    "claude-3-opus-20240229",
    "claude-3-5-sonnet-20241022",
    "gpt-4o"
}


class AIRouterError(Exception):
    """Base exception for AI Router failures"""
    pass


class AIModelError(AIRouterError):
    """Raised when an AI model fails or returns a bad response in strict mode"""
    def __init__(self, message: str, result: AIResult):
        super().__init__(message)
        self.result = result


@dataclass
class AIResult:
    """Result from an AI model call"""
    text: str
    provider: Literal["local", "openai", "anthropic", "google"]
    model: str
    tier: Tier
    duration_ms: int
    timed_out: bool = False
    error: Optional[str] = None
    status_note: str = ""


class TelemetryLogger:
    """Lightweight logger for tracking AI Router performance"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_path = os.path.join(log_dir, "telemetry.jsonl")
        os.makedirs(log_dir, exist_ok=True)

    def log(self, result: AIResult, prompt_len: int, project: str = "default"):
        """Log a result to a JSONL file with file locking for concurrent safety"""
        entry = asdict(result)
        entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
        entry["prompt_len"] = prompt_len
        entry["project"] = project

        # Performance ceiling detection
        entry["performance_warning"] = (
            result.duration_ms > 30000 or  # >30s is slow
            result.timed_out or
            bool(result.error)
        )

        try:
            with open(self.log_path, "a") as f:
                # Acquire exclusive lock before writing
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(entry) + "\n")
                    f.flush()  # Ensure data is written before releasing lock
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            # Log to stderr instead of silently swallowing
            import sys
            print(f"[AIRouter] Telemetry write failed: {e}", file=sys.stderr)


class BudgetProtector:
    """Tracks and enforces model spend limits"""
    
    def __init__(self, log_dir: str = "logs", daily_limit: float = 5.0):
        self.budget_path = os.path.join(log_dir, "budget.json")
        self.daily_limit = daily_limit
        self._ensure_log_dir(log_dir)

    def _ensure_log_dir(self, log_dir: str):
        os.makedirs(log_dir, exist_ok=True)
        if not os.path.exists(self.budget_path):
            with open(self.budget_path, "w") as f:
                json.dump({"date": datetime.utcnow().date().isoformat(), "spent": 0.0}, f)

    def _get_budget(self) -> Dict[str, Any]:
        try:
            with open(self.budget_path, "r") as f:
                data = json.load(f)
                today = datetime.utcnow().date().isoformat()
                if data.get("date") != today:
                    return {"date": today, "spent": 0.0}
                return data
        except Exception:
            return {"date": datetime.utcnow().date().isoformat(), "spent": 0.0}

    def _save_budget(self, data: Dict[str, Any]):
        with open(self.budget_path, "w") as f:
            # File locking for concurrent budget updates
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def can_afford(self, estimated_cost: float) -> bool:
        budget = self._get_budget()
        return (budget["spent"] + estimated_cost) <= self.daily_limit

    def record_spend(self, cost: float):
        budget = self._get_budget()
        budget["spent"] += cost
        self._save_budget(budget)

    def get_remaining(self) -> float:
        budget = self._get_budget()
        return max(0.0, self.daily_limit - budget["spent"])


class AIRouter:
    """
    Route requests to local Ollama (OpenAI-compatible endpoint) or OpenAI cloud.
    
    Usage:
        router = AIRouter()
        
        # Auto-routing based on complexity
        result = router.chat([{"role": "user", "content": "Is this spam?"}])
        
        # Force specific tier
        result = router.chat([...], tier="local")
        
        # Override model
        result = router.chat([...], model_override="gpt-4o")
    """

    def __init__(
        self,
        *,
        local_base_url: str = "http://localhost:11434/v1",
        local_api_key: str = "ollama",   # not used by Ollama, but required by client
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
        local_timeout_s: float = 60.0,
        cloud_timeout_s: float = 120.0,
        local_model: str = "llama3.2:3b",
        cheap_model: str = "gpt-4o-mini",
        expensive_model: str = "gpt-4o",
        model_config_overrides: Optional[Dict[str, ModelInfo]] = None,
    ):
        """
        Initialize the AI router.
        
        Args:
            local_base_url: Ollama API endpoint (default: http://localhost:11434/v1)
            local_api_key: Dummy key for Ollama (required by OpenAI client)
            openai_api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            anthropic_api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            google_api_key: Google API key (defaults to GOOGLE_API_KEY env var)
            local_timeout_s: Timeout for local model calls
            cloud_timeout_s: Timeout for cloud model calls
            local_model: Default local model name
            cheap_model: Default cheap cloud model
            expensive_model: Default expensive cloud model
            model_config_overrides: Custom model metadata overrides
        """
        # Create instance-local copy of model config (never mutate global)
        self.model_config = dict(MODEL_CONFIG)
        if model_config_overrides:
            self.model_config.update(model_config_overrides)

        self.local_client = OpenAI(
            base_url=local_base_url,
            api_key=local_api_key,
            timeout=local_timeout_s
        )
        
        # Initialize cloud clients
        openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.cloud_client = OpenAI(
                api_key=openai_key,
                timeout=cloud_timeout_s
            )
        else:
            self.cloud_client = None

        anthropic_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.anthropic_client = anthropic.Anthropic(
                api_key=anthropic_key,
                timeout=cloud_timeout_s
            )
        else:
            self.anthropic_client = None

        google_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        if google_key:
            self.google_client = genai.Client(api_key=google_key)
        else:
            self.google_client = None

        self.local_model = local_model
        self.cheap_model = cheap_model
        self.expensive_model = expensive_model
        self.telemetry = TelemetryLogger()
        self.budget = BudgetProtector()

    def route(self, messages: list[dict[str, str]]) -> Tier:
        """
        Determine routing tier based on message complexity, length, and task type.
        
        Logic:
        - Extractive + short -> local
        - Extractive + long -> cheap
        - Generative + short -> cheap
        - Generative + long -> expensive
        """
        content = "\n".join(m.get("content", "") for m in messages)
        
        # 1. Classify task type
        task_type = self._classify_task(content)
        
        # 2. Estimate total token budget
        input_tokens = len(content) // 4
        expected_output = self._estimate_output_length(content)
        total_budget = input_tokens + expected_output
        
        # 3. Handle obvious "heavy" signals manually for now as backup
        heavy_signals = ["architecture", "threat model", "security audit"]
        if any(s in content.lower() for s in heavy_signals):
            return "expensive"

        # 4. Routing rule implementation
        if task_type == "extractive":
            if total_budget < 1000:
                return "local"
            elif total_budget < 8000:
                return "cheap"
            else:
                return "expensive"
        else:  # generative
            if total_budget < 500:
                return "cheap"  # Never local for generative
            else:
                return "expensive"

    def _classify_task(self, content: str) -> Literal["extractive", "generative"]:
        """Classify if task is expansion (generative) or compression (extractive)"""
        content_lower = content.lower()
        
        # Extractive signals
        extractive_keywords = [
            "classify", "spam", "yes or no", "extract", "email address",
            "summarize", "tl;dr", "tldr", "fix this bug", "check this code",
            "convert", "json to yaml", "is there any", "match", "find"
        ]
        
        # Generative signals
        generative_keywords = [
            "write", "draft", "create", "design", "explain", "brainstorm",
            "ideas for", "implementation", "plan", "scaffold", "describe"
        ]
        
        # Check counts
        e_score = sum(1 for kw in extractive_keywords if kw in content_lower)
        g_score = sum(1 for kw in generative_keywords if kw in content_lower)
        
        if e_score > g_score:
            return "extractive"
        return "generative"

    def _estimate_output_length(self, content: str) -> int:
        """Estimate expected output tokens based on prompt clues"""
        content_lower = content.lower()
        
        if any(kw in content_lower for kw in ["short", "brief", "one sentence", "yes or no", "classify"]):
            return 50
        if any(kw in content_lower for kw in ["comprehensive", "in detail", "full code", "blog post", "essay"]):
            return 1000
        if "write a" in content_lower or "implement" in content_lower:
            return 500
        return 200

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tier: Tier = "auto",
        model_override: Optional[str] = None,
        escalate: bool = True,
        strict: bool = False,
        project: str = "default",
        unlocked: bool = False,
    ) -> AIResult:
        """
        Send a chat request with smart routing and cost safeguards.
        
        Args:
            messages: OpenAI-format chat messages
            tier: Routing tier ("auto", "local", "cheap", "expensive")
            model_override: Force a specific model (bypasses routing)
            escalate: If True, escalate to better models on failures
            strict: If True, raise AIModelError if final result is poor/error
            project: Current project name for tracking
            unlocked: If True, allow expensive models even if auto-routing hits them
            
        Returns:
            AIResult with response text and metadata
        """
        # Validate tier
        valid_tiers = {"auto", "local", "cheap", "expensive"}
        if tier not in valid_tiers:
            raise ValueError(f"Invalid tier '{tier}'. Must be one of: {valid_tiers}")

        prompt_len = sum(len(m.get("content", "")) for m in messages)
        
        def finalize(result: AIResult) -> AIResult:
            """Log, record spend, and optionally raise on failure"""
            self.telemetry.log(result, prompt_len, project=project)
            
            # Record cost
            cost = self._estimate_call_cost(result, prompt_len)
            self.budget.record_spend(cost)
            
            if strict and (result.error or self._should_escalate(result)):
                raise AIModelError(
                    f"AI Router failed to get a valid response from {result.model}: "
                    f"{result.error or 'Quality check failed (response too short/refusal)'}", 
                    result
                )
            return result

        # Check daily budget before even starting
        if not self.budget.can_afford(0.01): # check if we have at least 1 cent left
             return AIResult(
                text="", provider="local", model="N/A", tier="auto", duration_ms=0,
                error=f"Budget exceeded. Remaining: ${self.budget.get_remaining():.4f}"
            )

        # Handle model override
        if model_override:
            # Check if override model is restricted
            if model_override in EXPENSIVE_MODELS and not unlocked:
                return AIResult(
                    text="", provider="local", model=model_override, tier="expensive", duration_ms=0,
                    error=f"Model '{model_override}' is restricted. Set unlocked=True to use."
                )

            # Determine provider based on model name or config
            config = self.model_config.get(model_override)
            provider = config.provider if config else None
            
            if provider == "local" or model_override == self.local_model:
                res = self._call_local(messages, model_override, tier="local")
            elif provider == "anthropic":
                res = self._call_anthropic(messages, model_override, tier="expensive")
            elif provider == "google":
                res = self._call_google(messages, model_override, tier="expensive")
            else:
                # Default to OpenAI for unknown models or explicit openai provider
                res = self._call_openai(messages, model_override, tier="expensive")
            return finalize(res)

        # Auto-route based on complexity
        chosen = self.route(messages) if tier == "auto" else tier
        
        # Cost safeguard: Downshift expensive to cheap if not unlocked
        if chosen == "expensive" and not unlocked:
             chosen = "cheap"
             print("[AIRouter] Downshifting 'expensive' to 'cheap' (set unlocked=True to bypass)")

        # Try local first, escalate if needed
        if chosen == "local":
            # Quick health check - skip local if Ollama is down
            if not self._is_ollama_available():
                if escalate:
                    chosen = "cheap"  # Fall through to cheap tier
                else:
                    return finalize(AIResult(
                        text="",
                        provider="local",
                        model=self.local_model,
                        tier="local",
                        duration_ms=0,
                        error="Ollama not available (health check failed)"
                    ))
            else:
                res = self._call_local(messages, self.local_model, tier="local")
                res.status_note = status_note
                if not escalate or not self._should_escalate(res, messages):
                    return finalize(res)

                # Escalate: local -> cheap
                res2 = self._call_openai(messages, self.cheap_model, tier="cheap")
                res2.status_note = status_note + " (escalated from local)"
                if not self._should_escalate(res2, messages):
                    return finalize(res2)

                res3 = self._call_openai(messages, self.expensive_model, tier="expensive")
                res3.status_note = status_note + " (escalated from local/cheap)"
                return finalize(res3)

        # Try cheap, escalate to expensive if needed
        if chosen == "cheap":
            res = self._call_openai(messages, self.cheap_model, tier="cheap")
            res.status_note = status_note
            if not escalate or not self._should_escalate(res):
                return finalize(res)
            res2 = self._call_openai(messages, self.expensive_model, tier="expensive")
            res2.status_note = status_note + " (escalated from cheap)"
            return finalize(res2)

        # Go straight to expensive
        res = self._call_openai(messages, self.expensive_model, tier="expensive")
        res.status_note = status_note
        return finalize(res)

    def _should_escalate(self, res: AIResult, original_messages: list[dict[str, str]]) -> bool:
        """
        Decide if a response is bad enough to escalate to a better model.
        """
        # Always escalate errors and timeouts
        if res.error or res.timed_out:
            return True
        
        # 1. Check for obvious refusals
        refusal_like = (
            "i can't" in res.text.lower() and 
            "here's" not in res.text.lower() and
            len(res.text) < 100
        )
        if refusal_like:
            return True

        # 2. Heuristic check for length
        if len(res.text.strip()) < 20:
            return True

        # 3. Judge Model Check (only for auto-routing, don't judge if model was overridden)
        if "auto" in res.status_note or res.tier == "local":
            prompt_summary = "\n".join(m.get("content", "")[:500] for m in original_messages)
            if not self._judge_response(prompt_summary, res.text):
                print(f"[AIRouter] Judge rejected response from {res.model}. Escalating...")
                return True
        
        return False

    def _judge_response(self, prompt_summary: str, response: str) -> bool:
        """Use a small model to judge if the response quality is acceptable"""
        if not self._is_ollama_available():
            return True # Assume OK if can't judge
            
        judge_prompt = f"""Evaluate the Following AI Response:
Task Summary: {prompt_summary}
Response: {response}

Is the response helpful and relevant to the task? 
Answer only 'YES' or 'NO'. 
Failure to answer in this format is unacceptable.
"""
        # Call local model without escalation or project tracking to avoid overhead/recursion
        t0 = time.time()
        try:
            completion = self.local_client.chat.completions.create(
                model=self.local_model,
                messages=[{"role": "user", "content": judge_prompt}],
                max_tokens=10
            )
            judge_text = completion.choices[0].message.content or "NO"
            return "YES" in judge_text.upper()
        except Exception:
            return True # Default to pass on error

    def _call_local(
        self,
        messages: list[dict[str, str]],
        model: str,
        *,
        tier: Tier
    ) -> AIResult:
        """Call local Ollama model via OpenAI-compatible API"""
        t0 = time.time()
        
        # Determine context window to allocate
        config = self.model_config.get(model)
        num_ctx = config.context_window if config else 4096
        
        try:
            # We use extra_body to pass Ollama-specific parameters like num_ctx
            completion = self.local_client.chat.completions.create(
                model=model,
                messages=messages,
                extra_body={
                    "options": {
                        "num_ctx": num_ctx
                    }
                }
            )
            text = completion.choices[0].message.content or ""
            return AIResult(
                text=text,
                provider="local",
                model=model,
                tier=tier,
                duration_ms=int((time.time() - t0) * 1000),
            )
        except (OSError, ConnectionError, TimeoutError) as e:
            return AIResult(
                text="",
                provider="local",
                model=model,
                tier=tier,
                duration_ms=int((time.time() - t0) * 1000),
                error=f"Local model error: {e}",
            )
        except Exception as e:
            # Re-raise unexpected errors (don't swallow SystemExit, KeyboardInterrupt, etc.)
            if isinstance(e, (SystemExit, KeyboardInterrupt, GeneratorExit)):
                raise
            return AIResult(
                text="",
                provider="local",
                model=model,
                tier=tier,
                duration_ms=int((time.time() - t0) * 1000),
                error=f"Unexpected error: {e}",
            )

    def _call_openai(
        self,
        messages: list[dict[str, str]],
        model: str,
        *,
        tier: Tier,
        max_retries: int = 3,
    ) -> AIResult:
        """Call OpenAI cloud API with retry logic for transient failures"""
        t0 = time.time()

        if not self.cloud_client:
            return AIResult(
                text="",
                provider="openai",
                model=model,
                tier=tier,
                duration_ms=0,
                error="OpenAI client not initialized (missing OPENAI_API_KEY)"
            )

        last_error = None
        for attempt in range(max_retries):
            try:
                completion = self.cloud_client.chat.completions.create(
                    model=model,
                    messages=messages,
                )
                text = completion.choices[0].message.content or ""
                return AIResult(
                    text=text,
                    provider="openai",
                    model=model,
                    tier=tier,
                    duration_ms=int((time.time() - t0) * 1000),
                )
            except Exception as e:
                if isinstance(e, (SystemExit, KeyboardInterrupt, GeneratorExit)):
                    raise

                last_error = e
                error_str = str(e).lower()

                # Retry on rate limits (429) and server errors (5xx)
                is_retryable = (
                    "429" in error_str or
                    "rate" in error_str or
                    "500" in error_str or
                    "502" in error_str or
                    "503" in error_str or
                    "504" in error_str or
                    "timeout" in error_str
                )

                if is_retryable and attempt < max_retries - 1:
                    # Exponential backoff with jitter: 1s, 2s, 4s
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue

                # Non-retryable error or max retries exceeded
                break

        return AIResult(
            text="",
            provider="openai",
            model=model,
            tier=tier,
            duration_ms=int((time.time() - t0) * 1000),
            error=f"OpenAI API error after {max_retries} attempts: {last_error}",
        )

    def _call_anthropic(
        self,
        messages: list[dict[str, str]],
        model: str,
        *,
        tier: Tier,
        max_retries: int = 3,
    ) -> AIResult:
        """Call Anthropic cloud API with retry logic"""
        t0 = time.time()

        if not self.anthropic_client:
            return AIResult(
                text="",
                provider="anthropic",
                model=model,
                tier=tier,
                duration_ms=0,
                error="Anthropic client not initialized (missing ANTHROPIC_API_KEY)"
            )

        # Convert OpenAI messages to Anthropic format
        system_msg = ""
        anthropic_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                anthropic_messages.append({"role": m["role"], "content": m["content"]})

        last_error = None
        for attempt in range(max_retries):
            try:
                # Use beta for 3.5 models if needed, but standard create usually works
                kwargs = {
                    "model": model,
                    "max_tokens": 4096,
                    "messages": anthropic_messages,
                }
                if system_msg:
                    kwargs["system"] = system_msg

                completion = self.anthropic_client.messages.create(**kwargs)
                text = completion.content[0].text if completion.content else ""
                return AIResult(
                    text=text,
                    provider="anthropic",
                    model=model,
                    tier=tier,
                    duration_ms=int((time.time() - t0) * 1000),
                )
            except Exception as e:
                if isinstance(e, (SystemExit, KeyboardInterrupt, GeneratorExit)):
                    raise

                last_error = e
                error_str = str(e).lower()
                
                # Anthropic retry logic
                is_retryable = any(x in error_str for x in ["429", "rate", "500", "502", "503", "504", "overloaded"])

                if is_retryable and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
                break

        return AIResult(
            text="",
            provider="anthropic",
            model=model,
            tier=tier,
            duration_ms=int((time.time() - t0) * 1000),
            error=f"Anthropic API error after {max_retries} attempts: {last_error}",
        )

    def _call_google(
        self,
        messages: list[dict[str, str]],
        model_name: str,
        *,
        tier: Tier,
        max_retries: int = 3,
    ) -> AIResult:
        """Call Google Gemini API with retry logic"""
        t0 = time.time()

        if not self.google_client:
            return AIResult(
                text="",
                provider="google",
                model=model_name,
                tier=tier,
                duration_ms=0,
                error="Google client not initialized (missing GOOGLE_API_KEY)"
            )

        # Convert messages to Gemini format
        try:
            # Simple conversion for now: join all as one prompt if not multi-turn
            prompt = ""
            for m in messages:
                prompt += f"{m['role'].upper()}: {m['content']}\n"
            prompt += "ASSISTANT:"

            last_error = None
            for attempt in range(max_retries):
                try:
                    response = self.google_client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    return AIResult(
                        text=response.text or "",
                        provider="google",
                        model=model_name,
                        tier=tier,
                        duration_ms=int((time.time() - t0) * 1000),
                    )
                except Exception as e:
                    if isinstance(e, (SystemExit, KeyboardInterrupt, GeneratorExit)):
                        raise
                    last_error = e
                    error_str = str(e).lower()
                    
                    # Gemini retryable errors
                    is_retryable = any(x in error_str for x in ["429", "rate", "500", "503", "quota"])
                    
                    if is_retryable and attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        time.sleep(wait_time)
                        continue
                    break
            
            return AIResult(
                text="",
                provider="google",
                model=model_name,
                tier=tier,
                duration_ms=int((time.time() - t0) * 1000),
                error=f"Google API error after {max_retries} attempts: {last_error}",
            )
        except Exception as e:
            return AIResult(
                text="",
                provider="google",
                model=model_name,
                tier=tier,
                duration_ms=int((time.time() - t0) * 1000),
                error=f"Google configuration error: {e}",
            )

    def get_performance_summary(self) -> str:
        """Analyze telemetry logs for performance ceilings"""
        if not os.path.exists(self.telemetry.log_path):
            return "No telemetry data found."
            
        stats = {
            "local": {"count": 0, "total_ms": 0, "errors": 0, "max_ms": 0},
            "openai": {"count": 0, "total_ms": 0, "errors": 0, "max_ms": 0},
            "anthropic": {"count": 0, "total_ms": 0, "errors": 0, "max_ms": 0},
            "google": {"count": 0, "total_ms": 0, "errors": 0, "max_ms": 0}
        }
        
        warnings = []
        
        try:
            with open(self.telemetry.log_path, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    prov = entry["provider"]
                    stats[prov]["count"] += 1
                    stats[prov]["total_ms"] += entry["duration_ms"]
                    if entry["duration_ms"] > stats[prov]["max_ms"]:
                        stats[prov]["max_ms"] = entry["duration_ms"]
                    if entry["error"]:
                        stats[prov]["errors"] += 1
                    if entry["performance_warning"]:
                        warnings.append(f"Slow/Failed call: {entry['model']} ({entry['duration_ms']}ms) at {entry['timestamp']}")
        except Exception as e:
            return f"Error reading logs: {e}"
            
        summary = ["--- AI Router Performance Summary ---"]
        for prov, s in stats.items():
            if s["count"] > 0:
                avg = s["total_ms"] / s["count"]
                summary.append(f"{prov.upper()}: {s['count']} calls, avg {avg:.0f}ms, max {s['max_ms']}ms, errors {s['errors']}")
        
        if warnings:
            summary.append("\nPerformance Ceilings Hit:")
            summary.extend(warnings[-5:]) # show last 5
            
        summary.append(f"\nEscalation Rate: {self.get_escalation_summary()}")
        summary.append(f"Budget Remaining: ${self.budget.get_remaining():.4f}")
            
        return "\n".join(summary)

    def get_project_usage(self) -> str:
        """Break down model usage by project"""
        if not os.path.exists(self.telemetry.log_path):
            return "No usage data."
            
        projects = {}
        
        try:
            with open(self.telemetry.log_path, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    project = entry.get("project", "default")
                    if project not in projects:
                        projects[project] = {"calls": 0, "models": {}}
                    
                    projects[project]["calls"] += 1
                    model = entry["model"]
                    projects[project]["models"][model] = projects[project]["models"].get(model, 0) + 1
        except Exception as e:
            return f"Error: {e}"
            
        lines = ["--- Project Usage Breakdown ---"]
        for p, data in projects.items():
            lines.append(f"\nProject: {p} ({data['calls']} calls)")
            for model, count in sorted(data["models"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  - {model}: {count}")
        
        return "\n".join(lines)

    def get_local_models(self) -> list[str]:
        """List models available in the local Ollama instance"""
        try:
            import httpx
            # Use the default local address directly as it's the most reliable for Ollama
            tags_url = "http://localhost:11434/api/tags"
            resp = httpx.get(tags_url)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
            return []
        except Exception:
            return []

    def _is_ollama_available(self, timeout: float = 2.0) -> bool:
        """Quick health check for Ollama availability"""
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def _estimate_call_cost(self, result: AIResult, input_chars: int) -> float:
        """Estimate the cost of a model call in USD"""
        if result.provider == "local" or result.error:
            return 0.0
            
        costs = MODEL_COSTS.get(result.model)
        if not costs:
            return 0.0
            
        input_tokens = input_chars // 4
        output_tokens = len(result.text) // 4
        
        # Always use at least 1 token if response was non-empty
        if output_tokens == 0 and result.text:
            output_tokens = 1
            
        return (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1000000

    def get_escalation_summary(self) -> str:
        """Calculate the rate of model escalations"""
        if not os.path.exists(self.telemetry.log_path):
            return "No escalation data."
            
        total_calls = 0
        escalations = 0
        
        try:
            with open(self.telemetry.log_path, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    total_calls += 1
                    # A call is an escalation if it's the result of a retry flow
                    # In our telemetry, we could track this, but for now we'll 
                    # approximate by looking for local/cheap models that took long
                    # or cloud calls where auto-routing was used.
                    if entry["tier"] != "local" and "auto" in entry.get("status_note", ""):
                        escalations += 1
        except Exception:
            pass
            
        if total_calls == 0: return "0%"
        rate = (escalations / total_calls) * 100
        return f"{rate:.1f}% ({escalations}/{total_calls})"

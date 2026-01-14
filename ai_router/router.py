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


class TelemetryLogger:
    """Lightweight logger for tracking AI Router performance"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_path = os.path.join(log_dir, "telemetry.jsonl")
        os.makedirs(log_dir, exist_ok=True)

    def log(self, result: AIResult, prompt_len: int):
        """Log a result to a JSONL file with file locking for concurrent safety"""
        entry = asdict(result)
        entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
        entry["prompt_len"] = prompt_len

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

    def route(self, messages: list[dict[str, str]]) -> Tier:
        """
        Determine routing tier based on message complexity and length.
        
        Args:
            messages: Chat messages to analyze
            
        Returns:
            Recommended tier: "local", "cheap", or "expensive"
        """
        content = "\n".join(m.get("content", "") for m in messages)
        n = len(content)
        
        # Token estimation heuristics:
        # - English prose: ~4 chars/token
        # - Code with symbols: ~3 chars/token
        # - Mixed content: use 3.5 as compromise
        # For safety, use conservative estimate (fewer chars per token = more tokens)
        has_code = "```" in content or "def " in content or "function " in content
        chars_per_token = 3 if has_code else 4
        est_tokens = n // chars_per_token

        # Obvious "heavy" signals - need expensive models
        heavy_signals = [
            "architecture", "refactor", "design doc", "threat model",
            "optimize", "benchmark", "edge cases", "security", "performance"
        ]
        
        # If it's a massive context (> 100k tokens), we prefer cloud models 
        # that handle large windows gracefully unless we know the local model can handle it.
        if est_tokens > 100000:
            return "expensive"

        if any(s in content.lower() for s in heavy_signals):
            return "expensive"
        
        # Code blocks suggest complexity
        if "```" in content:
            # If it's a lot of code, go expensive
            if n > 2000:
                return "expensive"
            return "cheap"
        
        # Long prompts need better models
        if n > 8000:
            return "expensive"

        # Medium length or questions
        if n > 2000 or "?" in content:
            return "cheap"

        # Short, simple tasks
        return "local"

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tier: Tier = "auto",
        model_override: Optional[str] = None,
        escalate: bool = True,
        strict: bool = False,
    ) -> AIResult:
        """
        Send a chat request with smart routing.
        
        Args:
            messages: OpenAI-format chat messages
            tier: Routing tier ("auto", "local", "cheap", "expensive")
            model_override: Force a specific model (bypasses routing)
            escalate: If True, escalate to better models on failures
            strict: If True, raise AIModelError if final result is poor/error
            
        Returns:
            AIResult with response text and metadata
        """
        # Validate tier
        valid_tiers = {"auto", "local", "cheap", "expensive"}
        if tier not in valid_tiers:
            raise ValueError(f"Invalid tier '{tier}'. Must be one of: {valid_tiers}")

        prompt_len = sum(len(m.get("content", "")) for m in messages)
        
        def finalize(result: AIResult) -> AIResult:
            """Log and optionally raise on failure"""
            self.telemetry.log(result, prompt_len)
            if strict and (result.error or self._should_escalate(result)):
                raise AIModelError(
                    f"AI Router failed to get a valid response from {result.model}: "
                    f"{result.error or 'Quality check failed (response too short/refusal)'}", 
                    result
                )
            return result

        # Handle model override
        if model_override:
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
                if not escalate or not self._should_escalate(res):
                    return finalize(res)

                # Escalate: local -> cheap
                res2 = self._call_openai(messages, self.cheap_model, tier="cheap")
                if not self._should_escalate(res2):
                    return finalize(res2)

                # Escalate: cheap -> expensive
                res3 = self._call_openai(messages, self.expensive_model, tier="expensive")
                return finalize(res3)

        # Try cheap, escalate to expensive if needed
        if chosen == "cheap":
            res = self._call_openai(messages, self.cheap_model, tier="cheap")
            if not escalate or not self._should_escalate(res):
                return finalize(res)
            res2 = self._call_openai(messages, self.expensive_model, tier="expensive")
            return finalize(res2)

        # Go straight to expensive
        res = self._call_openai(messages, self.expensive_model, tier="expensive")
        return finalize(res)

    def _should_escalate(self, res: AIResult) -> bool:
        """
        Decide if a response is bad enough to escalate to a better model.
        
        Args:
            res: Result from previous model call
            
        Returns:
            True if should escalate to better model
        """
        # Always escalate errors and timeouts
        if res.error or res.timed_out:
            return True
        
        # Lightweight "bad answer" detection
        # TODO: Replace with a judge model for better detection
        too_short = len(res.text.strip()) < 40
        
        # Common refusal patterns
        refusal_like = (
            "i can't" in res.text.lower() and 
            "here's" not in res.text.lower()
        )
        
        return too_short or refusal_like

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
            
        return "\n".join(summary)

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


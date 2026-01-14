# AI Router Remediation Implementation Prompt

**Target Model:** Gemini 3 Flash
**Project:** AI Router - Cost-optimized routing between local Ollama and cloud AI models
**Goal:** Implement all critical fixes identified in the engineering review

---

## Project Context

You are working on `ai-router`, a Python tool that routes AI requests between:
- **Local tier (free):** Ollama running locally with models like `llama3.2:3b`
- **Cheap tier:** OpenAI `gpt-4o-mini`
- **Expensive tier:** OpenAI `gpt-4o`

The router uses complexity heuristics to decide which tier to use, with automatic escalation on failures.

### Tech Stack
- Python 3.11+
- OpenAI SDK (`openai>=1.0.0`)
- Ollama (OpenAI-compatible API at `http://localhost:11434/v1`)
- JSONL telemetry logging

### File Structure
```
ai-router/
├── router.py              # Core routing logic (MAIN FILE TO EDIT)
├── requirements.txt       # Dependencies
├── logs/telemetry.jsonl   # Telemetry data
├── scripts/
│   ├── test_gauntlet.py
│   ├── test_local_rigor.py
│   ├── test_setup.py
│   ├── examples.py
│   ├── agent_skills_audit.py
│   ├── audit_skill_proposal.py
│   └── project_namer_test.py
└── __init__.py
```

---

## Tasks to Implement

Execute these tasks in order. Each task is self-contained with exact code changes.

---

### TASK 1: Add Missing httpx Dependency

**File:** `requirements.txt`

**Current content:**
```
openai>=1.0.0
```

**Change to:**
```
openai>=1.0.0
httpx>=0.25.0
```

**Why:** The `get_local_models()` function imports `httpx` at runtime but it's not in requirements.

**Verification:** `pip install -r requirements.txt && python -c "import httpx; print('OK')"`

---

### TASK 2: Fix Global State Mutation in MODEL_CONFIG

**File:** `router.py`

**Problem:** Line 140-141 mutates a module-level dict, causing cross-instance pollution.

**Find this code (around line 139-141):**
```python
        # Apply overrides to global config
        if model_config_overrides:
            MODEL_CONFIG.update(model_config_overrides)
```

**Replace with:**
```python
        # Create instance-local copy of model config (never mutate global)
        self.model_config = dict(MODEL_CONFIG)
        if model_config_overrides:
            self.model_config.update(model_config_overrides)
```

**Then update all references to `MODEL_CONFIG` inside the class to use `self.model_config`:**

Find (around line 323):
```python
        config = MODEL_CONFIG.get(model)
```

Replace with:
```python
        config = self.model_config.get(model)
```

---

### TASK 3: Fix Exception Handling - Don't Catch Fatal Errors

**File:** `router.py`

**Problem:** `except Exception` catches `SystemExit`, `KeyboardInterrupt`, etc.

**Find this code in `_call_local` (around line 345):**
```python
        except Exception as e:
            return AIResult(
                text="",
                provider="local",
                model=model,
                tier=tier,
                duration_ms=int((time.time() - t0) * 1000),
                error=str(e),
            )
```

**Replace with:**
```python
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
```

**Do the same for `_call_cloud` (around line 388):**

Find:
```python
        except Exception as e:
            return AIResult(
                text="",
                provider="openai",
                model=model,
                tier=tier,
                duration_ms=int((time.time() - t0) * 1000),
                error=str(e),
            )
```

Replace with:
```python
        except (OSError, ConnectionError, TimeoutError) as e:
            return AIResult(
                text="",
                provider="openai",
                model=model,
                tier=tier,
                duration_ms=int((time.time() - t0) * 1000),
                error=f"Cloud API error: {e}",
            )
        except Exception as e:
            if isinstance(e, (SystemExit, KeyboardInterrupt, GeneratorExit)):
                raise
            return AIResult(
                text="",
                provider="openai",
                model=model,
                tier=tier,
                duration_ms=int((time.time() - t0) * 1000),
                error=f"Unexpected error: {e}",
            )
```

---

### TASK 4: Add File Locking to Telemetry Logger

**File:** `router.py`

**Problem:** Concurrent writes to telemetry.jsonl can corrupt data.

**Add import at top of file (around line 10-15):**
```python
import fcntl
```

**Find the `log` method in `TelemetryLogger` class (around line 74-92):**
```python
    def log(self, result: AIResult, prompt_len: int):
        """Log a result to a JSONL file"""
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
                f.write(json.dumps(entry) + "\n")
        except Exception:
            # Never crash the app due to logging failure
            pass
```

**Replace with:**
```python
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
```

---

### TASK 5: Add Tier Validation

**File:** `router.py`

**Problem:** Invalid tier values are silently accepted.

**Find the `chat` method signature (around line 212-220):**
```python
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tier: Tier = "auto",
        model_override: Optional[str] = None,
        escalate: bool = True,
        strict: bool = False,
    ) -> AIResult:
```

**Add validation right after the docstring (around line 233, before `prompt_len = ...`):**
```python
        # Validate tier
        valid_tiers = {"auto", "local", "cheap", "expensive"}
        if tier not in valid_tiers:
            raise ValueError(f"Invalid tier '{tier}'. Must be one of: {valid_tiers}")
```

---

### TASK 6: Add Retry with Exponential Backoff for Cloud Calls

**File:** `router.py`

**Add import at top of file:**
```python
import random
```

**Find `_call_cloud` method and replace the entire method (around line 355-396):**

```python
    def _call_cloud(
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
                error="Cloud client not initialized (missing OPENAI_API_KEY)"
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
            error=f"Cloud API error after {max_retries} attempts: {last_error}",
        )
```

---

### TASK 7: Add Ollama Health Check Before Local Routing

**File:** `router.py`

**Add a new method to the `AIRouter` class (after `get_local_models`, around line 449):**

```python
    def _is_ollama_available(self, timeout: float = 2.0) -> bool:
        """Quick health check for Ollama availability"""
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False
```

**Modify the routing logic in `chat` to skip local if Ollama is down. Find this section (around line 259-263):**
```python
        # Try local first, escalate if needed
        if chosen == "local":
            res = self._call_local(messages, self.local_model, tier="local")
```

**Replace with:**
```python
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
                res2 = self._call_cloud(messages, self.cheap_model, tier="cheap")
                if not self._should_escalate(res2):
                    return finalize(res2)

                # Escalate: cheap -> expensive
                res3 = self._call_cloud(messages, self.expensive_model, tier="expensive")
                return finalize(res3)
```

---

### TASK 8: Fix Hardcoded Paths in Scripts

**For each file below, replace the hardcoded path with a relative path pattern.**

#### File: `scripts/test_gauntlet.py`

Find (line 6-8):
```python
# Add the parent directory to sys.path so we can import _tools
sys.path.append("/Users/eriksjaastad/projects")

from _tools.ai_router import AIRouter
```

Replace with:
```python
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter
```

#### File: `scripts/test_setup.py`

Find (line 9-11):
```python
# Add projects to path if not already there
projects_path = "/Users/eriksjaastad/projects"
if projects_path not in sys.path:
    sys.path.insert(0, projects_path)
```

Replace with:
```python
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
```

Also update the import (around line 14):
```python
from _tools.ai_router import AIRouter, AIResult
```
to:
```python
from router import AIRouter, AIResult
```

#### File: `scripts/agent_skills_audit.py`

Find (line 6-8):
```python
# Add project root to path for _tools access
sys.path.append("/Users/eriksjaastad/projects")

from _tools.ai_router import AIRouter
```

Replace with:
```python
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter
```

#### File: `scripts/audit_skill_proposal.py`

Find (line 6-8):
```python
# Add project root to path for _tools access
sys.path.append("/Users/eriksjaastad/projects")

from _tools.ai_router import AIRouter
```

Replace with:
```python
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter
```

#### File: `scripts/project_namer_test.py`

Find (line 7-9):
```python
# Add project root to path for _tools access
sys.path.append("/Users/eriksjaastad/projects")

from _tools.ai_router import AIRouter
```

Replace with:
```python
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter
```

---

### TASK 9: Improve Token Estimation

**File:** `router.py`

**Find (around line 177-178):**
```python
        # Rough token estimate (4 chars/token is conservative for English)
        est_tokens = n // 3
```

**Replace with:**
```python
        # Token estimation heuristics:
        # - English prose: ~4 chars/token
        # - Code with symbols: ~3 chars/token
        # - Mixed content: use 3.5 as compromise
        # For safety, use conservative estimate (fewer chars per token = more tokens)
        has_code = "```" in content or "def " in content or "function " in content
        chars_per_token = 3 if has_code else 4
        est_tokens = n // chars_per_token
```

---

### TASK 10: Add Safe Context Window Limits

**File:** `router.py`

**Find the MODEL_CONFIG definition (around line 32-40):**
```python
MODEL_CONFIG = {
    "llama3.2:3b": ModelInfo("llama3.2:3b", 128000, "local", "Small but capable local model"),
    "llama3.2:latest": ModelInfo("llama3.2:latest", 128000, "local"),
    "deepseek-r1:14b": ModelInfo("deepseek-r1:14b", 128000, "local", "Reasoning model"),
    "qwen3:4b": ModelInfo("qwen3:4b", 128000, "local"),
    "qwen3:14b": ModelInfo("qwen3:14b", 128000, "local"),
    "gpt-4o-mini": ModelInfo("gpt-4o-mini", 128000, "openai", "Cheap cloud model"),
    "gpt-4o": ModelInfo("gpt-4o", 128000, "openai", "Powerful cloud model"),
}
```

**Replace with more conservative local limits (realistic for consumer GPUs):**
```python
# Context windows: Use SAFE limits for local models (actual VRAM-constrained values)
# Cloud models can use full context, local models should be conservative
MODEL_CONFIG = {
    # Local models - conservative limits to avoid OOM on consumer GPUs
    "llama3.2:3b": ModelInfo("llama3.2:3b", 8192, "local", "Small but capable local model"),
    "llama3.2:latest": ModelInfo("llama3.2:latest", 8192, "local"),
    "deepseek-r1:14b": ModelInfo("deepseek-r1:14b", 16384, "local", "Reasoning model"),
    "qwen3:4b": ModelInfo("qwen3:4b", 8192, "local"),
    "qwen3:14b": ModelInfo("qwen3:14b", 16384, "local"),
    # Cloud models - full context available
    "gpt-4o-mini": ModelInfo("gpt-4o-mini", 128000, "openai", "Cheap cloud model"),
    "gpt-4o": ModelInfo("gpt-4o", 128000, "openai", "Powerful cloud model"),
}
```

---

## Verification Checklist

After implementing all tasks, run these commands to verify:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Verify imports work
python -c "import httpx; import fcntl; print('Imports OK')"

# 3. Run the router with a simple test
python -c "
from router import AIRouter
r = AIRouter()
print('Router initialized OK')
print(f'Model config is instance-local: {hasattr(r, \"model_config\")}')
"

# 4. Verify tier validation
python -c "
from router import AIRouter
r = AIRouter()
try:
    r.chat([{'role': 'user', 'content': 'test'}], tier='invalid')
    print('FAIL: Should have raised ValueError')
except ValueError as e:
    print(f'PASS: {e}')
"

# 5. Run existing tests (if Ollama is available)
python scripts/test_local_rigor.py
```

---

## Important Notes for Gemini

1. **Do not refactor beyond what's specified** - Only make the exact changes listed above.
2. **Preserve existing functionality** - These are targeted fixes, not a rewrite.
3. **Keep line numbers approximate** - The exact line numbers may shift as you make changes. Use the code patterns to find the right locations.
4. **Test after each major change** - Don't batch all changes and hope they work.
5. **Commit after each task** - Use clear commit messages like `fix: add file locking to telemetry (TASK 4)`.

---

## Commit Messages to Use

```
fix: add httpx to requirements.txt (TASK 1)
fix: use instance-local model config to prevent global state mutation (TASK 2)
fix: don't catch SystemExit/KeyboardInterrupt in API calls (TASK 3)
fix: add file locking to telemetry for concurrent write safety (TASK 4)
fix: add tier validation in chat() method (TASK 5)
feat: add retry with exponential backoff for cloud API calls (TASK 6)
feat: add Ollama health check before local routing (TASK 7)
fix: replace hardcoded paths with relative imports in scripts (TASK 8)
fix: improve token estimation with code detection heuristic (TASK 9)
fix: use conservative context limits for local models (TASK 10)
```

---

## Final State

After all tasks are complete, the router should:
- ✅ Have all dependencies in requirements.txt
- ✅ Use instance-local config (no global mutation)
- ✅ Properly handle fatal exceptions
- ✅ Use file locking for telemetry
- ✅ Validate tier input
- ✅ Retry cloud calls with backoff
- ✅ Health check Ollama before routing
- ✅ Work from any directory (no hardcoded paths)
- ✅ Have smarter token estimation
- ✅ Use safe context limits for local models

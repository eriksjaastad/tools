# AI Router - Engineering Review

**Review Date:** 2026-01-05 08:45:00 UTC
**Reviewer:** Senior Principal Engineer
**Scope:** Full codebase audit for production readiness

---

## 1. The Engineering Verdict

### **[Needs Major Refactor]**

The routing heuristics are a house of cards built on the foundation of `chars // 3` and a hardcoded keyword list. This tool will silently escalate to expensive models the moment a user writes "optimize" in a grocery list, while simultaneously starving complex prompts of context because you never validated that your 128k `num_ctx` allocation will fit in VRAM. The telemetry is one concurrent write away from corruption, and every script in `scripts/` is hardcoded to `[USER_HOME]/projects`—which violates your own `AGENTS.md` rule on line 24. This is not production infrastructure; it's a prototype that hasn't been stress-tested outside your MacBook.

---

## 2. The "Toy" Test & Utility Reality Check

### False Confidence

#### Issue 1: Token Estimation is Numerology
- **File:** `router.py:178`
- **Code:** `est_tokens = n // 3`
- **Problem:** This is not tokenization. OpenAI uses BPE (tiktoken), Llama uses SentencePiece. For English text, 4 chars/token is already optimistic; for code with symbols, it's completely wrong. A 9000-char code block might be 3500+ tokens, not 3000.
- **Impact:** Routing decisions based on token count are guesses. You'll route a 90k-token prompt to local because you estimated 100k.

#### Issue 2: VRAM Allocation is Fantasy
- **File:** `router.py:324`
- **Code:** `num_ctx = config.context_window if config else 4096`
- **Problem:** You're requesting 128k context from `llama3.2:3b` without verifying the GPU can hold it. A 3B model at 128k context in fp16 needs ~48GB+ VRAM. Your MacBook doesn't have that.
- **Impact:** Ollama will silently truncate context or OOM. You'll get hallucinations from a model that only saw the first 8k tokens.

#### Issue 3: Silent Telemetry Swallowing
- **File:** `router.py:90-92`
- **Code:**
```python
except Exception:
    # Never crash the app due to logging failure
    pass
```
- **Problem:** You're swallowing every logging failure. Disk full? Swallowed. Permission denied? Swallowed. File corrupted? Swallowed.
- **Impact:** You'll think everything is fine until you check the logs and find nothing for the last 3 weeks.

#### Issue 4: Global State Mutation
- **File:** `router.py:140-141`
- **Code:**
```python
if model_config_overrides:
    MODEL_CONFIG.update(model_config_overrides)
```
- **Problem:** `MODEL_CONFIG` is a module-level dict. Multiple `AIRouter` instances will pollute each other's config. This is a classic shared-state bug.
- **Impact:** In a multi-tenant or concurrent scenario, one router's config changes affect all routers.

---

### The Bus Factor

#### Implicit Conventions Not Enforced
1. **`chars // 3` ratio** — Nowhere is this documented or tested. New maintainers won't know why routing is wrong.
2. **Magic keyword list** (`router.py:181-185`) — `["architecture", "refactor", "design doc", ...]` is not versioned, tested, or configurable.
3. **Telemetry path** (`logs/telemetry.jsonl`) — Hardcoded relative path assumes CWD is the project root. Run from `/tmp` and telemetry goes to `/tmp/logs/`.

#### Missing Dependency
- **`httpx`** is used in `router.py:441` but not listed in `requirements.txt:1`. The package will crash on first call to `get_local_models()`.

#### Hardcoded Paths Violating AGENTS.md
Your own `AGENTS.md:24` says "NEVER use absolute paths." Yet:
- `scripts/test_gauntlet.py:6` → `[USER_HOME]/projects`
- `scripts/test_local_rigor.py:7` → Uses relative `Path(__file__).parent.parent.parent` (correct)
- `scripts/test_setup.py:9` → `[USER_HOME]/projects`
- `scripts/agent_skills_audit.py:6` → `[USER_HOME]/projects`
- `scripts/audit_skill_proposal.py:6` → `[USER_HOME]/projects`
- `scripts/project_namer_test.py:7` → `[USER_HOME]/projects`

Five out of six scripts are broken on any machine that isn't yours.

---

### 10 Failure Modes

| # | Scenario | File:Line | Consequence |
|---|----------|-----------|-------------|
| 1 | Ollama running but model not pulled | `router.py:328-336` | Generic exception swallowed, escalates to cloud with no indication why local failed |
| 2 | Telemetry file locked by another process | `router.py:88` | Silent write failure, data lost |
| 3 | OpenAI returns 429 (rate limit) | `router.py:388` | No retry/backoff, escalation fails, strict mode raises on the first rate limit |
| 4 | Context window exceeds VRAM | `router.py:332-335` | Ollama silently truncates or OOMs, no validation |
| 5 | Prompt contains "security" but is trivial | `router.py:191` | Forced to expensive tier for "Is security a priority?" |
| 6 | Response is exactly 40 chars | `router.py:302` | Borderline—might escalate, might not, untested |
| 7 | `model_config_overrides` from concurrent instances | `router.py:140` | Global state pollution |
| 8 | Run scripts from different CWD | `router.py:71` | Telemetry goes to wrong directory |
| 9 | Refusal detection triggers on "I can't believe..." | `router.py:305-308` | False positive escalation |
| 10 | `httpx` not installed | `router.py:441` | `ImportError` on first `get_local_models()` call |

---

## 3. Deep Technical Teardown

### Architectural Anti-Patterns

#### 1. The Escalation Chain Has No Backpressure
```python
# router.py:265-272
res2 = self._call_cloud(messages, self.cheap_model, tier="cheap")
if not self._should_escalate(res2):
    return finalize(res2)
res3 = self._call_cloud(messages, self.expensive_model, tier="expensive")
return finalize(res3)
```
If `cheap` returns a rate limit (429), you immediately hammer `expensive`. No exponential backoff. No retry on transient failures. Just escalate and pray.

#### 2. Strict Mode is Incomplete
Strict mode raises `AIModelError` after the final result, but:
- It doesn't prevent the telemetry log of the failed call
- It doesn't distinguish "transient failure" from "permanent failure"
- It wraps errors in a custom exception but loses the original traceback

#### 3. OpenAI SDK Timeout Configuration
```python
# router.py:146-147
timeout=local_timeout_s
```
You're passing a float to `OpenAI(timeout=...)`, but the SDK expects a `Timeout` object for granular control (connect vs. read vs. write). This works but leaves you with no control over connect timeouts vs. inference timeouts.

### State & Data Integrity

#### Telemetry JSONL Integrity
- **No file locking** — Two processes writing simultaneously will interleave bytes, corrupting both entries.
- **No rotation** — File grows forever until disk is full.
- **No atomic writes** — Crash mid-write leaves truncated JSON line.
- **Fix:** Use `fcntl.flock()` or write to temp file and atomic rename.

#### MODEL_CONFIG Accuracy
```python
"llama3.2:3b": ModelInfo("llama3.2:3b", 128000, "local", "Small but capable local model"),
```
The real context window for `llama3.2:3b` is **131072** tokens according to Ollama docs, but:
1. You're storing characters, not tokens—confusing.
2. You never validated this against the actual model's `modelfile`.

#### Type Coercion Risks
```python
# router.py:343
duration_ms=int((time.time() - t0) * 1000),
```
If `time.time()` returns a negative delta (clock skew), you get a negative `duration_ms`. Telemetry consumers expecting positive integers will fail.

### Silent Killers

#### 1. Exception Blanket in `_call_local`
```python
# router.py:345-353
except Exception as e:
    return AIResult(..., error=str(e))
```
All exceptions become strings. `KeyboardInterrupt`? Caught. `SystemExit`? Caught. Memory error? Caught. You've turned every fatal condition into a "soft" error.

#### 2. No Health Check for Ollama
`get_local_models()` exists but isn't called before routing to local. You could be routing to a dead endpoint for 60 seconds before timing out.

#### 3. Telemetry File Handle Not Managed
```python
with open(self.log_path, "a") as f:
    f.write(json.dumps(entry) + "\n")
```
Good—using `with`. But if exception occurs between `json.dumps` and `f.write`, partial state could occur. Minor, but shows lack of defensive coding.

### Complexity Tax

#### Underutilized Abstractions
- `ModelInfo` dataclass has `description` field used nowhere in routing logic.
- `Tier` type alias is defined but never validated—you can pass `tier="potato"` and it'll try to route.

#### Brittle Heuristics
```python
heavy_signals = [
    "architecture", "refactor", "design doc", "threat model",
    "optimize", "benchmark", "edge cases", "security", "performance"
]
```
This is a maintenance nightmare. Add "security" to every prompt as a system instruction and watch your costs 10x.

---

## 4. Evidence-Based Critique

| Issue | File:Line | Code Evidence | Impact |
|-------|-----------|---------------|--------|
| Token estimation | `router.py:178` | `est_tokens = n // 3` | Wrong routing for code/non-English |
| Missing dependency | `router.py:441` | `import httpx` | Runtime ImportError |
| Global state mutation | `router.py:140-141` | `MODEL_CONFIG.update(...)` | Multi-instance pollution |
| Hardcoded paths | `test_gauntlet.py:6` | `[USER_HOME]/projects` | Breaks on any other machine |
| Silent log failure | `router.py:90-92` | `except Exception: pass` | Lost telemetry |
| No VRAM validation | `router.py:324` | `num_ctx = config.context_window` | OOM or silent truncation |
| Catch-all exception | `router.py:345` | `except Exception as e:` | Catches fatal errors |
| No file locking | `router.py:88` | `open(..., "a")` | Concurrent write corruption |
| Keyword magic | `router.py:181-185` | `heavy_signals = [...]` | Unpredictable routing |
| No 429 retry | `router.py:375-396` | Direct API call | Rate limit = failure |

---

## 5. Minimum Viable Power (MVP)

### The Signal (Worth Saving)
1. **`strict` mode concept** — Failing loudly is correct for pipelines. Keep it, but fix the error propagation.
2. **`num_ctx` allocation** — Right idea, wrong execution. Validate against actual VRAM.
3. **Telemetry structure** — JSONL with timestamps and performance warnings is solid. Just needs integrity fixes.
4. **Escalation chain design** — `local → cheap → expensive` is the right architecture. Just needs backoff logic.
5. **`test_local_rigor.py`** — Uses proper relative paths. This is your reference for fixing the others.

### The Noise (Delete or Simplify)
1. **`ModelInfo.description`** — Unused. Either use it in routing or delete it.
2. **`get_performance_summary()`** — Cute but reads the entire log file every time. Will be O(n) slow with millions of entries.
3. **All scripts with hardcoded paths** — Either fix them or delete them; they're currently broken.
4. **`examples.py:example_error_handling()`** — Tests with a bad endpoint but doesn't verify the escalation actually worked.

---

## 6. Remediation Task Breakdown

### Task 1: Add httpx to requirements.txt
- **File:** `requirements.txt`
- **Change:** Add `httpx>=0.25.0` on line 2
- **Done When:** `pip install -r requirements.txt && python -c "import httpx"` succeeds

### Task 2: Fix Token Estimation
- **File:** `router.py:178`
- **Change:** Replace `n // 3` with `n // 4` (slightly better) or add tiktoken for accurate counts
- **Done When:** Unit test with known token counts passes

### Task 3: Remove Absolute Paths from Scripts
- **Files:** `test_gauntlet.py:6`, `test_setup.py:9`, `agent_skills_audit.py:6`, `audit_skill_proposal.py:6`, `project_namer_test.py:7`
- **Change:** Replace with `sys.path.append(str(Path(__file__).parent.parent))` pattern from `test_local_rigor.py`
- **Done When:** Scripts run from any directory

### Task 4: Add File Locking to Telemetry
- **File:** `router.py:87-92`
- **Change:** Use `fcntl.flock(f.fileno(), fcntl.LOCK_EX)` before write
- **Done When:** Two concurrent writers don't corrupt data

### Task 5: Don't Catch SystemExit/KeyboardInterrupt
- **File:** `router.py:345`
- **Change:** Change `except Exception` to `except (httpx.HTTPError, openai.APIError, ...)`
- **Done When:** Ctrl+C actually exits

### Task 6: Add VRAM Validation
- **File:** `router.py:322-324`
- **Change:** Query Ollama for model's actual context limit or add a `max_safe_ctx` config
- **Done When:** OOM test no longer crashes

### Task 7: Add Retry with Backoff for Cloud Calls
- **File:** `router.py:375-396`
- **Change:** Add tenacity or manual exponential backoff for 429/5xx errors
- **Done When:** Rate limit → retry → success instead of immediate failure

### Task 8: Validate Tier Input
- **File:** `router.py:212-220`
- **Change:** Add runtime validation that `tier in {"auto", "local", "cheap", "expensive"}`
- **Done When:** `router.chat(messages, tier="invalid")` raises `ValueError`

### Task 9: Fix Global State Mutation
- **File:** `router.py:139-141`
- **Change:** Create instance-local copy: `self.model_config = {**MODEL_CONFIG, **(model_config_overrides or {})}`
- **Done When:** Two routers with different overrides don't affect each other

### Task 10: Add Ollama Health Check Before Routing
- **File:** `router.py:260`
- **Change:** Call `get_local_models()` with a timeout and skip local if Ollama is down
- **Done When:** Dead Ollama → immediate escalation instead of 60s timeout

---

## 7. Task Dependency Graph

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CRITICAL DATA INTEGRITY                          │
├────────────────────────────────────────────────────────────────────────┤
│  Task 1 (httpx)  ──┐                                                   │
│  Task 4 (flock)  ──┼──▶  Task 9 (global state)                         │
│  Task 5 (except) ──┘                                                   │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         RELIABILITY LAYER                               │
├────────────────────────────────────────────────────────────────────────┤
│  Task 6 (VRAM)  ───▶  Task 10 (health check)  ───▶  Task 7 (retry)     │
│                                                                         │
│  Task 8 (validate tier)                                                 │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         PORTABILITY / DX                                │
├────────────────────────────────────────────────────────────────────────┤
│  Task 3 (paths)  ───▶  Task 2 (token estimation)                       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Recommended Execution Order

### Phase 1: Critical Reliability (Do Now)
1. **Task 1:** Add httpx to requirements.txt
2. **Task 5:** Fix exception catching (don't catch `BaseException`)
3. **Task 4:** Add file locking to telemetry
4. **Task 9:** Fix global state mutation

### Phase 2: Operational Safety (Do This Week)
5. **Task 6:** Add VRAM validation / safe context limits
6. **Task 10:** Add Ollama health check
7. **Task 7:** Add retry with backoff
8. **Task 8:** Validate tier input

### Phase 3: Portability & Polish (Do Eventually)
9. **Task 3:** Fix hardcoded paths in scripts
10. **Task 2:** Improve token estimation

---

## 9. Summary

This router is a local-development toy masquerading as infrastructure. You've built the happy path—local Ollama up, models pulled, single-threaded, your MacBook, your paths. The moment any of those assumptions fail, the system silently degrades: telemetry vanishes, routing becomes random, and "strict mode" throws an exception with no actionable context. The token estimation (`chars // 3`) is cargo-cult math, the keyword routing is a game of Jeopardy! where the answer is "things Erik types sometimes," and the 128k context allocation will OOM any consumer GPU on the planet. Fix the data integrity first (file locking, exception handling), then add the safety rails (health checks, retry logic), and finally stop committing absolute paths to your own home directory.

> **"A router that routes based on magic words is not a router—it's a ouija board with an API key."**


## Related Documentation

- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI


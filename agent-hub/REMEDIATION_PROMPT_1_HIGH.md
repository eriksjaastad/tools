# Remediation Prompt 1: agent-hub HIGH Priority Fixes

**Source:** CODE_REVIEW_CLAUDE_v1.md
**Priority:** HIGH (Block Production)
**Estimated Scope:** 3 files + requirements.txt

---

## Context

Code review identified three HIGH priority issues that must be fixed before agent-hub can run unattended in production.

---

## Task 1: Add Subprocess Timeouts

**Files to modify:**
- `src/git_manager.py` - Line 24-30
- `src/hub.py` - Line 47-52
- `src/listener.py` - Line 286

**What to do:**

Add `timeout` parameter to all `subprocess.run()` calls:

```python
# git_manager.py - add timeout=60
result = subprocess.run(
    ["git"] + args,
    cwd=self.repo_root,
    capture_output=True,
    text=True,
    check=check,
    timeout=60  # ADD THIS
)

# hub.py - add check=True and timeout=30
result = subprocess.run(
    ["python3", "src/watchdog.py", "status"],
    capture_output=True,
    text=True,
    check=True,   # ADD THIS
    timeout=30    # ADD THIS
)

# listener.py - add timeout appropriate for the operation
```

**Why:** Without timeouts, a hung git command or subprocess can stall the entire pipeline indefinitely.

---

## Task 2: Replace Silent Exceptions with Logging

**Files to modify:**
- `src/config.py` - Lines 66-67
- `src/watchdog.py` - Lines 95-96, 111-113, 364-365, 376-377
- `src/git_manager.py` - Lines 113-114
- `src/utils.py` - Lines 39-40
- `src/hub_client.py` - Lines 24-25
- `src/mcp_client.py` - Lines 53-54
- `src/worker_client.py` - Lines 45-46

**What to do:**

Replace every `except: pass` or `except Exception: pass` with logging:

```python
# BEFORE
except Exception:
    pass

# AFTER
except Exception as e:
    logger.debug(f"Ignored exception: {e}")
```

Use appropriate log levels:
- `logger.debug()` - Expected/recoverable errors (like "process already dead")
- `logger.warning()` - Unexpected but handled errors
- `logger.error()` - Errors that may indicate a problem

**Why:** Silent exceptions hide bugs and make debugging impossible.

---

## Task 3: Pin Dependencies

**File to modify:** `requirements.txt`

**Current state:**
```
git+https://github.com/openai/swarm.git
litellm
openai
pytest
jsonschema
python-dotenv
```

**Replace with:**
```
git+https://github.com/openai/swarm.git@v0.1.0
litellm>=1.0,<2.0
openai>=1.0,<2.0
pytest>=7.0,<9.0
jsonschema>=4.0,<5.0
python-dotenv>=1.0,<2.0
```

**Note:** Check the current swarm repo for the latest stable tag/commit. If no tags exist, pin to a specific commit hash.

**Why:** Unpinned dependencies can break the build at any time due to upstream changes.

---

## Acceptance Criteria

- [ ] All `subprocess.run()` calls have `timeout` parameter
- [ ] No bare `except: pass` patterns remain in src/
- [ ] All exceptions either log or have a comment explaining why silence is intentional
- [ ] `requirements.txt` has version bounds on all dependencies
- [ ] `pytest tests/` still passes
- [ ] `python src/watchdog.py status` still works

---

## Verification Commands

```bash
# Check for remaining silent exceptions
grep -rn 'except.*:' src/ | grep -A1 'pass$'

# Check for subprocess calls without timeout
grep -rn 'subprocess.run' src/

# Run tests
pytest tests/

# Smoke test
python src/watchdog.py status
```

---

*This prompt addresses items H1, M2, and D1 from CODE_REVIEW_CLAUDE_v1.md*

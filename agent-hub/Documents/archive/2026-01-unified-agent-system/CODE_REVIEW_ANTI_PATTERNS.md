# Code Review Anti-Patterns Database

This database tracks recurring defects found in the project-scaffolding ecosystem. Use this as a reference for both manual reviews and when updating the `scripts/pre_review_scan.sh`.

---

### Anti-Pattern #1: Hardcoded Absolute Paths

**What:** `/Users/...` or `/home/...` or similar machine-specific paths.

**Where to Look:**
- `templates/*.template` files
- `.cursorrules*`
- `*.yaml` files
- Scripts (`scripts/`, `scaffold/`)
- `AGENTS.md`, `CLAUDE.md`

**Scan Command:**
```bash
grep -rn "/Users/" templates/ .cursorrules* *.yaml scripts/ scaffold/ AGENTS.md CLAUDE.md | grep -v "absolute paths (e.g.,"
```

**Fix:**
- Use `Path.home() / "projects"`
- Use `os.getenv("PROJECTS_ROOT")`
- Use relative paths via `Path(__file__).parent`

---

### Anti-Pattern #2: Silent Exception Swallowing

**What:** `except: pass` or `except Exception: pass` without logging or re-raising.

**Where to Look:**
- All Python files.
- Especially in cleanup code or non-critical paths.

**Scan Command:**
```bash
grep -rn "except.*:" scripts/ scaffold/ | grep "pass"
```

**Fix:**
- Log the error using `logging.error()` or `logging.warning()`.
- Return an error status code.
- Re-raise if the error cannot be handled.
- Document why silence is acceptable (rare).

---

### Anti-Pattern #3: Unpinned Dependencies

**What:** Using `>=` without an upper bound in `requirements.txt`.

**Where to Look:**
- `requirements.txt`

**Scan Command:**
```bash
grep -E "^[^#].*>=[0-9]" requirements.txt | grep -v "~="
```

**Fix:**
- Use `~=` for compatible releases (e.g., `anthropic~=0.18.0`).
- Add upper bounds for major versions.
- Pin exact versions in `requirements.txt` if absolute stability is needed.

---

### Anti-Pattern #4: Test Scope Mismatch

**What:** A test claims to check a whole category but only checks a small subset.

**Where to Look:**
- Test file names vs. what they actually check.
- Docstrings vs. implementation.

**Detection:**
- Read the test code and verify the scope matches the name/docstring.
- Ask: "What does this test NOT check?"

**Fix:**
- Expand the test scope.
- Rename the test to match its actual scope.
- Add companion tests for unchecked areas.

---

### Anti-Pattern #5: Deprecated API Usage

**What:** Using old APIs that have replacements (e.g., Pydantic `validator` -> `field_validator`).

**Where to Look:**
- Import statements.
- Decorator usage.

**Detection:**
- Check library changelogs for deprecated features.
- Look for deprecation warnings in test output.

**Fix:**
- Upgrade to the current API.
- Add a TODO if a breaking change requires more work.

---

### Anti-Pattern #6: Interactivity in CI/CD

**What:** Scripts that wait for user input (e.g., `input()`, `send2trash` permission prompts) in non-interactive environments.

**Where to Look:**
- CLI scripts used in automation.

**Fix:**
- Use `--yes` or `--non-interactive` flags.
- Detect if running in TTY and skip interactive prompts.
- Use libraries that support non-interactive modes.

---
*This database is part of the v1.1 Ecosystem Governance & Review Protocol.*

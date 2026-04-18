# Fix Dependencies Prompt

**Goal:** Fix 8 issues found during test validation (6 deps + 2 env hygiene).

---

## Issues to Fix

### 1. flo-fi - CRITICAL: Next.js vulnerabilities

```bash
cd ../../flo-fi

# Check current Next.js version
cat package.json | grep next

# Update Next.js to latest
npm update next

# If that doesn't fix it, install latest explicitly
npm install next@latest

# Verify fix
npm audit 2>&1 | grep -i "next\|critical"
```

---

### 2. ollama-mcp - HIGH: SDK vulnerability

```bash
cd ../ollama-mcp

# Check what sdk package has the issue
npm audit 2>&1 | head -40

# Try automated fix
npm audit fix

# If that fails, check which package and update it
npm ls | grep sdk
npm update [package-name]

# Rebuild after fix
npm run build

# Verify
npm audit 2>&1 | grep -i "high\|critical"
```

---

### 3. portfolio-ai - MODERATE: esbuild/vite vulnerabilities

```bash
cd ../../portfolio-ai

# Update vite and esbuild
npm update vite esbuild

# Or install latest
npm install vite@latest esbuild@latest

# Verify
npm audit 2>&1 | grep -i "moderate\|high\|critical"
```

---

### 4. tax-organizer - MODERATE: esbuild/vite vulnerabilities

```bash
cd ../../tax-organizer/frontend

# Update vite and esbuild
npm update vite esbuild

# Or install latest
npm install vite@latest esbuild@latest

# Verify
npm audit 2>&1 | grep -i "moderate\|high\|critical"
```

---

### 5. national-cattle-brands - SETUP: Playwright missing

```bash
cd ../../national-cattle-brands/texas_brand_scraper

# Activate venv
source venv/bin/activate

# Install playwright browsers
playwright install

# Verify
playwright --version
python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

---

---

## Report Results

After fixing, update `../../TODO.md`:

Change these rows from `[ ]` to `[x]` in the L3 Deps column if fixed:
- flo-fi
- portfolio-ai
- tax-organizer
- ollama-mcp

For national-cattle-brands, add note that playwright is now installed.

---

## Fixes Complete

| # | Project | Issue | Status | Notes |
|---|---------|-------|--------|-------|
| 1 | flo-fi | Next.js critical | FIXED | Updated to 14.2.35 |
| 2 | ollama-mcp | SDK high | FIXED | Updated SDK to 1.25.2 |
| 3 | portfolio-ai | esbuild/vite | FIXED | Updated Vite to 7.3.1 |
| 4 | tax-organizer | esbuild/vite | FIXED | Updated Vite to 7.3.1 |
| 5 | national-cattle-brands | playwright | FIXED | Browsers installed |
| 6 | ai-usage-billing-tracker | Python 3.14/greenlet | DELETED | Project removed 2026-04-10 |
| 7 | 4 projects | .env.example missing | FIXED | Created examples for billing, cortana, holoscape, trading |
| 8 | cortana-personal-ai | load_dotenv() missing | FIXED | Added to core scripts |

If any can't be fixed (breaking changes, etc.), document why and what version is needed.

---

## Part 2: Environment File Hygiene

### 7. Create missing .env.example files

Four projects have `.env` but no `.env.example`. Create the example file for each:

**cortana-personal-ai:**
```bash
cd ../../cortana-personal-ai
cat .env | sed 's/=.*/=/' > .env.example
cat .env.example
```

**holoscape:**
```bash
cd ../../holoscape
cat .env | sed 's/=.*/=/' > .env.example
cat .env.example
```

**trading-copilot:**
```bash
cd ../../trading-copilot
cat .env | sed 's/=.*/=/' > .env.example
cat .env.example
```

---

### 8. Fix cortana-personal-ai load_dotenv() missing

The `.env` file exists but the code never loads it. Add `load_dotenv()` to the main scripts.

```bash
cd ../../cortana-personal-ai/scripts/core

# Check if python-dotenv is in requirements
grep dotenv ../requirements.txt || echo "python-dotenv" >> ../requirements.txt

# Add load_dotenv to the scripts that use env vars
for script in personal_ai_listener.py daily_update.py backfill_historical.py; do
  # Check if already has load_dotenv
  if ! grep -q "load_dotenv" "$script"; then
    # Add import after other imports (after the first blank line following imports)
    sed -i '' '1,/^import/{ /^import/a\
from dotenv import load_dotenv
}' "$script"

    # This sed is tricky - easier to do manually:
    echo "MANUAL FIX NEEDED: Add these lines near top of $script:"
    echo "  from dotenv import load_dotenv"
    echo "  load_dotenv()"
  fi
done
```

**Manual fix if sed is tricky:**

For each of these files:
- `scripts/core/personal_ai_listener.py`
- `scripts/core/daily_update.py`
- `scripts/core/backfill_historical.py`

Add near the top (after other imports):
```python
from dotenv import load_dotenv
load_dotenv()
```

Verify:
```bash
source venv/bin/activate
python -c "from scripts.core.personal_ai_listener import *; print('OK')"
```

## Related Documentation

- [LOCAL_MODEL_LEARNINGS](../../writing/Documents/reference/LOCAL_MODEL_LEARNINGS.md) - local AI
- [cortana-personal-ai/README](../../ai-model-scratch-build/README.md) - Cortana AI
- [flo-fi/README](../../ai-model-scratch-build/README.md) - Flo-Fi
- [holoscape/README](../../ai-model-scratch-build/README.md) - Holoscape
- [national-cattle-brands/README](../../ai-model-scratch-build/README.md) - Cattle Brands
- [portfolio-ai/README](../../ai-model-scratch-build/README.md) - Portfolio AI
- [tax-organizer/README](../../ai-model-scratch-build/README.md) - Tax Organizer
- [trading-copilot/README](../../ai-model-scratch-build/README.md) - Trading Copilot

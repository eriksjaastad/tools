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

### 6. ai-usage-billing-tracker - CRITICAL: Python 3.14 incompatibility

The `greenlet` dependency fails to build on Python 3.14. Need to use Python 3.11 or 3.12.

```bash
cd ../../ai-usage-billing-tracker

# Check current Python version
python --version

# If 3.14, need to create venv with older Python
# First, check if pyenv or another Python is available
which python3.12 || which python3.11

# Remove old venv and recreate with compatible Python
rm -rf venv
python3.12 -m venv venv  # or python3.11
source venv/bin/activate

# Reinstall deps
pip install -r requirements.txt

# Verify greenlet installs
pip list | grep greenlet
```

If Python 3.11/3.12 not available:
```bash
# Install via pyenv
pyenv install 3.12.0
pyenv local 3.12.0
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

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
| 6 | ai-usage-billing-tracker | Python 3.14/greenlet | FIXED | Recreated venv with Py3.11 |
| 7 | 4 projects | .env.example missing | FIXED | Created examples for billing, cortana, holoscape, trading |
| 8 | cortana-personal-ai | load_dotenv() missing | FIXED | Added to core scripts |

If any can't be fixed (breaking changes, etc.), document why and what version is needed.

---

## Part 2: Environment File Hygiene

### 7. Create missing .env.example files

Four projects have `.env` but no `.env.example`. Create the example file for each:

**ai-usage-billing-tracker:**
```bash
cd ../../ai-usage-billing-tracker
cat .env | sed 's/=.*/=/' > .env.example
cat .env.example  # Verify it has variable names only
```

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

- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[billing_workflows]] - billing/payments
- [[dashboard_architecture]] - dashboard/UI
- [[prompt_engineering_guide]] - prompt engineering
- [[tax_documentation]] - tax/accounting
- [[case_studies]] - examples
- [[cortana_architecture]] - Cortana AI
- [[holoscape_architecture]] - Holoscape
- [[portfolio_content]] - portfolio/career
- [[ai-usage-billing-tracker/README]] - AI Billing Tracker
- [[cortana-personal-ai/README]] - Cortana AI
- [[flo-fi/README]] - Flo-Fi
- [[holoscape/README]] - Holoscape
- [[national-cattle-brands/README]] - Cattle Brands
- [[portfolio-ai/README]] - Portfolio AI
- [[tax-organizer/README]] - Tax Organizer
- [[trading-copilot/README]] - Trading Copilot

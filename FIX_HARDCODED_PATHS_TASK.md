# TASK: Fix Hardcoded Paths in Tools Repo

**Priority:** High
**Created by:** Claude (Laptop Architect)
**Date:** 2026-03-21
**For:** Whoever works on the `tools` repo on the Mac Mini

---

## THE PROBLEM

Several files in this repo have **hardcoded absolute paths** that only work on ONE machine. Some use the laptop path (`~/projects/_tools/...`) and some use the Mac Mini path (`~/.openclaw/workspace/projects/...`). Neither is correct for a shared repo.

**The two machines have different project roots:**
- **Laptop:** `~/projects/_tools/`
- **Mac Mini:** `~/.openclaw/workspace/projects/tools/`

Hardcoding either one breaks the other machine. We need to make ALL paths dynamic.

---

## HOW TO FIND THE PROBLEMS

Run this command to find every hardcoded path in the repo:

```bash
rg '/Users/' --type-not md
```

And for markdown files:
```bash
rg '/Users/' --type md
```

Every match is a potential problem. Fix them using the patterns below.

---

## WHAT TO DO

### Step 1: Pull the latest main branch

```bash
git checkout main
git pull origin main
```

You MUST be on the latest main. PR #3 was closed because it was stale.

### Step 2: Create a new branch

```bash
git checkout -b fix/remove-hardcoded-paths
```

### Step 3: Fix these specific files

Here is every file that has a hardcoded path problem. Fix each one exactly as described.

---

#### File 1: `agent-hub/.env.example`

The three path variables (HUB_SERVER_PATH, MCP_SERVER_PATH, PROJECTS_ROOT) are all hardcoded to laptop paths.

**Fix:** Change them to use `${PROJECTS_ROOT}` references. Make PROJECTS_ROOT a blank value with a comment telling the user to set it for their machine.

---

#### File 2: `agent-hub/scripts/generate_mcp_config.py`

Uses `Path.home() / "projects" / "_tools"` which only works on the laptop.

**Fix:** Read `PROJECTS_ROOT` from environment with a fallback:
```python
import os
PROJECTS_ROOT = Path(os.environ.get("PROJECTS_ROOT", Path.home() / "projects"))
TOOLS_DIR = PROJECTS_ROOT / "_tools"
```
Then replace all `Path.home() / "projects" / "_tools"` with `TOOLS_DIR`.

---

#### File 3: `agent-hub/scripts/review_drafts.py`

Has a comment with a hardcoded path example. The CODE is fine (it just does string replacement). Update the comment to note it works on both machines.

---

#### File 4: `ssh_agent/mcp_config.json`

Has hardcoded absolute paths for the Python command and PYTHONPATH.

**Fix:** Use `uv` as the command with relative args, or use a startup script. Set PYTHONPATH to `.` (relative).

---

#### File 5: `governance/COMPLETION_SUMMARY.md`

Has hardcoded path examples throughout.

**Fix:** Replace all absolute path examples with `$PROJECTS_ROOT/...` placeholders.

---

#### File 6: `agent-hub/Documents/CURSOR_MCP_SETUP.md`

Has a hardcoded path in an example.

**Fix:** Show both machine paths as options: "e.g., `~/projects/_tools` on laptop or `~/.openclaw/workspace/projects/tools` on Mac Mini"

---

#### File 7: `agent-hub/test_failures.txt`

**DELETE THIS FILE.** It's committed test output with hardcoded paths. Test output should never be committed.

```bash
trash agent-hub/test_failures.txt
git add -u agent-hub/test_failures.txt
```

---

### Step 4: Verify no remaining hardcoded paths

```bash
rg '/Users/' --type-not md
```

This should return ZERO matches. If there are hits, fix them using the same pattern (env vars or relative paths).

### Step 5: Test

```bash
cd agent-hub && uv run pytest tests/ -x --timeout=30
```

If tests fail for reasons unrelated to your changes, note it in the PR but don't try to fix unrelated test failures.

### Step 6: Commit and create PR

```bash
git add -A
git commit -m "fix: remove hardcoded paths for cross-machine compatibility

Uses PROJECTS_ROOT env var and relative paths so the repo works on both
laptop and Mac Mini. Deletes committed test output (test_failures.txt)."

git push -u origin fix/remove-hardcoded-paths
```

Then create a PR with title: `fix: remove hardcoded paths for cross-machine compatibility`

Include in the PR body:
- Summary of what was changed
- List of files modified
- Test plan: `rg '/Users/'` returns zero hits in non-doc files

---

## WHAT NOT TO DO

1. **DO NOT** rewrite paths to Mac Mini paths. That was the mistake in PR #3.
2. **DO NOT** change any code logic. Only paths and path-related comments.
3. **DO NOT** fix unrelated bugs you find along the way. Stay on task.
4. **DO NOT** use `rm`. Use `trash`.
5. **DO NOT** commit test output files.
6. **DO NOT** merge the PR yourself. It needs review from the laptop side.

---

## WHY THIS MATTERS

This repo is shared between two machines. Every hardcoded path is a bug that breaks one machine or the other. The pattern is simple: use `$PROJECTS_ROOT` or `os.environ.get("PROJECTS_ROOT")` everywhere, and let each machine set that variable to its own location.

# gen-loop

A bash script that runs an agent (Claude, Codex, or Gemini) inside a repo in a bounded loop, making small, incremental improvements one at a time.

## Usage

```bash
gen-loop <agent> <repo-path> [focus]
```

**Agents:** `claude`, `codex`, `gemini`
*(xAI/Grok is not currently supported — would require adding a `grok` case in the agent switch block.)*

**Examples:**
```bash
gen-loop codex ~/projects/muffinpanrecipes
gen-loop gemini ~/projects/ai-memory "focus on test coverage"
gen-loop claude ~/projects/data-vault-factory "refactor the pipeline module"
```

## What it does

The script builds a prompt that instructs the agent to:

1. Check it's on a feature branch (not main) — creates one if needed
2. Pick ONE concrete improvement: a bug, a TODO, a failing test, a code smell, a missing test, a perf issue, dead code, an inconsistency
3. Fix it COMPLETELY — no half-done work
4. Run tests if they exist
5. Commit with a clear message
6. Pick the NEXT thing and repeat
7. Take small bites — one function, one test, one fix per cycle
8. Stop after **20 commits** or when nothing useful remains

It then launches the specified agent in headless/exec mode and lets it run until the agent stops or the user hits Ctrl+C.

## Error handling

- Missing credentials or env vars → note in `GEN-LOOP-BLOCKERS.md` in the target repo, move on
- Failing tests the agent didn't cause → note in `GEN-LOOP-BLOCKERS.md`, move on
- Same error 3 times → stop that path, note it, move on
- Stuck on everything → write a summary to `GEN-LOOP-BLOCKERS.md` and stop

**`GEN-LOOP-BLOCKERS.md`** is the standard output when things go wrong. If you see that file in a repo, it means gen-loop ran there and hit something it couldn't fix.

## Safety rules

- **Never pushes to remote.** Local commits only.
- **Never works on main.** Always creates or stays on a feature branch.
- Must be on a feature branch before any work begins.

## When to use it

Good for:
- Housekeeping runs on a mature codebase ("clean up TODOs, tighten tests, kill dead code")
- Applying a focus area across many files ("improve error messages everywhere")
- Letting an agent spend an hour iterating on a repo while you're doing something else

Bad for:
- New feature work (the loop philosophy is "small bites," not "build the thing")
- Architecture changes (the script explicitly discourages refactoring 10 files at once)
- Anything where you need a human in the loop between changes

## Editing the script

`gen-loop` lives at `_tools/gen-loop` as a shared bash script. **Do not edit it in place for project-specific modifications.** If you need a variant:

1. Copy `_tools/gen-loop` into your project's `scripts/` directory
2. Rename it if helpful (e.g. `research-loop` for non-code use cases)
3. Edit the copy

This keeps the canonical version stable while allowing forks for specialized workflows.

## Known users

Based on `GEN-LOOP-BLOCKERS.md` files found in the ecosystem:
- `muffinpanrecipes` — ran into missing pytest/hypothesis deps and uv panics in March 2026

Other projects may have run gen-loop without leaving a BLOCKERS file (which only appears when something goes wrong).

## History

Committed once to `_tools/` via `e9d1a6e feat(tools): add new scripts, docs, model-bench, and ssh config`. No in-place edits since. The 140-line script is stable as shipped.

## See also

- `_tools/model-bench/` — benchmark tool, separate concern
- `_tools/route/` — token usage tracking CLI
- `~/projects/auxesis-research-labs/` — uses the same "bounded iteration" philosophy for research sessions, not code

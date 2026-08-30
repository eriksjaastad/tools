# CLAUDE.md - _tools

> Mirror of [`AGENTS.md`](AGENTS.md). Any agent system — Claude, Codex, or otherwise — reads the same rules here. **Change one, mirror it to the other.**
>
> Portfolio-wide rules (Kanban, Git workflow, secrets, `rm`) live in `~/projects/CLAUDE.md` and are deliberately not restated here.

> **You are the floor manager of _tools.** You own this project's Kanban board, write code, create PRs, make cards, and report status when explicitly asked. You can use sub-agents (the Agent tool) to parallelize work like running tests, exploring code, or researching — manage them and keep them on task.

Run `pt info -p _tools` for tech stack, env vars, infrastructure, and project-specific reference data.
Run `pt memory search "_tools"` before starting work for prior decisions and context.

## Session Continuity

If `PROGRESS.md` exists in the project root, read it FIRST before doing anything else. It contains state from your previous session: what was being worked on, decisions made, and next steps.

`PROGRESS.md` is currently **tracked** in this repo, which is a misconfiguration (#6783) — it belongs in `.gitignore`. Until that lands, expect a permanent `M PROGRESS.md` in `git status`. That is the steady state, not a finding. Never commit it, never stage it, never delete it.

## What Is This Directory?

`_tools/` is shared infrastructure used across all projects. Key subdirectories:

| Directory | Purpose |
|-----------|---------|
| `governance/` | Pre-commit hook validators (secrets, paths, api-wrapper enforcement) |
| `route/` | Model routing CLI + `model_registry.json` (pricing source of truth) |
| `hooks/` | Claude Code PreToolUse/PostToolUse hooks |
| `claude-hooks/` | Additional Claude Code hooks (PR enforcement) |
| `model-bench/` | Model benchmarking and comparison |
| `claude-mcp-go/` | MCP hub for agent communication (Go) |
| `ollama-mcp-go/` | MCP server for local Ollama models (Go) |
| `integrity-warden/` | Security and compliance auditing |

## GitHub Identity — Read Before Any `gh` or `git push`

**Identity is per-ROLE, not per-tool.** The 2026-04-24 cutover replaced per-tool identities with three canonical roles. Exactly these exist:

| Identity | Bot login |
|----------|-----------|
| `architect` | `architect-identity[bot]` |
| `manager` | `manager-identity[bot]` |
| `auxesis-coder` | `auxesis-coder[bot]` |

**Codex uses the same identities as every other agent** (Erik's ruling, 2026-08-30). There is no Codex bot and no Gemini bot — no App, no Doppler credentials, nothing to restore.

**`gh-claude.sh` is still present and it is dead.** It execs the `claude` identity, which no longer exists in `IDENTITY_MAP`, so invoking it fails with "Unknown identity". Do not use it. It is worse than merely dead: `~/.claude/hooks/gh-identity-check.py` still lists it in `WRAPPER_PATTERNS` as a sanctioned wrapper, so it looks blessed and then fails. Removing the script and that entry is #6782.

`gh-codex.sh` and `gh-gemini.sh` were removed in #46, together with `gh-agent.sh`'s old silent fallback to the retired `claude` identity. An unresolved identity now fails closed with a readable reason instead of exiting 1 with no output.

Rules:

- **All GitHub write operations go through `gh-agent.sh` / the `gha` wrapper**, never bare `gh`. A PreToolUse hook enforces this.
- **Never set `git config user.name` / `user.email` by hand.** This repo's `.git/config` already resolves to `manager-identity[bot]`. `--auto` picks `manager` inside a project dir and `architect` at `~/projects` root; `auxesis-coder` is never auto-picked.
- **Never let a `gh` call run with an empty `GH_TOKEN`.** An empty value is not treated as "no credentials" — `gh` reads it as unset and falls through to Erik's personal keyring, authenticating as `eriksjaastad` while the git author still says `<something>[bot]`. Any wrapper that builds a token in a subshell must explicitly test it is non-empty before invoking `gh`. Do not rely on `set -e` alone.
- **Token cache:** installation tokens are cached at `~/.cache/gh-agent/<identity>.json` (0600 in a 0700 dir) and reused until 300s before the expiry GitHub reports. Each entry carries a `config` fingerprint of its `IDENTITY_MAP` tuple, so repointing an identity re-mints instead of serving the superseded App's token. A Doppler secret rotated **in place** under an unchanged suffix is **not** caught — after that kind of change, pass `--no-cache` or clear the cache directory. Any corrupt, expired, or drifted entry is treated as a miss, never as a failure.

## Safety Rules

### NEVER Modify
1. **Production data** — any `data/` directories with real user data
2. **API keys** — `.env` files, never log or commit
3. **Git history** — no force pushes, no history rewrites

### Be Careful With
1. **MCP server code** — affects all downstream agents
2. **`gh-agent.sh` / `github-app-token.py`** — bot identity infrastructure, **check with Erik first.** This is the rule that got skipped when four commits landed on `perf/gha-token-cache` with no card on this board.
3. **Governance validators** — false positives block all commits across all projects

### Do Not Touch
`model-bench/` contains `codex` and `gemini` references that are **models under test**, not identities. Identity cleanup means `gh-*.sh` wrappers and `IDENTITY_MAP`, nothing else. Erik's standing instruction (2026-08-06): "do not tear the existing machinery out. The bench code, the schema, and 21 committed `seats.yaml` files stay put." Those `seats.yaml` files live in the portfolio project repos, not here — `_tools` owns the schema that validates them — so searching `model-bench/` for them turns up nothing. That is expected, not evidence the instruction is stale.

## Code Review Standards

Reviews follow the portfolio-wide protocol at `~/projects/project-scaffolding/REVIEWS_AND_GOVERNANCE_PROTOCOL.md` (canonical source — do not fork). Key checks:

| ID | Check |
|----|-------|
| M1 | No hardcoded `/Users/` or `/home/` paths |
| M2 | No silent `except: pass` patterns |
| M3 | No API keys in code |
| H1 | Subprocess uses `check=True` and `timeout` |

M1–M3 are enforced by governance validators in `governance/`. H1 is manual.

## Definition of Done

- [ ] M1–M3 robot checks pass
- [ ] Tests pass for any touched component with a suite (e.g. `pytest integrity-warden/tests/` when editing integrity-warden; Go tests where they exist)
- [ ] No new security vulnerabilities
- [ ] Documentation updated if behavior changed

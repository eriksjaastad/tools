# CLAUDE.md - _tools

> Mirror of [`AGENTS.md`](AGENTS.md). Any agent system — Claude, Codex, or otherwise — reads the same rules here. **Change one, mirror it to the other.**
>
> Portfolio-wide rules (Kanban, Git workflow, secrets, `rm`) live in `~/projects/CLAUDE.md` and are deliberately not restated here.

> **You are the floor manager of _tools.** You own this project's Kanban board, write code, create PRs, make cards, and report status when explicitly asked. You can use sub-agents (the Agent tool) to parallelize work like running tests, exploring code, or researching — manage them and keep them on task.

Run `pt info -p _tools` for tech stack, env vars, infrastructure, and project-specific reference data.
Run `pt memory search "_tools"` before starting work for prior decisions and context.

## Session Continuity

If `PROGRESS.md` exists in the project root, read it FIRST before doing anything else. It contains state from your previous session: what was being worked on, decisions made, and next steps.

`PROGRESS.md` is local session context, ignored and untracked since #6783 (PR #48). Keep it on disk and current. Never commit it, never stage it, never delete it. Verify that it is ignored and absent from tracked files when preparing a PR.

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

**`gh-claude.sh` has been removed**, together with its repository and installed user-hook allowances (#6782, completed after tools PR #53 and user-config PR #61). Use `gha` or `gh-agent.sh` with a canonical role. Installed hook wiring remains machine-local.

`gh-codex.sh` and `gh-gemini.sh` were removed in #46, together with `gh-agent.sh`'s old silent fallback to the retired `claude` identity. An unresolved identity now fails closed with a readable reason instead of exiting 1 with no output.

Rules:

- **All GitHub write operations go through `gh-agent.sh` / the `gha` wrapper**, never bare `gh`. A PreToolUse hook enforces this.
- **Never set `git config user.name` / `user.email` by hand.** This repo's `.git/config` already resolves to `manager-identity[bot]`. `--auto` picks `manager` inside a project dir and `architect` at `~/projects` root; `auxesis-coder` is never auto-picked.
- **`gha` is a shell alias — do not rely on it inside a script file.** It expands to
  `_tools/gh-agent.sh --auto` only in an interactive shell. Inside `bash script.sh` it is
  `command not found`, so every call returns nothing — and a loop that greps that empty
  output reports a clean sweep over zero data instead of failing. This silently produced
  false "no findings" results during the #7085 audit. **In any script, call
  `"$HOME/projects/_tools/gh-agent.sh" --auto` by path.** And check status, not
  emptiness — noting that `$?` after a pipe reports the *last* command, so
  `cmd | head` returns 0 even when `cmd` was not found. Use `set -o pipefail`, or
  test `${PIPESTATUS[0]}`, or capture output before filtering it.
  **A `~/bin/gha` PATH shim added 2026-09-14 makes the bare name resolve in
  non-interactive shells too — but only where that shim exists.** It lives outside
  every repo (`~/bin` is not tracked here or in `claude-user-config`), so it is
  laptop-local and absent on the Mac Mini and in any fresh environment. A script
  that works because of it will fail silently somewhere else. Call by path anyway.
- **To ask which identity you are about to act as, run `gha whoami`** (or
  `gh-agent.sh --auto whoami` in a script). It prints the resolved identity, bot login,
  git author, and the cwd that drove `--auto`. It makes no `gh` API call and never puts
  the token in its output — but it is **not** free: it runs after identity resolution,
  so on a cold token cache it still costs a Doppler read and a live mint, exactly like
  any other invocation. That is deliberate (it doubles as a check that the credential
  chain works), but do not call it in a loop believing it is local. It takes no
  arguments and rejects any it is given. **Do not probe GitHub for this.**
  `gh api user` returns `403 Resource not accessible by integration` because an
  installation token is not a user, and `gh api /app` returns `401` because that route
  wants a signed JWT. Both read like a broken wrapper and neither is.
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
`model-bench/` contains `codex` and `gemini` references that are **models under test**, not identities. Identity cleanup means `gh-*.sh` wrappers and `IDENTITY_MAP`, nothing else. Erik's standing instruction (2026-08-06): "do not tear the existing machinery out. The bench code, the schema, and 21 committed `seats.yaml` files stay put." Neither those `seats.yaml` files nor the schema they answer to live here. The files sit in the portfolio project repos, and the contract belongs to `project-scaffolding` (`scaffold/seats.py`, `templates/seats.schema.v1.md`); `model-bench/model_bench/seats.py` deliberately loads that repo's validator rather than copying schema rules in. So searching `_tools` for either turns up nothing — that is expected, not evidence the instruction is stale. **Changes to the seats contract belong in `project-scaffolding`, not here.**

## Code Review Standards

Reviews follow the portfolio-wide protocol at `~/projects/project-tracker/REVIEWS_AND_GOVERNANCE_PROTOCOL.md` (canonical source — do not fork). Key checks:

| ID | Check |
|----|-------|
| M1 | No hardcoded `/Users/` or `/home/` paths |
| M2 | No silent `except: pass` patterns |
| M3 | No API keys in code |
| H1 | Subprocess uses `check=True` and `timeout` |

**M1 and M3 are automated** by the shared governance checks, alongside API-wrapper enforcement. This repository's CI also runs `governance/silent-failure-gate.py` for M2 patterns SF001–SF003 against all tracked Python files. This bounded scan does not prove complete error handling: **manual M2 review beyond these patterns and H1 review remain required**. The shared pre-commit validator list stays unchanged until other owners resolve their findings; see `governance/SILENT_FAILURE_ROLLOUT.md`.

## Definition of Done

- [ ] Automated M1/M3, API-wrapper and repository silent-failure checks pass; remaining M2/H1 reviewed manually
- [ ] Tests pass for any touched component with a suite (e.g. `pytest integrity-warden/tests/` when editing integrity-warden; Go tests where they exist)
- [ ] No new security vulnerabilities
- [ ] Documentation updated if behavior changed

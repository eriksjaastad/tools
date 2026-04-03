# CLAUDE.md - _tools

> **You are the floor manager of _tools.** You own this project's Kanban board, write code, create PRs, make cards, and report status when explicitly asked. You can use sub-agents (the Agent tool) to parallelize work like running tests, exploring code, or researching — manage them and keep them on task.

Run `pt info -p _tools` for tech stack, env vars, infrastructure, and project-specific reference data.
Run `pt memory search "_tools"` before starting work for prior decisions and context.

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

## Safety Rules

### NEVER Modify
1. **Production data** - Any `data/` directories with real user data
2. **API keys** - `.env` files, never log or commit
3. **Git history** - No force pushes, no history rewrites

### Be Careful With
1. **MCP server code** - Affects all downstream agents
2. **`gh-agent.sh` / `github-app-token.py`** - Bot identity infrastructure, check with Erik first
3. **Governance validators** - False positives block all commits across all projects

## Code Review Standards

Reviews must follow `Documents/REVIEWS_AND_GOVERNANCE_PROTOCOL.md`. Key checks:

| ID | Check |
|----|-------|
| M1 | No hardcoded `/Users/` or `/home/` paths |
| M2 | No silent `except: pass` patterns |
| M3 | No API keys in code |
| H1 | Subprocess uses `check=True` and `timeout` |

Review documents: `CODE_REVIEW_{REVIEWER_NAME}_{VERSION}.md`

## Definition of Done

```markdown
- [ ] M1-M3 robot checks pass
- [ ] Tests pass: `pytest tests/`
- [ ] No new security vulnerabilities
- [ ] Documentation updated if behavior changed
```

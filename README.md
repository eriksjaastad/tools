# Developer Tools (_tools)

Builder utilities and helper scripts for working across all projects.

---

## Code Review

Code review runs **locally**, before push, via the `code-reviewer` Claude
subagent invoked by the `~/.claude/skills/pr/SKILL.md` workflow. The local
PreToolUse hook `pre-pr-review.py` blocks `git push` and `gh/gha pr create`
unless the run prepends `CLAUDE_PR_REVIEW_PASSED=1` (or, with explicit user
confirmation, `CLAUDE_PR_REVIEW_SKIPPED=1`).

The previous GitHub-Actions-based reusable review workflow
(`claude-review-reusable.yml` + per-repo `claude-review.yml` wrappers) was
removed on 2026-04-21. Reasons:
- It duplicated the local review the agent was already running.
- Status check `claude-review` was being required by branch protection on some
  repos but no longer posted by anything, silently blocking merges.
- We never want GitHub-side Claude API spend; review happens on the
  developer's machine.

The only CI workflow we still ship from this repo is the type-label gate
(`.github/workflows/pr-label-check.yml`), which posts the `check-label`
status that branch protection on `main` requires.

Use `governance/sync-gh-workflows.sh` to roll that workflow out across
target repos, delete obsolete
`claude-review.yml` wrappers, and handle the scoped `master` -> `main`
rename for `eriksjaastad/eriksjaastad`. Run with `--dry-run` first.

---

## Repo Settings Standardization (`governance/standardize-gh-repo.sh`)

Enforces canonical GitHub repo settings (auto-delete-on-merge, allowed
merge methods, canonical labels, branch protection requiring `check-label`)
across all `eriksjaastad/*` repos. See the script header for the full
policy. Run with `--dry-run` first; `--apply` when you're sure.

Common rollout commands:

```bash
_tools/governance/sync-gh-workflows.sh --dry-run install-pr-label-check
_tools/governance/sync-gh-workflows.sh --dry-run delete-dead-claude-review
_tools/governance/sync-gh-workflows.sh --dry-run rename-default-branch
```

---

## Local Pre-Commit Hooks (`governance/`)

Runs validators at `git commit` time — secrets, hardcoded paths, naked API calls, agent config sync. Unlike the CI workflow above (which propagates automatically via `@main` ref), these must be installed per repo:

```bash
_tools/governance/install-hooks.sh ~/projects/<project-name>
```

Overwrites existing `.git/hooks/pre-commit` — merge manually if the repo already has one.

---

## Active Tools

- [`governance/`](governance/README.md) - Pre-commit hook validators for secrets, hardcoded paths, API-wrapper enforcement, and agent config sync.
- [`route/`](route/README.md) - Model routing CLI and `model_registry.json` pricing source of truth.
- `hooks/` - Claude Code PreToolUse/PostToolUse hooks.
- `claude-hooks/` - Additional Claude Code hooks for PR enforcement.
- [`model-bench/`](model-bench/README.md) - Model benchmarking and comparison.
- [`claude-mcp-go/`](claude-mcp-go/README.md) - Go MCP hub for agent communication.
- [`ollama-mcp-go/`](ollama-mcp-go/README.md) - Go MCP server for local Ollama models.
- [`integrity-warden/`](integrity-warden/README.md) - Security and compliance auditing.
- [`ssh_agent/`](ssh_agent/README.md) - Automated SSH management and host routing.
- [`pdf-converter/`](pdf-converter/README.md) - PDF to Markdown conversion and cleanup utilities.
- [`claude-cli/`](claude-cli/README.md) - Legacy command-line interface to Claude.

---

## 📋 Planning Templates

Planning templates are no longer maintained in `_tools/`.
- Canonical pipeline: [Project-workflow.md](../Project-workflow.md)
- PRD/spec workflow: `/write-prd`, `/strategy`, and `/spec` skills.

---

## Setup

### Tool Usage

Most tools are script or CLI based. Start with the tool-specific README links
above where they exist; tools without a README are hook directories managed by
their installed entry points.

---

## Creating New Tools

When adding a new tool:

1. Create directory: `_tools/your_tool/`
2. Add `README.md` with usage instructions
3. Add `requirements.txt` or venv if needed
4. Update this README with a section

**Tools should be:**
- ✅ Reusable across projects
- ✅ Well-documented with examples
- ✅ Self-contained (own dependencies)
- ✅ Builder utilities, not project code

---

## Directory Structure

```
_tools/
├── governance/             # Repo governance scripts and hook installers
├── route/                  # Model routing CLI and registry
├── hooks/                  # Claude Code PreToolUse/PostToolUse hooks
├── claude-hooks/           # Additional Claude Code hooks
├── model-bench/            # Model benchmarking
├── claude-mcp-go/          # Go MCP hub for agent communication
├── ollama-mcp-go/          # Go MCP server for local Ollama models
├── integrity-warden/       # Security and compliance auditing
├── ssh_agent/              # SSH management and host routing
├── pdf-converter/          # PDF conversion utilities
└── claude-cli/             # Legacy Claude CLI
```

---

## Philosophy

`_tools/` contains **builder utilities** - scripts and libraries you use **while building projects**, not the projects themselves.

**Examples:**
- ✅ Model routing CLI (used by multiple projects)
- ✅ PDF converter (preprocessing documents)
- ✅ Governance hooks (repo safety checks)
- ❌ Cortana (that's a project, not a tool)
- ❌ actionable-ai-intel (that's a project)

**Rule of thumb:** If it's used **BY** your projects, it's a tool. If it's used **BY** end-users, it's a project.

---

Part of the `..` workspace.

## Related Documentation

- [Project-workflow.md](../Project-workflow.md) - canonical project planning pipeline
- [local-model-learnings.md](local-model-learnings.md) - local model notes

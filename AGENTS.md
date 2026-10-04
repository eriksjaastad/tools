<!-- GENERATED FROM: CLAUDE.md -->
<!-- DO NOT EDIT DIRECTLY. Edit CLAUDE.md and run instruction-writer . --changed claude --write from the project directory -->

# _tools repository instructions

> Project-specific instructions are authored here. Regenerate `AGENTS.md` with `instruction-writer . --changed claude --write` after an edit. The generated `runtime-doctor:shared:code-review-rules` block is present only in `AGENTS.md`: Claude inherits the portfolio rules from its parent instructions, while GitHub Codex needs them inside this repository.
>
> Portfolio-wide rules (Kanban, Git workflow, secrets, `rm`) live in the provider's parent instruction file and are deliberately not restated here.

> **You are the floor manager of _tools.** You own this project's Kanban board, write code, create PRs, make cards, and report status when explicitly asked. You can use sub-agents to parallelize work like running tests, exploring code, or researching — manage them and keep them on task.

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
| `claude-mcp-go/` | MCP hub for agent communication (Go) |
| `ollama-mcp-go/` | MCP server for local Ollama models (Go) |
| `integrity-warden/` | Security and compliance auditing |

## GitHub Identity — Read Before Any `gh` or `git push`

**Erik's personal GitHub account is the writer identity** as of 2026-09-23.
All agents use the same `eriksjaastad` account for new GitHub commits, PRs,
issues and reviews. The repo-local and global Git author is `eriksjaastad`
with the GitHub-linked ID-based `noreply` address. The installed `gha` shim on
the MacBook and Mac Mini clears inherited `GH_TOKEN`/`GITHUB_TOKEN` and uses
the personal `gh` login. Keep the agent's role in task/PR metadata, since the
GitHub actor alone no longer distinguishes a floor manager from a worker.

- Use `gha` for attributed GitHub operations. In non-interactive scripts,
  resolve `command -v gha` and fail if it is absent; do not silently fall back
  to an App token or another account. `gha api user --jq .login` should return
  `eriksjaastad` when diagnosing identity.
- Use plain `git` for commits and pushes. Do not override repo-local author or
  credential settings ad hoc. `github-identity-cutover.py` audits/applies the
  supported host setup and saves a private rollback snapshot first.
- The three historical custom Apps (`architect`, `manager`, `auxesis-coder`)
  remain installed only while the one-year GitHub archive is validated.
  `gh-agent.sh` and `github-app-token.py` are legacy archive tools, not writer
  paths. Never use an explicit App role for new PRs, reviews, comments or
  pushes. The old bot-identity installer is disabled.
- Preserve the independent Codex GitHub review connector and Discord agent
  identities. The existing exact-head review/CI merge gates still apply.

## Safety Rules

### NEVER Modify
1. **Production data** — any `data/` directories with real user data
2. **API keys** — `.env` files, never log or commit
3. **Git history** — no force pushes, no history rewrites

### Be Careful With
1. **MCP server code** — affects all downstream agents
2. **`gh-agent.sh` / `github-app-token.py`** — historical App credentials remain only for archive recovery; do not reintroduce them into a writer path.
3. **Governance validators** — false positives block all commits across all projects

### Do Not Touch
`model-bench` was retired on 2026-09-25 (#6453): the package, runners, CLI,
tests, dependencies, and CI references are removed, and the sealed pilot
results are preserved under `_archive/model-bench-results/` as historical
evidence. The project-owned `seats.yaml` files and their schema never lived in
`_tools`; they sit in the portfolio project repos, and the contract belongs to
`project-scaffolding` (`scaffold/seats.py`, `templates/seats.schema.v1.md`),
which is now archived. Nothing in `_tools` owns or changes the seats contract.

## Code Review Standards

Reviews follow the portfolio-wide protocol at `~/projects/project-tracker/REVIEWS_AND_GOVERNANCE_PROTOCOL.md` (canonical source — do not fork). Key checks:

| ID | Check |
|----|-------|
| M1 | No hardcoded `/Users/` or `/home/` paths |
| M2 | No silent `except: pass` patterns |
| M3 | No API keys in code |
| H1 | Subprocess has a timeout and handles failure with `check=True` or explicit validation of expected return codes |

**M1 and M3 are automated** by the shared governance checks, alongside API-wrapper enforcement. This repository's CI also runs `governance/silent-failure-gate.py` for M2 patterns SF001–SF003 against all tracked Python files. This bounded scan does not prove complete error handling: **manual M2 review beyond these patterns and H1 review remain required**. The shared pre-commit validator list stays unchanged until other owners resolve their findings; see `governance/SILENT_FAILURE_ROLLOUT.md`.

## Definition of Done

- [ ] Automated M1/M3, API-wrapper and repository silent-failure checks pass; remaining M2/H1 reviewed manually
- [ ] Tests pass for any touched component with a suite (e.g. `pytest integrity-warden/tests/` when editing integrity-warden; Go tests where they exist)
- [ ] No new security vulnerabilities
- [ ] Documentation updated if behavior changed

<!-- BEGIN runtime-doctor:shared:code-review-rules -->
## Code Review Rules

> Shared source: `agent-runtime-config/shared_blocks/code-review-rules.md`, kept
> in sync with its registry-declared authoring surface. Refresh through the
> shared-rule rollout; do not hand-copy rules into individual projects.

These rules apply to an independent local Codex review process.
Claude implements authorized coding cards; Codex reviews the exact committed
HEAD. This block contains the essential
checks for in-repository review without requiring workstation files. Additional
local detail: [full protocol](https://github.com/eriksjaastad/agent-runtime-config/blob/main/docs/code-review-protocol.md).

### Mechanical checks

A failure prevents PASS, but finish independent checks and report findings
together. Name any check that could not run.

| ID | Check |
|----|-------|
| M1 | Flag machine-specific paths in executable code/config or prescribed setup commands. Illustrative examples and committed evidence are not runtime dependencies. |
| M2 | Flag swallowed unexpected failures. Documented best-effort and expected-absence handling are valid when the contract is preserved. |
| M3 | No real credentials in files. Secrets come from Doppler. Synthetic fixtures and documented placeholders are permitted. |
| M4 | No unresolved placeholders in rendered deliverables or runtime config. Source templates and literal fixtures may contain them. |
| M5 | Changed `.js` files beneath any `static` directory must have no redeclarations. The manager's review launcher checks them on the exact HEAD and supplies the result to the independent reviewer. A missing or failed check prevents PASS; no matching files skips M5. The check's command and evidence format are owned by the review launcher and full protocol, not by this portable rule. |

### Judgment and scope

| ID | Check |
|----|-------|
| T1 | Identify the relevant behavior passing tests never exercise. |
| T2 | Assertions such as non-null/type checks alone are insufficient for behavioral claims. |
| E1 | Status contracts must be truthful. JSON deny with exit0 is valid if the caller consumes that protocol. |
| E2 | An operation failure must not silently become a successful empty result. |
| H1 | Subprocesses need timeouts and return-code handling; expected nonzero outcomes must remain usable. |
| H5 | Document foreign-key relationships before a DELETE, including cascade effects. |
| H7 | No unrequested destructive cleanup. |

Trace changed behavior to an authorized requirement. State the scope and check
claimed workflows; a written exclusion does not excuse a defect in behavior the
change promises. Separate unrelated pre-existing concerns from this PR's fixes.
Read propagation sources first, execution-critical code next, then reference docs.

### Evidence and convergence

- Review the whole diff and affected callers. Gather the complete supported
  finding set in one report; group related cases by root cause, most severe first.
- Check both failures and legitimate uses. Use focused synthetic probes where
  they materially validate a claim; do not turn review into an exhaustive audit.
- Separate evidence, inference and unchecked coverage. No supported findings is
  a valid result. Give each finding a concrete failure scenario and file/line.
- Compare base, previous reviewed revision and current head. Distinguish inherited
  misses from fix-induced regressions and verify prior fixes' adjacent effects.
- Test neighbouring legitimate behavior before requesting review. Batch corrections;
  a repeated regression family requires reassessing the approach, not another
  isolated patch. Local preflight also consumes resources and must stay bounded.

### Independent local review

Run a separate local Codex reviewer process on the exact committed HEAD.
The reviewer must not be the implementing agent or process.
Record the reviewed SHA, verdict and findings in the PR or task notes. Address
findings, test the affected behavior and request a fresh review for each new
commit. Repeated findings call for reassessing the approach and tests.

### Verdict and publication

Independent review verdicts end PASS or FAIL with the exact reviewed commit SHA;
a new commit requires fresh review. Review itself needs no workstation-tool access.

Publishing/merging agents follow the complete [PR review and merge policy](https://github.com/eriksjaastad/agent-runtime-config/blob/main/docs/pr-review-policy.md),
also mirrored in `pt info get pr_merge_policy` and `~/projects/Project-workflow.md`.
Independent local code-reviewer clearance must identify the current head and
clear findings; pending, stale, missing or ambiguous evidence is insufficient.
If that policy is unavailable, stop publication/merging, not review. An authorized
exception is recorded as an exception, never as PASS.
<!-- END runtime-doctor:shared:code-review-rules -->

<!-- BEGIN runtime-doctor:shared:model-seats -->
## Model seats (Manager / Worker / Judge)

Concrete bindings live in **`~/projects/MODEL_SEATS.md`** (update when vendors bounce). Full policy: **`~/projects/ORCHESTRATOR_CHEAP_CODER_RULES.md`**.

- **Manager** (Codex / Claude / Grok Bot): plan, brief, verify, review, and handle PRs.
- **Worker** (Claude Code): implement authorized code in an isolated task branch or worktree and run focused tests.
- **Judge** (separate local Codex CLI process): review the exact committed HEAD under the ChatGPT login.

### Floor-manager default on the MacBook

For an authorized coding card, brief Claude Code with the card ID, acceptance criteria, working directory, owned files, focused tests, a finite timeout when delegated, and action limits. Keep implementation in an isolated task branch or worktree. A Claude manager may implement directly. When Erik directs Codex manager implementation, or Claude is unavailable or unsuitable, record the reason on the card.

Inspect the coder's diff, tests, and handoff before accepting its work. Invoke a separate local Codex reviewer process on the exact committed HEAD and record its full-SHA PASS or FAIL verdict. The implementing process cannot review its own work. A missing, stale, timed-out, or inconclusive review blocks publication; repeat review after a new commit. The floor manager owns integration, the PR, CI, and merge. The coder's response alone does not complete a card.

Do not use DeepSeek as the coding Worker on the MacBook or Mini. The linked cutover cards own launcher and credential retirement; preserve their dependency gates. Current binding and rollback: `~/projects/MODEL_SEATS.md`.
<!-- END runtime-doctor:shared:model-seats -->

---
tags:
  - map/project
  - p/tools
  - type/index
  - tech/documentation
  - domain/infrastructure
  - status/active
created: 2026-01-24
---
# _tools

Builder utilities and shared infrastructure tools that power the AI-assisted development ecosystem. These are tools used across multiple projects - MCP servers, CLI utilities, governance hooks, and agent orchestration systems.

## Directory Rules

- **All subdirectories MUST have README.md files** - Each tool should be self-documenting
- **Tools should include usage examples** - Show how to run/invoke the tool
- **Dependencies should be declared** - requirements.txt, go.mod, or package.json as appropriate

<!-- LIBRARIAN-INDEX-START -->

### Subdirectories

| Directory | Files | Description |
| :--- | :---: | :--- |
| [agent-hub/](agent-hub/00_Index_agent-hub.md) | 12 | Autonomous Floor Manager for multi-agent task pipelines |
| [agent-news/](agent-news/) | 1 | No description available. |
| [agent-skills-library/](agent-skills-library/) | 0 | No description available. |
| [claude-cli/](claude-cli/README.md) | 3 | Command-line interface for Claude API |
| [claude-mcp-go/](claude-mcp-go/README.md) | 4 | Go MCP server for Claude integration |
| [governance/](governance/README.md) | 5 | Pre-commit hook system for code quality |
| [integrity-warden/](integrity-warden/README.md) | 6 | Security and compliance auditing tools |
| [model-bench/](model-bench/README.md) | 3 | Benchmark cheap/free models against worker tasks. Scores with Opus judge. |
| [multi-layer-delegation/](multi-layer-delegation/) | 1 | No description available. |
| [ollama-mcp-go/](ollama-mcp-go/README.md) | 4 | Go MCP server for local Ollama models |
| [pdf-converter/](pdf-converter/README.md) | 3 | PDF processing utilities |
| [route/](route/README.md) | 6 | A shared tool that reads session data from Claude Code, Codex CLI, and Gemini CLI, applies shadow pr... |
| [ssh_agent/](ssh_agent/README.md) | 7 | SSH key management for AI agents |

### Files

| File | Description |
| :--- | :--- |
| [CLAUDE.md](CLAUDE.md) | > **Purpose:** Instructions for AI reviewers working with Erik's tools ecosystem |
| [LICENSE](LICENSE) | No description available. |
| [PRD_UNIFIED_AGENT_SYSTEM.md](PRD_UNIFIED_AGENT_SYSTEM.md) | > **Document Type:** Product Requirements Document |
| [README.md](README.md) | Builder utilities and helper scripts for working across all projects. |
| [UAS_BUILD_LOG.md](UAS_BUILD_LOG.md) | **Role:** Gemini 3 Flash Floor Manager |
| [agent-hub/00_Index_agent-hub.md](agent-hub/00_Index_agent-hub.md) | > **Type:** Tool / Infrastructure |
| [agent-hub/AGENTS.md](agent-hub/AGENTS.md) | > **Read the ecosystem constitution first:** `project-scaffolding/AGENTS.md` |
| [agent-hub/BENCHMARK_RESULTS_2026-01-19.md](agent-hub/BENCHMARK_RESULTS_2026-01-19.md) | Benchmark |
| [agent-hub/CODE_REVIEW_FIXES_SUMMARY.md](agent-hub/CODE_REVIEW_FIXES_SUMMARY.md) | All 11 findings from `CODE_REVIEW_CLAUDE_v2.md` have been successfully addressed and committed to th... |
| [agent-hub/Documents/API.md](agent-hub/Documents/API.md) | > Quick reference for key classes and functions. For architecture details, see `AGENTS.md`. |
| [agent-hub/Documents/CURSOR_MCP_SETUP.md](agent-hub/Documents/CURSOR_MCP_SETUP.md) | This guide explains how to configure Cursor to communicate with the Agent Hub ecosystem using the Mo... |
| [agent-hub/Documents/FEATURE_FLAG_POLICY.md](agent-hub/Documents/FEATURE_FLAG_POLICY.md) | Feature flags are the primary mechanism for the safe, incremental rollout of new architectural compo... |
| [agent-hub/Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md](agent-hub/Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md) | > **Purpose:** Pre-flight checklist and context loading for Floor Manager before task execution |
| [agent-hub/Documents/MAD_FRAMEWORK.md](agent-hub/Documents/MAD_FRAMEWORK.md) | Here is the updated **Multi-Agent Debate (MAD)** framework, now enhanced with the **Project Brain La... |
| [agent-hub/Documents/README.md](agent-hub/Documents/README.md) | *Auto-generated index. Last updated: 2026-01-24* |
| [agent-hub/Documents/collaboration/AI_COLLABORATION_PATTERNS.md](agent-hub/Documents/collaboration/AI_COLLABORATION_PATTERNS.md) | This folder enables collaboration between different AI assistants (Claude, GPT4All, etc.) through fi... |
| [agent-hub/Documents/collaboration/handoff-spec.md](agent-hub/Documents/collaboration/handoff-spec.md) | **From:** [AI Name - GPT4All/Claude] |
| [agent-hub/Documents/collaboration/implementation-report.md](agent-hub/Documents/collaboration/implementation-report.md) | **From:** [AI Name - GPT4All/Claude] |
| [agent-hub/Documents/litellm/COOLDOWN_PATTERNS.md](agent-hub/Documents/litellm/COOLDOWN_PATTERNS.md) | Cooldowns act as circuit breakers, preventing the router from repeatedly hitting a known-failing or ... |
| [agent-hub/Documents/litellm/FALLBACK_PATTERNS.md](agent-hub/Documents/litellm/FALLBACK_PATTERNS.md) | Fallbacks ensure that our agents remain operational even when a specific provider is down, rate-limi... |
| [agent-hub/Documents/litellm/README.md](agent-hub/Documents/litellm/README.md) | This directory contains foundational documentation and code patterns for the **Unified Agent System*... |
| [agent-hub/Documents/litellm/ROUTING_PATTERNS.md](agent-hub/Documents/litellm/ROUTING_PATTERNS.md) | The `litellm.Router` is the heart of our provider abstraction. It allows us to group models by perfo... |
| [agent-hub/Documents/subagent/EXAMPLE_FLOW.md](agent-hub/Documents/subagent/EXAMPLE_FLOW.md) | This walkthrough demonstrates a worker encountering a logic blocker and resolving it via the parent. |
| [agent-hub/Documents/subagent/INTEGRATION_NOTES.md](agent-hub/Documents/subagent/INTEGRATION_NOTES.md) | These notes outline how the bi-directional protocol integrates with the Unified Agent System archite... |
| [agent-hub/Documents/subagent/PROTOCOL.md](agent-hub/Documents/subagent/PROTOCOL.md) | This document defines the tool schemas and state transitions for the subagent bi-directional communi... |
| [agent-hub/Documents/subagent/README.md](agent-hub/Documents/subagent/README.md) | This reference documents the bi-directional messaging protocol adopted from the **mcp-server-subagen... |
| [agent-hub/HALT.md](agent-hub/HALT.md) | **Time:** 2026-02-15T19:06:52.606740+00:00 |
| [agent-hub/README.md](agent-hub/README.md) | Autonomous Floor Manager for multi-agent task pipelines. Orchestrates task execution between Impleme... |
| [agent-hub/agent_hooks.json](agent-hub/agent_hooks.json) | No description available. |
| [agent-hub/docs/API_REFERENCE.md](agent-hub/docs/API_REFERENCE.md) | > Unified Agent System - Complete API Documentation |
| [agent-hub/docs/CONFIGURATION.md](agent-hub/docs/CONFIGURATION.md) | All feature flags follow the pattern `UAS_*` and can be set to `1` (enabled) or `0` (disabled). |
| [agent-hub/pyproject.toml](agent-hub/pyproject.toml) | No description available. |
| [agent-hub/registry-entry.json](agent-hub/registry-entry.json) | No description available. |
| [agent-hub/requirements.txt](agent-hub/requirements.txt) | No description available. |
| [agent-hub/skill.json](agent-hub/skill.json) | No description available. |
| [agent-hub/uv.lock](agent-hub/uv.lock) | No description available. |
| [agent-news/agent_news.py](agent-news/agent_news.py) | No description available. |
| [agent-skills-library/references/building-skills-for-claude.md](agent-skills-library/references/building-skills-for-claude.md) | **Source:** `The-Complete-Guide-to-Building-Skill-for-Claude.pdf` |
| [claude-cli/README.md](claude-cli/README.md) | Simple command-line interface for chatting with Claude via the Anthropic API. |
| [claude-cli/claude-cli.py](claude-cli/claude-cli.py) | No description available. |
| [claude-cli/requirements.txt](claude-cli/requirements.txt) | No description available. |
| [claude-mcp-go/Makefile](claude-mcp-go/Makefile) | No description available. |
| [claude-mcp-go/README.md](claude-mcp-go/README.md) | This directory contains Go source code for a tool that interacts with Claude's Managed Cloud Platfor... |
| [claude-mcp-go/bin/claude-mcp-go](claude-mcp-go/bin/claude-mcp-go) | No description available. |
| [claude-mcp-go/go.mod](claude-mcp-go/go.mod) | No description available. |
| [claude-mcp-go/go.sum](claude-mcp-go/go.sum) | No description available. |
| [ensure_grepai.py](ensure_grepai.py) | No description available. |
| [gen-loop](gen-loop) | No description available. |
| [github-app-token.py](github-app-token.py) | No description available. |
| [governance/COMPLETION_SUMMARY.md](governance/COMPLETION_SUMMARY.md) | _tools/governance/ |
| [governance/README.md](governance/README.md) | A standalone, portable pre-commit hook system for enforcing code quality and security across project... |
| [governance/governance-check.sh](governance/governance-check.sh) | governance-check.sh |
| [governance/install-hooks.sh](governance/install-hooks.sh) | install-hooks.sh |
| [governance/uninstall-hooks.sh](governance/uninstall-hooks.sh) | uninstall-hooks.sh |
| [governance/validators/absolute-path-check.py](governance/validators/absolute-path-check.py) | No description available. |
| [governance/validators/secrets-scanner.py](governance/validators/secrets-scanner.py) | No description available. |
| [grepai-wrapper.sh](grepai-wrapper.sh) | GrepAI search logging wrapper |
| [integrity-warden/README.md](integrity-warden/README.md) | A suite of tools for maintaining ecosystem integrity, performing deep cleanups, and managing documen... |
| [integrity-warden/TEST_SUITE.md](integrity-warden/TEST_SUITE.md) | Comprehensive pytest test suite for `integrity_warden.py` with full coverage of core components. |
| [integrity-warden/fix-prompt-dependencies.md](integrity-warden/fix-prompt-dependencies.md) | **Goal:** Fix 8 issues found during test validation (6 deps + 2 env hygiene). |
| [integrity-warden/integrity_warden.py](integrity-warden/integrity_warden.py) | No description available. |
| [integrity-warden/remediate_renames.py](integrity-warden/remediate_renames.py) | No description available. |
| [integrity-warden/rename_indices.py](integrity-warden/rename_indices.py) | No description available. |
| [local-model-learnings.md](local-model-learnings.md) | purpose: Operational knowledge for local Ollama models on Mac Mini |
| [model-bench/README.md](model-bench/README.md) | Benchmark cheap/free models against worker tasks. Scores with Opus judge. |
| [model-bench/model_bench/__init__.py](model-bench/model_bench/__init__.py) | model-bench: Worker model benchmarking tool. |
| [model-bench/model_bench/caller.py](model-bench/model_bench/caller.py) | Calls one model with one prompt. LiteLLM for cloud, httpx for Ollama. |
| [model-bench/model_bench/cli.py](model-bench/model_bench/cli.py) | Typer CLI: run, results, models, estimate. |
| [model-bench/model_bench/judge.py](model-bench/model_bench/judge.py) | Sends model responses to Opus for rubric-based 1-5 scoring. |
| [model-bench/model_bench/registry.py](model-bench/model_bench/registry.py) | Model registry — which models to benchmark, pricing, and judge config. |
| [model-bench/model_bench/reporter.py](model-bench/model_bench/reporter.py) | Renders matrix as terminal table (rich) or markdown. |
| [model-bench/model_bench/runner.py](model-bench/model_bench/runner.py) | Orchestrates: load tasks → call models → judge → score → save. |
| [model-bench/model_bench/scorer.py](model-bench/model_bench/scorer.py) | Aggregates scores into comparison matrix. Pure math, no I/O. |
| [model-bench/pyproject.toml](model-bench/pyproject.toml) | No description available. |
| [model-bench/results/run_2026-02-26_19-59-40.json](model-bench/results/run_2026-02-26_19-59-40.json) | No description available. |
| [model-bench/results/run_2026-02-26_19-59-40.md](model-bench/results/run_2026-02-26_19-59-40.md) | *Generated 2026-02-27 00:59 UTC* |
| [model-bench/results/run_2026-02-26_20-02-37.json](model-bench/results/run_2026-02-26_20-02-37.json) | No description available. |
| [model-bench/results/run_2026-02-26_20-02-37.md](model-bench/results/run_2026-02-26_20-02-37.md) | *Generated 2026-02-27 01:02 UTC* |
| [model-bench/results/run_2026-02-26_21-13-33.json](model-bench/results/run_2026-02-26_21-13-33.json) | No description available. |
| [model-bench/results/run_2026-02-26_21-13-33.md](model-bench/results/run_2026-02-26_21-13-33.md) | *Generated 2026-02-27 02:13 UTC* |
| [model-bench/results/run_2026-02-26_21-46-19.json](model-bench/results/run_2026-02-26_21-46-19.json) | No description available. |
| [model-bench/results/run_2026-02-26_21-46-19.md](model-bench/results/run_2026-02-26_21-46-19.md) | *Generated 2026-02-27 02:46 UTC* |
| [model-bench/tasks/code_generation.yaml](model-bench/tasks/code_generation.yaml) | No description available. |
| [model-bench/tasks/diagnosis_debugging.yaml](model-bench/tasks/diagnosis_debugging.yaml) | No description available. |
| [model-bench/tasks/dialogue_creative.yaml](model-bench/tasks/dialogue_creative.yaml) | No description available. |
| [model-bench/tasks/review_judgment.yaml](model-bench/tasks/review_judgment.yaml) | No description available. |
| [model-bench/tasks/summarization.yaml](model-bench/tasks/summarization.yaml) | No description available. |
| [model-bench/uv.lock](model-bench/uv.lock) | No description available. |
| [morning-briefing.sh](morning-briefing.sh) | morning-briefing.sh — Quick status of all projects across both machines |
| [multi-layer-agent-delegation-architecture.md](multi-layer-agent-delegation-architecture.md) | Multi-Layer Agent Delegation |
| [multi-layer-delegation/adapters/__init__.py](multi-layer-delegation/adapters/__init__.py) | Empty file. |
| [multi-layer-delegation/adapters/claude_code.py](multi-layer-delegation/adapters/claude_code.py) | No description available. |
| [multi-layer-delegation/adapters/floor_manager.py](multi-layer-delegation/adapters/floor_manager.py) | No description available. |
| [multi-layer-delegation/adapters/ssh_transport.py](multi-layer-delegation/adapters/ssh_transport.py) | No description available. |
| [multi-layer-delegation/orchestrate.py](multi-layer-delegation/orchestrate.py) | No description available. |
| [multi-layer-delegation/prompts/floor_manager.md](multi-layer-delegation/prompts/floor_manager.md) | You are a Floor Manager in a multi-layer agent delegation tree. You receive a Task Envelope from the... |
| [multi-layer-delegation/prompts/worker.md](multi-layer-delegation/prompts/worker.md) | You are a Worker in a multi-layer agent delegation tree. You receive a single, well-scoped task and ... |
| [multi-layer-delegation/schemas/result_envelope.schema.json](multi-layer-delegation/schemas/result_envelope.schema.json) | No description available. |
| [multi-layer-delegation/schemas/task_envelope.schema.json](multi-layer-delegation/schemas/task_envelope.schema.json) | No description available. |
| [oc-auth-watchdog.sh](oc-auth-watchdog.sh) | oc-auth-watchdog.sh - OpenClaw Auth Watchdog |
| [oc-monitor.sh](oc-monitor.sh) | oc-monitor.sh - Comprehensive OpenClaw Status Monitor |
| [ollama-mcp-go/README.md](ollama-mcp-go/README.md) | `ollama-mcp-go` is a Go library that provides tools for interacting with MCP (Model Configuration Pr... |
| [ollama-mcp-go/bin/server](ollama-mcp-go/bin/server) | No description available. |
| [ollama-mcp-go/go.mod](ollama-mcp-go/go.mod) | No description available. |
| [ollama-mcp-go/go.sum](ollama-mcp-go/go.sum) | No description available. |
| [ollama-mcp-go/test_regex.go](ollama-mcp-go/test_regex.go) | No description available. |
| [pdf-converter/README.md](pdf-converter/README.md) | This directory contains two Python scripts designed to automate PDF processing. The `cleanup_convert... |
| [pdf-converter/cleanup_converted_pdfs.py](pdf-converter/cleanup_converted_pdfs.py) | No description available. |
| [pdf-converter/pdf_to_markdown_converter.py](pdf-converter/pdf_to_markdown_converter.py) | No description available. |
| [pr-monitor.sh](pr-monitor.sh) | pr-monitor.sh — check all open PRs for failed reviews, alert on Slack if found |
| [route/README.md](route/README.md) | A shared tool that reads session data from Claude Code, Codex CLI, and Gemini CLI, applies shadow pr... |
| [route/claude_reader.py](route/claude_reader.py) | No description available. |
| [route/codex_reader.py](route/codex_reader.py) | No description available. |
| [route/model_registry.json](route/model_registry.json) | No description available. |
| [route/pricing.py](route/pricing.py) | No description available. |
| [route/route](route/route) | No description available. |
| [ssh_agent/README.md](ssh_agent/README.md) | Central SSH tool located in `_tools/ssh_agent`. It allows AI agents to run commands on remote hosts ... |
| [ssh_agent/agent.py](ssh_agent/agent.py) | No description available. |
| [ssh_agent/agent_log.txt](ssh_agent/agent_log.txt) | No description available. |
| [ssh_agent/mcp_config.json](ssh_agent/mcp_config.json) | No description available. |
| [ssh_agent/queue/requests.jsonl](ssh_agent/queue/requests.jsonl) | No description available. |
| [ssh_agent/queue/results.jsonl](ssh_agent/queue/results.jsonl) | Empty file. |
| [ssh_agent/requirements.txt](ssh_agent/requirements.txt) | No description available. |
| [ssh_agent/ssh_hosts.yaml](ssh_agent/ssh_hosts.yaml) | No description available. |
| [ssh_agent/start_agent.sh](ssh_agent/start_agent.sh) | Start SSH Agent |

<!-- LIBRARIAN-INDEX-END -->

## Recent Activity

- 2026-03-19: feat: Add GitHub App token generator for agent identities
- 2026-03-07: feat: add agent-news prototype for auditing tool updates
- 2026-02-26: chore: Remove librarian-mcp (previously trashed)
- 2026-02-26: docs: Update tools index
- 2026-02-26: docs: Add building skills for Claude reference doc
- 2026-02-26: feat: Add route CLI tool for AI usage data and shadow pricing
- 2026-02-26: feat: Add grepai shell wrapper for semantic search aliasing
- 2026-02-26: chore: Update agent-hub runtime data files
- 2026-02-26: feat: Agent Hub listener, watchdog updates, and new contract tests
- 2026-02-26: fix: Add system prompt, native tool defs, and retry nudge to worker dispatch

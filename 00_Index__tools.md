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
| [agent-hub/](agent-hub/00_Index_agent-hub.md) | 13 | Autonomous Floor Manager for multi-agent task pipelines |
| [agent-skills-library/](agent-skills-library/) | 0 | No description available. |
| [claude-cli/](claude-cli/README.md) | 3 | Command-line interface for Claude API |
| [claude-mcp-go/](claude-mcp-go/README.md) | 4 | Go MCP server for Claude integration |
| [governance/](governance/README.md) | 5 | Pre-commit hook system for code quality |
| [integrity-warden/](integrity-warden/README.md) | 6 | Security and compliance auditing tools |
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
| [agent-hub/test_failures.txt](agent-hub/test_failures.txt) | No description available. |
| [agent-hub/uv.lock](agent-hub/uv.lock) | No description available. |
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
| [ollama-mcp-go/README.md](ollama-mcp-go/README.md) | `ollama-mcp-go` is a Go library that provides tools for interacting with MCP (Model Configuration Pr... |
| [ollama-mcp-go/bin/server](ollama-mcp-go/bin/server) | No description available. |
| [ollama-mcp-go/go.mod](ollama-mcp-go/go.mod) | No description available. |
| [ollama-mcp-go/go.sum](ollama-mcp-go/go.sum) | No description available. |
| [ollama-mcp-go/test_regex.go](ollama-mcp-go/test_regex.go) | No description available. |
| [pdf-converter/README.md](pdf-converter/README.md) | This directory contains two Python scripts designed to automate PDF processing. The `cleanup_convert... |
| [pdf-converter/cleanup_converted_pdfs.py](pdf-converter/cleanup_converted_pdfs.py) | No description available. |
| [pdf-converter/pdf_to_markdown_converter.py](pdf-converter/pdf_to_markdown_converter.py) | No description available. |
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
| [ssh_agent/queue/results.jsonl](ssh_agent/queue/results.jsonl) | No description available. |
| [ssh_agent/requirements.txt](ssh_agent/requirements.txt) | No description available. |
| [ssh_agent/ssh_hosts.yaml](ssh_agent/ssh_hosts.yaml) | No description available. |
| [ssh_agent/start_agent.sh](ssh_agent/start_agent.sh) | Start SSH Agent |

<!-- LIBRARIAN-INDEX-END -->

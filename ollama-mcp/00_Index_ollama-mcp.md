---
tags:
  - map/project
  - p/ollama-mcp
  - type/ai-agent/tool
  - domain/local-ai
  - status/complete
  - tech/typescript
created: 2026-01-01
---

# ollama-mcp

Bridge between the Model Context Protocol (MCP) and local Ollama models. Enables AI assistants (like Cursor and Claude) to list and run local models with built-in telemetry, safety checks, and concurrency control. Currently in active development with core telemetry features complete.

## Key Components

### Core Server
- `src/server.ts` - MCP protocol implementation and tool registration
- `src/logger.ts` - Telemetry logging system (JSON Lines)
- `dist/server.js` - Compiled execution entry point

### Tooling & Analytics
- `scripts/analyze-runs.js` - Performance analysis of model runs
- `scripts/smoke_test.js` - Server validation script

### Documentation
- `PITCH.md` - Strategic value and high-level project summary
- `Documents/` - Centralized documentation (Standard pattern)
  - `core/ARCHITECTURE_OVERVIEW.md` - System design
  - `core/OPERATIONS_GUIDE.md` - Setup and deployment

## Status

**Tags:** #map/project #p/ollama-mcp
**Status:** #status/complete
**Last Major Update:** 2026-01-01 (Standardization and Telemetry Complete)

<!-- LIBRARIAN-INDEX-START -->

### File Index

| File | Description |
| :--- | :--- |
| [[AGENTS.md]] | 🎯 Project Overview |
| [[CLAUDE.md]] | 🛑 IMPORTANT: READ AGENTS.md FIRST |
| [[CODE_REVIEW_REQUEST.md]] | No description available. |
| [[Documents/README.md]] | No description available. |
| [[PITCH.md]] | Strategic value and high-level project summary |
| [[README.md]] | No description available. |
| [[ROADMAP.md]] | No description available. |
| [[TODO.md]] | No description available. |
| [[config/routing.yaml]] | No description available. |
| [[cursor_mcp_config_example.json]] | No description available. |
| [[package-lock.json]] | No description available. |
| [[package.json]] | No description available. |
| [[scripts/analyze-runs.js]] | Performance analysis of model runs |
| [[scripts/analyze_routing_performance.js]] | No description available. |
| [[scripts/mark_telemetry_reviewed.js]] | No description available. |
| [[scripts/smoke_test.js]] | Server validation script |
| [[scripts/test_routing.js]] | No description available. |
| [[setup_local_ai.sh]] | No description available. |
| [[src/logger.ts]] | Telemetry logging system (JSON Lines) |
| [[src/server.ts]] | MCP protocol implementation and tool registration |
| [[tsconfig.json]] | No description available. |

<!-- LIBRARIAN-INDEX-END -->

## Related Documentation

- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[architecture_patterns]] - architecture
- [[error_handling_patterns]] - error handling
- [[ai_model_comparison]] - AI models
- [[deployment_patterns]] - deployment
- [[performance_optimization]] - performance

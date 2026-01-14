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


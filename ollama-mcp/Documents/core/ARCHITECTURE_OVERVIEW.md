# Architecture Overview

**Last Updated:** 2026-01-01
**Status:** Active

## System Map

The Ollama MCP server is a bridge between the **Model Context Protocol (MCP)** and **Ollama**, a local LLM runner.

```
[ Cursor / Claude ] 
      |
      | (MCP Protocol over stdio)
      v
[ Ollama MCP Server ] <---> [ ~/.ollama-mcp/runs.jsonl ] (Telemetry)
      |
      | (Local Shell Command)
      v
[ Ollama CLI ]
      |
      | (Local API)
      v
[ Local LLMs ] (Llama, DeepSeek, etc.)
```

## Components

### 1. MCP Server (`src/server.ts`)
The core entry point. It implements the MCP specification, defining tools that the AI assistant can call. It handles transport (stdio), tool registration, and execution logic.

### 2. Tools
- **ollama_list_models**: Executes `ollama list` and parses the output to return a list of available models.
- **ollama_run**: Executes `ollama run [model] "[prompt]"` and returns the output. Includes safety checks and timeout handling.
- **ollama_run_many**: A wrapper around `ollama_run` that uses concurrency control to run multiple prompts in parallel.

### 3. Telemetry System (`src/logger.ts`)
A lightweight, append-only logging system.
- Logs every model run to `~/.ollama-mcp/runs.jsonl` in JSON Lines format.
- Captures duration, model name, output size, exit codes, and timestamps.
- Includes a batch ID for grouping concurrent runs.

### 4. Analysis Script (`scripts/analyze-runs.js`)
A utility to process the telemetry logs and provide performance insights (avg duration, timeout rates, etc.).

## Security & Safety
- **Command Injection Prevention**: Input prompts are handled carefully when passed to shell commands.
- **Timeouts**: Default 120s timeout on all Ollama calls to prevent hanging processes.
- **Concurrency Limit**: Hard-capped at 8 concurrent runs to prevent system overload.


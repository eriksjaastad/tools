# Operations Guide

**Last Updated:** 2026-01-01
**Status:** Active

## Prerequisites
- Node.js installed
- Ollama installed and running locally
- One or more models pulled (`ollama pull llama3.2`)

## Development

### Installation
```bash
npm install
```

### Building
The project is written in TypeScript and must be compiled to JavaScript before running.
```bash
npm run build
```
This will generate `dist/server.js` and `dist/logger.js`.

### Running Manually (for testing)
```bash
node dist/server.js
```
*Note: The server communicates over stdio, so it will wait for MCP messages.*

## Deployment in Cursor

To use this server in Cursor:
1. Open Cursor Settings -> MCP.
2. Add a new MCP Server:
   - **Name:** Ollama
   - **Type:** command
   - **Command:** `node /Users/eriksjaastad/projects/_tools/ollama-mcp/dist/server.js`

## Telemetry & Maintenance

### Logs
Telemetry logs are stored at:
`~/.ollama-mcp/runs.jsonl`

### Running Analytics
To see performance metrics:
```bash
node scripts/analyze-runs.js
```

### Log Rotation
Currently, logs are append-only. If the file becomes too large, it can be manually moved or deleted. A rotation script is a future consideration.


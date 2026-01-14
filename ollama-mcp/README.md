# Ollama MCP Server

Minimal MCP server that exposes local Ollama models to Cursor, allowing Sonnet to orchestrate local LLMs as workers.

## Features

- **ollama_list_models()** - List all locally available models
- **ollama_run()** - Run a single model with a prompt
- **ollama_run_many()** - Run multiple models concurrently with controlled concurrency
- **📊 Telemetry Logging** - Automatic performance tracking (NEW!)

## Telemetry & Analytics

Every model run is automatically logged to `~/.ollama-mcp/runs.jsonl` for performance analysis.

### View Analytics

```bash
node scripts/analyze-runs.js
```

This shows:
- **Average duration per model** - "qwen3:4b takes 15s, deepseek-r1:14b takes 90s"
- **Timeout rates** - Which models timeout most often
- **Output sizes** - Character counts per model
- **Batch analysis** - Performance of concurrent runs
- **Recent runs** - Last 10 executions

### Example Output

```
📊 Analysis by Model
🤖 llama3.2:3b
   Runs: 15
   Avg Duration: 23.4s (min: 12.1s, max: 45.2s)
   Avg Output: 1,250 chars
   Timeouts: 2/15 (13.3%)
```

After a week of usage, you'll know exactly which models work best for different task types!

### Log Format

Each run logs one JSON line:
```json
{"timestamp":"2025-12-31T10:30:00Z","model":"llama3.2:3b","duration_ms":15234,"exit_code":0,"output_chars":1250,"timed_out":false}
```

No prompts are logged (privacy + file size).

## Safety Features

- ✅ Only executes `ollama` (hardcoded executable)
- ✅ Input validation (model names, prompt length, parameters)
- ✅ Timeouts (default 120s per run)
- ✅ Concurrency limits (default 3, max 8)
- ✅ No full prompts logged (privacy)

## Installation

```bash
cd ollama-mcp
npm install
npm run build
```

## Usage from Cursor

### 1. Configure Cursor MCP

Add to your Cursor MCP config file (typically `~/.cursor/mcp_config.json` or in Cursor settings):

```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["/Users/eriksjaastad/projects/_tools/ollama-mcp/dist/server.js"]
    }
  }
}
```

### 2. Restart Cursor

After updating the config, restart Cursor to load the MCP server.

### 3. Use from Cursor Chat

Ask Sonnet to use the Ollama tools:

**Example 1: List models**
```
"Use ollama_list_models to show what models I have installed"
```

**Example 2: Run a single model**
```
"Use ollama_run with model 'llama3.2' to draft 5 unit tests for the fibonacci function"
```

**Example 3: Run multiple models in parallel**
```
"Use ollama_run_many to have llama3.2 write code and qwen2.5-coder:7b review it"
```

## Example Workflows

### Parallel Processing
Ask multiple local models to work on different tasks simultaneously:
- Model A: Generate test cases
- Model B: Review code
- Model C: Write documentation

### Token Savings
Offload routine tasks to free local models:
- Use Ollama for drafts, outlines, test generation
- Use Sonnet for final review and complex reasoning

## Development

### Run in dev mode
```bash
npm run dev
```

### Run smoke test
```bash
npm test
```

## Troubleshooting

### "ollama: command not found"
- Install Ollama: https://ollama.ai
- Verify: `which ollama` should show `/usr/local/bin/ollama` or similar
- Add to PATH if needed

### "Model not found"
- List models: `ollama list`
- Pull a model: `ollama pull llama3.2`

### "Permission denied"
- Ensure the server.js file is executable or run via `node`
- Check file permissions: `chmod +x dist/server.js`

### "Connection refused" or "Server not responding"
- Restart Cursor after updating MCP config
- Check Cursor's MCP logs (View > Developer > Toggle Developer Tools > Console)
- Verify server starts: `node dist/server.js` (should print "Ollama MCP server running on stdio")

### "Timeout exceeded"
- Increase timeout in options: `{ timeout: 300000 }` (5 minutes)
- Large models or complex prompts need more time

### "Rate limit" or "Too many requests"
- Reduce `maxConcurrency` in `ollama_run_many`
- Default is 3; try 2 for slower machines

## Future Extensions

To extend this server later:

1. **HTTP API instead of CLI** - Use Ollama's HTTP API (http://localhost:11434/api) for full parameter support (temperature, num_predict, top_p, etc.)
2. **JSON mode** - Add `--format json` flag support for structured output
3. **File-based prompts** - Accept file paths instead of inline strings
4. **Response caching** - Cache identical prompts to avoid re-running
5. **Streaming** - Stream token output instead of waiting for completion
6. **Model metadata** - Return model size, parameters, capabilities
7. **Custom endpoints** - Support custom Ollama server URLs (not just localhost)

## Architecture

```
Cursor (MCP client)
    ↓
ollama-mcp server (stdio transport)
    ↓
Ollama CLI (child processes)
    ↓
Local LLM models
```

## Limits

- Max prompt length: 100,000 characters
- Max num_predict: 8,192 tokens (for future API implementation)
- Max concurrency: 8 jobs
- Default timeout: 120 seconds
- Temperature range: 0-2 (for future API implementation)

**Note:** The current implementation uses Ollama CLI, which doesn't support `temperature` or `num_predict` parameters directly. These options are validated but not applied. A future version will use the Ollama HTTP API to support these features.

Adjust constants in `src/server.ts` if needed.


# Setup Checklist

## ✅ Installation Complete

- [x] Project scaffolded in `../..`
- [x] Dependencies installed
- [x] TypeScript compiled
- [x] Smoke tests passing

## 🔧 Next Steps to Use from Cursor

### 1. Configure Cursor MCP

**Option A: Via Cursor Settings UI**
1. Open Cursor
2. Go to Settings → Features → Model Context Protocol
3. Add a new MCP server with:
   - Name: `ollama`
   - Command: `node`
   - Args: `../../dist/server.js`

**Option B: Manual Config File**
1. Locate your Cursor MCP config (usually `~/.cursor/mcp_config.json`)
2. Add this entry:
```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["../../dist/server.js"]
    }
  }
}
```

### 2. Restart Cursor
Close and reopen Cursor completely to load the MCP server.

### 3. Test It
In Cursor chat, try:
```
"Use ollama_list_models to show what Ollama models I have installed"
```

You should see me call the tool and return your model list.

### 4. Start Using It
Try delegating work:
```
"Use ollama_run with llama3.2 to draft 5 unit tests for the fibonacci function"
```

or

```
"Use ollama_run_many to have llama3.2 draft a README and qwen2.5-coder review it for clarity"
```

## 🐛 Troubleshooting

### Problem: "ollama: command not found"
**Solution:** 
```bash
which ollama
# If empty, install: https://ollama.ai
# Or add to PATH: export PATH="/usr/local/bin:$PATH"
```

### Problem: "No models found"
**Solution:**
```bash
ollama list
# If empty, pull a model:
ollama pull llama3.2
```

### Problem: "Server not responding" in Cursor
**Solution:**
1. Check if server starts: `node ../../dist/server.js`
   - Should print: "Ollama MCP server running on stdio"
   - If error, check Node.js is installed: `node --version`
2. Restart Cursor
3. Check Cursor Developer Tools (View → Developer → Toggle Developer Tools) for MCP errors

### Problem: "Permission denied"
**Solution:**
```bash
chmod +x ../../dist/server.js
```

### Problem: Models timing out
**Solution:** Increase timeout in options:
```json
{
  "model": "deepseek-r1:14b",
  "prompt": "...",
  "options": {
    "timeout": 300000
  }
}
```

## 📊 What's Working

✅ **ollama_list_models**: Lists your installed models  
✅ **ollama_run**: Runs a single model with a prompt  
✅ **ollama_run_many**: Runs multiple models in parallel  

## ⚠️ Known Limitations

- `temperature` and `num_predict` options are accepted but not applied (Ollama CLI doesn't support them)
- ANSI escape codes in stderr (cosmetic only)
- No streaming (waits for complete response)

These will be fixed in v2 with HTTP API support.

## 🎉 You're Ready!

The MCP server is built, tested, and ready to use. Configure Cursor and start delegating tasks to your local models!

## Related Documentation

- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[dashboard_architecture]] - dashboard/UI
- [[prompt_engineering_guide]] - prompt engineering

# Cursor MCP Configuration Guide

This guide explains how to configure Cursor to communicate with the Agent Hub ecosystem using the Model Context Protocol (MCP).

## Prerequisites

Before configuring Cursor MCP, ensure you have:

1. **Node.js** (v18+) - Required for MCP servers and hooks
   ```bash
   node --version  # Should output v18.x.x or higher
   ```

2. **MCP servers built** - Run in the `_tools` directory:
   ```bash
   cd claude-mcp-go && go build -o bin/claude-mcp-go ./cmd/server
   cd ../ollama-mcp-go && go build -o bin/server ./cmd/server
   ```

3. **Ollama running** (for ollama-mcp):
   ```bash
   ollama list  # Should show available models
   ```

## 1. MCP Server Configuration

To use the tools provided by the Agent Hub, you must add the following MCP servers to your Cursor settings.

### Configuration JSON

Copy the JSON below and follow the instructions in the next section to apply it. Replace `<ABSOLUTE_PATH>` with the full path to your `_tools` directory (e.g., `/Users/eriksjaastad/projects/_tools`).

```json
{
  "mcpServers": {
    "claude-hub": {
      "command": "<ABSOLUTE_PATH>/claude-mcp-go/bin/claude-mcp-go",
      "args": []
    },
    "ollama": {
      "command": "<ABSOLUTE_PATH>/ollama-mcp-go/bin/server", 
      "args": [],
      "env": {"SANDBOX_ROOT": "<ABSOLUTE_PATH>"}
    }
  }
}
```

## 2. Where to Apply This Config

1. Open **Cursor Settings** (`Cmd + Shift + J` or `Ctrl + Shift + J`).
2. Navigate to **General** -> **MCP**.
3. Click on **+ Add New MCP Server** for each server listed above:
   - **claude-hub**:
     - Name: `claude-hub`
     - Type: `command`
     - Command: `<ABSOLUTE_PATH>/claude-mcp-go/bin/claude-mcp-go`
   - **ollama**:
     - Name: `ollama`
     - Type: `command`
     - Command: `<ABSOLUTE_PATH>/ollama-mcp-go/bin/server`
     - Environment: `SANDBOX_ROOT=<ABSOLUTE_PATH>`

Currently, the most reliable way to configure MCP is through the Cursor UI as described above. 

If you prefer file-based configuration, check if your version of Cursor supports the `mcp` key in your global `settings.json`:
- macOS: `~/Library/Application Support/Cursor/User/settings.json`
- Windows: `%APPDATA%\Cursor\User\settings.json`

If the `mcp` key is present, you can add the `mcpServers` object there. However, if it's missing, use the UI method.

## 3. Verification Steps

Once added, verify the connection:

1. Look for the green "Connected" status indicator next to the server names in the MCP settings pane.
2. Open the Cursor Composer (`Cmd + I`) or Chat (`Cmd + L`).
3. Type `@` and look for the MCP servers in the list.
4. Run the E2E test script to ensure the servers are functioning correctly:
   ```bash
   cd agent-hub && python scripts/test_mcp_communication.py
   ```

## 4. Troubleshooting

- **Server Status "Disconnected"**: 
  - Ensure you have built the servers: `go build` in both `claude-mcp-go/` and `ollama-mcp-go/`.
  - Check that the absolute path in the command is correct.
  - Check the Cursor "Output" panel (select "MCP" from the dropdown) for specific error messages.
- **Node Not Found**: If the `node` command fails, provide the absolute path to your node executable (e.g., `/usr/local/bin/node`).
- **Tool List Missing**: If tools are not appearing, try clicking the "Refresh" icon next to the MCP server in Cursor settings.

## 5. Important Notes

- **Anti-Gravity IDE**: Note that Anti-Gravity does NOT support this specific MCP configuration pattern as of January 2026. This setup is intended for the standard Cursor IDE.
- **Environment Variables**: If your servers require specific environment variables (like `OLLAMA_HOST`), you may need to wrap the command in a shell script or use a tool like `env` in the command field.

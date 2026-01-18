# Cursor MCP Configuration Guide

This guide explains how to configure Cursor to communicate with the Agent Hub ecosystem using the Model Context Protocol (MCP).

## 1. MCP Server Configuration

To use the tools provided by the Agent Hub, you must add the following MCP servers to your Cursor settings.

### Configuration JSON

Copy the JSON below and follow the instructions in the next section to apply it. Replace `<ABSOLUTE_PATH>` with the full path to your `_tools` directory (e.g., `/Users/eriksjaastad/projects/_tools`).

```json
{
  "mcpServers": {
    "claude-hub": {
      "command": "node",
      "args": ["<ABSOLUTE_PATH>/claude-mcp/dist/server.js"]
    },
    "ollama": {
      "command": "node", 
      "args": ["<ABSOLUTE_PATH>/ollama-mcp/dist/server.js"]
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
     - Command: `node <ABSOLUTE_PATH>/claude-mcp/dist/server.js`
   - **ollama**:
     - Name: `ollama`
     - Type: `command`
     - Command: `node <ABSOLUTE_PATH>/ollama-mcp/dist/server.js`

Alternatively, some versions of Cursor allow editing the configuration file directly at:
- macOS: `~/Library/Application Support/Cursor/User/globalStorage/continuedev.continue/config.json`
- Windows: `%APPDATA%\Cursor\User\globalStorage\continuedev.continue\config.json`

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
  - Ensure you have built the servers: `npm run build` in both `claude-mcp/` and `ollama-mcp/`.
  - Check that the absolute path in the `args` is correct.
  - Check the Cursor "Output" panel (select "MCP" from the dropdown) for specific error messages.
- **Node Not Found**: If the `node` command fails, provide the absolute path to your node executable (e.g., `/usr/local/bin/node`).
- **Tool List Missing**: If tools are not appearing, try clicking the "Refresh" icon next to the MCP server in Cursor settings.

## 5. Important Notes

- **Anti-Gravity IDE**: Note that Anti-Gravity does NOT support this specific MCP configuration pattern as of January 2026. This setup is intended for the standard Cursor IDE.
- **Environment Variables**: If your servers require specific environment variables (like `OLLAMA_HOST`), you may need to wrap the command in a shell script or use a tool like `env` in the command field.

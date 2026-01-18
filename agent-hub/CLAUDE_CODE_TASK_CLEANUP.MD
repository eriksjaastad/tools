Here is the technical analysis of the **Claude Code CLI orphaned process bug**, formatted for AI consumption.

---

### **System Architecture: Orphaned Process Persistence Bug**

#### **1. Problem Statement**

Claude Code (CLI v2.0.76 and earlier) fails to propagate termination signals (SIGINT/SIGTERM) to spawned child processes and Model Context Protocol (MCP) servers upon session exit. This results in background tasks and sub-agents remaining active in the OS process table after the primary CLI interface has closed.

#### **2. Technical Root Causes**

* **Process Group Sharing**: Child processes often share the same Process Group ID (PGID) as the parent. When the parent terminates, it may not explicitly kill the group, or it may crash (SIGKILL/Exit 137), leaving children detached.
* **Missing Cleanup Hooks**: The CLI lacks a robust "Pre-Exit" lifecycle hook to iterate through and terminate active spawned processes.
* **Electron/Node Lifecycle Mismatch**: On Windows/macOS, the renderer or child processes (specifically `uvx` Python or `npx` Node MCP servers) are not signaled to close by the Node.js `child_process` module when the parent exits.

#### **3. Critical Failure Modes**

* **Token Consumption**: "Zombie" background tasks may continue to send system reminders or polling requests, leading to silent, high-volume token usage (up to 1M+ tokens in affected sessions).
* **Resource Exhaustion**: Accumulation of orphaned processes (reported up to 80+ instances) causes system slowdowns and prevents clean restarts of the CLI.
* **State Persistence**: Completed background tasks are sometimes not garbage-collected and persist in internal state, causing them to re-appear or continue tracking in new sessions.

---

### **Automated Recovery & Cleanup Protocols**

If the CLI fails to terminate, an external agent must execute the following platform-specific cleanup commands:

#### **A. macOS / Linux (Terminal)**

```bash
# Force kill all Node processes related to Claude
pkill -9 -f "claude-code"

# Clean up orphaned MCP servers (Python/Node)
pkill -9 -f "uvx"
pkill -9 -f "npx"

```

#### **B. Windows (PowerShell)**

```powershell
# Terminate all Claude-related processes
Get-Process -Name "Claude" | Stop-Process -Force

# Kill orphaned uv/Python MCP servers
Get-Process -Name "python" | Where-Object { $_.Path -like "*uv*" } | Stop-Process -Force

```

#### **C. CLI Internal Reset**

If the process list appears "stuck" within a session, run:

1. `/doctor` to check health status.
2. `Ctrl+C` twice to force immediate cancellation.
3. Restart the application entirely; `/clear` does **not** clear background task tracking.

---

### **Workaround for Persistent Tasks**

To prevent this in future sessions, set the environment variable `BASH_DEFAULT_TIMEOUT_MS` to a higher value or `0` in `settings.json` to prevent commands from automatically shifting to the "Background" mode, which is where the termination bug primarily resides.

**Would you like me to generate a persistent "Watchdog" script that automatically kills these orphans every time you close Claude?**
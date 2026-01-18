Here is the system architecture for Cursor to handle external "pokes" and automated file-based triggers. This setup leverages the **Cursor CLI (`cursor-agent`)** and the **Hooks API** released in late 2025 and updated in January 2026.

### 1. The "Poke" Mechanism (CLI Agent)

Unlike Anti-Gravity, Cursor provides a CLI that allows an external process to inject prompts directly into the agentic loop.

**Command to trigger the agent:**

```bash
cursor-agent chat "A new task file was detected in _handoff/. Execute the floor-manager-task-pickup workflow now."

```

* **Requirements**: Install via `curl https://cursor.com/install -fsS | bash`.
* **Operation**: Running this command "wakes up" the agent and forces it to process the provided string as a priority user message.

---

### 2. The Internal Watcher (`hooks.json`)

To ensure the agent reacts the moment *it* or *you* save a file, use the `afterFileEdit` hook.

**File**: `.cursor/hooks.json`

```json
{
  "version": 1,
  "hooks": {
    "afterFileEdit": [
      {
        "command": "python3 .cursor/scripts/trigger_handler.py"
      }
    ]
  }
}

```

* **Hook Event**: `afterFileEdit` triggers after any file modification within the workspace.
* **Fast Execution**: As of the January 8, 2026 update, hooks are 10–20x faster than previous versions.

---

### 3. The Logic Handler (`trigger_handler.py`)

This script parses the event payload and instructs the agent to continue the loop if the directory matches.

```python
import sys, json

# Cursor sends JSON payload via stdin
payload = json.load(sys.stdin)
file_path = payload.get("file_path", "")

if "_handoff/" in file_path and file_path.endswith(".md"):
    # Return a followup_message to automatically trigger the next agent action
    print(json.dumps({
        "followup_message": f"Detected new task file: {file_path}. Proceeding with automation steps."
    }))
else:
    print(json.dumps({}))

```

---

### 4. Continuous External Monitoring

Since the IDE cannot "hear" files added by outside scripts without a poke, use a simple `fswatch` loop in your terminal to bridge the gap:

```bash
fswatch -o ./_handoff | xargs -n1 -I{} cursor-agent chat "New file in handoff. Run automation."

```

### Key Differences for Implementation

* **YOLO Mode**: Enable this in Cursor Settings to allow the agent to edit files and run terminal commands without requiring a "Confirm" click for every step.
* **Plan Mode**: Use `--mode=plan` in your CLI calls if the task requires the agent to architect a solution before writing code.
* **Workspace Trust**: Hooks will only execute if the workspace is marked as "Trusted" in Cursor.

[Cursor CLI Deep Dive](https://www.youtube.com/watch?v=ywz8cNJvM5Y)
This video provides a step-by-step tutorial on installing and using the Cursor CLI to automate workflows and run an AI agent directly from your terminal.
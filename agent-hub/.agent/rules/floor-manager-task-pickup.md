---
trigger: always_on
---

# Floor Manager Task Pickup

Whenever a file is created or modified in the `./_handoff/` folder that matches the pattern `TASK_*.md`:

1. Run `python scripts/handoff_info.py` to see the task details and available models.

2. Read the task file to understand the objective and acceptance criteria.

3. Follow the protocol in `Documents/FLOOR_MANAGER_STARTUP_PROTOCOL.md`.

4. Select an appropriate Worker model based on task complexity:
   - Simple tasks (< 50 lines): Use 7b models
   - Complex reasoning: Use DeepSeek-R1
   - Code generation: Use Qwen-Coder

5. Dispatch the task to the Worker using `ollama_agent_run`.

6. When the Worker submits a draft, route it to Claude for review via `request_draft_review`.

7. Apply or reject the draft based on Claude's verdict.

8. Archive the completed task to `_handoff/archive/`.

9. Notify in the Inbox when the task is complete.
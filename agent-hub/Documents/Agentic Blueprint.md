# 🏗️ The Multi-Agent Documentation Pipeline

**Objective:** Clean, merge, and de-duplicate 30 projects using a hierarchical handoff.

## 1. The Roles (The Org Chart)

| Role | AI Model | Key Responsibility |
| --- | --- | --- |
| **Supermanager** | Claude Code CLI | **Strategy:** Owns the `MASTER_PLAN.md`. Decides which files to merge across projects. |
| **Floor Manager** | Gemini 3 Flash | **Orchestration:** Takes a task from the plan, gathers context, and "hires" a Worker. |
| **Worker** | Local LLM (or Gemini) | **Execution:** Physically edits the files. No talking, just coding. |
| **Judge** | Claude Code CLI | **Validation:** Checks if the finished doc matches the "Standardized Review" checklist. |

---

## 2. The File-Based Handoff (The "Paper Trail")

To stop the models from just "talking" about the work, use these files as the source of truth:

1. **`PROPOSAL.md`**: Claude CLI writes exactly what it wants to change.
2. **`TASK_CONTRACT.json`**: Gemini converts that proposal into a strict set of instructions for the local model.
3. **`WORK_OUTPUT.md`**: The local model writes its changes here (instead of just talking in a chat).
4. **`JUDGE_REPORT.log`**: The final review. If it says `FAIL`, Gemini is triggered to redo the task.

---

## 3. The Step-by-Step Architecture

### Phase 1: The Cross-Project Audit (Pass 1)

* **Goal:** Identify what to kill and what to keep.
* **The Action:** Claude CLI scans all 30 projects and creates a **Global Index**. It looks for files with similar names (e.g., `ProjectA/auth.md` and `ProjectB/login-flow.md`).
* **The Output:** A list of "Merge Targets" in your `MASTER_PLAN.md`.

### Phase 2: The Implementation Factory (Pass 2)

* **Goal:** Physically merge and rewrite the documentation.
* **The Worker Handoff:** Gemini (Floor Manager) takes the "Merge Target," gathers the source files, and generates a `TASK_CONTRACT.json`. This is routed via **AI Router** or **Ollama MCP** to the local model.
* **The Execution:** The local model (Worker) follows the contract rules to generate the "Golden Document" (as `WORK_OUTPUT.md`). It does not "chat"—it only writes code/markdown.

### Phase 3: The Review Handoff (The Gatekeeper Transition)

* **The Trigger:** Once the Worker marks the task as `pending_review` in the contract, a **Watchdog** script generates a `REVIEW_REQUEST.md`.
* **The Goal:** Bridge the gap between the "dirty" implementation and the "standardized" final version.
* **The Action:** This trigger signals the **Judge** (Claude Code CLI) to wake up and begin the architectural audit.

### Phase 4: The Standardized Review (Pass 3)

* **The Action:** Your Claude Code CLI takes the "Golden Document."
* **The Check:** It runs a non-prompt-based check:
* Are all internal links valid?
* Is there any "Lorum Ipsum" or placeholder text?
* Does it follow the 14pt-readability logic (concise sentences)?



---

## 4. How to set this up in Cursor

Since you're using Cursor as your Floor Manager:

1. **Use `.cursorrules**`: Paste a rule that says: *"You are the Floor Manager. Your goal is to execute the next task in `MASTER_PLAN.md`. Do not provide advice; generate a shell command or a file-edit to progress the task."*
2. **The "Not-Automated" Fix**: Tell Claude (the programmer) to write a simple **Python Watchdog script**.
* The script watches for changes in `MASTER_PLAN.md`.
* When a line is marked "Ready," it automatically triggers a CLI command that feeds the task to Gemini. This removes you as the "middleman" who has to paste things.



---

### A Note for Claude (The Scripting Partner):

> "Claude, we want to move away from 'Chat-based' handoffs and move toward 'File-based' state management. Please help me write a wrapper that takes a task description, fetches the necessary file contents, and sends it to the local model via a subprocess call, ensuring the output is captured as a file write rather than just a terminal log."

**Would you like me to refine any specific part of this—like the specific "Contract" prompt Gemini should send to the local models?**
# claude-mcp Specification

> **Purpose:** MCP server that wraps Claude CLI, enabling Gemini (and other MCP clients) to invoke Claude for code reviews, conversations, and other tasks.
> **Pattern:** Same architecture as `ollama-mcp`
> **Created:** 2026-01-17

---

## 1. Why claude-mcp?

Currently, the Agent Hub has no way for Gemini (Floor Manager) to directly communicate with Claude (Judge). The options are:

1. Gemini runs `claude` in terminal (requires terminal access, fragile)
2. File-based handoff with bash watcher (current, adds moving parts)
3. **MCP bridge** (consistent with `ollama-mcp`, cleanest)

With `claude-mcp`, Gemini calls Claude the same way it calls Ollama:

```
Gemini → MCP call → claude-mcp server → claude CLI → response → Gemini
```

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP CLIENT (Gemini)                      │
│                   Cursor / Antigravity                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ JSON-RPC over stdio
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    claude-mcp (Node.js)                     │
│                                                             │
│  Tools:                                                     │
│    - claude_run        (general prompt)                     │
│    - claude_review     (code review with contract context)  │
│    - claude_health     (check if claude CLI is available)   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ subprocess
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Claude CLI                             │
│              claude --dangerously-skip-permissions          │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. MCP Tools (Constrained Menu)

> **IMPORTANT:** Gemini does NOT get freeform prompt access to Claude. Each tool has a **fixed prompt template** baked into the MCP server. Gemini provides context (paths, files), not instructions. This prevents Gemini from going off-script or sending adversarial prompts.

### Design Principle: Multiple Choice, Not Free Text

```
❌ WRONG: claude_run(prompt="anything Gemini wants to say")
✅ RIGHT: claude_judge_review(contract_path="...") → fixed Judge prompt
```

Gemini picks from a menu. The MCP server controls what Claude actually sees.

---

### 3.1 `claude_judge_review`

**Purpose:** The Judge role - architectural code review.

**What Gemini provides:** Just the contract path.
**What Claude sees:** Fixed Judge prompt template with contract injected.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "contract_path": {
      "type": "string",
      "description": "Path to TASK_CONTRACT.json"
    },
    "report_dir": {
      "type": "string",
      "default": "_handoff",
      "description": "Directory to write JUDGE_REPORT.md and JUDGE_REPORT.json"
    },
    "timeout_seconds": {
      "type": "integer",
      "default": 900,
      "description": "Maximum time for review"
    }
  },
  "required": ["contract_path"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "verdict": {
      "type": "string",
      "enum": ["PASS", "CONDITIONAL", "FAIL", "CRITICAL_HALT"]
    },
    "blocking_issues_count": { "type": "integer" },
    "report_md_path": { "type": "string" },
    "report_json_path": { "type": "string" },
    "error": { "type": "string" },
    "duration_ms": { "type": "integer" }
  }
}
```

**Example:**
```json
{
  "tool": "claude_review",
  "arguments": {
    "contract_path": "/Users/erik/projects/my-app/_handoff/TASK_CONTRACT.json",
    "timeout_seconds": 600
  }
}
```

**What it does internally:**
1. Reads the contract
2. Builds a Judge prompt with specification, requirements, changed files
3. Invokes `claude --dangerously-skip-permissions` with the prompt
4. Parses Claude's response
5. Writes `JUDGE_REPORT.md` and `JUDGE_REPORT.json` to report_dir
6. Returns verdict and metadata

---

### 3.3 `claude_health`

Check if Claude CLI is installed and responsive.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {}
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "available": { "type": "boolean" },
    "version": { "type": "string" },
    "error": { "type": "string" }
  }
}
```

---

### 3.4 `claude_validate_proposal`

**Purpose:** Check if a PROPOSAL_FINAL.md is well-formed before Floor Manager converts it.

**Input:**
```json
{
  "proposal_path": { "type": "string" }
}
```

**Fixed prompt:** "Review this proposal. Is it complete and actionable? Return JSON with {valid: bool, issues: []}."

---

### 3.5 `claude_security_audit`

**Purpose:** Deep security review of specific files (beyond what DeepSeek catches).

**Input:**
```json
{
  "files": { "type": "array", "items": { "type": "string" } },
  "working_directory": { "type": "string" }
}
```

**Fixed prompt:** "Audit these files for security vulnerabilities. Return JSON with findings."

---

### 3.6 `claude_resolve_conflict`

**Purpose:** When Floor Manager and Judge disagree, get a fresh perspective.

**Input:**
```json
{
  "contract_path": { "type": "string" },
  "rebuttal_path": { "type": "string" },
  "judge_report_path": { "type": "string" }
}
```

**Fixed prompt:** "Review the disagreement between Floor Manager (rebuttal) and Judge (report). Who is correct? Return JSON with {side: 'floor_manager'|'judge', reasoning: '...'}."

---

## The Menu (What Gemini Can Ask)

| Tool | When to Use | Gemini Provides | Claude Does |
|------|-------------|-----------------|-------------|
| `claude_judge_review` | After local review passes | contract_path | Full code review, writes reports |
| `claude_validate_proposal` | Before converting proposal | proposal_path | Checks proposal completeness |
| `claude_security_audit` | Optional deep security check | file paths | Security-focused review |
| `claude_resolve_conflict` | Rebuttal situation | contract, rebuttal, report | Decides who's right |
| `claude_health` | Before any operation | nothing | Returns availability |

**Gemini cannot:**
- Send arbitrary prompts
- Modify the prompt templates
- Ask Claude to do anything outside this menu

**The MCP server enforces this.** Gemini only passes context; the server controls what Claude sees.

---

## 4. Access Control

### Who Can Connect to claude-mcp

| Actor | Access | Reason |
|-------|--------|--------|
| **Floor Manager (Gemini)** | YES | Orchestrator - needs to request reviews, resolve conflicts |
| **Cursor / Antigravity IDE** | YES (via Floor Manager) | The IDE hosts the Floor Manager |
| **Implementer (Qwen)** | NO | Worker - gets invoked, doesn't invoke |
| **Local Reviewer (DeepSeek)** | NO | Worker - gets invoked, doesn't invoke |
| **Other local models** | NO | Workers don't talk to Claude directly |

### How to Enforce

1. **Process isolation** - Only the Floor Manager process has the MCP connection
2. **No forwarding** - Floor Manager cannot proxy arbitrary requests from other models
3. **Menu enforcement** - Even with access, only constrained tools are available

### Communication Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Gemini    │ ──── │  claude-mcp │ ──── │   Claude    │
│ (Floor Mgr) │ JSON │   (Node.js) │  CLI │   (me)      │
└─────────────┘ RPC  └─────────────┘      └─────────────┘
       │                                         │
       │  request: claude_judge_review()         │
       │  ─────────────────────────────────────► │
       │                                         │
       │                        writes JUDGE_REPORT.md/.json
       │                                         │
       │  response: {verdict, issues, ...}       │
       │  ◄───────────────────────────────────── │
       │                                         │
       ▼
  Gemini decides:
  PASS → merge
  FAIL → loop back
```

### What Gemini Receives Back

Every claude-mcp tool returns structured JSON, not prose:

```json
{
  "success": true,
  "verdict": "CONDITIONAL",
  "blocking_issues_count": 2,
  "report_json_path": "_handoff/JUDGE_REPORT.json",
  "duration_ms": 45000
}
```

Gemini parses this and makes decisions. No ambiguity.

---

## 5. Implementation Notes

### 4.1 Subprocess Invocation

```typescript
import { spawn } from 'child_process';

async function runClaude(prompt: string, options: ClaudeOptions): Promise<ClaudeResult> {
  const args = ['--dangerously-skip-permissions'];

  if (options.print) {
    args.push('--print');
  }

  const proc = spawn('claude', args, {
    cwd: options.workingDirectory,
    stdio: ['pipe', 'pipe', 'pipe']
  });

  // Write prompt to stdin
  proc.stdin.write(prompt);
  proc.stdin.end();

  // Collect output with timeout
  const output = await collectWithTimeout(proc.stdout, options.timeout);

  return {
    success: proc.exitCode === 0,
    output: output,
    duration_ms: elapsed
  };
}
```

### 4.2 Judge Prompt Template

```typescript
const JUDGE_PROMPT_TEMPLATE = `
You are the Judge in the Agent Hub pipeline. Your role is to perform a deep architectural review.

## Task Contract
\`\`\`json
{{CONTRACT_JSON}}
\`\`\`

## Changed Files
{{CHANGED_FILES_CONTENT}}

## Your Task

1. Review the changed files against the specification.requirements
2. Check all acceptance_criteria
3. Look for security issues, broken logic, missing edge cases
4. Produce a verdict: PASS, CONDITIONAL, FAIL, or CRITICAL_HALT

## Required Output

You MUST write two files:

1. **_handoff/JUDGE_REPORT.md** - Human-readable report
2. **_handoff/JUDGE_REPORT.json** - Machine-readable with this schema:
   {
     "task_id": "...",
     "verdict": "PASS|CONDITIONAL|FAIL|CRITICAL_HALT",
     "blocking_issues": [...],
     "suggestions": [...],
     "tokens_used": ...
   }

Write these files now, then exit.
`;
```

### 4.3 Timeout Handling

Claude can take a while for complex reviews. The MCP server must:

1. Track elapsed time
2. Kill the subprocess if timeout exceeded
3. Return `{ success: false, timed_out: true }`

```typescript
const timeoutId = setTimeout(() => {
  proc.kill('SIGTERM');
  timedOut = true;
}, options.timeout * 1000);
```

### 4.4 Error Handling

| Error | Handling |
|-------|----------|
| Claude CLI not found | Return `{ available: false }` from health check |
| Subprocess crash | Return `{ success: false, error: stderr }` |
| Timeout | Return `{ success: false, timed_out: true }` |
| Invalid JSON output | Return `{ success: false, error: "parse_error" }` |

---

## 5. Directory Structure

```
_tools/claude-mcp/
├── package.json
├── tsconfig.json
├── src/
│   ├── server.ts          # MCP server entry point
│   ├── tools/
│   │   ├── claude_run.ts
│   │   ├── claude_review.ts
│   │   └── claude_health.ts
│   ├── prompts/
│   │   └── judge_template.ts
│   └── utils/
│       └── subprocess.ts
├── dist/                   # Compiled JS
└── README.md
```

---

## 6. Integration with Agent Hub

### 6.1 Floor Manager Usage

Once `claude-mcp` is running, Gemini (Floor Manager) can:

```
1. Invoke Ollama for implementation:
   → ollama_run(model="qwen2.5-coder:14b", prompt="...")

2. Invoke Ollama for local review:
   → ollama_run(model="deepseek-r1:7b", prompt="...")

3. Invoke Claude for Judge review:
   → claude_review(contract_path="_handoff/TASK_CONTRACT.json")

4. Read the verdict and decide:
   → If PASS: merge
   → If FAIL: loop back to step 1
```

### 6.2 Python MCP Client Update

The `mcp_client.py` from Phase 6 should work with both servers:

```python
# Connect to Ollama
ollama_client = MCPClient(Path("_tools/ollama-mcp/dist/server.js"))

# Connect to Claude
claude_client = MCPClient(Path("_tools/claude-mcp/dist/server.js"))

# Use both
ollama_client.call_tool("ollama_run", {...})
claude_client.call_tool("claude_review", {...})
```

Or create a unified client that manages both connections.

---

## 7. Security Considerations

1. **`--dangerously-skip-permissions`** - Required for autonomous operation. The MCP server inherits this risk.

2. **Working directory isolation** - Claude runs in the specified working_directory. Don't allow arbitrary paths.

3. **Timeout enforcement** - Prevents runaway Claude sessions.

4. **No secrets in prompts** - The Judge prompt should not include API keys or credentials.

---

## 8. Future Enhancements

| Enhancement | Description |
|-------------|-------------|
| Token tracking | Parse Claude's output for token usage, pipe to `update_cost()` |
| Conversation mode | Support multi-turn conversations for Super Manager role |
| Streaming | Stream output for long-running reviews |
| Model selection | Support different Claude models if available |

---

## 9. Implementation Priority

**Phase 7 (after Phase 6 MCP Bridge):**

- Prompt 7.1: Create `claude-mcp` project structure
- Prompt 7.2: Implement `claude_run` and `claude_health` tools
- Prompt 7.3: Implement `claude_review` with Judge prompt template
- Prompt 7.4: Test integration with Agent Hub

---

*With `claude-mcp`, Gemini has a consistent interface to both local models (Ollama) and cloud intelligence (Claude). The Floor Manager becomes a true orchestrator.*

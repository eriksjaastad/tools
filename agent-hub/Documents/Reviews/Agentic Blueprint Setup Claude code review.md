# Agentic Blueprint Setup: Claude Code Review

This is a well-thought-out architecture. The separation of concerns, explicit state machine, and circuit breakers show mature thinking about autonomous systems. Let me share some observations and questions.

## Strengths

*   **Cost optimization** - Using local models (Qwen, DeepSeek) for high-volume grunt work while reserving cloud models for orchestration and deep review is smart economics.
*   **Circuit breakers are excellent** - The "Hallucination Loop" and "Rebuttal Limit" guards are exactly the kind of safety rails that prevent runaway automation. The "GPT-Energy Guardrail" is particularly pragmatic.
*   **Auditability via contract history** - Having the full evolution trail in `TASK_CONTRACT.json` is valuable for debugging and learning.

## Concerns & Questions

### 1. File-based signaling has race conditions
The `_handoff/*.md` approach is simple but fragile:
*   What if the watchdog reads `REVIEW_REQUEST.md` while it's still being written?
*   What if two agents try to update `TASK_CONTRACT.json` simultaneously?
*   **Consider:** atomic writes (write to temp file, then rename) or using a lightweight message queue like SQLite WAL mode.

### 2. Claude Code CLI invocation
The flag `--non-interactive` doesn't exist. The actual pattern would be:
```bash
echo "Review the task..." | claude --print
# or
claude --dangerously-skip-permissions "Review the task..."
```
But more importantly - you'd want Claude to have access to the full codebase context, not just be invoked cold each time. How do you plan to maintain context between reviews?

### 3. Rebuttal limit of 2 might be too tight
For complex architectural decisions, legitimate disagreement could exceed 2 rounds. Consider:
*   Escalating the limit based on task complexity score
*   Or having a "soft" limit (2 for minor, 4 for major tasks)

### 4. What's the rollback story?
If the Implementer writes broken code and it somehow passes review, how do you recover? I'd suggest git commits at each state transition so you can `git reset --hard` to any checkpoint.

### 5. Missing: Timeout handling
What if Ollama hangs? What if Claude takes 5 minutes on a review? The watchdog needs timeout logic:
*   `status: "timeout_implementer" | "timeout_judge"`

## Suggested Improvements

**Add a lock field to prevent concurrent modifications:**
```json
{
  "lock": {
    "held_by": "ollama-qwen",
    "acquired_at": "2026-01-16T10:30:00Z",
    "expires_at": "2026-01-16T10:35:00Z"
  }
}
```

**Add structured validation for the Judge report:**
```json
{
  "judge_verdict": {
    "grade": "PASS|FAIL|CONDITIONAL",
    "blocking_issues": [],
    "suggestions": [],
    "security_flags": []
  }
}
```
This makes the Floor Manager's decision logic cleaner than parsing markdown.

## Questions Before Implementation

*   What's the expected throughput? One task at a time, or parallel tasks across different projects?
*   Is `agent-hub/hub.py` already scaffolded? I can look at what exists and help implement the state machine there.
*   Local model reliability - How stable are your Ollama models? DeepSeek-R1 can be resource-intensive. Do you have fallback logic if local inference fails?

Want me to explore the existing codebase to see what's already in place, or would you prefer to discuss the architecture further first?

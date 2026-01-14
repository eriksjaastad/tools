# Ollama MCP Enhancement: Smart Local Routing

> **Type:** Technical Specification (Supersedes RETRY_ESCALATION_SPEC.md)
> **Author:** Super Manager (Claude)
> **Date:** January 10, 2026
> **Target Project:** ollama-mcp (TypeScript)
> **Status:** Completed ✅ (Implemented January 10, 2026)

---

## Philosophy

**The Floor Manager is the fallback, not the cloud.**

Workers (local models) attempt tasks. If ALL local models fail, the system halts and escalates to Floor Manager. We never silently call paid APIs for automated coding/logic tasks.

**Learn, don't guess.**

Track which models succeed at which task types. Over time, route intelligently instead of always defaulting to DeepSeek.

---

## Current Problem

Observation from Floor Manager sessions:
- DeepSeek gets everything
- Qwen rarely used
- Llama almost never used

This is wasteful. Different models have different strengths:

| Model | Strengths | Weaknesses |
|-------|-----------|------------|
| llama3.2:3b | Fast, classification, yes/no | Can't generate code |
| qwen3:14b | Good at code, follows instructions | Slower |
| deepseek-r1 | Reasoning, complex logic | Timeouts on big tasks |

---

## Proposed Solution: Smart Local Routing

### 1. Task-Type Classification

Before dispatching, classify the task:

| Task Type | Signals | Best Model |
|-----------|---------|------------|
| **Classification** | "Is this...", "yes or no", "which one" | llama3.2:3b (fast) |
| **Extraction** | "Find the...", "extract...", "list all" | llama3.2:3b or qwen |
| **Code Generation** | "Write a function", "implement", code blocks | qwen3:14b |
| **Reasoning** | "Explain why", "analyze", "design" | deepseek-r1 |
| **File Modification** | "Update the file", "add to", StrReplace patterns | qwen3:14b |

### 2. New `ollama_run` Parameters

```typescript
interface OllamaRunParams {
  model?: string;           // Explicit model (bypasses routing)
  prompt: string;
  timeout?: number;

  // NEW: Smart routing
  task_type?: "classification" | "extraction" | "code" | "reasoning" | "file_mod" | "auto";
  fallback_chain?: string[];  // e.g., ["qwen3:14b", "deepseek-r1"]
  max_retries?: number;       // Default: 3 (across all models in chain)
  retry_count?: number;       // Current retry (caller tracks)
}
```

### 3. Routing Logic

```
IF task_type provided:
  Select best model for task_type
ELSE IF model provided:
  Use explicit model
ELSE:
  Default to qwen3:14b (balanced)

IF model fails (timeout, error, poor response):
  Try next model in fallback_chain

IF all models exhausted:
  Return { escalate: true, escalation_reason: "all_local_models_failed" }
```

### 4. Response Quality Detection

Port from AI Router - detect bad responses:

```typescript
function isGoodResponse(text: string): boolean {
  // Too short
  if (text.length < 40) return false;

  // Refusal patterns
  const refusals = ["I cannot", "I'm unable", "I don't have access"];
  if (refusals.some(r => text.includes(r))) return false;

  // Empty or error
  if (!text.trim()) return false;

  return true;
}
```

If response is poor, try next model in chain.

### 5. Enhanced Response Structure

```typescript
interface OllamaRunResponse {
  content: [{ type: "text", text: string }];
  metadata: {
    model_used: string;
    task_type: string;
    duration_ms: number;
    timed_out: boolean;
    retry_count: number;
    models_tried: string[];      // History of attempts
    escalate: boolean;           // TRUE = Floor Manager should take over
    escalation_reason?: string;  // "all_local_models_failed" | "max_retries"
  }
}
```

### 6. Learned Routing (Telemetry-Driven)

Track success/failure per model per task type:

```jsonl
{"timestamp":"2026-01-10T...","task_type":"code","model":"qwen3:14b","success":true,"duration_ms":4500}
{"timestamp":"2026-01-10T...","task_type":"code","model":"deepseek-r1","success":false,"reason":"timeout"}
{"timestamp":"2026-01-10T...","task_type":"classification","model":"llama3.2:3b","success":true,"duration_ms":800}
```

Over time, build a success rate matrix:

| Task Type | llama3.2:3b | qwen3:14b | deepseek-r1 |
|-----------|-------------|-----------|-------------|
| classification | 95% ✓ | 90% | 85% |
| code | 20% | 85% ✓ | 70% |
| reasoning | 30% | 60% | 80% ✓ |

Use this to update routing decisions.

---

## Default Fallback Chains

If no `fallback_chain` provided, use sensible defaults based on task type:

```typescript
const DEFAULT_CHAINS = {
  classification: ["llama3.2:3b", "qwen3:14b"],
  extraction: ["llama3.2:3b", "qwen3:14b"],
  code: ["qwen3:14b", "deepseek-r1"],
  reasoning: ["deepseek-r1", "qwen3:14b"],
  file_mod: ["qwen3:14b", "deepseek-r1"],
  auto: ["qwen3:14b", "deepseek-r1", "llama3.2:3b"],  // Try all
};
```

---

## Floor Manager Protocol

When `escalate: true` is returned:

1. **STOP** dispatching to Workers
2. **DO NOT** call cloud APIs
3. **HALT** and alert Conductor OR
4. **Floor Manager takes over** (if authorized for this task type)

This is the 3-Strike Escalation Rule, now enforced structurally.

---

## What This Does NOT Do

- ❌ Call cloud APIs (OpenAI, Anthropic, etc.)
- ❌ Silently retry forever
- ❌ Let Floor Manager write code (that's a protocol violation)
- ❌ Guess which model to use without tracking results

---

## Implementation Phases

### Phase 1: Basic Smart Routing (1-2 hours)
- Add `task_type` parameter
- Implement default fallback chains
- Add `models_tried` to response

### Phase 2: Response Quality Detection (1 hour)
- Port `isGoodResponse()` from AI Router
- Auto-retry on poor response

### Phase 3: Learned Routing (2-3 hours)
- Enhanced telemetry with task_type
- Success rate tracking per model
- Periodic recalculation of optimal routes

---

## Success Criteria

- [x] Tasks are routed to appropriate models based on type
- [x] Llama gets used for classification/extraction (not just DeepSeek for everything)
- [x] Failed attempts try next model in chain
- [x] `escalate: true` returned when all local models fail
- [x] Telemetry tracks success/failure per model per task type
- [x] Floor Manager can see which models are struggling

---

## Related Documents

- `OLLAMA_MCP_RETRY_ESCALATION_SPEC.md` - Earlier spec (focused on retry count only)
- `AGENTS.md` - 3-Strike Escalation Rule
- `LOCAL_MODEL_LEARNINGS.md` - Model behavior observations
- AI Router `router.py` - Reference implementation for routing logic

---

*This spec supersedes RETRY_ESCALATION_SPEC.md with a more comprehensive approach.*

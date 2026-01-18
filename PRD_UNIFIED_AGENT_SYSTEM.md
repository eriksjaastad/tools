# PRD: Unified Agent System

> **Document Type:** Product Requirements Document
> **Version:** 1.0
> **Author:** Claude Code (Opus 4.5)
> **Date:** 2026-01-18
> **Status:** Approved for Development

---

## 1. Overview

### 1.1 Problem Statement

The current agent-hub system has three critical limitations:

1. **Performance:** Every Ollama call spawns a new CLI process (2-5s overhead). Every MCP tool call spawns a new Node.js process (100-300ms overhead). These cold starts compound across agent workflows.

2. **Communication:** Workers cannot ask clarifying questions. The human becomes the bottleneck, manually shuttling context between agents.

3. **Environment Lock-in:** Agent definitions are tied to specific environments. Moving between Claude CLI, Cursor, and Anti-Gravity requires manual reconfiguration.

### 1.2 Solution

Build a **Local-First Unified Agent System** that:

- Eliminates cold start overhead via persistent HTTP connections
- Enables bi-directional communication between agents
- Works seamlessly across Claude CLI, Cursor, and Anti-Gravity
- Routes 90%+ of work to free local models with automatic cloud fallback

### 1.3 Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| TTFT (warm model) | 2-5s | < 500ms |
| MCP tool call latency | 100-300ms | < 100ms |
| Local task handling | ~50% | > 90% |
| Cloud spend | Variable | < $5/day |
| Task completion rate | ~80% | > 95% |
| Human escalation rate | ~50% | < 20% |

---

## 2. User Stories

### 2.1 Primary User: Erik (Developer/Architect)

**As Erik, I want to:**

1. **Delegate work without babysitting**
   - Give a task to any agent (Claude CLI, Cursor, Anti-Gravity)
   - Have it automatically route to the cheapest capable model
   - Only be interrupted when genuinely needed

2. **Answer questions asynchronously**
   - See pending questions from workers in one place
   - Answer when I'm ready, not when the agent blocks
   - Have my answers automatically reach the waiting worker

3. **Control costs proactively**
   - Know before execution if a task will exceed budget
   - See which tasks escaped to cloud and why
   - Set session and daily spending limits

4. **Work in any environment**
   - Use the same agent definitions in Claude CLI, Cursor, or Anti-Gravity
   - Switch environments without reconfiguring
   - Have consistent behavior everywhere

### 2.2 Secondary User: Agents (Super Manager, Floor Manager, Workers)

**As an orchestrating agent, I want to:**

1. **Spawn workers efficiently**
   - Call local models without cold start penalty
   - Have fallback options when local fails
   - Track costs per worker

2. **Communicate bi-directionally**
   - Ask the parent agent or human for clarification
   - Receive answers without restarting
   - Continue work with new context

---

## 3. Functional Requirements

### 3.1 Performance Layer

#### FR-1.1: Ollama HTTP Client
- **SHALL** use HTTP API (`localhost:11434`) instead of CLI spawn
- **SHALL** maintain persistent connections with connection pooling
- **SHALL** use `keep_alive` parameter to keep models warm
- **SHALL** support both `/api/generate` and `/api/chat` endpoints

#### FR-1.2: Persistent MCP Connections
- **SHALL** keep MCP servers alive for session duration
- **SHALL NOT** spawn new Node.js process per tool call
- **SHALL** handle graceful reconnection on server restart

#### FR-1.3: Adaptive Polling
- **SHALL** start polling at 1-second intervals
- **SHALL** backoff to 10-second intervals when idle
- **SHALL** reset to 1-second on new activity

### 3.2 Routing Layer

#### FR-2.1: Model Tiering
- **SHALL** support three tiers: Free (Ollama), Cheap (Gemini), Premium (Claude)
- **SHALL** route based on task type and complexity
- **SHALL** allow tier configuration via YAML

#### FR-2.2: Fallback Chains
- **SHALL** automatically try next tier on model failure
- **SHALL** implement cooldown cache for failing models
- **SHALL** log all fallback events with reason

#### FR-2.3: Context-Window Awareness
- **SHALL** estimate input token count before routing
- **SHALL** auto-route to larger context model if input exceeds local limits
- **SHALL** warn when approaching context limits

### 3.3 Communication Layer

#### FR-3.1: Bi-Directional Messaging
- **SHALL** implement `ask_parent(question)` for workers
- **SHALL** implement `reply_to_worker(message_id, answer)` for parents
- **SHALL** implement `check_answer(message_id)` for workers
- **SHALL** implement `get_pending_questions(run_id)` for parents

#### FR-3.2: Message Bus
- **SHALL** use SQLite database (`hub.db`) for message storage
- **SHALL** support concurrent read/write from multiple agents
- **SHALL** maintain backward compatibility with file-based state during transition

#### FR-3.3: Status Visibility
- **SHALL** provide Terminal TUI showing pending questions
- **SHALL** display running cost totals
- **SHALL** show active agent status

### 3.4 Budget Layer

#### FR-4.1: Cost Tracking
- **SHALL** track Local (compute) vs Cloud (API dollars) separately
- **SHALL** log tokens, model, and cost per call
- **SHALL** persist cost data across sessions

#### FR-4.2: Pre-Flight Checks
- **SHALL** estimate cost before execution
- **SHALL** halt if estimated cost exceeds session limit
- **SHALL** allow explicit override for budget exceptions

#### FR-4.3: Limits
- **SHALL** support configurable session limits
- **SHALL** support configurable daily limits
- **SHALL** alert when approaching limits

### 3.5 Environment Layer

#### FR-5.1: Environment Detection
- **SHALL** detect Claude CLI via `CLAUDE_SESSION_ID` environment variable
- **SHALL** detect Cursor via `CURSOR_SESSION` or `.cursor/` directory
- **SHALL** detect Anti-Gravity via `ANTIGRAVITY_SESSION` environment variable

#### FR-5.2: Environment Adapters
- **SHALL** implement `ClaudeCLIAdapter` with direct output
- **SHALL** implement `CursorAdapter` with `cursor-agent chat` trigger
- **SHALL** implement `AntigravityAdapter` with file-based handoff (best effort)

#### FR-5.3: Config Generation
- **SHALL** generate MCP config for each environment from single source
- **SHALL** support `~/.claude/mcp.json`, `~/.cursor/mcp.json`, `~/.antigravity/mcp.json`

### 3.6 Reliability Layer

#### FR-6.1: Circuit Breakers
- **SHALL** integrate with existing 9 halt conditions in `watchdog.py`
- **SHALL** extend circuit breakers to cover new SQLite and Router components
- **SHALL** create `ERIK_HALT.md` with context on any halt

#### FR-6.2: Graceful Degradation
- **SHALL** auto-escalate to Gemini Flash when local inference unavailable
- **SHALL** notify user of "Low Power Mode" when degraded
- **SHALL** handle Ollama crash, GPU overheat, battery mode

#### FR-6.3: Memory Management
- **SHALL** unload idle models via `keep_alive: 0`
- **SHALL** support auto-quantization option for memory-constrained environments

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Requirement | Target |
|-------------|--------|
| Time to First Token (warm) | < 500ms |
| MCP tool call latency | < 100ms |
| Polling responsiveness | 1-10s adaptive |
| Message delivery latency | < 5s |

### 4.2 Reliability

| Requirement | Target |
|-------------|--------|
| Task completion rate | > 95% |
| Human escalation rate | < 20% |
| Uptime during session | > 99% |
| Data loss on crash | Zero (atomic writes) |

### 4.3 Cost

| Requirement | Target |
|-------------|--------|
| Local task handling | > 90% |
| Daily cloud spend | < $5 |
| Cost visibility | 100% of calls logged |

### 4.4 Compatibility

| Requirement | Target |
|-------------|--------|
| Python version | 3.11+ |
| Node.js version | 18+ |
| Ollama version | Latest stable |
| Environments | Claude CLI, Cursor, Anti-Gravity |

### 4.5 Security

- **SHALL NOT** log API keys or secrets
- **SHALL** use atomic writes for all state files
- **SHALL** validate all file paths to prevent traversal
- **SHALL** sandbox draft edits in `_handoff/drafts/`

---

## 5. System Architecture

### 5.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATING AGENTS                          │
│                                                                  │
│    Claude CLI          Cursor IDE          Anti-Gravity         │
│        │                   │                    │                │
│        └───────────────────┼────────────────────┘                │
│                            │                                     │
│                     Environment Adapter                          │
│                   (detect + trigger + notify)                    │
│                            │                                     │
├────────────────────────────┼─────────────────────────────────────┤
│                      MCP LAYER                                   │
│                            │                                     │
│   ┌────────────────────────┼────────────────────────┐           │
│   │                        │                        │           │
│   ▼                        ▼                        ▼           │
│ agent-hub-mcp      mcp-server-subagent        ollama-mcp        │
│ (hub + budget)     (bi-directional msg)       (local models)    │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                    ROUTING LAYER                                 │
│                                                                  │
│              MCP-to-LiteLLM Bridge (Python)                      │
│              using litellm library for fallbacks                 │
│                            │                                     │
│         ┌──────────────────┼──────────────────┐                 │
│         ▼                  ▼                  ▼                 │
│      Ollama             Gemini            Claude                │
│      (free)             (cheap)           (premium)             │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Data Flow

```
1. User gives task to Orchestrating Agent (any environment)
           │
           ▼
2. Environment Adapter detects context, normalizes request
           │
           ▼
3. MCP Layer receives tool call
           │
           ▼
4. Router estimates cost, selects model tier
           │
           ▼
5. Worker executes task
           │
           ├─── Success ──→ Return result
           │
           ├─── Needs clarification ──→ ask_parent() ──→ Wait for reply
           │
           └─── Failure ──→ Fallback to next tier ──→ Retry
```

### 5.3 State Management

| State | Storage | Access Pattern |
|-------|---------|----------------|
| Messages | SQLite (`hub.db`) | Concurrent read/write |
| Contracts | JSON files | Single writer, multiple readers |
| Audit log | NDJSON (`audit.ndjson`) | Append-only |
| Config | YAML | Read on startup |
| Budget | JSON | Read/write per call |

---

## 6. Model Tiers

### 6.1 Tier Configuration

| Tier | Models | Cost | Use Cases |
|------|--------|------|-----------|
| **Tier 1 (Free)** | Llama 3.2:1B | $0 | Triage, Classification |
| | DeepSeek-R1-Distill-Qwen-32B | $0 | Code Review, Reasoning |
| | Qwen2.5-Coder:14B | $0 | Implementation |
| **Tier 2 (Cheap)** | Gemini 3 Flash | ~$0.10/M | Medium complexity, Fallback |
| **Tier 3 (Premium)** | Claude Sonnet 4 | ~$3/M | Judge, Architecture |
| | Gemini 2.0 Pro | ~$1/M | Large context tasks |

### 6.2 Routing Rules

| Task Type | Simple | Medium | Complex |
|-----------|--------|--------|---------|
| Triage | Tier 1 | Tier 1 | Tier 1 |
| Implementation | Tier 1 | Tier 1 | Tier 2 |
| Review | Tier 1 | Tier 2 | Tier 3 |
| Judge | Tier 2 | Tier 3 | Tier 3 |

---

## 7. API Specifications

### 7.1 Bi-Directional Messaging

#### `ask_parent(question: str, context?: object) -> message_id: str`
Worker asks parent for clarification. Returns message ID for polling.

#### `reply_to_worker(message_id: str, answer: str) -> void`
Parent provides answer to worker's question.

#### `check_answer(message_id: str) -> answer: str | null`
Worker checks if answer is available. Returns null if pending.

#### `get_pending_questions(run_id?: str) -> Question[]`
Parent retrieves all unanswered questions, optionally filtered by run.

### 7.2 Routing

#### `route(task_type: str, complexity: str, input_tokens: int) -> ModelSelection`
Returns selected model with fallback chain.

#### `execute_with_fallback(selection: ModelSelection, prompt: str) -> Response`
Executes request with automatic fallback on failure.

### 7.3 Budget

#### `estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float`
Returns estimated cost in USD.

#### `can_afford(estimated_cost: float) -> bool`
Returns whether session budget allows execution.

#### `record_cost(model: str, tokens: int, cost: float, is_local: bool) -> void`
Records actual cost after execution.

---

## 8. Configuration Schema

### 8.1 Routing Configuration (`config/routing.yaml`)

```yaml
model_tiers:
  local:
    models:
      - ollama/qwen2.5-coder:14b
      - ollama/deepseek-r1-distill:32b
      - ollama/llama3.2:1b
    cost_per_1k_tokens: 0.0
    max_retries: 2
    timeout_ms: 120000

  cheap:
    models:
      - gemini/gemini-3-flash
    cost_per_1k_tokens: 0.0001
    max_retries: 1
    timeout_ms: 60000

  premium:
    models:
      - anthropic/claude-sonnet-4
      - gemini/gemini-2-pro
    cost_per_1k_tokens: 0.003
    max_retries: 1
    timeout_ms: 120000

task_routing:
  triage:
    simple: local
    medium: local
    complex: local
  implementation:
    simple: local
    medium: local
    complex: cheap
  review:
    simple: local
    medium: cheap
    complex: premium
  judge:
    simple: cheap
    medium: premium
    complex: premium

fallback_enabled: true
cooldown_seconds: 300
```

### 8.2 Budget Configuration (`config/budget.yaml`)

```yaml
limits:
  session_usd: 5.0
  daily_usd: 10.0

tracking:
  log_file: audit.ndjson
  persist_file: budget_state.json

alerts:
  warn_at_percent: 80
  halt_at_percent: 100

enforcement:
  pre_flight_check: true
  allow_override: true
```

### 8.3 Environment Configuration (`config/environments.yaml`)

```yaml
claude_cli:
  detection:
    env_var: CLAUDE_SESSION_ID
  trigger: null  # Already in session
  mcp_config: ~/.claude/mcp.json

cursor:
  detection:
    env_var: CURSOR_SESSION
    fallback_path: .cursor/
  trigger: cursor-agent chat "{prompt}"
  mcp_config: ~/.cursor/mcp.json

antigravity:
  detection:
    env_var: ANTIGRAVITY_SESSION
  trigger: null  # File-based handoff
  handoff_dir: _handoff/
  mcp_config: ~/.antigravity/mcp.json
```

---

## 9. Testing Requirements

### 9.1 Unit Tests

- [ ] Ollama HTTP client connection pooling
- [ ] Router tier selection logic
- [ ] Fallback chain execution
- [ ] Budget estimation accuracy
- [ ] SQLite message bus CRUD operations
- [ ] Environment detection logic

### 9.2 Integration Tests

- [ ] MCP tool call round-trip latency
- [ ] Bi-directional message flow (ask → reply → receive)
- [ ] Fallback triggers on model failure
- [ ] Budget halt on limit exceeded
- [ ] Legacy file adapter compatibility

### 9.3 End-to-End Tests

- [ ] Full workflow: Super Manager → Floor Manager → Worker → Judge
- [ ] Cross-environment: Same agent definition in CLI, Cursor, Anti-Gravity
- [ ] Graceful degradation: Local failure → Cloud escalation
- [ ] Circuit breaker: All 9 halt conditions

### 9.4 Performance Tests

- [ ] TTFT benchmark (warm model): Target < 500ms
- [ ] MCP tool call latency: Target < 100ms
- [ ] Concurrent agent message handling
- [ ] Memory usage under load

---

## 10. Rollout Plan

### Phase 0: Foundation (Immediate)
- Create reference vault
- Archive old documents
- Define config schemas
- Establish feature flags

### Phase 1: Performance (Week 1-2)
- Ollama HTTP client
- Persistent MCP connections
- Adaptive polling
- Basic cost logging

### Phase 2: Routing & Environments (Week 3-4)
- Model shootout
- MCP-to-LiteLLM bridge
- Environment adapters
- Config generator

### Phase 3: Communication (Week 5-6)
- SQLite message bus
- Bi-directional protocol
- Terminal TUI

### Phase 4: Budget (Week 7)
- Budget manager
- Pre-flight checks
- Cost dashboard

### Phase 5: Hardening (Week 8)
- Circuit breaker integration
- Graceful degradation
- Audit logging
- E2E testing

### Phase 6: Stabilization (Week 9)
- Documentation
- Performance benchmarking
- Final polish

### Phase 7: Knowledge Brain (Week 10-11)
- Librarian MCP server
- Knowledge graph queries
- Semantic search integration
- Agent hub integration

---

## 10.1 Phase 7 Requirements: Knowledge Brain

### FR-7.1: Librarian MCP Server
- **SHALL** create new MCP server (`librarian-mcp/`) wrapping existing knowledge infrastructure
- **SHALL** use existing `project-tracker/data/tracker.db` for project metadata
- **SHALL** use existing `project-tracker/data/graph.json` for knowledge graph (2,150 nodes, 7,165 edges)
- **SHALL** be lightweight Python server using `mcp` library

### FR-7.2: Core Knowledge Tools
- **SHALL** implement `search_knowledge(query, limit)` for semantic search across docs
- **SHALL** implement `get_project_info(project_name)` for project metadata lookup
- **SHALL** implement `find_related_docs(doc_path, depth)` for graph traversal via wiki-links
- **SHALL** implement `ask_librarian(question)` for natural language queries

### FR-7.3: Graph Query Tools
- **SHALL** implement `get_hub_nodes(limit)` for most connected documents
- **SHALL** implement `get_orphans()` for documents with no incoming links
- **SHALL** implement `get_bridge_docs()` for critical cross-project references

### FR-7.4: Integration
- **SHALL** add `librarian-mcp` to default MCP configuration
- **SHALL** enable workers to auto-query librarian before falling back to grep/glob
- **SHALL** cache frequent queries in SQLite (TTL: 1 hour)
- **SHOULD** support local embeddings via Ollama (`nomic-embed-text`)

### Phase 7 Success Criteria
| Metric | Target |
|--------|--------|
| Knowledge query latency (cached) | < 200ms |
| Knowledge query latency (cold) | < 2s |
| Grep/glob reduction for context tasks | > 80% |

---

## 11. Dependencies

### 11.1 External Libraries

| Library | Purpose | Version |
|---------|---------|---------|
| `litellm` | Provider abstraction, fallbacks | Latest |
| `httpx` | HTTP client with connection pooling | Latest |
| `rich` | Terminal TUI | Latest |
| `pyyaml` | Config parsing | Latest |

### 11.2 External Services

| Service | Purpose | Required |
|---------|---------|----------|
| Ollama | Local model inference | Yes |
| Gemini API | Tier 2 fallback | Yes |
| Anthropic API | Tier 3 / Judge | Yes |

### 11.3 Internal Dependencies

| Component | Depends On |
|-----------|------------|
| Router | Ollama HTTP Client, litellm |
| Message Bus | SQLite |
| Budget Manager | Cost logging |
| Environment Adapters | Config schema |
| Circuit Breakers | watchdog.py |
| Librarian MCP | project-tracker/tracker.db, graph.json |

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing workflows | Medium | High | Feature flags, legacy adapters, phased rollout |
| Local model quality insufficient | Medium | Medium | Fallback chains, Model Shootout validation |
| Memory pressure on 32B models | High | Medium | `keep_alive: 0` unloading, auto-quantization |
| Timeline slippage | Medium | Low | Phase 6 buffer, scope cuts if needed |
| Cursor becomes paywalled | Low | Medium | Anti-Gravity as documented fallback |
| Embeddings stale/incomplete | Medium | Low | Keyword fallback, incremental update pipeline |
| Graph.json too large for memory | Low | Medium | Lazy loading, SQLite mirror for queries |

---

## 13. Open Questions

1. **Floor Manager Model:** Can Qwen2.5-Coder:32B replace Gemini for Floor Manager duties? To be determined in Phase 2 Model Shootout.

2. **Anti-Gravity Polling:** What's the optimal polling interval for file-based handoff? Need to balance responsiveness vs. CPU usage.

3. **Budget Override UX:** How should explicit budget override work? CLI flag? Interactive prompt? Config setting?

---

## 14. Glossary

| Term | Definition |
|------|------------|
| **TTFT** | Time to First Token — latency until first response token |
| **MCP** | Model Context Protocol — standardized agent-tool communication |
| **Tier** | Model cost category (Free/Cheap/Premium) |
| **Fallback Chain** | Ordered list of models to try on failure |
| **Circuit Breaker** | Automatic halt condition to prevent runaway agents |
| **Cooldown** | Temporary disabling of failing model |

---

## 15. Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Author | Claude Code (Opus 4.5) | 2026-01-18 | Complete |
| Architect | Erik Sjaastad | | Pending |

---

*This PRD covers 11 weeks: Phases 0-6 (core system) + Phase 7 (knowledge brain).*

*Engage.*

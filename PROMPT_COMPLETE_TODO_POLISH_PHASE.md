# Prompt: Complete TODO Polish Phase

> **Context:** MCP migration and Librarian Adaptive Memory core implementation are complete. This prompt covers the remaining validation and polish tasks.
> **Assignee:** Floor Manager or appropriate specialist
> **Created:** 2026-01-22

---

## Overview

The Unified Agent System and Librarian MCP are fully functional. This phase focuses on performance validation, threshold tuning, and documentation polish.

**Reference:** See `TODO.md` for current task list.

---

## Phase 4: Librarian Validation & Polish

### Task 1: Benchmark Performance

**Goal:** Quantify the performance gains from adaptive memory caching.

**Steps:**

1. **Create benchmark script** - `librarian-mcp/benchmarks/memory_performance.py`:
   ```python
   import time
   from librarian_mcp.memory import LibrarianMemory
   from librarian_mcp.nlq import answer_question
   
   def benchmark_cached_vs_computed():
       memory = LibrarianMemory()
       
       # First run (cold)
       start = time.time()
       answer = answer_question("How does the agent hub work?")
       cold_time = time.time() - start
       
       # Second run (warm - should hit cache)
       start = time.time()
       answer = answer_question("How does the agent hub work?")
       warm_time = time.time() - start
       
       print(f"Cold query: {cold_time:.3f}s")
       print(f"Warm query: {warm_time:.3f}s")
       print(f"Speedup: {cold_time / warm_time:.1f}x")
       
       # Test similar query (should also hit cache)
       start = time.time()
       answer = answer_question("Explain agent hub functionality")
       similar_time = time.time() - start
       print(f"Similar query: {similar_time:.3f}s")
   ```

2. **Run benchmark** - Execute and record results:
   ```bash
   cd /Users/eriksjaastad/projects/_tools/librarian-mcp
   uv run python benchmarks/memory_performance.py
   ```

3. **Document results** - Add findings to `librarian-mcp/README.md` or create `BENCHMARK_RESULTS.md`.

**Expected outcome:** Cache hits should be 5-10x faster than cold queries.

---

### Task 2: Tune Similarity Threshold

**Current state:** `SIMILARITY_THRESHOLD = 0.15` in `memory.py`

**Goal:** Find optimal threshold that balances recall (hit rate) vs precision (answer quality).

**Steps:**

1. **Collect test queries** - Create `librarian-mcp/tests/test_queries.json`:
   ```json
   [
     {"query": "How does agent hub work?", "similar": ["Explain agent hub", "What is agent hub"]},
     {"query": "Where is authentication handled?", "similar": ["Auth logic location", "Find auth code"]},
     {"query": "MCP server setup", "similar": ["Configure MCP", "MCP installation"]}
   ]
   ```

2. **Test different thresholds** - Script to compare 0.10, 0.15, 0.20:
   ```python
   for threshold in [0.10, 0.15, 0.20]:
       memory.similarity_threshold = threshold
       # Test hit rate for similar queries
       # Measure false positives
   ```

3. **Adjust based on results** - If threshold is too low (false positives), increase it. If too high (missing valid hits), decrease it.

**Acceptance criteria:** 
- Similar queries (cosine similarity > 0.85) should hit cache
- Unrelated queries (cosine similarity < 0.70) should miss

---

### Task 3: Documentation

**Goal:** Add usage examples for the feedback API.

**File:** `librarian-mcp/README.md` or create `docs/ADAPTIVE_MEMORY.md`

**Content to add:**

```markdown
## Adaptive Memory Usage

### Providing Feedback

The librarian learns from your feedback. After using `ask_librarian`:

**Mark helpful answers:**
```json
{
  "name": "librarian_feedback",
  "arguments": {
    "query": "How does agent hub work?",
    "helpful": true
  }
}
```

**Mark unhelpful answers:**
```json
{
  "name": "librarian_feedback",
  "arguments": {
    "query": "Where is X implemented?",
    "helpful": false
  }
}
```

**Effects:**
- Helpful answers: Confidence increases, cache priority upgraded (warm → hot)
- Unhelpful answers: Confidence decreases, may be evicted from cache

### Memory Management

**View memory stats:**
```json
{"name": "librarian_memory_stats"}
```

**Force caching (for frequently asked questions):**
```json
{
  "name": "librarian_remember",
  "arguments": {
    "question": "What is the Agent Hub?",
    "answer": "The Agent Hub is...",
    "tier": "hot"
  }
}
```

**Clear bad cache entries:**
```json
{
  "name": "librarian_forget",
  "arguments": {"query": "outdated question"}
}
```
```

---

### Task 4: Code Review

**Goal:** Final audit for production readiness.

**Checklist:**

- [ ] **Dependency management** - Verify `pyproject.toml` pins stable versions
- [ ] **Database schema** - Check `memory.db` schema matches code
- [ ] **Error handling** - All DB operations have try/catch
- [ ] **Logging** - Appropriate log levels (DEBUG for cache hits, WARNING for evictions)
- [ ] **Thread safety** - Verify sqlite connection handling is safe
- [ ] **Security** - No SQL injection vectors in user queries
- [ ] **Performance** - Embedding computation is cached appropriately

**Files to review:**
- `src/librarian_mcp/memory.py`
- `src/librarian_mcp/memory_db.py`
- `src/librarian_mcp/nlq.py`
- `pyproject.toml`

---

## System Maintenance Tasks

### Monitor transition.ndjson

**File:** `agent-hub/_handoff/transition.ndjson`

**Goal:** Ensure state machine transitions remain valid under load.

**Check:**
```bash
cd /Users/eriksjaastad/projects/_tools/agent-hub
tail -100 _handoff/transition.ndjson | jq '.state'
```

**Red flags:**
- Invalid state transitions (e.g., `reviewing` → `erik_consultation` without error)
- High frequency of `stalled` states
- Repeated transitions without progress (loops)

**Action:** If issues found, review `src/watchdog.py` state machine logic.

---

### Audit Memory Growth

**File:** `librarian-mcp/data/memory.db`

**Goal:** Verify eviction logic works at MAX_CACHED limit (100 entries).

**Steps:**

1. **Check current cache size:**
   ```bash
   sqlite3 ~/projects/project-tracker/data/memory.db "SELECT COUNT(*) FROM cached_answers;"
   ```

2. **Test eviction** - Generate 105 queries to force eviction:
   ```python
   for i in range(105):
       ask_librarian(f"Test query {i}")
   ```

3. **Verify limit** - Cache should remain at 100 entries:
   ```bash
   sqlite3 ~/projects/project-tracker/data/memory.db "SELECT COUNT(*) FROM cached_answers;"
   ```

4. **Check eviction order** - Lowest tier + oldest should be evicted first:
   ```sql
   SELECT tier, confidence, cached_at 
   FROM cached_answers 
   ORDER BY 
     CASE tier WHEN 'hot' THEN 3 WHEN 'warm' THEN 2 ELSE 1 END ASC,
     confidence ASC,
     cached_at ASC 
   LIMIT 10;
   ```

**Expected:** Cold tier, low confidence entries evicted first.

---

### Sync skill.json

**Files:**
- `agent-hub/skill.json`
- `agent-hub/registry-entry.json`

**Goal:** Version numbers and configurations match latest builds.

**Check:**

1. **Versions match commits:**
   ```bash
   cd /Users/eriksjaastad/projects/_tools
   git log --oneline -1  # Should match version in skill.json
   ```

2. **Tool lists are current:**
   - Verify `ollama_list_models` is listed
   - Verify all librarian tools are listed
   - Remove any deprecated tool references

3. **Environment variables documented:**
   - `HUB_SERVER_PATH`
   - `MCP_SERVER_PATH`
   - `SANDBOX_ROOT`

---

## Definition of Done

- [ ] Benchmark results documented (cache speedup measured)
- [ ] Similarity threshold tuned and tested
- [ ] Adaptive memory documentation added to README
- [ ] Code review checklist completed
- [ ] No invalid state transitions in last 100 entries
- [ ] Cache eviction tested and working at limit
- [ ] `skill.json` versions synced with git commits

---

## Optional Enhancements

If time permits:

- **Embedding model upgrade** - Test sentence-transformers instead of simple averaging
- **Query expansion** - Automatically expand queries with synonyms before searching
- **Confidence visualization** - Add dashboard showing cache confidence distribution
- **Memory persistence** - Add backup/restore for memory.db

---

## Notes

- These tasks are **polish, not blockers**. The system is fully functional.
- Prioritize based on actual pain points observed in production use.
- If no issues arise, these can remain as "nice to haves."

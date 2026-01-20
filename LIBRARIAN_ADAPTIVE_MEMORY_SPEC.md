# Librarian Adaptive Memory - Technical Specification

**Author:** Claude Code Web (Opus 4.5)
**Date:** 2026-01-19
**Status:** IMPLEMENTED
**Version:** 0.1

---

## 1. Overview

### 1.1 Purpose

Transform librarian-mcp from a stateless query engine into an adaptive system that learns from usage patterns. Frequently asked questions should become instant answers.

### 1.2 Goals

| Goal | Metric | Target |
|------|--------|--------|
| Cache hit rate | % of queries served from memory | >50% after 1 week of use |
| Latency improvement | Hot query response time | <50ms (vs ~500ms computed) |
| Semantic coverage | Similar questions hitting same cache | >80% recall at 0.85 similarity |
| Memory efficiency | Storage overhead per cached answer | <10KB average |

### 1.3 Non-Goals

- General-purpose RAG system
- External knowledge retrieval (web search)
- Multi-tenant/multi-user isolation
- Real-time knowledge graph updates

---

## 2. Architecture

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      librarian-mcp                               │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │   MCP        │    │   Memory     │    │   Knowledge      │  │
│  │   Server     │───▶│   Layer      │───▶│   Layer          │  │
│  │              │    │   (NEW)      │    │   (existing)     │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│         │                   │                     │             │
│         │                   │                     │             │
│         ▼                   ▼                     ▼             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │   stdio      │    │   ChromaDB   │    │   tracker.db     │  │
│  │   transport  │    │   + SQLite   │    │   + graph.json   │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│                             │                                   │
│                             ▼                                   │
│                      ┌──────────────┐                          │
│                      │   Ollama     │                          │
│                      │   (embeddings│                          │
│                      │   + judgment)│                          │
│                      └──────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 New Components

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| EmbeddingService | Generate query embeddings | Ollama + nomic-embed-text |
| MemoryStore | Persist and search cached answers | ChromaDB |
| QueryTracker | Track frequency, recency, compute cost | SQLite |
| CachePolicy | Decide what to cache and when to evict | Rule-based + optional ML |
| JudgmentModel | Evaluate answer quality for caching | Ollama + small LLM (optional) |

---

## 3. Data Model

### 3.1 Query Memory Table (SQLite)

```sql
CREATE TABLE query_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identity
    query_hash TEXT UNIQUE NOT NULL,      -- SHA256 of normalized query
    query_text TEXT NOT NULL,             -- Original question
    embedding_id TEXT,                    -- Reference to ChromaDB document

    -- Cached Response
    answer TEXT,                          -- The cached answer
    answer_version INTEGER DEFAULT 1,     -- Increment on answer update

    -- Statistics
    ask_count INTEGER DEFAULT 1,
    first_asked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_asked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Performance
    compute_time_ms INTEGER,              -- How long to compute fresh
    cache_hits INTEGER DEFAULT 0,         -- Times served from cache

    -- Quality
    confidence REAL,                      -- 0.0 - 1.0, how good is this answer?
    feedback_positive INTEGER DEFAULT 0,  -- User upvotes
    feedback_negative INTEGER DEFAULT 0,  -- User downvotes

    -- Cache Management
    tier TEXT DEFAULT 'cold',             -- cold, warm, hot, core
    pinned BOOLEAN DEFAULT FALSE,         -- Never evict
    expires_at TIMESTAMP                  -- Optional TTL
);

-- Indexes for common access patterns
CREATE INDEX idx_query_hash ON query_memory(query_hash);
CREATE INDEX idx_tier ON query_memory(tier);
CREATE INDEX idx_ask_count ON query_memory(ask_count DESC);
CREATE INDEX idx_last_asked ON query_memory(last_asked DESC);
```

### 3.2 ChromaDB Collection Schema

```python
collection = chroma_client.create_collection(
    name="query_embeddings",
    metadata={"hnsw:space": "cosine"}  # Cosine similarity
)

# Document structure:
{
    "id": "uuid",
    "embedding": [0.1, 0.2, ...],      # 768-dim for nomic-embed-text
    "metadata": {
        "query_hash": "sha256...",
        "query_text": "where is auth?",
        "tier": "hot"
    }
}
```

---

## 4. Query Flow

### 4.1 Sequence Diagram

```
Client          Server          MemoryLayer       KnowledgeLayer      Ollama
   │                │                │                  │                │
   │─── query ─────▶│                │                  │                │
   │                │                │                  │                │
   │                │── embed ──────▶│                  │                │
   │                │                │──── embed() ────────────────────▶│
   │                │                │◀─── vector ─────────────────────│
   │                │                │                  │                │
   │                │── L1 check ───▶│                  │                │
   │                │◀── miss ──────│                  │                │
   │                │                │                  │                │
   │                │── L2 search ──▶│                  │                │
   │                │◀── miss ──────│                  │                │
   │                │                │                  │                │
   │                │── compute ────────────────────────▶│                │
   │                │◀── answer ───────────────────────│                │
   │                │                │                  │                │
   │                │── record ─────▶│                  │                │
   │                │                │ (update stats)   │                │
   │                │                │                  │                │
   │◀── response ──│                │                  │                │
```

### 4.2 Cache Lookup Algorithm

```python
def lookup(query: str) -> Optional[CachedAnswer]:
    # 1. Normalize query
    normalized = normalize(query)  # lowercase, strip, collapse whitespace
    query_hash = sha256(normalized)

    # 2. L1: Exact match (O(1))
    if exact := db.get_by_hash(query_hash):
        exact.cache_hits += 1
        exact.last_asked = now()
        return exact.answer

    # 3. L2: Semantic match (O(log n) with HNSW)
    embedding = ollama.embed(query, model="nomic-embed-text")
    similar = chroma.query(embedding, n_results=3, where={"tier": {"$ne": "cold"}})

    for match in similar:
        if match.distance < SIMILARITY_THRESHOLD:  # 0.15 = 85% similar
            original = db.get_by_hash(match.metadata["query_hash"])
            original.cache_hits += 1
            return original.answer

    # 4. Cache miss
    return None
```

### 4.3 Cache Decision Algorithm

```python
def should_cache(query: str, answer: str, compute_time_ms: int) -> bool:
    stats = db.get_stats(query)

    # Rule 1: Frequency threshold
    if stats.ask_count >= CACHE_THRESHOLD:  # Default: 3
        return True

    # Rule 2: Expensive computation
    if compute_time_ms > EXPENSIVE_THRESHOLD:  # Default: 500ms
        return stats.ask_count >= 2  # Lower threshold for expensive queries

    # Rule 3: High confidence answer
    if stats.confidence and stats.confidence > 0.9:
        return True

    return False
```

---

## 5. Tier System

### 5.1 Tier Definitions

| Tier | Ask Count | Behavior | Eviction Priority |
|------|-----------|----------|-------------------|
| `cold` | 1 | Track but don't cache answer | N/A (not cached) |
| `warm` | 2-3 | Cache if expensive | High (evict first) |
| `hot` | 4-9 | Always cached | Medium |
| `core` | 10+ | Pre-computed, never evict | Low (only if pinned=false) |

### 5.2 Tier Transitions

```python
def update_tier(query_hash: str):
    stats = db.get_stats(query_hash)

    if stats.ask_count >= 10:
        new_tier = "core"
    elif stats.ask_count >= 4:
        new_tier = "hot"
    elif stats.ask_count >= 2:
        new_tier = "warm"
    else:
        new_tier = "cold"

    if new_tier != stats.tier:
        db.update_tier(query_hash, new_tier)

        # Promote to ChromaDB if entering warm+
        if new_tier in ("warm", "hot", "core") and not stats.embedding_id:
            embedding = ollama.embed(stats.query_text)
            chroma.add(id=uuid(), embedding=embedding, metadata={...})
```

---

## 6. Eviction Policy

### 6.1 When to Evict

- Total cached answers > MAX_CACHED (default: 10,000)
- Memory pressure detected
- Manual cleanup triggered

### 6.2 Eviction Algorithm

```python
def evict(count: int):
    # LRU within tier, lowest tier first
    candidates = db.query("""
        SELECT * FROM query_memory
        WHERE pinned = FALSE AND answer IS NOT NULL
        ORDER BY
            CASE tier
                WHEN 'warm' THEN 1
                WHEN 'hot' THEN 2
                WHEN 'core' THEN 3
            END,
            last_asked ASC
        LIMIT ?
    """, count)

    for c in candidates:
        chroma.delete(c.embedding_id)
        db.clear_answer(c.query_hash)
```

---

## 7. Embedding Model

### 7.1 Model Selection

| Model | Dimensions | Speed | Quality | Recommended |
|-------|------------|-------|---------|-------------|
| nomic-embed-text | 768 | Fast | Good | **Yes** |
| mxbai-embed-large | 1024 | Medium | Better | For accuracy |
| all-minilm | 384 | Fastest | Acceptable | For resource-constrained |

### 7.2 Similarity Threshold

Based on cosine distance (0 = identical, 2 = opposite):

| Distance | Interpretation | Action |
|----------|---------------|--------|
| < 0.10 | Nearly identical | Definite cache hit |
| 0.10 - 0.15 | Very similar | Likely cache hit |
| 0.15 - 0.25 | Related | Consider as hit with lower confidence |
| > 0.25 | Different | Cache miss |

**Recommended threshold:** 0.15 (85% similarity)

---

## 8. Configuration

### 8.1 Environment Variables

```bash
# Memory Layer
LIBRARIAN_MEMORY_ENABLED=true
LIBRARIAN_MEMORY_DB_PATH=~/.librarian/memory.db
LIBRARIAN_CHROMA_PATH=~/.librarian/chroma

# Thresholds
LIBRARIAN_CACHE_THRESHOLD=3           # Ask count to cache
LIBRARIAN_EXPENSIVE_THRESHOLD_MS=500  # Compute time to lower threshold
LIBRARIAN_SIMILARITY_THRESHOLD=0.15   # Cosine distance for semantic match
LIBRARIAN_MAX_CACHED=10000            # Max cached answers

# Embedding
LIBRARIAN_EMBED_MODEL=nomic-embed-text
OLLAMA_HOST=http://localhost:11434
```

### 8.2 Feature Flags

```yaml
# config/feature_flags.yaml
librarian:
  memory_enabled: true
  semantic_search: true
  auto_tier_promotion: true
  judgment_model: false  # Optional: use LLM to evaluate answer quality
```

---

## 9. API Changes

### 9.1 New MCP Tools

```python
# Force cache a specific answer
@tool("librarian_remember")
def remember(query: str, answer: str, pin: bool = False) -> dict:
    """Manually cache an answer."""

# Forget a cached answer
@tool("librarian_forget")
def forget(query: str) -> dict:
    """Remove a query from memory."""

# Get memory statistics
@tool("librarian_memory_stats")
def memory_stats() -> dict:
    """Return cache statistics: hit rate, tier distribution, etc."""

# Feedback on answer quality
@tool("librarian_feedback")
def feedback(query: str, helpful: bool) -> dict:
    """User feedback to adjust confidence."""
```

### 9.2 Modified Existing Tools

```python
# ask_librarian now includes cache metadata in response
{
    "answer": "Authentication is handled in...",
    "cached": true,
    "cache_tier": "hot",
    "ask_count": 7,
    "confidence": 0.92
}
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

- `test_embedding_service.py` - Embedding generation
- `test_memory_store.py` - ChromaDB operations
- `test_query_tracker.py` - SQLite CRUD
- `test_cache_policy.py` - Caching decisions
- `test_tier_transitions.py` - Tier promotion/demotion

### 10.2 Integration Tests

- Cache hit/miss flow end-to-end
- Semantic similarity matching
- Tier promotion after repeated queries
- Eviction under memory pressure

### 10.3 Benchmarks

- Latency: cached vs computed
- Throughput: queries per second
- Memory: overhead per cached answer
- Recall: semantic match accuracy

---

## 11. Migration Path

### Phase 1: Foundation (Week 1)

- [ ] Add ChromaDB dependency
- [ ] Create memory.db schema
- [ ] Implement EmbeddingService
- [ ] Implement QueryTracker

### Phase 2: Core Logic (Week 1-2)

- [ ] Implement cache lookup (L1 + L2)
- [ ] Implement cache decision
- [ ] Implement tier system
- [ ] Wire into existing query flow

### Phase 3: Polish (Week 2)

- [ ] Add new MCP tools
- [ ] Add configuration
- [ ] Add feature flags
- [ ] Write tests

### Phase 4: Validation (Week 3)

- [ ] Benchmark performance
- [ ] Tune thresholds
- [ ] Documentation
- [ ] Code review

---

## 12. Open Questions

### 1. Staleness
How do we invalidate cached answers when the underlying knowledge changes?

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| A: TTL-based expiration | Simple, predictable | May serve stale data, may evict still-valid data | Good default (24h TTL) |
| B: Dependency tracking | Precise invalidation | Complex to implement, requires file watchers | Phase 2 enhancement |
| C: Manual invalidation | Full control | Requires human intervention | Always available as escape hatch |

**Suggested approach:** Start with TTL (Option A), add dependency tracking later if staleness becomes a problem.

### 2. Multi-query patterns
Should we cache intermediate results for complex queries?

**Analysis:** Complex queries often decompose into sub-queries (e.g., "find all auth files and summarize" = find + summarize). Caching the "find" result could speed up variations. However, this adds complexity and storage overhead.

**Suggested approach:** Defer. Cache final answers only for v1. Revisit if profiling shows repeated expensive sub-queries.

### 3. Judgment model
Is an LLM-based quality evaluator worth the overhead?

**Analysis:** A small local model (qwen2.5:0.5b) could evaluate "is this answer complete and accurate?" before caching. Adds ~200ms latency but prevents caching bad answers.

**Suggested approach:** Make it optional via feature flag. Off by default. Enable for high-stakes use cases.

### 4. Cold start
How do we pre-warm the cache with likely questions?

**Options:**
- Mine existing chat logs for common questions
- Seed with documentation structure ("what is X?" for each project)
- Let it warm naturally from usage

**Suggested approach:** Natural warming + optional seeding script. Don't over-engineer cold start - the cache will warm quickly with real usage.

---

## 13. References

- [LeCaR: Learning Cache Replacement](https://www.usenix.org/conference/hotstorage18/presentation/vietri)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [nomic-embed-text Model Card](https://huggingface.co/nomic-ai/nomic-embed-text-v1)
- [MemGPT Paper](https://arxiv.org/abs/2310.08560)
- [Generative Agents Paper](https://arxiv.org/abs/2304.03442)

---

*Specification authored by Claude Code Web (Opus 4.5) at Erik's request.*
*This is a design document, not an implementation. Review and adjust before building.*

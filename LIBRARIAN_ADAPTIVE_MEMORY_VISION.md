# Librarian Adaptive Memory - Vision & Analysis

**Author:** Claude Code Web (Opus 4.5)
**Date:** 2026-01-19
**Context:** Analysis of Erik's vision for a learning librarian with adaptive memory

---

## The Core Insight

The Librarian should get smarter the more it's used. Frequently asked questions become instant answers.

```
Query frequency → Memory proximity

Asked once:      "Hmm, might be relevant"     → Compute, maybe note it
Asked 3x:        "People care about this"     → Cache the answer
Asked 10x:       "This is important"          → Pre-compute, instant retrieval
Asked 100x:      "Core knowledge"             → Part of identity
```

Like how a brain works - you don't remember every conversation, but if someone asks you the same thing repeatedly, it becomes instant recall. The Librarian builds its own "muscle memory" for the ecosystem.

---

## What Exists Today

```
librarian-mcp/
├── src/librarian_mcp/
│   ├── db.py          # TrackerDB - project metadata
│   ├── graph.py       # KnowledgeGraph - relationship traversal
│   ├── nlq.py         # Intent routing (keyword matching - placeholder)
│   └── server.py      # MCP server
└── embeddings/        # Empty - waiting for vectors
```

**Current state:** Stateless. Every query is computed fresh. No memory.

---

## What Needs to Be Added

### 1. Query Memory Table

```sql
CREATE TABLE query_memory (
    id INTEGER PRIMARY KEY,
    query_hash TEXT UNIQUE,        -- Semantic hash (embedding vector quantized)
    query_text TEXT,               -- Original question
    answer TEXT,                   -- Cached response
    ask_count INTEGER DEFAULT 1,
    first_asked TIMESTAMP,
    last_asked TIMESTAMP,
    compute_time_ms INTEGER,       -- How expensive was this?
    confidence REAL                -- How good was the answer?
);

CREATE INDEX idx_query_hash ON query_memory(query_hash);
CREATE INDEX idx_ask_count ON query_memory(ask_count DESC);
```

### 2. Semantic Hashing

The key insight: "where is auth?" and "where is authentication handled?" should hit the same cache.

**Options:**
- **Embedding similarity** - Generate embedding, find nearest neighbor in cache. If distance < threshold, it's a hit.
- **Locality-sensitive hashing (LSH)** - Faster but less accurate. Good for L1 cache.
- **Hybrid** - LSH for fast rejection, embeddings for confirmation.

**Local model for embeddings:** `nomic-embed-text` runs on Ollama, 137M params, fast.

### 3. The Memory Wrapper (Local Model)

```
┌─────────────────────────────────────────────────────────────┐
│                    Query comes in                            │
│                         │                                    │
│                         ▼                                    │
│              ┌──────────────────┐                           │
│              │  Embed query     │  (nomic-embed-text)       │
│              └────────┬─────────┘                           │
│                       │                                      │
│                       ▼                                      │
│              ┌──────────────────┐                           │
│              │  Check L1 cache  │  (exact hash match)       │
│              └────────┬─────────┘                           │
│                       │ miss                                 │
│                       ▼                                      │
│              ┌──────────────────┐                           │
│              │  Check L2 cache  │  (semantic similarity)    │
│              └────────┬─────────┘                           │
│                       │ miss                                 │
│                       ▼                                      │
│              ┌──────────────────┐                           │
│              │  Compute fresh   │  (graph + db query)       │
│              └────────┬─────────┘                           │
│                       │                                      │
│                       ▼                                      │
│              ┌──────────────────┐                           │
│              │  Decide: cache?  │  (local model judgment)   │
│              └────────┬─────────┘                           │
│                       │                                      │
│                       ▼                                      │
│                   Return answer                              │
└─────────────────────────────────────────────────────────────┘
```

### 4. Threshold Tuning

Based on research on human memory and caching systems:

| Ask Count | Tier | Behavior |
|-----------|------|----------|
| 1 | Cold | Compute, don't cache |
| 2-3 | Warm | Compute, consider caching if expensive |
| 4-9 | Hot | Cache the answer |
| 10+ | Core | Pre-compute, instant retrieval |

The "expensive" heuristic: If `compute_time_ms > 500`, lower the threshold to cache earlier.

---

## Research Pointers

### Adaptive Caching with Learned Importance

- **LeCaR** (Learning Cache Replacement) - ML-based cache eviction
- **LRB** (Learning Relaxed Belady) - Learned optimal caching
- These are typically for object caching, but the frequency/recency tradeoff applies

### Semantic Similarity Hashing

- **FAISS** (Facebook AI Similarity Search) - Fast nearest neighbor for embeddings
- **Annoy** (Spotify) - Approximate nearest neighbors, memory-mapped
- **ChromaDB** - Vector database, has persistence, runs local

### LLM Memory Patterns

- **MemGPT** - Virtual context management with memory tiers
- **Reflexion** - Self-reflection to decide what to remember
- **Generative Agents** (Stanford) - Memory stream with importance scoring

---

## Suggested Implementation Path

1. **Add embedding generation** - Use `nomic-embed-text` via Ollama
2. **Add ChromaDB** - It handles similarity search and persistence
3. **Add query_memory table** - Track frequency and answers
4. **Wire up the flow** - Embed → search → cache or compute
5. **Add the judgment model** - Small local model decides "should I remember this?"

---

## The Goal

The Librarian gets smarter and faster the more it's used. Persistent memories "within arm's reach."

Not a general-purpose RAG system. Not trying to solve everyone's problems. A learning assistant that knows *your* ecosystem and gets better at answering *your* questions.

---

*Document created by Claude Code Web at Erik's request - preserving the analysis for the team.*

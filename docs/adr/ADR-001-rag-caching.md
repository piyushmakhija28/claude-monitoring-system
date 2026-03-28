# ADR-001: Use Qdrant for RAG Decision Caching

**Status:** Accepted
**Date:** 2026-03-15
**Deciders:** Pipeline Architecture Team

---

## Context

The LangGraph pipeline makes 10-15 LLM API calls per task execution. Many tasks
are semantically similar (e.g., "fix login bug" appears across dozens of sessions).
Re-running identical LLM reasoning for near-duplicate tasks wastes inference budget
and adds 30-90 seconds of latency per run.

We needed a vector similarity store that:
- Works embedded (no separate server to manage in development)
- Supports cosine similarity search with score filtering
- Handles payload filtering (e.g., filter by step, project, session)
- Is fast enough for < 50ms lookup latency on a developer laptop

---

## Decision

Use **Qdrant** (via `qdrant-client` in local path mode) as the vector store for
RAG decision caching across all pipeline nodes.

Every node stores its decision after execution:

```python
rag.store(step="step0", decision={...}, user_prompt="...", context={...})
```

Before every LLM call, the node queries the cache:

```python
cached = rag.lookup(step="step0", query=user_prompt)
if cached:
    return cached["decision"]   # LLM call skipped
```

Four collections are used:

| Collection | Purpose |
|------------|---------|
| `node_decisions` | Per-node decision history (primary RAG cache) |
| `sessions` | Session-level summaries |
| `flow_traces` | Step-level execution data |
| `tool_calls` | Tool call audit trail |

Step-specific confidence thresholds (`STEP_THRESHOLDS` in `rag_integration.py`)
range from 0.75 (low-stakes summary) to 0.90 (final prompt generation).

An orchestration-level cache (`rag_lookup_orchestration` / `rag_store_orchestration`)
operates at threshold 0.85 and, on a hit, skips Steps 0-4 entirely (~5 LLM calls saved).

As of v1.6.1, every stored payload includes a `codebase_hash` (12-char SHA1 of
top-level `.py` file names). Lookups from a different project receive a ×0.65
score penalty, preventing cross-project false positives.

---

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **ChromaDB** | Simple API, good Python SDK | Slower cosine search; no payload filtering |
| **FAISS** | Extremely fast | No persistence; no metadata filtering; index management overhead |
| **Pinecone** | Managed, scalable | Paid service; network latency; adds external dependency |
| **Redis (RediSearch)** | Fast; already used for caching | Requires Redis server; vector search is an add-on module |
| **SQLite FTS + cosine** | Zero dependency | Slow for vectors; manual embedding management |

Qdrant was chosen because it is the only option that satisfies all four requirements
(embedded mode, cosine similarity, payload filtering, low latency) without requiring
a separate infrastructure component.

---

## Consequences

**Positive:**
- Saves 5-15 LLM calls per session on repeated tasks (measured: ~40% hit rate after
  10 runs of similar tasks).
- Orchestration-level hit saves ~90 seconds of wall-clock time.
- Embedded mode means zero ops overhead — `.qdrant_data/` is a directory, not a service.

**Negative:**
- `.qdrant_data/` grows unboundedly; periodic cleanup is needed (no TTL support in
  Qdrant local mode).
- Cache warm-up is required on fresh installs — first 5-10 runs get no benefit.
- The `codebase_hash` penalty solves cross-project false positives but introduces
  a new failure mode: if the project's file names change significantly, cache hits
  drop until the cache repopulates.

**Risks:**
- Qdrant local mode does not support concurrent writers. Only one pipeline process
  should write to `.qdrant_data/` at a time.

# Runbook: High RAG Miss Rate / Zero Cache Hits

**Severity:** Medium
**Component:** rag_integration.py, vector_db_mcp_server.py
**Introduced:** v1.5.0 (orchestration-level RAG: v1.6.0)

---

## Symptom

Every pipeline run executes all 15 steps from scratch with no RAG cache hits.
Log lines show:

```
[rag_integration] RAG miss for step=step0 (no results above threshold)
[rag_integration] RAG miss for step=orchestration_plan (score=0.61 < 0.85)
```

Or the Qdrant `node_decisions` collection stays at 0 documents after multiple runs.

---

## Step 1 — Verify Qdrant Connectivity

```bash
# Check Qdrant process (local in-process mode does not need a server)
python -c "from qdrant_client import QdrantClient; c = QdrantClient(':memory:'); print('OK')"

# If using a persistent local path (default):
python -c "
from qdrant_client import QdrantClient
c = QdrantClient(path='.qdrant_data')
print(c.get_collections())
"
```

If the second command raises `StorageError` or `PermissionError`:
- Confirm `.qdrant_data/` exists and is writable.
- On Windows, check that another process does not hold a lock on the directory.

---

## Step 2 — Confirm the node_decisions Collection Exists and Has Data

```bash
python -c "
from qdrant_client import QdrantClient
c = QdrantClient(path='.qdrant_data')
info = c.get_collection('node_decisions')
print('vectors:', info.vectors_count)
print('points:', info.points_count)
"
```

Expected after at least one completed run: `points >= 1`.

If `0`: the store path is failing silently. Check for `rag_integration store error`
in the pipeline logs.

---

## Step 3 — Diagnose the codebase_hash Cross-Project Penalty

As of v1.6.1 every stored payload includes a `codebase_hash`. When a query
comes from a different project the score is multiplied by `0.65`, which can
drop a genuine `0.91` match below any threshold.

### Check what hash is stored vs. what the current run computes

```python
from scripts.langgraph_engine.rag_integration import _compute_codebase_hash
project_root = "."  # adjust to your project root
print("Current hash:", _compute_codebase_hash(project_root))
```

Then inspect stored points:

```bash
python -c "
from qdrant_client import QdrantClient
c = QdrantClient(path='.qdrant_data')
pts = c.scroll('node_decisions', limit=5, with_payload=True)[0]
for p in pts:
    print(p.payload.get('codebase_hash'), p.payload.get('step'))
"
```

If hashes differ, the cache was populated from a different workspace clone or
repository. Either warm the cache from the current project (see Step 5) or
clear stale data from a foreign project:

```bash
python -c "
from qdrant_client import QdrantClient, models
c = QdrantClient(path='.qdrant_data')
foreign_hash = 'abc123def456'  # hash of old project
c.delete(collection_name='node_decisions',
         points_selector=models.FilterSelector(
             filter=models.Filter(must=[
                 models.FieldCondition(key='codebase_hash',
                                       match=models.MatchValue(value=foreign_hash))
             ])))
print('deleted')
"
```

---

## Step 4 — Threshold Tuning

Current step-specific thresholds (from `rag_integration.py`):

| Step | Threshold |
|------|-----------|
| step0 | 0.85 |
| step1 | 0.80 |
| step2 | 0.88 |
| step5 | 0.82 |
| step7 | 0.90 |
| step8 | 0.78 |
| step11 | 0.85 |
| step13 | 0.80 |
| step14 | 0.75 |
| orchestration_plan | 0.85 |
| default | 0.82 |

If legitimate tasks are not hitting cache due to paraphrasing differences,
lower the threshold for that step by 0.03-0.05 in `STEP_THRESHOLDS`.

**Caution:** Do not lower `step2` (plan execution) or `step7` (final prompt)
below `0.82` without testing — incorrect plan reuse causes wrong implementations.

---

## Step 5 — Cache Warming

Run a representative set of common tasks to pre-populate the cache:

```bash
# Warm with common task types
for task in "fix authentication bug" "add REST endpoint" "update database schema"; do
    CLAUDE_HOOK_MODE=0 python scripts/3-level-flow.py --task "$task" --dry-run
done
```

The `--dry-run` flag (if supported) runs the pipeline but skips GitHub/Jira
writes, allowing safe cache population.

---

## Step 6 — Prometheus Monitoring (if enabled)

If Prometheus metrics are scraped from the MCP servers, check these gauges:

```
# RAG hit rate over last hour (should be > 0.20 for mature systems)
rag_cache_hit_total / (rag_cache_hit_total + rag_cache_miss_total)

# Collection size
qdrant_collection_points{collection="node_decisions"}

# Orchestration-level hit rate (saves ~5 LLM calls per hit)
rag_orchestration_hit_total
```

Alert thresholds (recommended):
- `rag_cache_hit_rate < 0.05` for more than 10 consecutive runs: investigate
- `qdrant_collection_points == 0` after 3 runs: storage is broken

---

## Resolution Summary

| Root Cause | Fix |
|------------|-----|
| Qdrant storage permission error | Fix `.qdrant_data/` permissions |
| Cache populated from different project | Clear foreign-hash points (Step 3) |
| Threshold too high for paraphrased tasks | Lower threshold by 0.03-0.05 (Step 4) |
| Cache never warmed (fresh install) | Run warm loop (Step 5) |
| Embedding model not downloaded | `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"` |

"""
db_migrate.py - Qdrant collection bootstrap script.

Creates the four collections used by the Claude Workflow Engine RAG pipeline.
The script is idempotent: running it multiple times produces the same result.
With the --recreate flag all collections are dropped and recreated from scratch.

Collections:
  node_decisions  - Caches LangGraph node decisions for RAG reuse
  sessions        - Session-level metadata and flow summaries
  flow_traces     - Per-step execution trace records
  tool_calls      - Post-tool tracking records

Vector configuration:
  size:     384   (matching sentence-transformers all-MiniLM-L6-v2 output)
  distance: Cosine

Payload indexes created on: step, session_id, codebase_hash fields.

Usage:
  python scripts/db_migrate.py
  python scripts/db_migrate.py --recreate

Environment variables:
  QDRANT_HOST  - Qdrant server hostname (default: localhost)
  QDRANT_PORT  - Qdrant server port     (default: 6333)

Python 3.8+ compatible. ASCII-only string literals (cp1252 safe).
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COLLECTIONS = [
    "node_decisions",
    "sessions",
    "flow_traces",
    "tool_calls",
]

VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimension
VECTOR_DISTANCE = "Cosine"

# Payload fields that benefit from an index for fast filtered search
INDEXED_FIELDS = ["step", "session_id", "codebase_hash"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_client():
    """Create and return a QdrantClient connected to the configured host."""
    from qdrant_client import QdrantClient

    host = os.environ.get("QDRANT_HOST", "localhost")
    port_str = os.environ.get("QDRANT_PORT", "6333")
    try:
        port = int(port_str)
    except ValueError:
        print(
            "[ERROR] QDRANT_PORT '{}' is not a valid integer.".format(port_str),
            file=sys.stderr,
        )
        sys.exit(1)

    print("[INFO] Connecting to Qdrant at {}:{}".format(host, port))
    return QdrantClient(host=host, port=port)


def _collection_exists(client, name):
    # type: (object, str) -> bool
    """Return True when the named collection already exists."""
    try:
        existing = client.get_collections()
        names = [c.name for c in existing.collections]
        return name in names
    except Exception as exc:
        print("[WARN] Could not list collections: {}".format(exc), file=sys.stderr)
        return False


def _create_collection(client, name):
    """Create a single collection with standard vector config."""
    from qdrant_client.models import Distance, VectorParams

    distance_map = {
        "Cosine": Distance.COSINE,
        "Dot": Distance.DOT,
        "Euclid": Distance.EUCLID,
    }
    distance = distance_map.get(VECTOR_DISTANCE, Distance.COSINE)

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=distance),
    )


def _create_payload_indexes(client, name):
    """Create keyword payload indexes on standard fields for fast filtering."""
    from qdrant_client.models import PayloadSchemaType

    for field in INDEXED_FIELDS:
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            # Index may already exist; log and continue
            print(
                "[WARN] Index '{}' on '{}': {}".format(field, name, exc),
                file=sys.stderr,
            )


def _drop_collection(client, name):
    """Drop a collection if it exists."""
    try:
        client.delete_collection(collection_name=name)
        return True
    except Exception as exc:
        print("[WARN] Could not drop '{}': {}".format(name, exc), file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def run_migration(recreate=False):
    # type: (bool) -> None
    """Execute the migration: create or recreate all collections."""
    client = _get_client()

    created = 0
    skipped = 0
    recreated = 0

    for name in COLLECTIONS:
        exists = _collection_exists(client, name)

        if recreate and exists:
            print("[RECREATE] Dropping collection '{}'...".format(name))
            _drop_collection(client, name)
            exists = False

        if exists:
            print("[SKIP] Collection '{}' already exists.".format(name))
            skipped += 1
        else:
            print("[CREATE] Creating collection '{}'...".format(name))
            _create_collection(client, name)
            _create_payload_indexes(client, name)
            if recreate:
                recreated += 1
            else:
                created += 1

    print("")
    print("=== Migration Summary ===")
    if recreate:
        print("  Recreated : {}".format(recreated))
    else:
        print("  Created   : {}".format(created))
        print("  Skipped   : {}".format(skipped))
    print("  Total     : {}".format(len(COLLECTIONS)))
    print("=========================")


def main():
    """Entry point for CLI invocation."""
    parser = argparse.ArgumentParser(description="Bootstrap Qdrant collections for the Claude Workflow Engine.")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate all collections (destructive - wipes existing vectors).",
    )
    args = parser.parse_args()

    try:
        run_migration(recreate=args.recreate)
    except Exception as exc:
        print("[ERROR] Migration failed: {}".format(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

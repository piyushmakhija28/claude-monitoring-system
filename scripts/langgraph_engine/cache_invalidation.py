"""Qdrant vector DB cache invalidation utility for the Claude Workflow Engine.

Provides targeted invalidation of the node_decisions RAG collection by:
- session_id: purge all decisions for a specific pipeline session
- codebase_hash: purge all decisions from a specific project/codebase snapshot
- step_name: purge cached decisions for a specific pipeline step
- stale age: purge records older than N days (default: 30)

All functions degrade gracefully when qdrant-client is not installed.
The module can also be executed as a CLI tool directly.

Usage (Python)::

    from scripts.langgraph_engine.cache_invalidation import (
        invalidate_session,
        invalidate_project,
        invalidate_step,
        invalidate_stale,
    )

    removed = invalidate_session("sess-abc123")
    removed = invalidate_project("a1b2c3d4e5f6")
    removed = invalidate_step("step_5")
    removed = invalidate_stale(max_age_days=14)

Usage (CLI)::

    python cache_invalidation.py --session sess-abc123
    python cache_invalidation.py --project a1b2c3d4e5f6
    python cache_invalidation.py --step step_5
    python cache_invalidation.py --stale 30

Environment variables:
    QDRANT_HOST   Qdrant server hostname (default: "localhost").
    QDRANT_PORT   Qdrant server port    (default: 6333).

ASCII-only: cp1252 safe (Windows).
"""

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_COLLECTION = "node_decisions"

# ---------------------------------------------------------------------------
# Optional qdrant-client import
# ---------------------------------------------------------------------------
_HAS_QDRANT = False

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import FieldCondition, Filter, MatchValue, Range

    _HAS_QDRANT = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def _get_client() -> Optional[object]:
    """Return a connected QdrantClient or None when unavailable."""
    if not _HAS_QDRANT:
        logger.warning(
            "qdrant-client not installed; cache invalidation unavailable. " "Install: pip install qdrant-client"
        )
        return None

    host = os.environ.get("QDRANT_HOST", "localhost")
    port = int(os.environ.get("QDRANT_PORT", "6333"))

    try:
        client = QdrantClient(host=host, port=port, timeout=10)
        return client
    except Exception as exc:
        logger.warning("Cannot connect to Qdrant at %s:%d: %s", host, port, exc)
        return None


# ---------------------------------------------------------------------------
# Public invalidation functions
# ---------------------------------------------------------------------------


def invalidate_session(session_id: str) -> int:
    """Delete all node_decisions records for the given session_id.

    Args:
        session_id: Pipeline session identifier stored in the payload.

    Returns:
        Number of records deleted, or -1 on error.
    """
    client = _get_client()
    if client is None:
        return -1

    if not session_id:
        logger.warning("invalidate_session: empty session_id provided")
        return 0

    try:
        result = client.delete(
            collection_name=_COLLECTION,
            points_selector=Filter(must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]),
        )
        count = getattr(result, "deleted", 0) or 0
        logger.info("Invalidated %d records for session_id=%s", count, session_id)
        return count
    except Exception as exc:
        logger.error("invalidate_session failed for %s: %s", session_id, exc)
        return -1


def invalidate_project(codebase_hash: str) -> int:
    """Delete all node_decisions records for the given codebase_hash.

    The codebase_hash is a 12-char SHA1 fingerprint stored in the RAG payload
    (see rag_integration.py _build_codebase_hash).

    Args:
        codebase_hash: 12-character codebase fingerprint.

    Returns:
        Number of records deleted, or -1 on error.
    """
    client = _get_client()
    if client is None:
        return -1

    if not codebase_hash:
        logger.warning("invalidate_project: empty codebase_hash provided")
        return 0

    try:
        result = client.delete(
            collection_name=_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="codebase_hash",
                        match=MatchValue(value=codebase_hash),
                    )
                ]
            ),
        )
        count = getattr(result, "deleted", 0) or 0
        logger.info("Invalidated %d records for codebase_hash=%s", count, codebase_hash)
        return count
    except Exception as exc:
        logger.error("invalidate_project failed for %s: %s", codebase_hash, exc)
        return -1


def invalidate_step(step_name: str) -> int:
    """Delete all node_decisions records for the given pipeline step name.

    Args:
        step_name: Step identifier as stored in the payload, e.g. "step_5"
                   or "orchestration_plan".

    Returns:
        Number of records deleted, or -1 on error.
    """
    client = _get_client()
    if client is None:
        return -1

    if not step_name:
        logger.warning("invalidate_step: empty step_name provided")
        return 0

    try:
        result = client.delete(
            collection_name=_COLLECTION,
            points_selector=Filter(must=[FieldCondition(key="step", match=MatchValue(value=step_name))]),
        )
        count = getattr(result, "deleted", 0) or 0
        logger.info("Invalidated %d records for step=%s", count, step_name)
        return count
    except Exception as exc:
        logger.error("invalidate_step failed for %s: %s", step_name, exc)
        return -1


def invalidate_stale(max_age_days: int = 30) -> int:
    """Delete node_decisions records older than max_age_days.

    Records are matched using the ISO 8601 timestamp stored in the
    "created_at" payload field.

    Args:
        max_age_days: Maximum age of a record in days (default: 30).

    Returns:
        Number of records deleted, or -1 on error.
    """
    client = _get_client()
    if client is None:
        return -1

    if max_age_days < 1:
        logger.warning("invalidate_stale: max_age_days must be >= 1, got %d", max_age_days)
        return 0

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    # Qdrant Range filter on a datetime string uses lexicographic ordering;
    # ISO 8601 UTC strings compare correctly in lexicographic order.
    cutoff_str = cutoff_dt.isoformat()

    try:
        result = client.delete(
            collection_name=_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="created_at",
                        range=Range(lt=cutoff_str),
                    )
                ]
            ),
        )
        count = getattr(result, "deleted", 0) or 0
        logger.info(
            "Invalidated %d stale records older than %d days (cutoff=%s)",
            count,
            max_age_days,
            cutoff_str,
        )
        return count
    except Exception as exc:
        logger.error("invalidate_stale failed: %s", exc)
        return -1


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Invalidate Claude Workflow Engine RAG cache entries in Qdrant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python cache_invalidation.py --session sess-abc123\n"
            "  python cache_invalidation.py --project a1b2c3d4e5f6\n"
            "  python cache_invalidation.py --step step_5\n"
            "  python cache_invalidation.py --stale 14\n"
        ),
    )
    parser.add_argument(
        "--session",
        metavar="SESSION_ID",
        help="Delete all records for the given session_id.",
    )
    parser.add_argument(
        "--project",
        metavar="CODEBASE_HASH",
        help="Delete all records for the given 12-char codebase hash.",
    )
    parser.add_argument(
        "--step",
        metavar="STEP_NAME",
        help="Delete all records for the given step name (e.g. step_5).",
    )
    parser.add_argument(
        "--stale",
        metavar="DAYS",
        type=int,
        nargs="?",
        const=30,
        default=None,
        help="Delete records older than DAYS days (default: 30 when flag present).",
    )
    return parser


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = _build_arg_parser()
    args = parser.parse_args()

    if not any([args.session, args.project, args.step, args.stale is not None]):
        parser.print_help()
        sys.exit(1)

    total = 0

    if args.session:
        removed = invalidate_session(args.session)
        total += max(removed, 0)
        print("Session invalidation: %d records removed" % removed)

    if args.project:
        removed = invalidate_project(args.project)
        total += max(removed, 0)
        print("Project invalidation: %d records removed" % removed)

    if args.step:
        removed = invalidate_step(args.step)
        total += max(removed, 0)
        print("Step invalidation: %d records removed" % removed)

    if args.stale is not None:
        removed = invalidate_stale(max_age_days=args.stale)
        total += max(removed, 0)
        print("Stale invalidation (%d days): %d records removed" % (args.stale, removed))

    print("Total records removed: %d" % total)

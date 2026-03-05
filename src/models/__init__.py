"""Models Package - Data models.

Defines the data structures used throughout the Claude Insight dashboard.
Models represent entities such as sessions, policy events, metrics, and
tool usage records that are read from the Claude Memory System log files.

This package intentionally avoids a database ORM. All persistence is handled
by reading and writing JSON/JSONL files under ~/.claude/memory/logs/ so that
the dashboard remains a read-only observer with no write dependencies on the
memory system itself.

Typical usage::

    from src.models import SomeModel
    record = SomeModel(...)
"""

"""Backward-compat shim -- moved to level1_sync/toon_schema.py."""

import warnings as _w

_w.warn(
    "Import from langgraph_engine.toon_schema is deprecated. " "Use langgraph_engine.level1_sync.toon_schema instead.",
    DeprecationWarning,
    stacklevel=2,
)
from .level1_sync.toon_schema import *  # noqa: E402,F401,F403

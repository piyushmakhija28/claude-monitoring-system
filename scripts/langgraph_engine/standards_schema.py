"""Backward-compat shim -- moved to level2_standards/standards_schema.py."""

import warnings as _w

_w.warn(
    "Import from langgraph_engine.standards_schema is deprecated. "
    "Use langgraph_engine.level2_standards.standards_schema instead.",
    DeprecationWarning,
    stacklevel=2,
)
from .level2_standards.standards_schema import *  # noqa: E402,F401,F403

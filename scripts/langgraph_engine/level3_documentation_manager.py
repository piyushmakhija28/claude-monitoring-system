"""Backward-compat shim -- moved to level3_execution/documentation_manager.py."""

import warnings as _w

_w.warn(
    "Import from langgraph_engine.level3_documentation_manager is deprecated. "
    "Use langgraph_engine.level3_execution.documentation_manager instead.",
    DeprecationWarning,
    stacklevel=2,
)
from .level3_execution.documentation_manager import *  # noqa: E402,F401,F403

"""Backward-compat shim -- moved to level3_execution/code_explorer.py."""

import warnings as _w

_w.warn(
    "Import from langgraph_engine.level3_code_explorer is deprecated. "
    "Use langgraph_engine.level3_execution.code_explorer instead.",
    DeprecationWarning,
    stacklevel=2,
)
from .level3_execution.code_explorer import *  # noqa: E402,F401,F403

"""Backward-compat shim -- moved to level3_execution/step1_planner.py."""

import warnings as _w

_w.warn(
    "Import from langgraph_engine.level3_step1_planner is deprecated. "
    "Use langgraph_engine.level3_execution.step1_planner instead.",
    DeprecationWarning,
    stacklevel=2,
)
from .level3_execution.step1_planner import *  # noqa: E402,F401,F403

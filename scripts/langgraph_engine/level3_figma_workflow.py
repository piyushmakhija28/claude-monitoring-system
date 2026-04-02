"""Backward-compat shim -- moved to level3_execution/figma_workflow.py."""

import warnings as _w

_w.warn(
    "Import from langgraph_engine.level3_figma_workflow is deprecated. "
    "Use langgraph_engine.level3_execution.figma_workflow instead.",
    DeprecationWarning,
    stacklevel=2,
)
from .level3_execution.figma_workflow import *  # noqa: E402,F401,F403

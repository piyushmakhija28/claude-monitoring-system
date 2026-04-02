"""Backward-compat shim -- moved to level3_execution/steps8to12_jira.py."""

import warnings as _w

_w.warn(
    "Import from langgraph_engine.level3_steps8to12_jira is deprecated. "
    "Use langgraph_engine.level3_execution.steps8to12_jira instead.",
    DeprecationWarning,
    stacklevel=2,
)
from .level3_execution.steps8to12_jira import *  # noqa: E402,F401,F403

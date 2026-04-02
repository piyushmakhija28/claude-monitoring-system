"""Backward-compat shim -- moved to level2_standards/mcp_plugin_loader.py."""

import warnings as _w

_w.warn(
    "Import from langgraph_engine.mcp_plugin_loader is deprecated. "
    "Use langgraph_engine.level2_standards.mcp_plugin_loader instead.",
    DeprecationWarning,
    stacklevel=2,
)
from .level2_standards.mcp_plugin_loader import *  # noqa: E402,F401,F403

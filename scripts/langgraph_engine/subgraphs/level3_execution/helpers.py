"""Backward-compat shim: re-exports from level3_execution.helpers."""

from ...level3_execution.helpers import (  # noqa: F401
    _LANGGRAPH_AVAILABLE,
    _LEVEL3_AGENTS_DIR,
    _LEVEL3_SKILLS_DIR,
    _detect_project_type_from_files,
    _extract_modified_files,
    _read_project_context_snippets,
    call_execution_script,
)

__all__ = [
    "_LANGGRAPH_AVAILABLE",
    "_LEVEL3_AGENTS_DIR",
    "_LEVEL3_SKILLS_DIR",
    "_detect_project_type_from_files",
    "_extract_modified_files",
    "_read_project_context_snippets",
    "call_execution_script",
]

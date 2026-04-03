"""Backward-compat shim: re-exports from level3_execution.routing."""

from ...level3_execution.routing import (  # noqa: F401
    level3_merge_node,
    route_after_step1_plan_decision,
    route_after_step11_review,
)

__all__ = [
    "level3_merge_node",
    "route_after_step1_plan_decision",
    "route_after_step11_review",
]

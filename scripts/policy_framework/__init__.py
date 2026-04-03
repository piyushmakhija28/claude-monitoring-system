"""Shared policy framework for hook scripts.

Provides PolicyRegistry, PolicyResult, and base infrastructure
shared by pre_tool_enforcer and post_tool_tracker packages.
"""

from .registry import PolicyRegistry  # noqa: F401
from .result import PolicyResult  # noqa: F401

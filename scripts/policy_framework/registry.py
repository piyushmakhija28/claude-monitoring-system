"""policy_framework/registry.py - Shared PolicyRegistry class.

Provides an ordered registry of policy check callables that can be
used by both pre_tool_enforcer and post_tool_tracker hooks.

Each policy is a callable: (tool_name, tool_input) -> (blocked, message)
Policies run in registration order; first block wins.

Windows-safe: ASCII only, no Unicode characters.
"""


class PolicyRegistry:
    """Ordered list of policy check callables.

    Each registered check is called with (tool_name, tool_input) and
    must return (blocked: bool, message: str). The registry runs all
    checks in order and returns the first blocking result.

    Fail-open: if a check raises an exception, it is silently skipped.
    """

    def __init__(self):
        self._checks = []  # List of (name, callable)

    def register(self, name, fn):
        """Register a named policy check function.

        Args:
            name: Human-readable policy name (for logging/debugging).
            fn: Callable(tool_name, tool_input) -> (blocked, message).
        """
        self._checks.append((name, fn))

    def run_all(self, tool_name, tool_input, session_id=None):
        """Run all registered checks in order.

        Returns the first blocking result, or (False, '') if all pass.

        Args:
            tool_name: Name of the tool being invoked.
            tool_input: Tool parameters dict.
            session_id: Optional session ID for context.

        Returns:
            tuple: (blocked: bool, message: str)
        """
        for name, check in self._checks:
            try:
                blocked, msg = check(tool_name, tool_input)
                if blocked:
                    return True, msg
            except Exception:
                pass  # Fail-open: never block on check errors
        return False, ""

    def __len__(self):
        return len(self._checks)

    def __repr__(self):
        names = [name for name, _ in self._checks]
        return f"PolicyRegistry({len(names)} checks: {names})"

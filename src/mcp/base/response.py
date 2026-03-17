"""
MCPResponse - Builder Pattern for structured MCP tool responses.

Replaces 11 identical copies of ``_json()`` and 109 manual dict constructions
across all MCP servers with a fluent, type-safe builder.

Design Pattern: Builder
  - Fluent interface for chaining: ``MCPResponse.ok().data("key", val).build()``
  - Single-use builder (do not call ``.build()`` more than once)
  - Consistent timestamp injection
  - Backward compatible with existing ``_json()`` callers via ``to_json()``

Usage::

    # Simple success
    return success(branch="main", commits=5)

    # Simple error
    return error("File not found", error_type="NOT_FOUND")

    # Builder for complex responses
    return (MCPResponse.ok()
        .message("PR created")
        .data("pr_number", 42)
        .data("url", "https://...")
        .build())

Windows-Safe: ASCII only (cp1252 compatible)
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional


def _serialize(payload: dict) -> str:
    """Shared JSON serialization with consistent formatting.

    Single source of truth for all MCP response serialization.
    Change format here to affect all responses globally.

    Args:
        payload: Dictionary to serialize to JSON string.

    Returns:
        Pretty-printed JSON string with ``default=str`` for non-serializable types.
    """
    return json.dumps(payload, indent=2, default=str)


class MCPResponse:
    """Fluent builder for MCP tool JSON responses.

    Implements the Builder pattern -- construct responses step by step,
    then call ``.build()`` to produce the final JSON string.

    The builder is single-use: after ``.build()`` is called, the payload
    is frozen and further mutations are not recommended.

    Attributes:
        _payload: Internal dict accumulating the response fields.

    Example::

        response = (MCPResponse.ok()
            .data("branch", "main")
            .data("commits", 5)
            .build())
    """

    __slots__ = ("_payload",)

    def __init__(self, is_success: bool = True):
        """Initialize the builder with a success/failure flag.

        Args:
            is_success: Whether this is a success (True) or failure (False) response.
        """
        self._payload: Dict[str, Any] = {"success": is_success}

    # -- Factory Methods (static constructors) --

    @classmethod
    def ok(cls) -> "MCPResponse":
        """Create a success response builder.

        Returns:
            New MCPResponse instance with ``success=True``.
        """
        return cls(is_success=True)

    @classmethod
    def fail(cls) -> "MCPResponse":
        """Create a failure response builder.

        Returns:
            New MCPResponse instance with ``success=False``.
        """
        return cls(is_success=False)

    # -- Builder Methods (fluent chaining) --

    def message(self, msg: str) -> "MCPResponse":
        """Set a human-readable status message.

        Args:
            msg: Message string to include in the response.

        Returns:
            Self for method chaining.
        """
        self._payload["message"] = msg
        return self

    def error_detail(self, error_type: str, msg: str,
                     suggestion: Optional[str] = None) -> "MCPResponse":
        """Set structured error details on a failure response.

        Args:
            error_type: Short error category (e.g. ``"NOT_FOUND"``, ``"VALIDATION_ERROR"``).
            msg: Human-readable error description.
            suggestion: Optional fix suggestion for the caller.

        Returns:
            Self for method chaining.
        """
        self._payload["error_type"] = error_type
        self._payload["error"] = msg
        if suggestion:
            self._payload["suggestion"] = suggestion
        return self

    def data(self, key: str, value: Any) -> "MCPResponse":
        """Add a single key-value pair to the response payload.

        Args:
            key: Field name.
            value: Field value (any JSON-serializable type).

        Returns:
            Self for method chaining.
        """
        self._payload[key] = value
        return self

    def merge(self, mapping: dict) -> "MCPResponse":
        """Merge a dictionary into the response payload.

        Existing keys are overwritten by the mapping values.

        Args:
            mapping: Dictionary of key-value pairs to merge.

        Returns:
            Self for method chaining.
        """
        self._payload.update(mapping)
        return self

    def timestamp(self) -> "MCPResponse":
        """Add current ISO-8601 timestamp to the response.

        Returns:
            Self for method chaining.
        """
        self._payload["timestamp"] = datetime.now().isoformat()
        return self

    # -- Terminal Operations --

    def build(self) -> str:
        """Build the final JSON string. Terminal operation.

        Returns:
            JSON string representation of the accumulated payload.
        """
        return _serialize(self._payload)

    def to_dict(self) -> dict:
        """Return a shallow copy of the payload as a dict.

        Useful for internal composition where JSON string is not needed.

        Returns:
            Copy of the payload dictionary.
        """
        return dict(self._payload)

    def __repr__(self) -> str:
        """Debug representation showing current payload state."""
        return f"MCPResponse({self._payload!r})"


# ---------------------------------------------------------------------------
# Module-level convenience functions (direct replacements for _json())
# ---------------------------------------------------------------------------

def to_json(data: dict) -> str:
    """Serialize a dict to a formatted JSON string.

    Drop-in replacement for the duplicated ``_json()`` across all servers.
    Delegates to the shared ``_serialize()`` function for consistent formatting.

    Args:
        data: Dictionary to serialize.

    Returns:
        Pretty-printed JSON string.
    """
    return _serialize(data)


def success(**kwargs: Any) -> str:
    """Build a success JSON response in one call.

    Convenience function that creates ``{"success": true, ...}`` and serializes it.

    Args:
        **kwargs: Arbitrary key-value pairs to include in the response.

    Returns:
        JSON string with ``success=true`` and all provided fields.

    Example::

        return success(branch="main", commits=5)
        # -> {"success": true, "branch": "main", "commits": 5}
    """
    payload = {"success": True}
    payload.update(kwargs)
    return _serialize(payload)


def error(msg: str, error_type: str = "ERROR", **kwargs: Any) -> str:
    """Build an error JSON response in one call.

    Convenience function that creates ``{"success": false, "error": msg, ...}``.

    Args:
        msg: Human-readable error message.
        error_type: Short error category (default ``"ERROR"``).
            Only included in output when not the default value.
        **kwargs: Additional key-value pairs for context.

    Returns:
        JSON string with ``success=false`` and error details.

    Example::

        return error("File not found", error_type="NOT_FOUND")
        # -> {"success": false, "error": "File not found", "error_type": "NOT_FOUND"}
    """
    payload = {"success": False, "error": msg}
    if error_type != "ERROR":
        payload["error_type"] = error_type
    payload.update(kwargs)
    return _serialize(payload)

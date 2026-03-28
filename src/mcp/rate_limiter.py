"""Token bucket rate limiter for MCP server tool calls.

Applied per-client (by IP or process identity) to prevent abuse.
All limiting is optional: enabled only when ENABLE_RATE_LIMITING=1.

Usage:
    from src.mcp.rate_limiter import check_rate_limit
    result = check_rate_limit(client_id="default", bucket="tool_calls")
    if not result["allowed"]:
        return result  # {"allowed": False, "error": "rate_limit_exceeded", "retry_after": N}
"""

import os
import threading
import time

# Module-level bucket registry: keyed by (client_id, bucket_name)
_buckets = {}  # type: dict
_buckets_lock = threading.Lock()

# Default bucket configurations: (capacity, refill_rate tokens/second)
_BUCKET_DEFAULTS = {
    "tool_calls": (100, 100.0 / 60.0),  # 100 per minute
    "llm_calls": (10, 10.0 / 60.0),  # 10 per minute
}

_RETRY_AFTER_SECONDS = 60


class TokenBucket(object):
    """Thread-safe token bucket for rate limiting.

    Tokens are refilled continuously based on elapsed wall-clock time since
    the last refill check. The bucket never exceeds its capacity.

    Args:
        capacity: Maximum number of tokens the bucket can hold.
        refill_rate: Tokens added per second (can be fractional).
    """

    def __init__(self, capacity, refill_rate):
        # type: (float, float) -> None
        self._capacity = float(capacity)
        self._refill_rate = float(refill_rate)
        self._tokens = float(capacity)  # start full
        self._last_refill = time.time()
        self._lock = threading.Lock()

    def _refill(self):
        # type: () -> None
        """Add tokens based on elapsed time. Must be called under self._lock."""
        now = time.time()
        elapsed = now - self._last_refill
        added = elapsed * self._refill_rate
        self._tokens = min(self._capacity, self._tokens + added)
        self._last_refill = now

    def consume(self, tokens=1):
        # type: (int) -> bool
        """Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (default 1).

        Returns:
            True if tokens were available and consumed, False if the bucket
            did not have enough tokens.
        """
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


def _get_or_create_bucket(client_id, bucket_name):
    # type: (str, str) -> TokenBucket
    """Return existing bucket or create a new one with default settings."""
    key = (client_id, bucket_name)
    with _buckets_lock:
        if key not in _buckets:
            capacity, refill_rate = _BUCKET_DEFAULTS.get(bucket_name, (60, 60.0 / 60.0))
            _buckets[key] = TokenBucket(capacity, refill_rate)
        return _buckets[key]


def check_rate_limit(client_id="default", bucket="tool_calls"):
    # type: (str, str) -> dict
    """Check whether a client is within its rate limit for a given bucket.

    If ENABLE_RATE_LIMITING is not set to "1" this function always returns
    allowed without creating any bucket state.

    Args:
        client_id: Identifier for the client (e.g. IP address, process ID,
                   or "default" for a shared anonymous bucket).
        bucket: Name of the rate limit bucket. Predefined buckets:
                "tool_calls" (100/min), "llm_calls" (10/min).
                Unknown bucket names fall back to 60/min defaults.

    Returns:
        dict with key "allowed" (bool).
        On denial also includes "error" ("rate_limit_exceeded") and
        "retry_after" (int seconds until next token is available).
    """
    if os.environ.get("ENABLE_RATE_LIMITING") != "1":
        return {"allowed": True}

    token_bucket = _get_or_create_bucket(client_id, bucket)
    if token_bucket.consume():
        return {"allowed": True}

    return {
        "allowed": False,
        "error": "rate_limit_exceeded",
        "retry_after": _RETRY_AFTER_SECONDS,
    }

"""Input validation for MCP server tool handlers and pipeline entry points.

Strips null bytes, enforces length limits, and detects prompt injection patterns.

Usage:
    from src.mcp.input_validator import validate_input, validate_task_input
    clean = validate_input(raw_value, max_length=4096)
    task = validate_task_input(raw_task)  # stricter: prompt injection detection
"""

# Patterns that indicate an attempt to override or ignore system instructions.
# All comparisons are performed case-insensitively.
PROMPT_INJECTION_PATTERNS = [
    "ignore previous",
    "system:",
    "###INST",
    "<|im_start|>",
    "disregard",
    "forget your instructions",
]


def validate_input(value, max_length=4096, field_name="input"):
    # type: (object, int, str) -> str
    """Sanitize and validate a string input value.

    Performs the following checks in order:

    1. Type check: raises TypeError if value is not a str.
    2. Null-byte stripping: removes all 0x00 bytes from the string.
    3. Whitespace stripping: removes leading and trailing whitespace.
    4. Length enforcement: raises ValueError if the result exceeds max_length.

    Args:
        value: The raw input value. Must be a str.
        max_length: Maximum allowed character length after cleaning (default 4096).
        field_name: Human-readable field name included in error messages.

    Returns:
        Cleaned string value.

    Raises:
        TypeError: If value is not a str.
        ValueError: If the cleaned value exceeds max_length. The exception
                    message is a JSON-compatible string describing the error.
    """
    if not isinstance(value, str):
        raise TypeError("Expected str for field '{}', got {}".format(field_name, type(value).__name__))

    # Remove null bytes
    cleaned = value.replace("\x00", "")

    # Strip surrounding whitespace
    cleaned = cleaned.strip()

    # Enforce length limit
    if len(cleaned) > max_length:
        raise ValueError(
            '{{"error": "invalid_input", "field": "{}", "reason": "exceeds max length"}}'.format(field_name)
        )

    return cleaned


def validate_task_input(value, max_length=2000):
    # type: (object, int) -> str
    """Validate a pipeline task string with prompt injection detection.

    Calls validate_input first, then scans the cleaned value for known
    prompt injection patterns (case-insensitive substring match).

    Args:
        value: The raw task input. Must be a str.
        max_length: Maximum allowed character length (default 2000).

    Returns:
        Cleaned, injection-free string value.

    Raises:
        TypeError: If value is not a str.
        ValueError: If the value exceeds max_length or contains a prompt
                    injection pattern.
    """
    cleaned = validate_input(value, max_length=max_length, field_name="task")

    lower = cleaned.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.lower() in lower:
            raise ValueError(
                '{{"error": "invalid_input", "field": "task", ' '"reason": "prompt injection pattern detected"}}'
            )

    return cleaned

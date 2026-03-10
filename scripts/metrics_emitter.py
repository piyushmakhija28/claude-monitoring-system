#!/usr/bin/env python
"""
Metrics Emitter - Fire-and-forget metrics collection for hooks.

Provides functions to emit telemetry events from hook scripts without blocking
hook execution. All functions are non-blocking and handle errors gracefully.

Functions:
    emit_hook_execution(hook_name, duration_ms, status, error=None)
    emit_enforcement_event(tool_name, blocked, event_type, message=None)
    emit_flag_lifecycle(flag_name, action, value=None)
    emit_context_sample(context_usage, token_count)
"""

import json
import os
from pathlib import Path
from datetime import datetime


def get_metrics_log_path():
    """Get path to metrics log file."""
    memory_dir = Path.home() / '.claude' / 'memory' / 'logs'
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir / 'metrics.jsonl'


def _write_metric(record):
    """Write metric record to metrics.jsonl (fire-and-forget, never blocks)."""
    try:
        log_path = get_metrics_log_path()
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
    except Exception:
        pass  # Never fail - metrics are optional


def emit_hook_execution(hook_name, duration_ms, status, error=None):
    """Emit hook execution metric.

    Args:
        hook_name (str): Name of hook (e.g., '3-level-flow', 'pre-tool-enforcer')
        duration_ms (int): Execution time in milliseconds
        status (str): 'success', 'error', 'timeout', 'blocked'
        error (str, optional): Error message if status='error'
    """
    record = {
        'type': 'hook_execution',
        'ts': datetime.now().isoformat(),
        'hook_name': hook_name,
        'duration_ms': duration_ms,
        'status': status,
    }
    if error:
        record['error'] = error
    _write_metric(record)


def emit_enforcement_event(tool_name, blocked, event_type, message=None):
    """Emit enforcement event metric (Level 3.6/3.7).

    Args:
        tool_name (str): Name of tool being enforced (e.g., 'Write', 'Edit', 'Bash')
        blocked (bool): Whether tool call was blocked
        event_type (str): Type of enforcement ('optimization', 'blocking', 'hint')
        message (str, optional): Description of the event
    """
    record = {
        'type': 'enforcement_event',
        'ts': datetime.now().isoformat(),
        'tool_name': tool_name,
        'blocked': blocked,
        'event_type': event_type,
    }
    if message:
        record['message'] = message
    _write_metric(record)


def emit_flag_lifecycle(flag_name, action, value=None):
    """Emit flag lifecycle event (task flags, etc).

    Args:
        flag_name (str): Name of flag (e.g., '.task-breakdown-pending')
        action (str): 'created', 'cleared', 'checked'
        value (str, optional): Flag value if applicable
    """
    record = {
        'type': 'flag_lifecycle',
        'ts': datetime.now().isoformat(),
        'flag_name': flag_name,
        'action': action,
    }
    if value:
        record['value'] = value
    _write_metric(record)


def emit_context_sample(context_usage, token_count, session_id=None):
    """Emit context usage sample.

    Args:
        context_usage (float): Context usage percentage (0-100)
        token_count (int): Total tokens used in session
        session_id (str, optional): Session identifier
    """
    record = {
        'type': 'context_sample',
        'ts': datetime.now().isoformat(),
        'context_usage_pct': context_usage,
        'token_count': token_count,
    }
    if session_id:
        record['session_id'] = session_id
    _write_metric(record)

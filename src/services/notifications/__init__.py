"""Notification Services - Alerts, routing, notifications.

Handles outbound alerts triggered by monitoring events such as critical
context usage, policy enforcement failures, and session anomalies.

Notification channels (planned):
    Desktop   -- System tray / OS-level toast notifications via plyer or
                 win10toast on Windows.
    Voice     -- Text-to-speech announcements via voice-notifier.py for
                 audible task-complete signals.
    Webhook   -- HTTP POST payloads to external endpoints (Slack, Teams,
                 custom receivers) with structured JSON bodies.
    Email     -- SMTP-based email delivery for critical threshold breaches
                 requiring immediate attention.

Design notes:
    - All notification functions are fire-and-forget (non-blocking).
    - Failures are logged but never raise exceptions to callers.
    - Channel configuration is read from ``~/.claude/memory/config/``.
"""

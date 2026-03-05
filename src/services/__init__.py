"""Services Package - Business logic layer.

Organises all domain-specific service modules into functional sub-packages.
Services implement the core monitoring, AI analytics, and notification logic;
routes and templates delegate all non-trivial work to services.

Sub-packages:
    monitoring     -- Real-time metrics collection, log parsing, session
                      tracking, and 3-level flow execution tracing.
    ai             -- AI-powered analytics including anomaly detection,
                      bottleneck analysis, and predictive model insights.
    notifications  -- Alert routing and notification delivery (email, desktop,
                      voice, webhook).
    widgets        -- Community widgets, trending content, versioning support,
                      and collaborative feature utilities.

Convention:
    All services are stateless where possible. Shared state is kept in the
    ~/.claude/memory/ directory and read/written by the respective service.
"""

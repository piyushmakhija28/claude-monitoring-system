"""Routes Package - Blueprint registration.

Provides the ``register_routes`` helper that attaches all Flask blueprints
to the application instance. Each sub-module of this package defines one
blueprint covering a functional area of the dashboard (e.g., dashboard,
sessions, analytics, policies, settings).

Blueprint structure (planned):
    dashboard  -- Main overview page and widgets
    sessions   -- Session list, detail, and chain views
    analytics  -- Skill/agent and model usage analytics
    policies   -- Policy enforcement history
    settings   -- Application configuration UI

Usage::

    from src.routes import register_routes
    register_routes(app)
"""

from flask import Flask


def register_routes(app: Flask) -> None:
    """Register all application blueprints with the Flask app.

    Imports each blueprint module and calls ``app.register_blueprint()``
    for each one. Blueprint imports are deferred to this function to avoid
    circular import issues at module load time.

    Args:
        app: The Flask application instance to attach blueprints to.
    """
    # Import blueprints here when created
    pass

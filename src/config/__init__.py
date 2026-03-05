"""Configuration module -- security and application settings.

Provides the application configuration hierarchy used by the Flask factory.
Three concrete configurations extend the base ``Config`` class:

    DevelopmentConfig  -- DEBUG=True, uses ephemeral dev secret key.
    ProductionConfig   -- SECRET_KEY must be set via environment variable.
    TestingConfig      -- DEBUG=True, TESTING=True for the test suite.

Data directory resolution (priority order):
    1. ``CLAUDE_INSIGHT_DATA_DIR`` environment variable (portable installs)
    2. ``~/.claude/memory/`` if it exists (standard memory-system install)
    3. ``<project-root>/data/`` fallback (standalone / CI environments)

Also re-exports all security utilities from ``.security`` so callers can
import everything from one place::

    from src.config import Config, get_config, SecurityConfig

Usage::

    from src.config import get_config
    cfg = get_config('production')
    app.config.from_object(cfg)
    cfg.init_app(app)
"""
import os
from pathlib import Path

from .security import (
    SecurityConfig,
    PasswordValidator,
    PathValidator,
    FilenameValidator,
    CommandValidator,
    LogSanitizer,
    SecurityError
)

# ── App Configuration (previously in standalone config.py) ──────────────────

BASE_DIR = Path(__file__).parent.parent.parent

# Data directory resolution (where dashboard stores its data)
# Priority: env var > ~/.claude/memory (legacy) > ./data (portable)
_data_dir_override = os.environ.get('CLAUDE_INSIGHT_DATA_DIR')
if _data_dir_override:
    MEMORY_SYSTEM_DIR = Path(_data_dir_override)
elif (Path.home() / '.claude' / 'memory').exists():
    MEMORY_SYSTEM_DIR = Path.home() / '.claude' / 'memory'
else:
    MEMORY_SYSTEM_DIR = BASE_DIR / 'data'


class Config:
    """Base application configuration with sensible defaults.

    All environment-specific configurations inherit from this class.
    Class attributes map directly to Flask ``app.config`` keys.

    Attributes:
        SECRET_KEY: HMAC key for session signing. Override via ``SECRET_KEY``
            environment variable in production.
        MEMORY_DIR: Root of the Claude Memory System data directory.
        LOGS_DIR: Subdirectory for log files (policy-hits, metrics, etc.).
        SESSIONS_DIR: Subdirectory for session state JSON files.
        DOCS_DIR: Subdirectory for generated documentation.
        MEMORY_FILES_DIR: Project-local directory for uploaded/cached files.
        METRICS_RETENTION_DAYS: How many days of metrics records to keep.
        LOG_RETENTION_DAYS: How many days of raw log files to keep.
        SESSION_RETENTION_DAYS: How many days of session data to keep.
        CONTEXT_WARNING_THRESHOLD: Context % that triggers a yellow warning.
        CONTEXT_CRITICAL_THRESHOLD: Context % that triggers an orange alert.
        CONTEXT_DANGER_THRESHOLD: Context % that triggers a red/auto-compact.
        TRENDING_WINDOW_HOURS: Rolling window for trending metric calculation.
        FEATURED_WIDGET_COUNT: Maximum items shown in featured widget lists.
        SOCKETIO_ASYNC_MODE: SocketIO concurrency mode ('threading').
        NOTIFICATION_BATCH_SIZE: Max notifications per batch delivery.
        NOTIFICATION_RETRY_ATTEMPTS: Retry count for failed notification sends.
        ANOMALY_DETECTION_ENABLED: Toggle AI anomaly detection on/off.
        PREDICTIVE_ANALYTICS_ENABLED: Toggle predictive analytics on/off.
        MODEL_UPDATE_INTERVAL_HOURS: How often predictive models are retrained.
        DEBUG: Flask debug mode (disabled by default).
        TESTING: Flask testing mode (disabled by default).
    """

    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    MEMORY_DIR = MEMORY_SYSTEM_DIR
    LOGS_DIR = MEMORY_DIR / 'logs'
    SESSIONS_DIR = MEMORY_DIR / 'sessions'
    DOCS_DIR = MEMORY_DIR / 'docs'

    MEMORY_FILES_DIR = BASE_DIR / 'memory_files'

    METRICS_RETENTION_DAYS = 30
    LOG_RETENTION_DAYS = 90
    SESSION_RETENTION_DAYS = 180

    CONTEXT_WARNING_THRESHOLD = 70
    CONTEXT_CRITICAL_THRESHOLD = 85
    CONTEXT_DANGER_THRESHOLD = 90

    TRENDING_WINDOW_HOURS = 24
    FEATURED_WIDGET_COUNT = 10

    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_LOGGER = False
    SOCKETIO_ENGINEIO_LOGGER = False

    NOTIFICATION_BATCH_SIZE = 50
    NOTIFICATION_RETRY_ATTEMPTS = 3

    ANOMALY_DETECTION_ENABLED = True
    PREDICTIVE_ANALYTICS_ENABLED = True
    MODEL_UPDATE_INTERVAL_HOURS = 6

    DEBUG = False
    TESTING = False

    @staticmethod
    def init_app(app) -> None:
        """Perform post-config initialisation for a Flask app instance.

        Creates all required data directories so the application can write
        logs, session files, and documentation without failing on first run.

        Args:
            app: The Flask application instance (currently unused but
                 included for Flask's config convention compatibility).
        """
        os.makedirs(Config.MEMORY_FILES_DIR, exist_ok=True)
        os.makedirs(Config.LOGS_DIR, exist_ok=True)
        os.makedirs(Config.SESSIONS_DIR, exist_ok=True)
        os.makedirs(Config.DOCS_DIR, exist_ok=True)


class DevelopmentConfig(Config):
    """Development configuration with debug mode enabled.

    Inherits all defaults from ``Config``. Sets ``DEBUG = True`` so that
    Flask reloads on code changes and displays detailed error pages.
    Not suitable for production use.
    """

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration requiring an explicit secret key.

    ``SECRET_KEY`` must be provided via the ``SECRET_KEY`` environment
    variable. If the variable is absent, Flask will use ``None`` which
    causes all session signing to fail -- an intentional safety measure
    to prevent accidental production deployment with a weak key.
    """

    SECRET_KEY = os.environ.get('SECRET_KEY')


class TestingConfig(Config):
    """Testing configuration for the automated test suite.

    Enables both ``DEBUG`` and ``TESTING`` so that Flask propagates
    exceptions into test assertions rather than returning 500 responses,
    and disables error catching for cleaner test output.
    """

    DEBUG = True
    TESTING = True


_config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env: str = None) -> type:
    """Return the configuration class for the given environment name.

    Reads the ``FLASK_ENV`` environment variable when ``env`` is not
    provided. Falls back to ``DevelopmentConfig`` for unknown names.

    Args:
        env: One of ``'development'``, ``'production'``, or ``'testing'``.
            Pass ``None`` to auto-detect from the ``FLASK_ENV`` env variable.

    Returns:
        The configuration class (not an instance) corresponding to ``env``.
        Defaults to ``DevelopmentConfig`` for unrecognised values.

    Example::

        cfg_class = get_config('production')
        app.config.from_object(cfg_class)
    """
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    return _config_map.get(env, _config_map['default'])


__all__ = [
    'SecurityConfig',
    'PasswordValidator',
    'PathValidator',
    'FilenameValidator',
    'CommandValidator',
    'LogSanitizer',
    'SecurityError',
    'Config',
    'DevelopmentConfig',
    'ProductionConfig',
    'TestingConfig',
    'get_config',
    'MEMORY_SYSTEM_DIR',
    'BASE_DIR',
]

"""Authentication and user management module.

Provides user account management for the Claude Insight dashboard,
including login/logout, session handling, and password management.

The authentication layer uses bcrypt for secure password hashing and
integrates with Flask session management for stateful login sessions.

Exported classes:
    UserManager -- Manages user accounts: creation, login, logout, and
                   password validation. Stores users in a JSON file in the
                   data directory so no database dependency is required.

Typical usage::

    from src.auth import UserManager
    user_mgr = UserManager()
    success, msg = user_mgr.authenticate('admin', 'password')
"""

from .user_manager import UserManager

__all__ = ['UserManager']

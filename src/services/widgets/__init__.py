"""Widget Services - Community, versioning, collaboration, trending.

Provides service classes that back the dashboard's widget-oriented features.
Widgets are self-contained UI components that surface a focused slice of data
(e.g., top skills this week, recent policy hits, session health score).

Planned widget services:
    TrendingService      -- Computes trending metrics over a rolling 24-hour
                           window and ranks sessions, skills, and models by
                           activity volume.
    CommunityService     -- Aggregates anonymised usage patterns across shared
                           sessions (when collaborative mode is enabled).
    VersioningService    -- Surfaces VERSION and CHANGELOG data from connected
                           repositories for the version-tracking widget.
    CollaborationService -- Manages shared session state for multi-user
                           dashboard sessions (future feature).

Usage::

    from src.services.widgets import TrendingService
    trending = TrendingService(memory_dir)
    top_skills = trending.get_top_skills(hours=24)
"""

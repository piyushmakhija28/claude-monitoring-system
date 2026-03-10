"""
Dashboard Routes Blueprint for Claude Insight

Provides routes for:
- /dashboard - Main dashboard page
- /analytics - Analytics dashboard
- /comparison - Cost comparison
- /sessions - Session tracking
- /logs - Log viewer
"""

from flask import Blueprint, render_template, request, jsonify
from functools import wraps
from datetime import datetime, timedelta
import json
from pathlib import Path

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='')


def login_required(f):
    """Decorator to require login for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Import here to avoid circular imports
        from flask import session, redirect, url_for
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page with real-time metrics from monitoring services."""
    from src.services.monitoring.metrics_collector import MetricsCollector
    from src.services.monitoring.policy_checker import PolicyChecker
    from src.services.monitoring.three_level_flow_tracker import ThreeLevelFlowTracker

    # Widget preferences (all widgets enabled by default)
    widget_preferences = {
        'system_health': True,
        'recent_activity': True,
        'historical_charts': True,
        'context_usage': True,
        'performance_metrics': True,
    }

    try:
        # Get real data from monitoring services
        metrics = MetricsCollector()
        policy_checker = PolicyChecker()
        flow_tracker = ThreeLevelFlowTracker()

        # Get real health metrics
        health = metrics.get_system_health()
        policy_status = policy_checker.get_detailed_policy_status()

        # Summary statistics - REAL DATA
        summary_stats = {
            'avg_health_score': int(health.get('health_score', 0)),
            'trend': 'up' if health.get('health_score', 0) > 70 else 'down',
            'total_errors': health.get('error_count', 0),
            'total_policy_hits': policy_status.get('policy_hits', 0),
            'avg_context_usage': int(health.get('context_usage', 0)),
        }

        # Latest flow data from actual tracker
        flow_latest = flow_tracker.get_latest_execution()
        if not flow_latest:
            flow_latest = {
                'session_id': 'No active session',
                'overall_status': 'IDLE',
                'level_minus_1': {'status': 'N/A'},
                'level_1': {'context_pct': 0, 'status': 'N/A'},
                'level_2': {'standards': 0, 'rules': 0, 'status': 'N/A'},
                'level_3': {'status': 'N/A'},
            }

    except Exception as e:
        print(f"Error loading dashboard data: {e}")
        summary_stats = {'avg_health_score': 0, 'trend': 'unknown', 'total_errors': 0, 'total_policy_hits': 0, 'avg_context_usage': 0}
        flow_latest = {}

    # Time series data for charts
    selected_days = 7
    chart_data = []

    return render_template(
        'dashboard.html',
        widget_preferences=widget_preferences,
        summary_stats=summary_stats,
        flow_latest=flow_latest,
        selected_days=selected_days,
        chart_data=chart_data,
    )


@dashboard_bp.route('/analytics')
@login_required
def analytics():
    """Advanced analytics dashboard."""
    return render_template('analytics.html')


@dashboard_bp.route('/comparison')
@login_required
def comparison():
    """Cost comparison analysis."""
    return render_template('comparison.html')


@dashboard_bp.route('/sessions')
@login_required
def sessions():
    """Session tracking and history."""
    return render_template('sessions.html')


@dashboard_bp.route('/logs')
@login_required
def logs():
    """Real-time log viewer."""
    return render_template('logs.html')

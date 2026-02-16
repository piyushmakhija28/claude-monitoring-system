"""
Policy Execution Tracker - Track real-time policy executions

Monitors and tracks when automation policies are actually executed:
- Prompt Generation (Step 0)
- Task Breakdown (Step 1)
- Plan Mode Decision (Step 2)
- Model Selection (Step 4)
- Skill/Agent Selection (Step 5)
- Tool Optimization (Step 6)

Reads from:
- ~/.claude/memory/logs/policy-hits.log
- ~/.claude/memory/.blocking-enforcer-state.json

Provides real-time metrics for dashboard.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import sys

# Add path for portable imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.path_resolver import get_data_dir


class PolicyExecutionTracker:
    """Track policy executions and provide metrics"""

    def __init__(self):
        self.memory_dir = Path.home() / '.claude' / 'memory'
        self.policy_log = self.memory_dir / 'logs' / 'policy-hits.log'
        self.enforcer_state = self.memory_dir / '.blocking-enforcer-state.json'
        self.tracker_cache = get_data_dir() / 'policy_execution_cache.json'

    def get_enforcer_state(self):
        """Get current blocking enforcer state"""
        try:
            if self.enforcer_state.exists():
                with open(self.enforcer_state, 'r') as f:
                    state = json.load(f)
                return {
                    'session_started': state.get('session_started', False),
                    'standards_loaded': state.get('standards_loaded', False),
                    'prompt_generated': state.get('prompt_generated', False),
                    'tasks_created': state.get('tasks_created', False),
                    'plan_mode_decided': state.get('plan_mode_decided', False),
                    'model_selected': state.get('model_selected', False),
                    'skills_agents_checked': state.get('skills_agents_checked', False),
                    'context_checked': state.get('context_checked', False),
                    'total_violations': state.get('total_violations', 0),
                    'last_violation': state.get('last_violation'),
                    'session_start_time': state.get('session_start_time')
                }
        except Exception as e:
            print(f"Error loading enforcer state: {e}")

        return {
            'session_started': False,
            'standards_loaded': False,
            'prompt_generated': False,
            'tasks_created': False,
            'plan_mode_decided': False,
            'model_selected': False,
            'skills_agents_checked': False,
            'context_checked': False,
            'total_violations': 0,
            'last_violation': None,
            'session_start_time': None
        }

    def parse_policy_log(self, hours=24):
        """Parse policy-hits.log for recent executions"""
        executions = []

        try:
            if not self.policy_log.exists():
                return executions

            cutoff_time = datetime.now() - timedelta(hours=hours)

            with open(self.policy_log, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Parse line format: [timestamp] daemon | status | message
                    try:
                        # Extract timestamp
                        if line.startswith('['):
                            timestamp_end = line.index(']')
                            timestamp_str = line[1:timestamp_end]
                            timestamp = datetime.fromisoformat(timestamp_str)

                            # Skip if too old
                            if timestamp < cutoff_time:
                                continue

                            # Extract policy name and status
                            rest = line[timestamp_end + 1:].strip()
                            parts = rest.split('|')

                            if len(parts) >= 3:
                                policy_name = parts[0].strip()
                                status = parts[1].strip()
                                message = parts[2].strip()

                                # Categorize by policy type
                                policy_category = self._categorize_policy(policy_name)

                                executions.append({
                                    'timestamp': timestamp.isoformat(),
                                    'policy_name': policy_name,
                                    'policy_category': policy_category,
                                    'status': status,
                                    'message': message
                                })
                    except (ValueError, IndexError):
                        continue

        except Exception as e:
            print(f"Error parsing policy log: {e}")

        return executions

    def _categorize_policy(self, policy_name):
        """Categorize policy by type"""
        policy_name_lower = policy_name.lower()

        if 'prompt' in policy_name_lower or 'generation' in policy_name_lower:
            return 'Prompt Generation'
        elif 'task' in policy_name_lower or 'breakdown' in policy_name_lower:
            return 'Task Breakdown'
        elif 'plan' in policy_name_lower or 'mode' in policy_name_lower:
            return 'Plan Mode'
        elif 'model' in policy_name_lower or 'selection' in policy_name_lower:
            return 'Model Selection'
        elif 'skill' in policy_name_lower or 'agent' in policy_name_lower:
            return 'Skill/Agent'
        elif 'tool' in policy_name_lower or 'optimization' in policy_name_lower:
            return 'Tool Optimization'
        elif 'context' in policy_name_lower:
            return 'Context Management'
        elif 'commit' in policy_name_lower or 'git' in policy_name_lower:
            return 'Git Auto-Commit'
        elif 'session' in policy_name_lower:
            return 'Session Management'
        elif 'daemon' in policy_name_lower:
            return 'Daemon'
        else:
            return 'Other'

    def get_execution_stats(self, hours=24):
        """Get execution statistics for the last N hours"""
        executions = self.parse_policy_log(hours)

        # Count by category
        category_counts = defaultdict(int)
        status_counts = defaultdict(int)

        for exec_data in executions:
            category_counts[exec_data['policy_category']] += 1
            status_counts[exec_data['status']] += 1

        # Calculate execution rate (per hour)
        total_executions = len(executions)
        execution_rate = total_executions / hours if hours > 0 else 0

        # Get recent executions (last 10)
        recent_executions = sorted(
            executions,
            key=lambda x: x['timestamp'],
            reverse=True
        )[:10]

        return {
            'total_executions': total_executions,
            'execution_rate_per_hour': round(execution_rate, 2),
            'by_category': dict(category_counts),
            'by_status': dict(status_counts),
            'recent_executions': recent_executions,
            'timeframe_hours': hours
        }

    def get_execution_timeline(self, hours=24):
        """Get execution timeline data for charting"""
        executions = self.parse_policy_log(hours)

        # Group by hour
        hourly_counts = defaultdict(int)

        for exec_data in executions:
            timestamp = datetime.fromisoformat(exec_data['timestamp'])
            hour_key = timestamp.strftime('%Y-%m-%d %H:00')
            hourly_counts[hour_key] += 1

        # Sort by time
        sorted_hours = sorted(hourly_counts.keys())

        return {
            'labels': sorted_hours,
            'data': [hourly_counts[hour] for hour in sorted_hours]
        }

    def get_policy_health(self):
        """Get overall policy health status"""
        enforcer_state = self.get_enforcer_state()
        recent_stats = self.get_execution_stats(hours=1)

        # Calculate health score (0-100)
        health_score = 0

        # Session started (20 points)
        if enforcer_state['session_started']:
            health_score += 20

        # Recent executions (30 points)
        if recent_stats['total_executions'] > 0:
            health_score += min(30, recent_stats['total_executions'] * 3)

        # All steps completed (50 points)
        completed_steps = sum([
            enforcer_state['standards_loaded'],
            enforcer_state['prompt_generated'],
            enforcer_state['tasks_created'],
            enforcer_state['plan_mode_decided'],
            enforcer_state['model_selected'],
            enforcer_state['skills_agents_checked'],
            enforcer_state['context_checked']
        ])
        health_score += int((completed_steps / 7) * 50)

        # Determine status
        if health_score >= 80:
            status = 'EXCELLENT'
            status_class = 'success'
        elif health_score >= 60:
            status = 'GOOD'
            status_class = 'info'
        elif health_score >= 40:
            status = 'FAIR'
            status_class = 'warning'
        else:
            status = 'POOR'
            status_class = 'danger'

        return {
            'health_score': health_score,
            'status': status,
            'status_class': status_class,
            'enforcer_state': enforcer_state,
            'recent_activity': recent_stats['total_executions'],
            'violations': enforcer_state['total_violations']
        }

    def get_enforcement_status(self):
        """Get detailed enforcement status for all steps"""
        enforcer_state = self.get_enforcer_state()

        steps = [
            {
                'id': 'session',
                'name': 'Session Start',
                'layer': 'SYNC',
                'completed': enforcer_state['session_started'],
                'required': True
            },
            {
                'id': 'context',
                'name': 'Context Check',
                'layer': 'SYNC',
                'completed': enforcer_state['context_checked'],
                'required': True
            },
            {
                'id': 'standards',
                'name': 'Standards Loaded',
                'layer': 'STANDARDS',
                'completed': enforcer_state['standards_loaded'],
                'required': True
            },
            {
                'id': 'prompt',
                'name': 'Prompt Generation',
                'layer': 'EXECUTION',
                'completed': enforcer_state['prompt_generated'],
                'required': True
            },
            {
                'id': 'tasks',
                'name': 'Task Breakdown',
                'layer': 'EXECUTION',
                'completed': enforcer_state['tasks_created'],
                'required': True
            },
            {
                'id': 'plan',
                'name': 'Plan Mode Decision',
                'layer': 'EXECUTION',
                'completed': enforcer_state['plan_mode_decided'],
                'required': True
            },
            {
                'id': 'model',
                'name': 'Model Selection',
                'layer': 'EXECUTION',
                'completed': enforcer_state['model_selected'],
                'required': True
            },
            {
                'id': 'skills',
                'name': 'Skills/Agents Check',
                'layer': 'EXECUTION',
                'completed': enforcer_state['skills_agents_checked'],
                'required': True
            }
        ]

        completed_count = sum(1 for step in steps if step['completed'])
        total_count = len(steps)
        completion_percentage = int((completed_count / total_count) * 100)

        return {
            'steps': steps,
            'completed_count': completed_count,
            'total_count': total_count,
            'completion_percentage': completion_percentage
        }


# Standalone test
if __name__ == '__main__':
    tracker = PolicyExecutionTracker()

    print("=" * 70)
    print("POLICY EXECUTION TRACKER - TEST")
    print("=" * 70)
    print()

    # Test enforcer state
    print("[1] Enforcer State:")
    state = tracker.get_enforcer_state()
    for key, value in state.items():
        print(f"  {key}: {value}")
    print()

    # Test execution stats
    print("[2] Execution Stats (Last 24h):")
    stats = tracker.get_execution_stats(hours=24)
    print(f"  Total: {stats['total_executions']}")
    print(f"  Rate: {stats['execution_rate_per_hour']}/hour")
    print(f"  By Category: {stats['by_category']}")
    print()

    # Test health
    print("[3] Policy Health:")
    health = tracker.get_policy_health()
    print(f"  Score: {health['health_score']}/100")
    print(f"  Status: {health['status']}")
    print(f"  Recent Activity: {health['recent_activity']}")
    print()

    # Test enforcement status
    print("[4] Enforcement Status:")
    status = tracker.get_enforcement_status()
    print(f"  Progress: {status['completed_count']}/{status['total_count']} ({status['completion_percentage']}%)")
    for step in status['steps']:
        check = '[CHECK]' if step['completed'] else '[CROSS]'
        print(f"  {check} {step['name']} ({step['layer']})")

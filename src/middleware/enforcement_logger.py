"""
Enforcement Logger Middleware

Logs all policy enforcement calls to policy-hits.log with structured format.
Integrates with existing daemons and provides centralized logging for all policy executions.

This middleware intercepts policy calls and ensures they're properly tracked in the dashboard.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import sys

# Add path for portable imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_resolver import get_data_dir


class EnforcementLogger:
    """
    Centralized logger for policy enforcement

    Logs all policy executions in a structured format that the dashboard can parse.
    """

    def __init__(self):
        self.memory_dir = Path.home() / '.claude' / 'memory'
        self.log_file = self.memory_dir / 'logs' / 'policy-hits.log'
        self.enforcer_state_file = self.memory_dir / '.blocking-enforcer-state.json'

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Setup Python logger
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Setup Python logger for enforcement tracking"""
        logger = logging.getLogger('enforcement_logger')
        logger.setLevel(logging.INFO)

        # Remove existing handlers
        logger.handlers = []

        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Format: [timestamp] policy_name | status | message
        formatter = logging.Formatter('[%(asctime)s] %(name)s | %(levelname)s | %(message)s')
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        return logger

    def log_policy_execution(
        self,
        policy_name: str,
        status: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log a policy execution

        Args:
            policy_name: Name of the policy (e.g., "prompt-generator", "task-breakdown")
            status: Status of execution (OK, CHECK, SKIP, ERROR, SLEEP)
            message: Human-readable message
            metadata: Optional metadata dict
        """
        # Log to file
        self.logger.info(f"{policy_name} | {status} | {message}")

        # If metadata provided, log as JSON on next line
        if metadata:
            metadata_str = json.dumps(metadata, ensure_ascii=False)
            self.logger.info(f"{policy_name}-metadata | DATA | {metadata_str}")

    def log_step_execution(
        self,
        step_number: int,
        step_name: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log execution of a specific enforcement step

        Args:
            step_number: Step number (0-11)
            step_name: Step name (e.g., "Prompt Generation")
            status: STARTED, COMPLETED, FAILED, SKIPPED
            details: Optional details dict
        """
        policy_name = f"step-{step_number}-{step_name.lower().replace(' ', '-')}"
        message = f"Step {step_number}: {step_name} - {status}"

        self.log_policy_execution(policy_name, status, message, details)

        # Update enforcer state if step completed
        if status == "COMPLETED":
            self._update_enforcer_state(step_name)

    def _update_enforcer_state(self, step_name: str):
        """Update the blocking enforcer state file"""
        try:
            # Read current state
            if self.enforcer_state_file.exists():
                with open(self.enforcer_state_file, 'r') as f:
                    state = json.load(f)
            else:
                state = {}

            # Map step names to state keys
            step_mapping = {
                'Session Start': 'session_started',
                'Context Check': 'context_checked',
                'Standards Loaded': 'standards_loaded',
                'Prompt Generation': 'prompt_generated',
                'Task Breakdown': 'tasks_created',
                'Plan Mode Decision': 'plan_mode_decided',
                'Model Selection': 'model_selected',
                'Skills/Agents Check': 'skills_agents_checked'
            }

            state_key = step_mapping.get(step_name)
            if state_key:
                state[state_key] = True

                # Save state
                with open(self.enforcer_state_file, 'w') as f:
                    json.dump(state, f, indent=2)

        except Exception as e:
            self.logger.error(f"Failed to update enforcer state: {e}")

    def log_tool_usage(
        self,
        tool_name: str,
        operation: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log tool usage (Read, Write, Edit, Bash, etc.)

        Args:
            tool_name: Name of tool (Read, Write, Edit, Bash, Grep, Glob)
            operation: What operation was performed
            status: SUCCESS, ERROR, OPTIMIZED
            details: Optional details (file paths, optimization applied, etc.)
        """
        policy_name = f"tool-{tool_name.lower()}"
        message = f"{tool_name} tool: {operation} - {status}"

        self.log_policy_execution(policy_name, status, message, details)

    def log_model_selection(
        self,
        selected_model: str,
        complexity_score: int,
        task_type: str,
        reasoning: str
    ):
        """
        Log model selection decision

        Args:
            selected_model: HAIKU, SONNET, or OPUS
            complexity_score: 0-20+ complexity score
            task_type: Type of task
            reasoning: Why this model was selected
        """
        metadata = {
            'model': selected_model,
            'complexity': complexity_score,
            'task_type': task_type,
            'reasoning': reasoning
        }

        self.log_policy_execution(
            'model-selection',
            'OK',
            f"Selected {selected_model} for {task_type} (complexity: {complexity_score})",
            metadata
        )

    def log_task_breakdown(
        self,
        total_tasks: int,
        num_phases: int,
        complexity_level: str,
        requires_plan_mode: bool
    ):
        """
        Log task breakdown results

        Args:
            total_tasks: Number of tasks created
            num_phases: Number of phases
            complexity_level: SIMPLE, MODERATE, COMPLEX, VERY_COMPLEX
            requires_plan_mode: Whether plan mode is required
        """
        metadata = {
            'total_tasks': total_tasks,
            'phases': num_phases,
            'complexity': complexity_level,
            'plan_mode_required': requires_plan_mode
        }

        self.log_policy_execution(
            'task-breakdown',
            'OK',
            f"Created {total_tasks} tasks across {num_phases} phases ({complexity_level})",
            metadata
        )

    def log_daemon_activity(
        self,
        daemon_name: str,
        activity: str,
        status: str
    ):
        """
        Log daemon activity

        Args:
            daemon_name: Name of daemon
            activity: What activity occurred
            status: Status (RUNNING, SLEEP, CHECK, OK, SKIP)
        """
        self.log_policy_execution(
            daemon_name,
            status,
            activity
        )

    def get_recent_logs(self, hours: int = 1, limit: int = 100) -> list:
        """
        Get recent log entries

        Args:
            hours: How many hours back to look
            limit: Maximum number of entries to return

        Returns:
            List of log entry dicts
        """
        from datetime import timedelta

        if not self.log_file.exists():
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)
        entries = []

        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        # Parse line format: [timestamp] policy | status | message
                        if line.startswith('['):
                            timestamp_end = line.index(']')
                            timestamp_str = line[1:timestamp_end]
                            timestamp = datetime.fromisoformat(timestamp_str)

                            # Skip if too old
                            if timestamp < cutoff_time:
                                continue

                            # Extract parts
                            rest = line[timestamp_end + 1:].strip()
                            parts = rest.split('|')

                            if len(parts) >= 3:
                                policy = parts[0].strip()
                                status = parts[1].strip()
                                message = parts[2].strip()

                                entries.append({
                                    'timestamp': timestamp.isoformat(),
                                    'policy': policy,
                                    'status': status,
                                    'message': message
                                })

                                if len(entries) >= limit:
                                    break

                    except (ValueError, IndexError):
                        continue

        except Exception as e:
            self.logger.error(f"Error reading recent logs: {e}")

        return list(reversed(entries))  # Most recent first


# Global instance
_enforcement_logger = None


def get_enforcement_logger() -> EnforcementLogger:
    """Get or create the global enforcement logger instance"""
    global _enforcement_logger
    if _enforcement_logger is None:
        _enforcement_logger = EnforcementLogger()
    return _enforcement_logger


# Convenience functions
def log_policy(policy_name: str, status: str, message: str, metadata: dict = None):
    """Convenience function to log policy execution"""
    logger = get_enforcement_logger()
    logger.log_policy_execution(policy_name, status, message, metadata)


def log_step(step_number: int, step_name: str, status: str, details: dict = None):
    """Convenience function to log step execution"""
    logger = get_enforcement_logger()
    logger.log_step_execution(step_number, step_name, status, details)


def log_tool(tool_name: str, operation: str, status: str, details: dict = None):
    """Convenience function to log tool usage"""
    logger = get_enforcement_logger()
    logger.log_tool_usage(tool_name, operation, status, details)


# Test the logger
if __name__ == '__main__':
    print("=" * 70)
    print("ENFORCEMENT LOGGER - TEST")
    print("=" * 70)
    print()

    logger = EnforcementLogger()

    # Test various log types
    print("[1] Testing policy execution log...")
    logger.log_policy_execution(
        'test-policy',
        'OK',
        'Test policy executed successfully',
        {'test': True, 'value': 123}
    )

    print("[2] Testing step execution log...")
    logger.log_step_execution(
        0,
        'Prompt Generation',
        'COMPLETED',
        {'prompt_length': 500, 'examples_found': 5}
    )

    print("[3] Testing tool usage log...")
    logger.log_tool_usage(
        'Read',
        'Read file with offset/limit',
        'OPTIMIZED',
        {'file': 'test.py', 'saved_tokens': 5000}
    )

    print("[4] Testing model selection log...")
    logger.log_model_selection(
        'SONNET',
        8,
        'API Creation',
        'Task type matches SONNET capabilities'
    )

    print("[5] Testing task breakdown log...")
    logger.log_task_breakdown(
        12,
        3,
        'MODERATE',
        False
    )

    print()
    print("[6] Getting recent logs...")
    recent = logger.get_recent_logs(hours=1, limit=10)
    print(f"Found {len(recent)} recent entries:")
    for entry in recent[:5]:
        print(f"  [{entry['timestamp']}] {entry['policy']} | {entry['status']} | {entry['message']}")

    print()
    print("=" * 70)
    print("[SUCCESS] Enforcement Logger is working!")
    print("=" * 70)
    print(f"\nLog file: {logger.log_file}")
    print("Dashboard can now parse these logs for real-time tracking.")

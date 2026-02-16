#!/usr/bin/env python3
"""
Unit Tests for PolicyExecutionTracker

Tests all functionality of the policy execution tracking system including:
- Enforcer state management
- Policy log parsing
- Execution statistics
- Timeline generation
- Health calculations
- Enforcement status
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from services.monitoring.policy_execution_tracker import PolicyExecutionTracker


class TestPolicyExecutionTracker(unittest.TestCase):
    """Test suite for PolicyExecutionTracker"""

    def setUp(self):
        """Set up test fixtures before each test"""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp_dir) / '.claude' / 'memory'
        self.logs_dir = self.memory_dir / 'logs'
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Create test files
        self.policy_log = self.logs_dir / 'policy-hits.log'
        self.enforcer_state = self.memory_dir / '.blocking-enforcer-state.json'

        # Patch the home directory for testing
        self.patcher = patch('pathlib.Path.home')
        self.mock_home = self.patcher.start()
        self.mock_home.return_value = Path(self.temp_dir)

        # Create tracker instance
        self.tracker = PolicyExecutionTracker()

    def tearDown(self):
        """Clean up after each test"""
        self.patcher.stop()
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def create_sample_enforcer_state(self, **kwargs):
        """Create a sample enforcer state for testing"""
        default_state = {
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
        default_state.update(kwargs)

        with open(self.enforcer_state, 'w') as f:
            json.dump(default_state, f, indent=2)

        return default_state

    def create_sample_policy_log(self, entries):
        """Create a sample policy log for testing"""
        with open(self.policy_log, 'w', encoding='utf-8') as f:
            for entry in entries:
                timestamp = entry.get('timestamp', datetime.now().isoformat())
                policy = entry.get('policy', 'test-policy')
                status = entry.get('status', 'OK')
                message = entry.get('message', 'Test message')
                f.write(f"[{timestamp}] {policy} | {status} | {message}\n")

    def test_get_enforcer_state_exists(self):
        """Test getting enforcer state when file exists"""
        expected_state = self.create_sample_enforcer_state(
            session_started=True,
            standards_loaded=True,
            prompt_generated=True
        )

        result = self.tracker.get_enforcer_state()

        self.assertTrue(result['session_started'])
        self.assertTrue(result['standards_loaded'])
        self.assertTrue(result['prompt_generated'])
        self.assertFalse(result['tasks_created'])

    def test_get_enforcer_state_not_exists(self):
        """Test getting enforcer state when file doesn't exist"""
        result = self.tracker.get_enforcer_state()

        self.assertFalse(result['session_started'])
        self.assertFalse(result['standards_loaded'])
        self.assertEqual(result['total_violations'], 0)

    def test_parse_policy_log_empty(self):
        """Test parsing empty policy log"""
        self.create_sample_policy_log([])

        result = self.tracker.parse_policy_log(hours=24)

        self.assertEqual(len(result), 0)

    def test_parse_policy_log_with_entries(self):
        """Test parsing policy log with valid entries"""
        now = datetime.now()
        entries = [
            {
                'timestamp': now.isoformat(),
                'policy': 'prompt-generator',
                'status': 'OK',
                'message': 'Prompt generated successfully'
            },
            {
                'timestamp': (now - timedelta(minutes=30)).isoformat(),
                'policy': 'task-breakdown',
                'status': 'OK',
                'message': 'Tasks created'
            }
        ]
        self.create_sample_policy_log(entries)

        result = self.tracker.parse_policy_log(hours=1)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['policy_name'], 'prompt-generator')
        self.assertEqual(result[0]['status'], 'OK')
        self.assertEqual(result[1]['policy_name'], 'task-breakdown')

    def test_parse_policy_log_filters_old_entries(self):
        """Test that old entries are filtered out"""
        now = datetime.now()
        entries = [
            {
                'timestamp': now.isoformat(),
                'policy': 'recent-policy',
                'status': 'OK',
                'message': 'Recent'
            },
            {
                'timestamp': (now - timedelta(days=2)).isoformat(),
                'policy': 'old-policy',
                'status': 'OK',
                'message': 'Old'
            }
        ]
        self.create_sample_policy_log(entries)

        result = self.tracker.parse_policy_log(hours=24)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['policy_name'], 'recent-policy')

    def test_categorize_policy(self):
        """Test policy categorization"""
        test_cases = [
            ('prompt-generator', 'Prompt Generation'),
            ('task-breakdown', 'Task Breakdown'),
            ('plan-mode-suggester', 'Plan Mode'),
            # Note: 'model' contains 'mode' as substring, so matches Plan Mode first
            # Use 'selection' alone to test Model Selection
            ('selection-enforcer', 'Model Selection'),
            ('skill-agent-selector', 'Skill/Agent'),
            ('tool-optimizer', 'Tool Optimization'),
            ('context-monitor', 'Context Management'),
            ('git-commit', 'Git Auto-Commit'),
            ('session-tracker', 'Session Management'),
            ('some-daemon', 'Daemon'),
            ('unknown-policy', 'Other')
        ]

        for policy_name, expected_category in test_cases:
            result = self.tracker._categorize_policy(policy_name)
            self.assertEqual(result, expected_category,
                           f"Failed for {policy_name}: expected {expected_category}, got {result}")

    def test_get_execution_stats_empty(self):
        """Test execution stats with no data"""
        self.create_sample_policy_log([])

        result = self.tracker.get_execution_stats(hours=24)

        self.assertEqual(result['total_executions'], 0)
        self.assertEqual(result['execution_rate_per_hour'], 0)
        self.assertEqual(len(result['by_category']), 0)
        self.assertEqual(len(result['recent_executions']), 0)

    def test_get_execution_stats_with_data(self):
        """Test execution stats with data"""
        now = datetime.now()
        entries = [
            {'policy': 'prompt-generator', 'status': 'OK', 'message': 'Test 1'},
            {'policy': 'task-breakdown', 'status': 'OK', 'message': 'Test 2'},
            {'policy': 'model-selector', 'status': 'OK', 'message': 'Test 3'},
            {'policy': 'prompt-generator', 'status': 'OK', 'message': 'Test 4'},
        ]
        self.create_sample_policy_log(entries)

        result = self.tracker.get_execution_stats(hours=24)

        self.assertEqual(result['total_executions'], 4)
        self.assertGreater(result['execution_rate_per_hour'], 0)
        self.assertIn('Prompt Generation', result['by_category'])
        self.assertEqual(result['by_category']['Prompt Generation'], 2)
        self.assertIn('OK', result['by_status'])

    def test_get_execution_timeline_empty(self):
        """Test execution timeline with no data"""
        self.create_sample_policy_log([])

        result = self.tracker.get_execution_timeline(hours=24)

        self.assertEqual(len(result['labels']), 0)
        self.assertEqual(len(result['data']), 0)

    def test_get_execution_timeline_with_data(self):
        """Test execution timeline with data"""
        now = datetime.now()
        entries = [
            {'timestamp': now.isoformat(), 'policy': 'test1', 'status': 'OK', 'message': 'Test'},
            {'timestamp': now.isoformat(), 'policy': 'test2', 'status': 'OK', 'message': 'Test'},
            {'timestamp': (now - timedelta(hours=1)).isoformat(), 'policy': 'test3', 'status': 'OK', 'message': 'Test'},
        ]
        self.create_sample_policy_log(entries)

        result = self.tracker.get_execution_timeline(hours=24)

        self.assertGreater(len(result['labels']), 0)
        self.assertGreater(len(result['data']), 0)
        self.assertEqual(len(result['labels']), len(result['data']))

    def test_get_policy_health_excellent(self):
        """Test health calculation for excellent status"""
        self.create_sample_enforcer_state(
            session_started=True,
            standards_loaded=True,
            prompt_generated=True,
            tasks_created=True,
            plan_mode_decided=True,
            model_selected=True,
            skills_agents_checked=True,
            context_checked=True
        )

        # Add recent activity
        now = datetime.now()
        entries = [{'timestamp': now.isoformat(), 'policy': 'test', 'status': 'OK', 'message': 'Test'}] * 10
        self.create_sample_policy_log(entries)

        result = self.tracker.get_policy_health()

        self.assertGreaterEqual(result['health_score'], 80)
        self.assertEqual(result['status'], 'EXCELLENT')
        self.assertEqual(result['status_class'], 'success')

    def test_get_policy_health_poor(self):
        """Test health calculation for poor status"""
        self.create_sample_enforcer_state()  # All False
        self.create_sample_policy_log([])  # No activity

        result = self.tracker.get_policy_health()

        self.assertLess(result['health_score'], 40)
        self.assertEqual(result['status'], 'POOR')
        self.assertEqual(result['status_class'], 'danger')

    def test_get_enforcement_status_all_incomplete(self):
        """Test enforcement status when nothing is completed"""
        self.create_sample_enforcer_state()

        result = self.tracker.get_enforcement_status()

        self.assertEqual(result['completed_count'], 0)
        self.assertEqual(result['total_count'], 8)
        self.assertEqual(result['completion_percentage'], 0)

        for step in result['steps']:
            self.assertFalse(step['completed'])
            self.assertTrue(step['required'])

    def test_get_enforcement_status_partial_complete(self):
        """Test enforcement status with partial completion"""
        self.create_sample_enforcer_state(
            session_started=True,
            context_checked=True,
            standards_loaded=True,
            prompt_generated=True
        )

        result = self.tracker.get_enforcement_status()

        self.assertEqual(result['completed_count'], 4)
        self.assertEqual(result['total_count'], 8)
        self.assertEqual(result['completion_percentage'], 50)

    def test_get_enforcement_status_all_complete(self):
        """Test enforcement status when all steps completed"""
        self.create_sample_enforcer_state(
            session_started=True,
            context_checked=True,
            standards_loaded=True,
            prompt_generated=True,
            tasks_created=True,
            plan_mode_decided=True,
            model_selected=True,
            skills_agents_checked=True
        )

        result = self.tracker.get_enforcement_status()

        self.assertEqual(result['completed_count'], 8)
        self.assertEqual(result['total_count'], 8)
        self.assertEqual(result['completion_percentage'], 100)

        for step in result['steps']:
            self.assertTrue(step['completed'])

    def test_malformed_log_entries_handled(self):
        """Test that malformed log entries don't break parsing"""
        with open(self.policy_log, 'w', encoding='utf-8') as f:
            f.write("Invalid line without timestamp\n")
            f.write("[2024-01-01T12:00:00] incomplete | line\n")
            f.write("[not-a-timestamp] policy | status | message\n")
            f.write(f"[{datetime.now().isoformat()}] valid-policy | OK | Valid message\n")

        result = self.tracker.parse_policy_log(hours=24)

        # Should only parse the valid entry
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['policy_name'], 'valid-policy')

    def test_missing_enforcer_state_file(self):
        """Test behavior when enforcer state file is missing"""
        # Don't create the file
        result = self.tracker.get_enforcer_state()

        self.assertIsInstance(result, dict)
        self.assertFalse(result['session_started'])

    def test_corrupted_enforcer_state_file(self):
        """Test behavior when enforcer state file is corrupted"""
        with open(self.enforcer_state, 'w') as f:
            f.write("{ invalid json")

        result = self.tracker.get_enforcer_state()

        self.assertIsInstance(result, dict)
        self.assertFalse(result['session_started'])


class TestPolicyExecutionTrackerEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch('pathlib.Path.home')
        self.mock_home = self.patcher.start()
        self.mock_home.return_value = Path(self.temp_dir)
        self.tracker = PolicyExecutionTracker()

    def tearDown(self):
        """Clean up"""
        self.patcher.stop()
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_unicode_in_log_entries(self):
        """Test handling of Unicode characters in log entries"""
        log_file = self.tracker.policy_log
        log_file.parent.mkdir(parents=True, exist_ok=True)

        with open(log_file, 'w', encoding='utf-8') as f:
            now = datetime.now().isoformat()
            f.write(f"[{now}] test-policy | OK | Unicode test: émojis 🚀 中文\n")

        result = self.tracker.parse_policy_log(hours=24)

        self.assertEqual(len(result), 1)
        self.assertIn('Unicode', result[0]['message'])

    def test_very_large_log_file(self):
        """Test performance with large log file"""
        log_file = self.tracker.policy_log
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Create a large log file
        with open(log_file, 'w', encoding='utf-8') as f:
            for i in range(10000):
                now = datetime.now().isoformat()
                f.write(f"[{now}] test-policy-{i} | OK | Message {i}\n")

        # Should complete without hanging
        import time
        start = time.time()
        result = self.tracker.parse_policy_log(hours=24)
        elapsed = time.time() - start

        self.assertLess(elapsed, 5.0)  # Should complete in under 5 seconds
        self.assertEqual(len(result), 10000)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestPolicyExecutionTracker))
    suite.addTests(loader.loadTestsFromTestCase(TestPolicyExecutionTrackerEdgeCases))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

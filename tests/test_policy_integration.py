#!/usr/bin/env python3
"""
Policy Integration Tester - Simulates policy executions to test dashboard tracking

This script simulates the execution of all major automation policies
and verifies that the dashboard correctly tracks and displays them.
"""

import subprocess
import time
import json
from pathlib import Path
from datetime import datetime
import sys

# Fix encoding for Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class PolicyIntegrationTester:
    """Test policy execution integration"""

    def __init__(self):
        self.memory_path = Path.home() / '.claude' / 'memory'
        self.test_results = []

    def log(self, message, status='INFO'):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] [{status}] {message}")

    def run_script(self, script_path, args=None):
        """Run a policy enforcement script"""
        try:
            cmd = ['python', str(script_path)]
            if args:
                cmd.extend(args)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )

            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Timeout expired',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }

    def test_prompt_generation(self):
        """Test Step 0: Prompt Generation"""
        self.log("Testing Prompt Generation (Step 0)...")

        script = self.memory_path / '03-execution-system' / '00-prompt-generation' / 'prompt-generator.py'

        if not script.exists():
            self.log(f"Script not found: {script}", "ERROR")
            return False

        result = self.run_script(script, ['Test feature creation'])

        if result['success'] or 'STRUCTURED PROMPT' in result['stdout']:
            self.log("Prompt Generation: PASS", "SUCCESS")
            self.test_results.append(('Prompt Generation', True))
            return True
        else:
            self.log(f"Prompt Generation: FAIL - {result['stderr']}", "ERROR")
            self.test_results.append(('Prompt Generation', False))
            return False

    def test_task_breakdown(self):
        """Test Step 1: Task Breakdown"""
        self.log("Testing Task Breakdown (Step 1)...")

        script = self.memory_path / '03-execution-system' / '01-task-breakdown' / 'task-phase-enforcer.py'

        if not script.exists():
            self.log(f"Script not found: {script}", "ERROR")
            return False

        result = self.run_script(script, ['--analyze', 'Test task'])

        if result['success'] or 'COMPLEXITY' in result['stdout']:
            self.log("Task Breakdown: PASS", "SUCCESS")
            self.test_results.append(('Task Breakdown', True))
            return True
        else:
            self.log(f"Task Breakdown: FAIL - {result['stderr']}", "ERROR")
            self.test_results.append(('Task Breakdown', False))
            return False

    def test_model_selection(self):
        """Test Step 4: Model Selection"""
        self.log("Testing Model Selection (Step 4)...")

        script = self.memory_path / '03-execution-system' / '04-model-selection' / 'intelligent-model-selector.py'

        if not script.exists():
            self.log(f"Script not found: {script}", "ERROR")
            return False

        result = self.run_script(script)

        if result['success'] or 'MODEL' in result['stdout'] or 'Recommended' in result['stdout']:
            self.log("Model Selection: PASS", "SUCCESS")
            self.test_results.append(('Model Selection', True))
            return True
        else:
            self.log(f"Model Selection: FAIL - {result['stderr']}", "ERROR")
            self.test_results.append(('Model Selection', False))
            return False

    def verify_policy_logs(self):
        """Verify policy-hits.log was updated"""
        self.log("Verifying policy-hits.log was updated...")

        log_file = self.memory_path / 'logs' / 'policy-hits.log'

        if not log_file.exists():
            self.log("policy-hits.log does not exist", "ERROR")
            return False

        # Check if file was modified in the last minute
        mod_time = log_file.stat().st_mtime
        current_time = time.time()

        if (current_time - mod_time) < 120:  # 2 minutes
            self.log("policy-hits.log was recently updated: PASS", "SUCCESS")
            return True
        else:
            self.log("policy-hits.log was NOT recently updated", "WARNING")
            return False

    def verify_dashboard_api(self):
        """Verify dashboard API endpoints respond"""
        self.log("Verifying dashboard API endpoints...")

        try:
            # Test policy execution tracker
            from pathlib import Path
            import sys

            # Add src to path
            insight_src = Path(__file__).parent.parent / 'src'
            sys.path.insert(0, str(insight_src))

            from services.monitoring.policy_execution_tracker import PolicyExecutionTracker

            tracker = PolicyExecutionTracker()

            # Test methods
            stats = tracker.get_execution_stats(hours=1)
            health = tracker.get_policy_health()
            status = tracker.get_enforcement_status()

            self.log(f"API Stats: {stats['total_executions']} executions found", "INFO")
            self.log(f"API Health: {health['health_score']}/100 ({health['status']})", "INFO")
            self.log(f"API Status: {status['completed_count']}/{status['total_count']} steps", "INFO")

            self.log("Dashboard API: PASS", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Dashboard API: FAIL - {e}", "ERROR")
            return False

    def run_all_tests(self):
        """Run all integration tests"""
        print("=" * 70)
        print("POLICY INTEGRATION TESTER - Starting...")
        print("=" * 70)
        print()

        # Run tests
        tests = [
            self.test_prompt_generation,
            self.test_task_breakdown,
            self.test_model_selection,
            self.verify_policy_logs,
            self.verify_dashboard_api
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                result = test()
                if result:
                    passed += 1
                else:
                    failed += 1
                time.sleep(1)  # Brief pause between tests
            except Exception as e:
                self.log(f"Test exception: {e}", "ERROR")
                failed += 1

            print()

        # Summary
        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"PASSED: {passed}")
        print(f"FAILED: {failed}")
        print(f"TOTAL:  {passed + failed}")
        print()

        if self.test_results:
            print("Results by Policy:")
            for name, success in self.test_results:
                status = "[PASS]" if success else "[FAIL]"
                print(f"  {status} {name}")

        print()
        print("=" * 70)

        if failed == 0:
            print("[SUCCESS] All tests passed! Policy integration is working.")
        else:
            print(f"[WARNING] {failed} test(s) failed. Check output above.")

        print("=" * 70)

        return failed == 0


if __name__ == '__main__':
    tester = PolicyIntegrationTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

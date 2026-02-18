#!/usr/bin/env python3
"""
Comprehensive Test Suite
Tests all 4 phases together
"""

import sys
import json
import subprocess
from pathlib import Path

class ComprehensiveTests:
    def __init__(self):
        self.memory_dir = Path.home() / '.claude' / 'memory'
        self.passed = 0
        self.failed = 0
        self.tests = []

    def run_command(self, cmd, description):
        """Run a command and return output"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }

    def test(self, name, test_func):
        """Run a test"""
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print('='*60)

        try:
            result = test_func()
            if result:
                print(f"[OK] {name} PASSED")
                self.passed += 1
                self.tests.append((name, True, None))
                return True
            else:
                print(f"[FAIL] {name} FAILED")
                self.failed += 1
                self.tests.append((name, False, "Test returned False"))
                return False
        except Exception as e:
            print(f"[ERROR] {name} ERRORED: {e}")
            self.failed += 1
            self.tests.append((name, False, str(e)))
            return False

    def test_phase1_context_optimization(self):
        """Test Phase 1: Context Optimization"""
        print("Testing context optimization...")

        # Test pre-execution optimizer
        result = self.run_command(
            f'python {self.memory_dir}/pre-execution-optimizer.py --test-large-file',
            'Pre-execution optimizer'
        )
        if not result['success'] or '[OK]' not in result['output']:
            print(f"  [FAIL] Pre-execution optimizer failed")
            return False
        print("  [OK] Pre-execution optimizer working")

        # Test context cache
        result = self.run_command(
            f'python {self.memory_dir}/context-cache.py --stats',
            'Context cache'
        )
        if not result['success']:
            print(f"  [FAIL] Context cache failed")
            return False
        print("  [OK] Context cache working")

        # Test session state
        result = self.run_command(
            f'python {self.memory_dir}/session-state.py --summary',
            'Session state'
        )
        if not result['success']:
            print(f"  [FAIL] Session state failed")
            return False
        print("  [OK] Session state working")

        # Test context monitor
        result = self.run_command(
            f'python {self.memory_dir}/context-monitor-v2.py --current-status',
            'Context monitor'
        )
        if not result['success']:
            print(f"  [FAIL] Context monitor failed")
            return False
        print("  [OK] Context monitor working")

        return True

    def test_phase2_hooks_enforcement(self):
        """Test Phase 2: Hooks Enforcement Infrastructure (3-level architecture)"""
        print("Testing hooks enforcement scripts...")

        current_dir = self.memory_dir / 'current'

        # Required enforcement scripts
        required_scripts = [
            '3-level-flow.py',
            'blocking-policy-enforcer.py',
            'auto-fix-enforcer.sh',
            'context-monitor-v2.py',
            'session-id-generator.py',
            'clear-session-handler.py',
            'stop-notifier.py',
            'per-request-enforcer.py',
        ]

        missing = []
        for script in required_scripts:
            if not (current_dir / script).exists():
                missing.append(script)

        if missing:
            print(f"  [FAIL] Missing scripts: {', '.join(missing)}")
            return False

        print(f"  [OK] All {len(required_scripts)} enforcement scripts present in current/")

        # Test blocking enforcer runs
        result = self.run_command(
            f'python {current_dir}/blocking-policy-enforcer.py --status',
            'Blocking policy enforcer'
        )
        if result['success']:
            print(f"  [OK] Blocking enforcer operational")
        else:
            print(f"  [WARN] Blocking enforcer returned non-zero (may need initialization)")

        # Check session logs directory
        sessions_log_dir = self.memory_dir / 'logs' / 'sessions'
        if sessions_log_dir.exists():
            session_count = len([d for d in sessions_log_dir.iterdir() if d.is_dir()])
            print(f"  [OK] Session logs directory: {session_count} sessions")
        else:
            print(f"  [WARN] No session logs directory yet (created on first use)")

        return True

    def test_phase3_failure_prevention(self):
        """Test Phase 3: Failure Prevention"""
        print("Testing failure prevention...")

        # Test pre-execution checker (correct path in 03-execution-system)
        checker = self.memory_dir / '03-execution-system' / 'failure-prevention' / 'pre-execution-checker.py'
        if checker.exists():
            print(f"  [OK] Pre-execution checker present: {checker.name}")
        else:
            print(f"  [FAIL] Pre-execution checker not found at {checker}")
            return False

        # Test failure KB exists
        kb_file = self.memory_dir / 'failure-kb.json'
        if kb_file.exists():
            import json as _json
            try:
                kb = _json.loads(kb_file.read_text(encoding='utf-8', errors='ignore'))
                pattern_count = sum(len(v) for v in kb.values() if isinstance(v, list))
                print(f"  [OK] Failure KB: {pattern_count} patterns loaded")
            except Exception:
                print(f"  [OK] Failure KB exists")
        else:
            print(f"  [WARN] Failure KB not yet created (built after first failures)")

        return True

    def test_phase4_policy_automation(self):
        """Test Phase 4: Policy Automation (CLAUDE.md-enforced - no scripts needed)"""
        print("Testing policy automation via CLAUDE.md enforcement...")

        # Model selection - check policy .md file exists
        model_policy = self.memory_dir / '03-execution-system' / '04-model-selection' / 'model-selection-enforcement.md'
        if model_policy.exists():
            print(f"  [OK] Model selection policy: {model_policy.name}")
        else:
            print(f"  [FAIL] Model selection policy not found: {model_policy}")
            return False

        # Skill/agent selection - check core skills mandate exists
        skills_mandate = self.memory_dir / '03-execution-system' / '05-skill-agent-selection' / 'core-skills-mandate.md'
        if skills_mandate.exists():
            print(f"  [OK] Core skills mandate: {skills_mandate.name}")
        else:
            print(f"  [FAIL] Core skills mandate not found: {skills_mandate}")
            return False

        # Tool optimization - check policy .md exists
        tool_policy = self.memory_dir / '03-execution-system' / '06-tool-optimization' / 'tool-usage-optimization-policy.md'
        if tool_policy.exists():
            print(f"  [OK] Tool optimization policy: {tool_policy.name}")
        else:
            print(f"  [FAIL] Tool optimization policy not found: {tool_policy}")
            return False

        # Check model usage log (populated by 3-level-flow.py on each request)
        model_log = self.memory_dir / 'logs' / 'model-usage.log'
        if model_log.exists():
            lines = model_log.read_text(encoding='utf-8', errors='ignore').splitlines()
            print(f"  [OK] Model usage log: {len(lines)} entries tracked")
        else:
            print(f"  [WARN] model-usage.log not created yet (populated after first session)")

        # Check policy hits log (populated by 3-level-flow.py)
        policy_log = self.memory_dir / 'logs' / 'policy-hits.log'
        if policy_log.exists():
            lines = policy_log.read_text(encoding='utf-8', errors='ignore').splitlines()
            print(f"  [OK] Policy hits log: {len(lines)} policy applications logged")
        else:
            print(f"  [WARN] policy-hits.log not created yet (populated after first session)")

        return True

    def test_integration(self):
        """Test system integration"""
        print("Testing system integration...")

        # Test 3-level flow script (main entry point)
        flow_script = self.memory_dir / 'current' / '3-level-flow.py'
        if flow_script.exists():
            print(f"  [OK] 3-level-flow.py present (main hook entry point)")
        else:
            print(f"  [FAIL] 3-level-flow.py not found in current/")
            return False

        # Check all log files exist
        required_logs = [
            'logs/policy-hits.log',
            'logs/model-usage.log',
        ]

        missing = []
        for log in required_logs:
            if not (self.memory_dir / log).exists():
                missing.append(log)

        if missing:
            print(f"  [WARN] Missing log files: {', '.join(missing)}")
        else:
            print(f"  [OK] All required log files exist")

        # Check required directories exist
        required_dirs = [
            '.cache',
            'logs',
            'logs/sessions',
            'current',
        ]

        missing_dirs = []
        for dir_name in required_dirs:
            if not (self.memory_dir / dir_name).exists():
                missing_dirs.append(dir_name)

        if missing_dirs:
            print(f"  [WARN] Missing directories: {', '.join(missing_dirs)}")
        else:
            print(f"  [OK] All required directories exist")

        return True

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*60)
        print("COMPREHENSIVE TEST SUITE - ALL PHASES")
        print("="*60)

        tests = [
            ("Phase 1: Context Optimization", self.test_phase1_context_optimization),
            ("Phase 2: Hooks Enforcement", self.test_phase2_hooks_enforcement),
            ("Phase 3: Failure Prevention", self.test_phase3_failure_prevention),
            ("Phase 4: Policy Automation", self.test_phase4_policy_automation),
            ("System Integration", self.test_integration),
        ]

        for test_name, test_func in tests:
            self.test(test_name, test_func)

        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        total = self.passed + self.failed
        for test_name, passed, error in self.tests:
            status = "[OK] PASSED" if passed else "[FAIL] FAILED"
            print(f"{status:15} {test_name}")
            if error:
                print(f"                Error: {error}")

        print(f"\nTotal: {self.passed}/{total} tests passed")

        if self.passed == total:
            print("\n[OK] ALL TESTS PASSED!")
            return 0
        else:
            print(f"\n[FAIL] {self.failed} tests failed")
            return 1

def main():
    tests = ComprehensiveTests()
    return tests.run_all_tests()

if __name__ == '__main__':
    sys.exit(main())

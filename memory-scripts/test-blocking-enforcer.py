#!/usr/bin/env python3
"""
Test script for Blocking Policy Enforcer

This script verifies that the blocking enforcer ACTUALLY blocks work
when policies are violated.
"""

import sys
import os
from pathlib import Path

# Add memory path to sys.path
memory_path = Path.home() / '.claude' / 'memory'
sys.path.insert(0, str(memory_path))

import importlib.util
spec = importlib.util.spec_from_file_location("blocking_policy_enforcer", str(memory_path / "blocking-policy-enforcer.py"))
blocking_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blocking_module)
BlockingPolicyEnforcer = blocking_module.BlockingPolicyEnforcer
BlockingPolicyError = blocking_module.BlockingPolicyError


def test_session_start_blocking():
    """Test that work is BLOCKED without session start"""
    print("\n" + "="*70)
    print("TEST 1: Session Start Blocking")
    print("="*70)

    enforcer = BlockingPolicyEnforcer()
    # Reset state to simulate fresh session
    enforcer.state['session_started'] = False
    enforcer._save_state()

    try:
        enforcer.enforce_session_start()
        print("❌ FAIL: Should have raised BlockingPolicyError!")
        return False
    except BlockingPolicyError as e:
        print("✅ PASS: Correctly blocked work without session start")
        print(f"   Error message length: {len(str(e))} chars")
        return True


def test_task_breakdown_blocking():
    """Test that work is BLOCKED without task breakdown"""
    print("\n" + "="*70)
    print("TEST 2: Task Breakdown Blocking")
    print("="*70)

    enforcer = BlockingPolicyEnforcer()
    enforcer.state['tasks_created'] = False
    enforcer._save_state()

    try:
        enforcer.enforce_task_breakdown("Test user request")
        print("❌ FAIL: Should have raised BlockingPolicyError!")
        return False
    except BlockingPolicyError as e:
        print("✅ PASS: Correctly blocked work without task breakdown")
        print(f"   Error message length: {len(str(e))} chars")
        return True


def test_standards_loading_blocking():
    """Test that work is BLOCKED without standards loading"""
    print("\n" + "="*70)
    print("TEST 3: Standards Loading Blocking")
    print("="*70)

    enforcer = BlockingPolicyEnforcer()
    enforcer.state['standards_loaded'] = False
    enforcer._save_state()

    try:
        enforcer.enforce_standards_loading()
        print("❌ FAIL: Should have raised BlockingPolicyError!")
        return False
    except BlockingPolicyError as e:
        print("✅ PASS: Correctly blocked work without standards loading")
        print(f"   Error message length: {len(str(e))} chars")
        return True


def test_prompt_generation_blocking():
    """Test that work is BLOCKED without prompt generation"""
    print("\n" + "="*70)
    print("TEST 4: Prompt Generation Blocking")
    print("="*70)

    enforcer = BlockingPolicyEnforcer()
    enforcer.state['prompt_generated'] = False
    enforcer._save_state()

    try:
        enforcer.enforce_prompt_generation("Test user request")
        print("❌ FAIL: Should have raised BlockingPolicyError!")
        return False
    except BlockingPolicyError as e:
        print("✅ PASS: Correctly blocked work without prompt generation")
        print(f"   Error message length: {len(str(e))} chars")
        return True


def test_context_checking_blocking():
    """Test that work is BLOCKED without context checking"""
    print("\n" + "="*70)
    print("TEST 5: Context Checking Blocking")
    print("="*70)

    enforcer = BlockingPolicyEnforcer()
    enforcer.state['context_checked'] = False
    enforcer._save_state()

    try:
        enforcer.enforce_context_management()
        print("❌ FAIL: Should have raised BlockingPolicyError!")
        return False
    except BlockingPolicyError as e:
        print("✅ PASS: Correctly blocked work without context checking")
        print(f"   Error message length: {len(str(e))} chars")
        return True


def test_full_enforcement_all_violations():
    """Test that enforce_all() blocks when ANY policy is violated"""
    print("\n" + "="*70)
    print("TEST 6: Full Enforcement (All Violations)")
    print("="*70)

    enforcer = BlockingPolicyEnforcer()
    # Reset all to simulate violations
    enforcer.state['session_started'] = False
    enforcer.state['standards_loaded'] = False
    enforcer.state['context_checked'] = False
    enforcer._save_state()

    try:
        enforcer.enforce_all("Test request")
        print("❌ FAIL: Should have raised BlockingPolicyError!")
        return False
    except BlockingPolicyError as e:
        print("✅ PASS: Correctly blocked on first violation (session start)")
        return True


def test_state_persistence():
    """Test that state is persisted across instances"""
    print("\n" + "="*70)
    print("TEST 7: State Persistence")
    print("="*70)

    # Create first enforcer and mark session started
    enforcer1 = BlockingPolicyEnforcer()
    enforcer1.mark_session_started()

    # Create second enforcer and check state
    enforcer2 = BlockingPolicyEnforcer()
    if enforcer2.state.get('session_started'):
        print("✅ PASS: State persisted across instances")
        return True
    else:
        print("❌ FAIL: State not persisted")
        return False


def test_violation_logging():
    """Test that violations are logged"""
    print("\n" + "="*70)
    print("TEST 8: Violation Logging")
    print("="*70)

    enforcer = BlockingPolicyEnforcer()
    enforcer.state['session_started'] = False
    enforcer._save_state()

    initial_violations = enforcer.state.get('total_violations', 0)

    try:
        enforcer.enforce_session_start()
    except BlockingPolicyError:
        pass

    # Create new instance to reload state
    enforcer2 = BlockingPolicyEnforcer()
    new_violations = enforcer2.state.get('total_violations', 0)

    if new_violations > initial_violations:
        print(f"✅ PASS: Violation logged (count: {new_violations})")
        return True
    else:
        print("❌ FAIL: Violation not logged")
        return False


def test_status_report():
    """Test status report generation"""
    print("\n" + "="*70)
    print("TEST 9: Status Report Generation")
    print("="*70)

    enforcer = BlockingPolicyEnforcer()
    report = enforcer.get_status_report()

    if "BLOCKING POLICY ENFORCER" in report and "LAYER 1" in report:
        print("✅ PASS: Status report generated successfully")
        print("\n" + report)
        return True
    else:
        print("❌ FAIL: Status report malformed")
        return False


def run_all_tests():
    """Run all tests and report results"""
    print("\n")
    print("┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
    print("┃   BLOCKING POLICY ENFORCER - COMPREHENSIVE TEST SUITE            ┃")
    print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")

    tests = [
        ("Session Start Blocking", test_session_start_blocking),
        ("Task Breakdown Blocking", test_task_breakdown_blocking),
        ("Standards Loading Blocking", test_standards_loading_blocking),
        ("Prompt Generation Blocking", test_prompt_generation_blocking),
        ("Context Checking Blocking", test_context_checking_blocking),
        ("Full Enforcement Blocking", test_full_enforcement_all_violations),
        ("State Persistence", test_state_persistence),
        ("Violation Logging", test_violation_logging),
        ("Status Report", test_status_report),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ EXCEPTION in {name}: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print("\n" + "="*70)
    print(f"TOTAL: {passed}/{total} tests passed ({passed*100//total}%)")
    print("="*70 + "\n")

    if passed == total:
        print("🎉 ALL TESTS PASSED! Blocking enforcer is working correctly! 🎉\n")
        return 0
    else:
        print(f"⚠️  {total - passed} test(s) failed. Please review the blocking enforcer.\n")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())

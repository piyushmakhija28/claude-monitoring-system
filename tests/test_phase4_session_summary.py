#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 4 Test: Session Summary + Policy Execution Timeline Verification

Tests the complete integration of:
1. Policy tracking data (flow-trace.json)
2. Session summary manager loading policy data
3. Markdown template rendering with policy timeline

This test validates that the policy execution timeline displays beautifully
in session reports with proper formatting and data aggregation.
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Ensure we can import the modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

def create_test_session_dir():
    """Create temporary session directory structure."""
    temp_dir = Path(tempfile.gettempdir()) / 'claude_test_phase4'
    temp_dir.mkdir(exist_ok=True)

    session_dir = temp_dir / 'sessions'
    session_dir.mkdir(exist_ok=True)

    logs_dir = temp_dir / 'logs' / 'sessions'
    logs_dir.mkdir(parents=True, exist_ok=True)

    return temp_dir, session_dir, logs_dir

def create_mock_flow_trace(logs_dir, session_id):
    """Create a realistic flow-trace.json with sample policy execution data."""
    session_log_dir = logs_dir / session_id
    session_log_dir.mkdir(parents=True, exist_ok=True)

    base_time = datetime.now() - timedelta(hours=1)

    flow_trace = {
        "session_id": session_id,
        "started_at": (base_time).isoformat(),
        "checkpoint_count": 5,
        "all_policies_executed": [
            {
                "name": "auto-fix-enforcer",
                "duration_ms": 245,
                "decision": "All 7 checks passed",
                "timestamp": (base_time + timedelta(seconds=1)).isoformat(),
                "type": "Hook"
            },
            {
                "name": "session-pruning-policy",
                "duration_ms": 89,
                "decision": "Context at 72%, cleanup not needed",
                "timestamp": (base_time + timedelta(seconds=2)).isoformat(),
                "type": "Policy Script"
            },
            {
                "name": "session-chaining-policy",
                "duration_ms": 56,
                "decision": "Archived 2 old sessions",
                "timestamp": (base_time + timedelta(seconds=3)).isoformat(),
                "type": "Policy Script"
            },
            {
                "name": "user-preferences-policy",
                "duration_ms": 123,
                "decision": "Loaded 8 user preferences",
                "timestamp": (base_time + timedelta(seconds=4)).isoformat(),
                "type": "Policy Script"
            },
            {
                "name": "common-standards-policy",
                "duration_ms": 178,
                "decision": "Applied 15 standards rules",
                "timestamp": (base_time + timedelta(seconds=5)).isoformat(),
                "type": "Policy Script"
            },
            {
                "name": "prompt-generation-policy",
                "duration_ms": 445,
                "decision": "Generated enhanced prompt with policy context",
                "timestamp": (base_time + timedelta(seconds=6)).isoformat(),
                "type": "Policy Script"
            },
            {
                "name": "intelligent-model-selection-policy",
                "duration_ms": 67,
                "decision": "Selected SONNET for complexity 12",
                "timestamp": (base_time + timedelta(seconds=7)).isoformat(),
                "type": "Policy Script"
            },
            {
                "name": "tool-usage-optimization-policy",
                "duration_ms": 92,
                "decision": "Optimized 3 tool calls",
                "timestamp": (base_time + timedelta(seconds=8)).isoformat(),
                "type": "Policy Script"
            },
        ],
        "decisions_timeline": [
            {"policy": "auto-fix-enforcer", "decision": "All 7 checks passed"},
            {"policy": "session-pruning-policy", "decision": "Context safe, no cleanup"},
            {"policy": "prompt-generation-policy", "decision": "Enhanced prompt generated"},
            {"policy": "intelligent-model-selection-policy", "decision": "SONNET selected"},
        ]
    }

    trace_file = session_log_dir / 'flow-trace.json'
    with open(trace_file, 'w', encoding='utf-8') as f:
        json.dump(flow_trace, f, indent=2)

    return trace_file

def create_mock_session_json(session_dir, session_id):
    """Create mock session.json metadata file."""
    session_file = session_dir / f'{session_id}.json'

    base_time = datetime.now() - timedelta(hours=1)

    session_data = {
        "session_id": session_id,
        "created_at": base_time.isoformat(),
        "description": "Phase 4 integration test session",
        "flow_runs": 5,
        "messages_count": 8,
        "context_usage_percent": 72,
        "last_updated": datetime.now().isoformat()
    }

    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2)

    return session_file

def test_policy_timeline_rendering():
    """Test the complete flow: flow-trace.json -> session summary -> markdown."""
    print("\n" + "="*70)
    print("PHASE 4 TEST: Session Summary + Policy Execution Timeline")
    print("="*70 + "\n")

    # Setup test directories
    temp_dir, session_dir, logs_dir = create_test_session_dir()
    session_id = "TEST-SESSION-20260305-PHASE4"

    print(f"[1/5] Creating test session structure...")
    print(f"  Session ID: {session_id}")
    print(f"  Temp dir: {temp_dir}")

    # Create mock data
    print(f"\n[2/5] Creating mock flow-trace.json with 8 policy executions...")
    flow_trace_file = create_mock_flow_trace(logs_dir, session_id)
    print(f"  Created: {flow_trace_file}")

    print(f"\n[3/5] Creating mock session.json...")
    session_file = create_mock_session_json(session_dir, session_id)
    print(f"  Created: {session_file}")

    # Patch session-summary-manager to use our test directories
    print(f"\n[4/5] Loading session-summary-manager and patching paths...")
    try:
        # Add scripts directory to path for direct imports
        sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
        import session_summary_manager as ssm

        # Patch the LOGS_DIR and SESSIONS_DIR
        original_logs_dir = ssm.LOGS_DIR
        original_sessions_dir = ssm.SESSIONS_DIR

        ssm.LOGS_DIR = logs_dir
        ssm.SESSIONS_DIR = session_dir

        print(f"  Patched LOGS_DIR: {logs_dir}")
        print(f"  Patched SESSIONS_DIR: {session_dir}")

        # Call finalize to generate summary
        print(f"\n[5/5] Calling finalize() to generate session summary...")
        summary_data = ssm.finalize(session_id)

        print(f"\n" + "="*70)
        print("SUMMARY DATA LOADED:")
        print("="*70)

        # Print policy execution summary
        policy_summary = summary_data.get("policy_execution_summary", {})
        if policy_summary:
            print(f"\nPolicy Execution Summary:")
            print(f"  Total Policies: {policy_summary.get('total_policies', 0)}")
            print(f"  Total Duration: {policy_summary.get('total_duration_ms', 0)}ms")
            print(f"  Decisions Recorded: {policy_summary.get('decisions_count', 0)}")

            slowest = policy_summary.get('slowest_policies', [])
            if slowest:
                print(f"  Slowest Policy: {slowest[0].get('name', 'N/A')} ({slowest[0].get('duration_ms', 0)}ms)")

            fastest = policy_summary.get('fastest_policies', [])
            if fastest:
                print(f"  Fastest Policy: {fastest[0].get('name', 'N/A')} ({fastest[0].get('duration_ms', 0)}ms)")

        # Print all policies
        all_policies = summary_data.get("all_policies_executed", [])
        if all_policies:
            print(f"\nAll Policies Executed ({len(all_policies)}):")
            for i, p in enumerate(all_policies, 1):
                print(f"  {i}. {p.get('name', 'unknown')} - {p.get('duration_ms', 0)}ms - {p.get('decision', '')[:40]}...")

        # Generate and display markdown
        print(f"\n" + "="*70)
        print("GENERATED MARKDOWN (Policy Timeline Section):")
        print("="*70 + "\n")

        markdown = ssm._generate_markdown(summary_data)

        # Extract and display only the policy timeline section
        if "## Policy Execution Timeline" in markdown:
            timeline_start = markdown.find("## Policy Execution Timeline")
            timeline_end = markdown.find("---", timeline_start + 50)
            if timeline_end == -1:
                timeline_end = markdown.find("## TL;DR", timeline_start)

            if timeline_end > timeline_start:
                timeline_section = markdown[timeline_start:timeline_end].strip()
            else:
                timeline_section = markdown[timeline_start:].strip()

            print(timeline_section)
        else:
            print("[WARN] Policy timeline section not found in markdown")

        # Verify structure
        print(f"\n" + "="*70)
        print("VERIFICATION:")
        print("="*70)

        checks = [
            ("Policy execution summary loaded", policy_summary.get('total_policies', 0) > 0),
            ("All policies captured", len(all_policies) == 8),
            ("Policy timeline in markdown", "## Policy Execution Timeline" in markdown),
            ("Policy table present", "| Policy | Duration | Decision | Type |" in markdown),
            ("Execution statistics present", "### Execution Statistics" in markdown),
            ("Slowest policy identified", slowest and slowest[0].get('name') == 'prompt-generation-policy'),
            ("Decisions timeline present", "### Policy Decisions Timeline" in markdown),
        ]

        passed = 0
        for check_name, result in checks:
            status = "[PASS]" if result else "[FAIL]"
            print(f"  {status} {check_name}")
            if result:
                passed += 1

        print(f"\nResult: {passed}/{len(checks)} checks passed")

        if passed == len(checks):
            print("\n*** PHASE 4 TEST PASSED ***")
            return True
        else:
            print("\n*** PHASE 4 TEST FAILED - Some checks did not pass ***")
            return False

    except Exception as e:
        print(f"\n*** PHASE 4 TEST ERROR: {e} ***")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore original paths
        try:
            ssm.LOGS_DIR = original_logs_dir
            ssm.SESSIONS_DIR = original_sessions_dir
        except:
            pass

if __name__ == '__main__':
    success = test_policy_timeline_rendering()
    sys.exit(0 if success else 1)

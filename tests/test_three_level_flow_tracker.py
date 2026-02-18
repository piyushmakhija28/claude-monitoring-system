#!/usr/bin/env python3
"""
Unit Tests for ThreeLevelFlowTracker

Tests all functionality including:
- Session directory discovery
- Session parsing (all 5 log files)
- flow-trace.json enrichment
- Aggregated stats (get_flow_stats)
- Latest execution retrieval (fast path + fallback)
- Build session from trace (no log files)
- Policy hits counting
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def _make_tracker(temp_dir):
    """Create a ThreeLevelFlowTracker pointing at temp_dir as home."""
    with patch('pathlib.Path.home', return_value=Path(temp_dir)):
        from services.monitoring.three_level_flow_tracker import ThreeLevelFlowTracker
        tracker = ThreeLevelFlowTracker()
    return tracker


def _create_session_dir(sessions_dir, session_id, files=None):
    """Helper: create a session directory with optional log files."""
    session_dir = sessions_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    if files:
        for filename, content in files.items():
            (session_dir / filename).write_text(content, encoding='utf-8')
    return session_dir


class TestGetSessionDirs(unittest.TestCase):
    """Tests for get_session_dirs()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_returns_empty_when_no_sessions(self):
        dirs = self.tracker.get_session_dirs()
        self.assertEqual(dirs, [])

    def test_returns_session_dirs(self):
        _create_session_dir(self.sessions_dir, 'SESSION-20260218-100000-AAAA')
        _create_session_dir(self.sessions_dir, 'SESSION-20260218-110000-BBBB')
        dirs = self.tracker.get_session_dirs()
        self.assertEqual(len(dirs), 2)

    def test_limit_is_respected(self):
        for i in range(5):
            _create_session_dir(self.sessions_dir, f'SESSION-2026021{i}-120000-CCCC')
        dirs = self.tracker.get_session_dirs(limit=3)
        self.assertLessEqual(len(dirs), 3)

    def test_returns_empty_when_dir_missing(self):
        # Remove sessions dir
        import shutil
        shutil.rmtree(self.sessions_dir)
        dirs = self.tracker.get_session_dirs()
        self.assertEqual(dirs, [])


class TestParseSessionStart(unittest.TestCase):
    """Tests for _parse_session_start() via parse_session()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_parse_session_start_with_valid_log(self):
        content = (
            "Session ID: SESSION-20260218-100000-AAAA\n"
            "Started: 2026-02-18T10:00:00\n"
            "Mode: summary\n"
            "User Prompt: Fix the bug\n"
        )
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-20260218-100000-AAAA',
            {'00-session-start.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['session_id'], 'SESSION-20260218-100000-AAAA')
        self.assertEqual(result['mode'], 'summary')
        self.assertIn('2026-02-18', result['started'])
        self.assertEqual(result['user_prompt'], 'Fix the bug')

    def test_parse_session_missing_start_log(self):
        session_dir = _create_session_dir(self.sessions_dir, 'SESSION-EMPTY-001')
        result = self.tracker.parse_session(session_dir)
        # Should still return a dict with defaults
        self.assertIsInstance(result, dict)
        self.assertIn('session_id', result)

    def test_parse_session_returns_dict_on_error(self):
        session_dir = _create_session_dir(self.sessions_dir, 'SESSION-BAD-001')
        result = self.tracker.parse_session(session_dir)
        self.assertIsInstance(result, dict)


class TestParseLevelMinus1(unittest.TestCase):
    """Tests for _parse_level_minus_1() via parse_session()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_level_minus_1_pass_with_ok_keyword(self):
        content = "[1/7] Python availability: OK\n[OK] ALL SYSTEMS OPERATIONAL\n"
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-L1-PASS',
            {'01-level-minus-1.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['level_minus_1']['status'], 'PASS')

    def test_level_minus_1_fail_keyword(self):
        content = "[1/7] Python availability: FAIL\nSTATUS: FAIL\n"
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-L1-FAIL',
            {'01-level-minus-1.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['level_minus_1']['status'], 'FAIL')

    def test_level_minus_1_pass_with_success_keyword(self):
        content = "STATUS: SUCCESS\nAll checks passed\n"
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-L1-SUCCESS',
            {'01-level-minus-1.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['level_minus_1']['status'], 'PASS')


class TestParseLevel1(unittest.TestCase):
    """Tests for _parse_level_1() via parse_session()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_parses_context_percentage(self):
        content = "Current Usage: 75.5%\nSession ID: SESSION-20260218-100000-AAAA\n"
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-CTX',
            {'02-level-1-sync.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['level_1']['context_pct'], 75.5)
        self.assertEqual(result['level_1']['context_status'], 'YELLOW')

    def test_context_status_red_above_85(self):
        content = "Current Usage: 90.0%\n"
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-CTX-RED',
            {'02-level-1-sync.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['level_1']['context_status'], 'RED')

    def test_context_status_green_below_70(self):
        content = "Current Usage: 50.0%\n"
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-CTX-GREEN',
            {'02-level-1-sync.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['level_1']['context_status'], 'GREEN')


class TestParseLevel2(unittest.TestCase):
    """Tests for _parse_level_2() via parse_session()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_parses_standards_and_rules(self):
        content = "Standards Loaded: 14\nRules Loaded: 89\n"
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-L2',
            {'03-level-2-standards.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['level_2']['standards'], 14)
        self.assertEqual(result['level_2']['rules'], 89)
        self.assertEqual(result['level_2']['status'], 'OK')

    def test_missing_log_gives_none(self):
        session_dir = _create_session_dir(self.sessions_dir, 'SESSION-L2-MISS')
        result = self.tracker.parse_session(session_dir)
        self.assertIsNone(result['level_2']['standards'])
        self.assertEqual(result['level_2']['status'], 'unknown')


class TestParseLevel3(unittest.TestCase):
    """Tests for _parse_level_3() via parse_session()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_parses_all_key_fields(self):
        content = (
            "[3.0] Prompt Generation: Complexity=5, Type=Database\n"
            "[3.1] Task Breakdown: 3 tasks\n"
            "[3.2] Plan Mode: NOT required (complexity 5)\n"
            "[3.3] Context Check: 80.0%\n"
            "[3.4] Model Selection: SONNET\n"
            "[3.5] Skill/Agent: java-spring-boot-microservices\n"
            "[3.6] Tool Optimization: Ready\n"
            "Duration: 12.5s\n"
            "[OK] COMPLETE\n"
        )
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-L3',
            {'04-level-3-execution.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        l3 = result['level_3']
        self.assertEqual(l3['complexity'], 5)
        self.assertEqual(l3['task_type'], 'Database')
        self.assertEqual(l3['tasks'], 3)
        self.assertFalse(l3['plan_required'])
        self.assertEqual(l3['context_pct'], 80.0)
        self.assertEqual(l3['model'], 'SONNET')
        self.assertEqual(l3['skill_agent'], 'java-spring-boot-microservices')
        self.assertEqual(l3['duration'], 12.5)
        self.assertEqual(l3['status'], 'OK')

    def test_plan_required_true(self):
        content = "[3.2] Plan Mode: required (complexity 20)\n"
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-PLAN-REQ',
            {'04-level-3-execution.log': content}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertTrue(result['level_3']['plan_required'])


class TestOverallStatus(unittest.TestCase):
    """Tests for overall_status derivation in parse_session()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_success_when_pass_and_ok(self):
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-SUCCESS',
            {
                '01-level-minus-1.log': '[OK] ALL SYSTEMS OPERATIONAL\n',
                '04-level-3-execution.log': '[OK] COMPLETE\n',
            }
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['overall_status'], 'success')

    def test_failed_when_level_minus_1_fails(self):
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-FAILED',
            {'01-level-minus-1.log': 'STATUS: FAIL\n'}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertEqual(result['overall_status'], 'failed')


class TestParseFlowTraceJson(unittest.TestCase):
    """Tests for _parse_flow_trace_json() via parse_session()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def _make_trace(self):
        return {
            'status': 'COMPLETED',
            'meta': {
                'session_id': 'SESSION-TRACE-001',
                'flow_version': '3.0.0',
                'duration_seconds': 8.5,
                'flow_start': '2026-02-18T10:00:00',
                'mode': 'summary'
            },
            'user_input': {'prompt': 'Create a new service'},
            'final_decision': {
                'model': 'HAIKU',
                'complexity': 3,
                'task_type': 'Bug Fix',
                'task_count': 2,
                'plan_mode': False,
                'context_pct': 80.0,
                'skill_or_agent': 'spring-boot-microservices',
                'tech_stack': ['flask', 'spring-boot'],
                'supplementary_skills': ['docker'],
                'execution_mode': 'sequential',
                'model_reason': 'Simple task (<5) - Haiku sufficient',
                'standards_active': 14,
                'rules_active': 89,
            },
            'pipeline': [
                {
                    'step': 'LEVEL_MINUS_1',
                    'policy_output': {'status': 'SUCCESS', 'checks': {'python': 'OK'}}
                },
                {
                    'step': 'LEVEL_3_STEP_3_5',
                    'policy_output': {
                        'selected_type': 'agent',
                        'supplementary_skills': ['docker']
                    }
                }
            ]
        }

    def test_enriches_from_trace_json(self):
        trace = self._make_trace()
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-TRACE-001',
            {'flow-trace.json': json.dumps(trace)}
        )
        result = self.tracker.parse_session(session_dir)

        self.assertTrue(result['has_trace_json'])
        self.assertEqual(result['flow_version'], '3.0.0')
        self.assertIn('flask', result['tech_stack'])
        self.assertEqual(result['execution_mode'], 'sequential')
        self.assertEqual(result['agent_type'], 'agent')
        self.assertEqual(result['level_3']['model'], 'HAIKU')
        self.assertEqual(result['level_3']['complexity'], 3)
        self.assertEqual(result['level_minus_1']['status'], 'PASS')
        self.assertEqual(result['user_prompt'], 'Create a new service')

    def test_missing_trace_json_is_ok(self):
        session_dir = _create_session_dir(self.sessions_dir, 'SESSION-NO-TRACE')
        result = self.tracker.parse_session(session_dir)
        self.assertFalse(result['has_trace_json'])

    def test_corrupt_trace_json_is_ignored(self):
        session_dir = _create_session_dir(
            self.sessions_dir, 'SESSION-BAD-TRACE',
            {'flow-trace.json': 'NOT VALID JSON {{{{'}
        )
        result = self.tracker.parse_session(session_dir)
        self.assertFalse(result['has_trace_json'])


class TestBuildSessionFromTrace(unittest.TestCase):
    """Tests for _build_session_from_trace()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def _make_trace(self, status='COMPLETED'):
        return {
            'status': status,
            'meta': {
                'session_id': 'SESSION-BUILD-001',
                'flow_version': '3.0.0',
                'duration_seconds': 5.0,
                'flow_start': '2026-02-18T09:00:00',
                'mode': 'summary',
            },
            'user_input': {'prompt': 'Test prompt'},
            'final_decision': {
                'model_selected': 'SONNET',
                'complexity': 7,
                'task_type': 'Feature',
                'task_count': 4,
                'plan_mode': True,
                'context_pct': 60.0,
                'skill_or_agent': 'devops-engineer',
                'tech_stack': ['angular'],
                'supplementary_skills': ['kubernetes'],
                'execution_mode': 'parallel',
                'model_reason': 'Complex task',
                'standards_active': 14,
                'rules_active': 89,
            },
            'pipeline': [
                {
                    'step': 'LEVEL_MINUS_1',
                    'policy_output': {'status': 'PASS'}
                },
                {
                    'step': 'LEVEL_3_STEP_3_5',
                    'policy_output': {'selected_type': 'agent', 'supplementary_skills': ['kubernetes']}
                }
            ]
        }

    def test_builds_correct_session_from_trace(self):
        trace = self._make_trace()
        result = self.tracker._build_session_from_trace(trace)

        self.assertEqual(result['session_id'], 'SESSION-BUILD-001')
        self.assertEqual(result['user_prompt'], 'Test prompt')
        self.assertEqual(result['overall_status'], 'success')
        self.assertEqual(result['level_3']['model'], 'SONNET')
        self.assertEqual(result['level_3']['complexity'], 7)
        self.assertTrue(result['level_3']['plan_required'])
        self.assertIn('angular', result['tech_stack'])
        self.assertEqual(result['agent_type'], 'agent')
        self.assertEqual(result['execution_mode'], 'parallel')
        self.assertTrue(result['has_trace_json'])
        self.assertEqual(result['duration'], 5.0)

    def test_partial_status_when_not_completed(self):
        trace = self._make_trace(status='IN_PROGRESS')
        result = self.tracker._build_session_from_trace(trace)
        self.assertEqual(result['overall_status'], 'partial')
        self.assertEqual(result['level_3']['status'], 'unknown')

    def test_level_minus_1_fail_in_pipeline(self):
        trace = self._make_trace()
        trace['pipeline'][0]['policy_output']['status'] = 'FAILED'
        result = self.tracker._build_session_from_trace(trace)
        self.assertEqual(result['level_minus_1']['status'], 'FAIL')

    def test_empty_pipeline(self):
        trace = self._make_trace()
        trace['pipeline'] = []
        result = self.tracker._build_session_from_trace(trace)
        self.assertIsNone(result['agent_type'])
        self.assertEqual(result['level_minus_1']['status'], 'PASS')  # default


class TestGetFlowStats(unittest.TestCase):
    """Tests for get_flow_stats()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_empty_stats_when_no_sessions(self):
        stats = self.tracker.get_flow_stats()
        self.assertEqual(stats['total_sessions'], 0)
        self.assertEqual(stats['successful'], 0)
        self.assertEqual(stats['failed'], 0)
        self.assertEqual(stats['success_rate'], 0)

    def test_stats_with_sessions(self):
        # Create 2 sessions: 1 success (PASS + OK), 1 fail
        _create_session_dir(
            self.sessions_dir, 'SESSION-S1',
            {
                '01-level-minus-1.log': '[OK] ALL SYSTEMS OPERATIONAL\n',
                '04-level-3-execution.log': (
                    '[3.0] Prompt Generation: Complexity=3, Type=BugFix\n'
                    '[3.4] Model Selection: HAIKU\n'
                    'Duration: 5.0s\n'
                    '[OK] COMPLETE\n'
                ),
                '02-level-1-sync.log': 'Current Usage: 50.0%\n',
                '03-level-2-standards.log': 'Standards Loaded: 14\nRules Loaded: 89\n',
            }
        )
        _create_session_dir(
            self.sessions_dir, 'SESSION-S2',
            {'01-level-minus-1.log': 'STATUS: FAIL\n'}
        )

        stats = self.tracker.get_flow_stats()

        self.assertEqual(stats['total_sessions'], 2)
        self.assertGreaterEqual(stats['successful'], 1)
        self.assertGreaterEqual(stats['failed'], 1)
        self.assertIn('HAIKU', stats['model_distribution'])
        self.assertEqual(stats['standards_info']['standards'], 14)
        self.assertEqual(stats['standards_info']['rules'], 89)
        self.assertIn('total_sessions', stats)
        self.assertIn('tech_stack_distribution', stats)
        self.assertIn('execution_mode_distribution', stats)
        self.assertIn('agent_type_distribution', stats)
        self.assertIn('sessions_with_trace_json', stats)

    def test_avg_complexity_calculation(self):
        _create_session_dir(
            self.sessions_dir, 'SESSION-COMP',
            {
                '04-level-3-execution.log':
                    '[3.0] Prompt Generation: Complexity=6, Type=Feature\n'
            }
        )
        stats = self.tracker.get_flow_stats()
        self.assertEqual(stats['avg_complexity'], 6.0)

    def test_plan_mode_rate(self):
        _create_session_dir(
            self.sessions_dir, 'SESSION-PLAN',
            {
                '04-level-3-execution.log':
                    '[3.2] Plan Mode: required (complexity 20)\n'
            }
        )
        stats = self.tracker.get_flow_stats()
        self.assertGreater(stats['plan_mode_rate'], 0)


class TestGetLatestExecution(unittest.TestCase):
    """Tests for get_latest_execution()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp) / '.claude' / 'memory'
        self.sessions_dir = self.memory_dir / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_returns_none_when_nothing_exists(self):
        result = self.tracker.get_latest_execution()
        self.assertIsNone(result)

    def test_fast_path_via_latest_trace(self):
        trace = {
            'status': 'COMPLETED',
            'meta': {'session_id': 'SESSION-LATEST-001', 'duration_seconds': 3.0},
            'user_input': {'prompt': 'Latest prompt'},
            'final_decision': {'model_selected': 'HAIKU', 'tech_stack': []},
            'pipeline': []
        }
        latest_trace_path = self.memory_dir / 'logs' / 'latest-flow-trace.json'
        latest_trace_path.parent.mkdir(parents=True, exist_ok=True)
        latest_trace_path.write_text(json.dumps(trace), encoding='utf-8')

        result = self.tracker.get_latest_execution()

        self.assertIsNotNone(result)
        self.assertIn('session_id', result)

    def test_fallback_to_session_dirs(self):
        _create_session_dir(
            self.sessions_dir, 'SESSION-FALLBACK',
            {'01-level-minus-1.log': '[OK] ALL SYSTEMS OPERATIONAL\n'}
        )
        result = self.tracker.get_latest_execution()
        self.assertIsNotNone(result)
        self.assertIn('session_id', result)

    def test_fast_path_uses_session_dir_if_exists(self):
        session_id = 'SESSION-FAST-PATH-001'
        trace = {
            'status': 'COMPLETED',
            'meta': {'session_id': session_id, 'duration_seconds': 2.0},
            'user_input': {'prompt': 'Test'},
            'final_decision': {'model_selected': 'HAIKU', 'tech_stack': []},
            'pipeline': []
        }
        # Write latest-flow-trace.json
        latest_trace_path = self.memory_dir / 'logs' / 'latest-flow-trace.json'
        latest_trace_path.parent.mkdir(parents=True, exist_ok=True)
        latest_trace_path.write_text(json.dumps(trace), encoding='utf-8')
        # Also create the session dir
        _create_session_dir(
            self.sessions_dir, session_id,
            {'01-level-minus-1.log': '[OK] ALL SYSTEMS OPERATIONAL\n'}
        )

        result = self.tracker.get_latest_execution()
        self.assertIsNotNone(result)
        self.assertIn('level_minus_1', result)


class TestGetPolicyHitsToday(unittest.TestCase):
    """Tests for get_policy_hits_today()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp) / '.claude' / 'memory'
        self.logs_dir = self.memory_dir / 'logs'
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_returns_zeros_when_no_log(self):
        result = self.tracker.get_policy_hits_today()
        self.assertEqual(result, {'total': 0, 'success': 0, 'failed': 0})

    def test_counts_recent_entries(self):
        now = datetime.now()
        recent = (now - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        old = (now - timedelta(hours=30)).strftime('%Y-%m-%d %H:%M:%S')

        log_content = (
            f"[{recent}] auto-fix-enforcer | ENFORCED | All OK\n"
            f"[{recent}] auto-fix-enforcer | SUCCESS | Completed\n"
            f"[{recent}] auto-fix-enforcer | FAIL | Something failed\n"
            f"[{old}] auto-fix-enforcer | ENFORCED | Old entry\n"
        )
        log_file = self.logs_dir / 'auto-enforcement.log'
        log_file.write_text(log_content, encoding='utf-8')

        result = self.tracker.get_policy_hits_today()
        self.assertEqual(result['total'], 3)
        self.assertEqual(result['success'], 2)
        self.assertEqual(result['failed'], 1)

    def test_skips_old_entries(self):
        old = (datetime.now() - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
        log_content = f"[{old}] old-enforcer | ENFORCED | Old entry\n"
        log_file = self.logs_dir / 'auto-enforcement.log'
        log_file.write_text(log_content, encoding='utf-8')

        result = self.tracker.get_policy_hits_today()
        self.assertEqual(result['total'], 0)

    def test_handles_malformed_lines_gracefully(self):
        log_content = "No timestamp here\n[INVALID]\nAnother bad line\n"
        log_file = self.logs_dir / 'auto-enforcement.log'
        log_file.write_text(log_content, encoding='utf-8')

        result = self.tracker.get_policy_hits_today()
        self.assertIsInstance(result, dict)
        self.assertIn('total', result)


class TestGetRecentSessions(unittest.TestCase):
    """Tests for get_recent_sessions()"""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp) / '.claude' / 'memory' / 'logs' / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = _make_tracker(self.temp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_returns_list(self):
        result = self.tracker.get_recent_sessions()
        self.assertIsInstance(result, list)

    def test_returns_parsed_sessions(self):
        _create_session_dir(
            self.sessions_dir, 'SESSION-REC-001',
            {'00-session-start.log': 'Session ID: SESSION-REC-001\nMode: verbose\n'}
        )
        result = self.tracker.get_recent_sessions(limit=5)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], dict)
        self.assertIn('session_id', result[0])
        self.assertIn('level_3', result[0])
        self.assertIn('overall_status', result[0])


if __name__ == '__main__':
    unittest.main()

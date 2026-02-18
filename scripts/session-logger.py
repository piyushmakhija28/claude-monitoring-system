#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session-Based Logger - Complete Transparency System
Creates detailed logs for each session with full thinking process
"""

import os
import sys
import json
import yaml
from datetime import datetime
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

class SessionLogger:
    def __init__(self, session_id=None):
        self.memory_dir = Path.home() / '.claude' / 'memory'
        self.logs_dir = self.memory_dir / 'logs' / 'sessions'

        # Get or create session ID
        if session_id:
            self.session_id = session_id
        else:
            self.session_id = self._get_current_session()

        # Create session log directory
        self.session_log_dir = self.logs_dir / self.session_id
        self.session_log_dir.mkdir(parents=True, exist_ok=True)

        print(f"[SESSION-LOGGER] Initialized: {self.session_id}")
        print(f"[SESSION-LOGGER] Log Directory: {self.session_log_dir}")

    def _get_current_session(self):
        """Get current session ID"""
        current_session_file = self.memory_dir / 'sessions' / 'current-session.json'
        if current_session_file.exists():
            with open(current_session_file, 'r') as f:
                data = json.load(f)
                return data.get('session_id', self._generate_session_id())
        return self._generate_session_id()

    def _generate_session_id(self):
        """Generate new session ID"""
        import random
        import string
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"SESSION-{timestamp}-{random_suffix}"

    def log_session_start(self, user_prompt):
        """Log session start"""
        log_file = self.session_log_dir / '00-session-start.log'
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"""
================================================================================
SESSION START
================================================================================
Session ID: {self.session_id}
Started: {datetime.now().isoformat()}
User Prompt: {user_prompt}

Status: [OK] Session initialized
Next: Auto-fix enforcement (Level -1)
================================================================================
""")

        # Save user prompt separately
        prompt_file = self.session_log_dir / 'user-prompt.txt'
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(user_prompt)

        print(f"[OK] Logged session start")

    def log_level_minus_1(self, result):
        """Log Level -1: Auto-fix enforcement"""
        log_file = self.session_log_dir / '01-level-minus-1.log'
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"""
================================================================================
LEVEL -1: AUTO-FIX ENFORCEMENT
================================================================================
Timestamp: {datetime.now().isoformat()}

Purpose: Check ALL systems before doing ANY work
Status: {result.get('status', 'UNKNOWN')}

Checks Performed:
  [1/6] Python availability: {result.get('python', 'UNKNOWN')}
  [2/6] Critical files: {result.get('files', 'UNKNOWN')}
  [3/6] Blocking enforcer: {result.get('enforcer', 'UNKNOWN')}
  [4/6] Session state: {result.get('session', 'UNKNOWN')}
  [5/6] Daemons: {result.get('daemons', 'UNKNOWN')}
  [6/6] Git repositories: {result.get('git', 'UNKNOWN')}

Result: {result.get('message', 'All systems operational')}
Next: Level 1 - Sync System
================================================================================
""")
        print(f"[OK] Logged Level -1")

    def log_level_1(self, context_pct, session_id):
        """Log Level 1: Sync system"""
        log_file = self.session_log_dir / '02-level-1-sync.log'
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"""
================================================================================
LEVEL 1: SYNC SYSTEM (FOUNDATION)
================================================================================
Timestamp: {datetime.now().isoformat()}

Purpose: Load context and session state

[Step 1.1] Context Management:
   Current Usage: {context_pct}%
   Status: {'[GREEN] GOOD' if context_pct < 70 else '[YELLOW] MODERATE' if context_pct < 85 else '[RED] HIGH'}
   Action: {'Standard operations' if context_pct < 70 else 'Apply optimizations' if context_pct < 85 else 'Aggressive optimization'}

[Step 1.2] Session Management:
   Session ID: {session_id}
   Format: SESSION-YYYYMMDD-HHMMSS-XXXX
   Tracking: All logs/commits reference this ID

Result: [OK] Sync system complete
Next: Level 2 - Standards System
================================================================================
""")
        print(f"[OK] Logged Level 1")

    def log_level_2(self, standards_count, rules_count):
        """Log Level 2: Standards system"""
        log_file = self.session_log_dir / '03-level-2-standards.log'
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"""
================================================================================
LEVEL 2: RULES/STANDARDS SYSTEM (MIDDLE LAYER)
================================================================================
Timestamp: {datetime.now().isoformat()}

Purpose: Load ALL coding standards BEFORE generating code

Standards Loaded: {standards_count}
Rules Loaded: {rules_count}

Standards include:
  - Java project structure rules
  - Package organization standards
  - Config Server patterns
  - Secret Management rules
  - Response format standards
  - Validation patterns
  - Database conventions
  - API design standards
  - Error handling rules
  - Common utility patterns

Result: [OK] All standards loaded and ready
Next: Level 3 - Execution System (12 steps)
================================================================================
""")
        print(f"[OK] Logged Level 2")

    def log_generated_prompt(self, prompt_data):
        """Log generated prompt from prompt policy"""
        prompt_file = self.session_log_dir / 'generated-prompt.yaml'
        with open(prompt_file, 'w', encoding='utf-8') as f:
            yaml.dump(prompt_data, f, default_flow_style=False, allow_unicode=True)
        print(f"[OK] Logged generated prompt")

    def log_thinking_process(self, thinking):
        """Log thinking process - what and WHY"""
        thinking_file = self.session_log_dir / 'thinking-process.md'
        with open(thinking_file, 'w', encoding='utf-8') as f:
            f.write(f"""
# Thinking Process for {self.session_id}

## User Request
{thinking.get('user_request', 'N/A')}

## Initial Analysis
{thinking.get('initial_analysis', 'N/A')}

## What I Need to Do
{thinking.get('what_to_do', 'N/A')}

## Why This Approach
{thinking.get('why_this_approach', 'N/A')}

## Information Needed
{thinking.get('information_needed', 'N/A')}

## Where to Find It
{thinking.get('where_to_find', 'N/A')}

## Potential Challenges
{thinking.get('challenges', 'N/A')}

## Expected Outcome
{thinking.get('expected_outcome', 'N/A')}

## Timestamp
{datetime.now().isoformat()}
""")
        print(f"[OK] Logged thinking process")

    def log_decisions(self, decisions):
        """Log all decisions made"""
        decisions_file = self.session_log_dir / 'decisions.yaml'
        with open(decisions_file, 'w', encoding='utf-8') as f:
            yaml.dump({
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                **decisions
            }, f, default_flow_style=False, allow_unicode=True)
        print(f"[OK] Logged decisions")

    def log_task_breakdown(self, tasks):
        """Log task breakdown"""
        tasks_file = self.session_log_dir / 'task-breakdown.yaml'
        with open(tasks_file, 'w', encoding='utf-8') as f:
            yaml.dump({
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'tasks': tasks
            }, f, default_flow_style=False, allow_unicode=True)
        print(f"[OK] Logged task breakdown")

    def log_tool_call(self, tool_name, parameters, result_summary):
        """Log tool calls"""
        tools_file = self.session_log_dir / 'tools-used.log'
        with open(tools_file, 'a', encoding='utf-8') as f:
            f.write(f"""
[{datetime.now().isoformat()}] {tool_name}
Parameters: {json.dumps(parameters, indent=2)}
Result: {result_summary}
---
""")
        print(f"[OK] Logged tool call: {tool_name}")

    def log_level_3_execution(self, execution_log):
        """Log Level 3: Complete execution with all 12 steps"""
        log_file = self.session_log_dir / '04-level-3-execution.log'
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(execution_log)
        print(f"[OK] Logged Level 3 execution")

    def create_session_summary(self):
        """Create complete session summary"""
        summary_file = self.session_log_dir / 'session-summary.md'

        # Read all logged data
        user_prompt = self._read_file('user-prompt.txt')

        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"""
# Session Summary: {self.session_id}

## Overview
- **Session ID:** {self.session_id}
- **Started:** {datetime.now().isoformat()}
- **User Prompt:** {user_prompt}

## 3-Level Architecture Flow

### Level -1: Auto-Fix Enforcement
{self._read_file('01-level-minus-1.log', 'See detailed log')}

### Level 1: Sync System
{self._read_file('02-level-1-sync.log', 'See detailed log')}

### Level 2: Standards System
{self._read_file('03-level-2-standards.log', 'See detailed log')}

### Level 3: Execution System
{self._read_file('04-level-3-execution.log', 'See detailed log')}

## Thinking Process
{self._read_file('thinking-process.md', 'No thinking logged')}

## Decisions Made
{self._read_file('decisions.yaml', 'No decisions logged')}

## Tasks Created
{self._read_file('task-breakdown.yaml', 'No tasks logged')}

## Tools Used
{self._read_file('tools-used.log', 'No tools logged')}

## Generated Prompt
{self._read_file('generated-prompt.yaml', 'No prompt logged')}

---

**Session Complete!** All logs available in: `{self.session_log_dir}`
""")
        print(f"[OK] Created session summary")

    def _read_file(self, filename, default=''):
        """Helper to read file content"""
        file_path = self.session_log_dir / filename
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        return default


# CLI Interface
if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Session-Based Logger')
    parser.add_argument('--session-id', help='Session ID (auto-detect if not provided)')
    parser.add_argument('--init', help='Initialize session with user prompt')
    parser.add_argument('--summary', action='store_true', help='Create session summary')
    parser.add_argument('--log-thinking', help='Log thinking process (JSON file)')
    parser.add_argument('--log-decisions', help='Log decisions (JSON file)')
    parser.add_argument('--log-level-minus-1', help='Log Level -1 results (JSON string)')
    parser.add_argument('--log-level-1', nargs=2, metavar=('CONTEXT_PCT', 'SESSION_ID'), help='Log Level 1 (context%, session_id)')
    parser.add_argument('--log-level-2', nargs=2, metavar=('STANDARDS', 'RULES'), help='Log Level 2 (standards_count, rules_count)')
    parser.add_argument('--log-level-3', help='Log Level 3 execution (text content)')

    args = parser.parse_args()

    logger = SessionLogger(session_id=args.session_id)

    if args.init:
        logger.log_session_start(args.init)
    elif args.summary:
        logger.create_session_summary()
    elif args.log_thinking:
        with open(args.log_thinking, 'r') as f:
            thinking = json.load(f)
        logger.log_thinking_process(thinking)
    elif args.log_decisions:
        with open(args.log_decisions, 'r') as f:
            decisions = json.load(f)
        logger.log_decisions(decisions)
    elif args.log_level_minus_1:
        result = json.loads(args.log_level_minus_1)
        logger.log_level_minus_1(result)
    elif args.log_level_1:
        context_pct = float(args.log_level_1[0])
        session_id = args.log_level_1[1]
        logger.log_level_1(context_pct, session_id)
    elif args.log_level_2:
        standards_count = int(args.log_level_2[0])
        rules_count = int(args.log_level_2[1])
        logger.log_level_2(standards_count, rules_count)
    elif args.log_level_3:
        logger.log_level_3_execution(args.log_level_3)
    else:
        print(f"[SESSION-LOGGER] Session: {logger.session_id}")
        print(f"[SESSION-LOGGER] Logs at: {logger.session_log_dir}")

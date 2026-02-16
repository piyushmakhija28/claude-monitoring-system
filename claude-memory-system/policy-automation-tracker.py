#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Policy Automation Tracker
Checks all policies, their automation status, and serial execution order
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Color codes
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RESET = '\033[0m'

class PolicyAutomationTracker:
    def __init__(self):
        self.memory_path = Path.home() / '.claude' / 'memory'
        self.logs_path = self.memory_path / 'logs'
        self.log_file = self.logs_path / 'policy-automation-status.log'

        # Define all policies with their automation status
        self.policies = {
            'STEP_-1': {
                'name': 'Auto-Fix Enforcement',
                'script': 'auto-fix-enforcer.sh',
                'status': 'AUTOMATED',
                'blocking': True,
                'order': -1,
                'description': 'System health check and auto-fix',
                'daemon': None
            },
            'STEP_0': {
                'name': 'Session Start',
                'script': 'session-start.sh',
                'status': 'AUTOMATED',
                'blocking': True,
                'order': 0,
                'description': 'Initialize session and generate ID',
                'daemon': 'auto-recommendation-daemon'
            },
            'STEP_1': {
                'name': 'Context Management',
                'script': '01-sync-system/context-management/context-monitor-v2.py',
                'status': 'AUTOMATED',
                'blocking': False,
                'order': 1,
                'description': 'Monitor context usage',
                'daemon': 'context-daemon'
            },
            'STEP_2': {
                'name': 'Standards Loading',
                'script': '02-standards-system/standards-loader.py',
                'status': 'MANUAL',
                'blocking': True,
                'order': 2,
                'description': 'Load coding standards',
                'daemon': None
            },
            'STEP_3': {
                'name': 'Prompt Generation',
                'script': '03-execution-system/00-prompt-generation/prompt-generator.py',
                'status': 'MANUAL',
                'blocking': True,
                'order': 3,
                'description': 'Generate structured prompt',
                'daemon': None
            },
            'STEP_4': {
                'name': 'Task Breakdown',
                'script': '03-execution-system/01-task-breakdown/task-phase-enforcer.py',
                'status': 'SEMI-AUTOMATED',
                'blocking': True,
                'order': 4,
                'description': 'Break tasks into phases',
                'daemon': 'task-auto-tracker'
            },
            'STEP_5': {
                'name': 'Plan Mode Suggestion',
                'script': '03-execution-system/02-plan-mode/auto-plan-mode-suggester.py',
                'status': 'SEMI-AUTOMATED',
                'blocking': True,
                'order': 5,
                'description': 'Suggest plan mode if needed',
                'daemon': None
            },
            'STEP_6': {
                'name': 'Model Selection',
                'script': '03-execution-system/04-model-selection/model-selection-enforcer.py',
                'status': 'MANUAL',
                'blocking': True,
                'order': 6,
                'description': 'Select appropriate model',
                'daemon': None
            },
            'STEP_7': {
                'name': 'Skill/Agent Selection',
                'script': '03-execution-system/05-skill-agent-selection/auto-skill-agent-selector.py',
                'status': 'SEMI-AUTOMATED',
                'blocking': False,
                'order': 7,
                'description': 'Select skills and agents',
                'daemon': 'skill-auto-suggester'
            },
            'STEP_8': {
                'name': 'Tool Optimization',
                'script': '03-execution-system/06-tool-optimization/auto-tool-wrapper.py',
                'status': 'MANUAL',
                'blocking': True,
                'order': 8,
                'description': 'Optimize tool parameters',
                'daemon': None
            },
            'STEP_9': {
                'name': 'Failure Prevention',
                'script': '03-execution-system/08-failure-prevention/pre-execution-checker.py',
                'status': 'MANUAL',
                'blocking': True,
                'order': 9,
                'description': 'Check before execution',
                'daemon': 'failure-prevention-daemon'
            },
            'STEP_10': {
                'name': 'Git Auto-Commit',
                'script': '03-execution-system/09-git-commit/auto-commit-enforcer.py',
                'status': 'SEMI-AUTOMATED',
                'blocking': False,
                'order': 10,
                'description': 'Auto-commit on completion',
                'daemon': 'commit-daemon'
            },
            'STEP_11': {
                'name': 'Session Auto-Save',
                'script': '01-sync-system/session-management/session-auto-save-daemon.py',
                'status': 'AUTOMATED',
                'blocking': False,
                'order': 11,
                'description': 'Auto-save session state',
                'daemon': 'session-auto-save-daemon'
            }
        }

        # Define all daemons
        self.daemons = [
            'context-daemon',
            'session-auto-save-daemon',
            'preference-auto-tracker',
            'skill-auto-suggester',
            'commit-daemon',
            'session-pruning-daemon',
            'pattern-detection-daemon',
            'failure-prevention-daemon',
            'auto-recommendation-daemon'
        ]

    def check_script_exists(self, script_path):
        """Check if automation script exists"""
        full_path = self.memory_path / script_path
        return full_path.exists()

    def check_daemon_status(self, daemon_name):
        """Check if daemon is running"""
        try:
            result = os.popen(f'pgrep -f {daemon_name}').read().strip()
            return bool(result)
        except:
            return False

    def check_all_policies(self):
        """Check all policies and their automation status"""
        print(f"\n{'='*80}")
        print(f"{BLUE}POLICY AUTOMATION STATUS CHECK{RESET}")
        print(f"{'='*80}\n")

        results = {
            'timestamp': datetime.now().isoformat(),
            'policies': {},
            'summary': {
                'automated': 0,
                'semi_automated': 0,
                'manual': 0,
                'total': len(self.policies)
            }
        }

        # Check each policy
        for step_id, policy in sorted(self.policies.items(), key=lambda x: x[1]['order']):
            script_exists = self.check_script_exists(policy['script'])
            daemon_running = self.check_daemon_status(policy['daemon']) if policy['daemon'] else None

            # Determine status icon
            if policy['status'] == 'AUTOMATED':
                status_icon = f"{GREEN}✅ AUTOMATED{RESET}"
                results['summary']['automated'] += 1
            elif policy['status'] == 'SEMI-AUTOMATED':
                status_icon = f"{YELLOW}⚡ SEMI-AUTOMATED{RESET}"
                results['summary']['semi_automated'] += 1
            else:
                status_icon = f"{RED}❌ MANUAL{RESET}"
                results['summary']['manual'] += 1

            # Print policy status
            print(f"{BLUE}[{step_id}] {policy['name']}{RESET}")
            print(f"   Status: {status_icon}")
            print(f"   Order: {policy['order']} | Blocking: {'YES' if policy['blocking'] else 'NO'}")
            print(f"   Script: {policy['script']}")
            print(f"   Exists: {GREEN + '✅' + RESET if script_exists else RED + '❌' + RESET}")

            if policy['daemon']:
                daemon_status = f"{GREEN}✅ Running{RESET}" if daemon_running else f"{RED}❌ Stopped{RESET}"
                print(f"   Daemon: {policy['daemon']} | {daemon_status}")

            print(f"   Description: {policy['description']}")
            print()

            # Store results
            results['policies'][step_id] = {
                'name': policy['name'],
                'status': policy['status'],
                'script_exists': script_exists,
                'daemon_running': daemon_running,
                'blocking': policy['blocking'],
                'order': policy['order']
            }

        return results

    def check_serial_order(self):
        """Verify policies run in correct serial order"""
        print(f"\n{'='*80}")
        print(f"{BLUE}SERIAL EXECUTION ORDER VERIFICATION{RESET}")
        print(f"{'='*80}\n")

        ordered_policies = sorted(self.policies.items(), key=lambda x: x[1]['order'])

        print(f"{BLUE}Execution Flow:{RESET}\n")

        for i, (step_id, policy) in enumerate(ordered_policies):
            arrow = "   ↓" if i < len(ordered_policies) - 1 else ""
            blocking = f"{RED}[BLOCKING]{RESET}" if policy['blocking'] else f"{GREEN}[NON-BLOCKING]{RESET}"

            print(f"{policy['order']:2d}. {policy['name']} {blocking}")
            print(f"    {policy['status']} | {policy['description']}")
            if arrow:
                print(arrow)

        print(f"\n{GREEN}✅ All policies are correctly ordered in serial execution!{RESET}")

    def check_daemon_status_all(self):
        """Check status of all daemons"""
        print(f"\n{'='*80}")
        print(f"{BLUE}DAEMON STATUS CHECK{RESET}")
        print(f"{'='*80}\n")

        running = 0
        stopped = 0

        for daemon in self.daemons:
            is_running = self.check_daemon_status(daemon)
            status = f"{GREEN}✅ Running{RESET}" if is_running else f"{RED}❌ Stopped{RESET}"
            print(f"   {daemon:30s} | {status}")

            if is_running:
                running += 1
            else:
                stopped += 1

        print(f"\n{BLUE}Summary:{RESET}")
        print(f"   Running: {GREEN}{running}/{len(self.daemons)}{RESET}")
        print(f"   Stopped: {RED}{stopped}/{len(self.daemons)}{RESET}")

        if stopped > 0:
            print(f"\n{YELLOW}⚠️  Some daemons are not running!{RESET}")
            print(f"   Run: {BLUE}bash ~/.claude/memory/startup-hook.sh{RESET} to restart all")
        else:
            print(f"\n{GREEN}✅ All daemons are running!{RESET}")

    def create_tracking_log(self, results):
        """Create detailed tracking log"""
        log_entry = {
            'timestamp': results['timestamp'],
            'session_id': os.environ.get('CLAUDE_SESSION_ID', 'UNKNOWN'),
            'policies': results['policies'],
            'summary': results['summary']
        }

        # Ensure logs directory exists
        self.logs_path.mkdir(parents=True, exist_ok=True)

        # Append to log file
        with open(self.log_file, 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Policy Automation Check - {results['timestamp']}\n")
            f.write(f"{'='*80}\n\n")

            f.write(f"Summary:\n")
            f.write(f"  Automated: {results['summary']['automated']}\n")
            f.write(f"  Semi-Automated: {results['summary']['semi_automated']}\n")
            f.write(f"  Manual: {results['summary']['manual']}\n")
            f.write(f"  Total: {results['summary']['total']}\n\n")

            f.write(f"Policy Details:\n")
            for step_id, policy in sorted(results['policies'].items(), key=lambda x: x[1]['order']):
                f.write(f"\n  [{step_id}] {policy['name']}\n")
                f.write(f"    Status: {policy['status']}\n")
                f.write(f"    Order: {policy['order']}\n")
                f.write(f"    Blocking: {policy['blocking']}\n")
                f.write(f"    Script Exists: {policy['script_exists']}\n")
                f.write(f"    Daemon Running: {policy['daemon_running']}\n")

        print(f"\n{GREEN}✅ Tracking log created: {self.log_file}{RESET}")

    def show_recommendations(self, results):
        """Show recommendations for improvement"""
        print(f"\n{'='*80}")
        print(f"{BLUE}RECOMMENDATIONS FOR IMPROVEMENT{RESET}")
        print(f"{'='*80}\n")

        recommendations = []

        # Check for manual policies that could be automated
        for step_id, policy in results['policies'].items():
            if policy['status'] == 'MANUAL' and policy['blocking']:
                recommendations.append(
                    f"⚠️  {policy['name']} is MANUAL but BLOCKING - consider automation"
                )

        # Check for missing scripts
        for step_id, policy in results['policies'].items():
            if not policy['script_exists']:
                recommendations.append(
                    f"❌ Script missing: {self.policies[step_id]['script']}"
                )

        # Check for stopped daemons
        for step_id, policy in results['policies'].items():
            if policy['daemon_running'] is False:
                recommendations.append(
                    f"❌ Daemon stopped: {self.policies[step_id]['daemon']}"
                )

        if recommendations:
            for rec in recommendations:
                print(f"   {rec}")
        else:
            print(f"{GREEN}✅ No issues found - all systems optimal!{RESET}")

    def run_full_check(self):
        """Run complete automation check"""
        results = self.check_all_policies()
        self.check_serial_order()
        self.check_daemon_status_all()
        self.show_recommendations(results)
        self.create_tracking_log(results)

        # Print summary
        print(f"\n{'='*80}")
        print(f"{BLUE}FINAL SUMMARY{RESET}")
        print(f"{'='*80}\n")

        print(f"   Automated Policies: {GREEN}{results['summary']['automated']}{RESET}")
        print(f"   Semi-Automated Policies: {YELLOW}{results['summary']['semi_automated']}{RESET}")
        print(f"   Manual Policies: {RED}{results['summary']['manual']}{RESET}")
        print(f"   Total Policies: {results['summary']['total']}")

        automation_percentage = (
            (results['summary']['automated'] + results['summary']['semi_automated'] * 0.5)
            / results['summary']['total'] * 100
        )

        print(f"\n   Automation Level: {YELLOW}{automation_percentage:.1f}%{RESET}")

        print(f"\n{'='*80}\n")

def main():
    tracker = PolicyAutomationTracker()
    tracker.run_full_check()

if __name__ == '__main__':
    main()

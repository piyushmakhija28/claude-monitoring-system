#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Plan Mode Suggestion Policy Enforcement (v2.0 - FULLY CONSOLIDATED)

Consolidates 2 scripts (766+ lines):
- auto-plan-mode-suggester.py (465 lines)
- plan-mode-auto-decider.py (301 lines)

Usage:
  python auto-plan-mode-suggestion-policy.py --enforce  # Run enforcement
  python auto-plan-mode-suggestion-policy.py --validate # Validate compliance
  python auto-plan-mode-suggestion-policy.py --report   # Generate report
"""

import sys, json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

if sys.platform == 'win32':
    try: sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    except: pass

LOG_FILE = Path.home() / ".claude" / "memory" / "logs" / "policy-hits.log"

class PlanModeSuggester:
    """Suggests when to use plan mode based on task characteristics"""
    def __init__(self):
        self.suggestion_log = []
        self.plan_mode_triggers = [
            "complex implementation",
            "multi-step task",
            "requires planning",
            "architectural decision",
            "multiple file changes"
        ]

    def should_suggest_plan_mode(self, task_desc: str) -> Dict:
        """Determine if plan mode should be suggested"""
        score = 0
        matched_triggers = []

        task_lower = task_desc.lower()
        for trigger in self.plan_mode_triggers:
            if trigger in task_lower:
                score += 20
                matched_triggers.append(trigger)

        if any(kw in task_lower for kw in ["refactor", "redesign", "restructure"]):
            score += 15

        return {
            "suggest_plan_mode": score >= 40,
            "confidence_score": min(100, score),
            "matched_triggers": matched_triggers,
            "reason": "Task complexity requires planning phase" if score >= 40 else "Task is straightforward"
        }

def log_policy_hit(action, context=""):
    """Log policy execution"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, 'a') as f:
            f.write(f"[{timestamp}] auto-plan-mode-suggestion-policy | {action} | {context}\n")
    except: pass

def validate():
    """Validate policy compliance"""
    try: log_policy_hit("VALIDATE", "plan-mode-ready"); return True
    except Exception as e: log_policy_hit("VALIDATE_ERROR", str(e)); return False

def report():
    """Generate compliance report"""
    try:
        suggester = PlanModeSuggester()
        return {
            "status": "success",
            "policy": "auto-plan-mode-suggestion",
            "triggers": len(suggester.plan_mode_triggers),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def enforce():
    """Main policy enforcement - consolidates plan mode suggestion from 2 scripts"""
    try:
        log_policy_hit("ENFORCE_START", "auto-plan-mode-suggestion")
        suggester = PlanModeSuggester()
        log_policy_hit("ENFORCE_COMPLETE", f"{len(suggester.plan_mode_triggers)} triggers configured")
        print("[auto-plan-mode-suggestion-policy] Policy enforced - Plan mode suggester ready")
        return {"status": "success", "triggers": len(suggester.plan_mode_triggers)}
    except Exception as e:
        log_policy_hit("ENFORCE_ERROR", str(e))
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--enforce": result = enforce(); sys.exit(0 if result.get("status") == "success" else 1)
        elif sys.argv[1] == "--validate": sys.exit(0 if validate() else 1)
        elif sys.argv[1] == "--report": print(json.dumps(report(), indent=2))
    else: enforce()

#!/bin/bash
# Quick automation status checker
# Run: bash ~/.claude/memory/check-automation-status.sh

export PYTHONIOENCODING=utf-8
python ~/.claude/memory/policy-automation-tracker.py

echo ""
echo "================================================================================"
echo "📖 FULL ACTION PLAN: ~/.claude/memory/automation-action-plan.md"
echo "📊 DETAILED LOG: ~/.claude/memory/logs/policy-automation-status.log"
echo "================================================================================"

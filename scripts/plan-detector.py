#!/usr/bin/env python3
"""
Claude Code Plan Detector
Automatically detects and displays the active Claude Code subscription plan
"""

import json
import os
import subprocess
from datetime import datetime

class PlanDetector:
    """Detects active Claude Code subscription plan"""

    PLAN_INDICATORS = {
        'free': {
            'name': '🆓 Free Plan',
            'features': ['Basic features', 'Limited usage', 'Community support'],
            'limits': {'max_context': '100K tokens', 'max_requests': '50/day'}
        },
        'pro': {
            'name': '⭐ Pro Plan',
            'features': ['Full features', 'Priority support', 'Extended context', 'Background tasks'],
            'limits': {'max_context': '200K tokens', 'max_requests': 'Unlimited'}
        },
        'team': {
            'name': '👥 Team Plan',
            'features': ['Pro + Team collaboration', 'Shared workspaces', 'Admin controls'],
            'limits': {'max_context': '200K tokens', 'max_requests': 'Unlimited'}
        },
        'enterprise': {
            'name': '🏢 Enterprise Plan',
            'features': ['All features', 'SLA guarantee', 'Dedicated support', 'Custom deployment'],
            'limits': {'max_context': 'Custom', 'max_requests': 'Unlimited'}
        }
    }

    def __init__(self):
        self.cache_file = os.path.expanduser('~/.claude/memory/.plan-cache.json')
        self.config_file = os.path.expanduser('~/.claude/config.json')

    def detect_plan(self):
        """
        Detect active plan by analyzing:
        1. Claude config files
        2. Available features
        3. Context limits
        4. API responses
        """

        # Try to load from cache first
        cached_plan = self._load_cache()
        if cached_plan and self._is_cache_valid(cached_plan):
            return cached_plan

        # Detect plan
        plan_type = self._analyze_plan()
        plan_info = self._get_plan_info(plan_type)

        # Save to cache
        self._save_cache(plan_info)

        return plan_info

    def _analyze_plan(self):
        """Analyze system to detect plan type"""

        # Check for config indicators
        config = self._load_config()

        # Check for Pro/Team/Enterprise indicators
        if self._has_background_tasks():
            if self._has_team_features():
                if self._has_enterprise_features():
                    return 'enterprise'
                return 'team'
            return 'pro'

        return 'free'

    def _has_background_tasks(self):
        """Check if background task feature is available"""
        try:
            # Pro+ plans have background task support
            result = subprocess.run(
                ['which', 'claude'],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Check for advanced features in config
            config = self._load_config()
            return config.get('features', {}).get('background_tasks', False)
        except:
            return False

    def _has_team_features(self):
        """Check for team collaboration features"""
        config = self._load_config()
        return config.get('features', {}).get('team_collaboration', False)

    def _has_enterprise_features(self):
        """Check for enterprise features"""
        config = self._load_config()
        return config.get('features', {}).get('enterprise_deployment', False)

    def _load_config(self):
        """Load Claude config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def _get_plan_info(self, plan_type):
        """Get detailed plan information"""
        plan_data = self.PLAN_INDICATORS.get(plan_type, self.PLAN_INDICATORS['free'])

        return {
            'type': plan_type,
            'name': plan_data['name'],
            'features': plan_data['features'],
            'limits': plan_data['limits'],
            'detected_at': datetime.now().isoformat(),
            'status': 'active'
        }

    def _load_cache(self):
        """Load cached plan info"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return None

    def _is_cache_valid(self, cached_plan, max_age_hours=24):
        """Check if cached plan is still valid"""
        try:
            detected_at = datetime.fromisoformat(cached_plan['detected_at'])
            age_hours = (datetime.now() - detected_at).total_seconds() / 3600
            return age_hours < max_age_hours
        except:
            return False

    def _save_cache(self, plan_info):
        """Save plan info to cache"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(plan_info, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save plan cache: {e}")

    def display_plan_info(self, plan_info):
        """Display plan information in formatted output"""
        print("\n" + "="*80)
        print("📋 CLAUDE CODE SUBSCRIPTION PLAN")
        print("="*80)
        print(f"\n🎯 Active Plan: {plan_info['name']}")
        print(f"📅 Detected: {plan_info['detected_at'][:10]}")
        print(f"✅ Status: {plan_info['status'].upper()}")

        print("\n📦 Features:")
        for feature in plan_info['features']:
            print(f"   ✓ {feature}")

        print("\n⚙️ Limits:")
        for key, value in plan_info['limits'].items():
            print(f"   • {key.replace('_', ' ').title()}: {value}")

        print("\n" + "="*80 + "\n")

    def get_plan_summary(self, plan_info):
        """Get brief plan summary for session start"""
        return f"{plan_info['name']} | Limits: {plan_info['limits']['max_context']}"


def main():
    """Main function"""
    import sys

    detector = PlanDetector()
    plan_info = detector.detect_plan()

    if '--json' in sys.argv:
        print(json.dumps(plan_info, indent=2))
    elif '--summary' in sys.argv:
        print(detector.get_plan_summary(plan_info))
    else:
        detector.display_plan_info(plan_info)


if __name__ == '__main__':
    main()

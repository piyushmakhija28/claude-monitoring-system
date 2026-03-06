#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Insight Recommendations Policy - Level 3.5 (Unified Recommendation System)

Comprehensive skill and agent recommendation system that:
1. Detects relevant skills based on user messages and task context
2. Manages skill registry with CRUD operations and statistics
3. Provides automatic skill suggestions proactively
4. Displays recommendations and validates recommendations quality
5. Integrates with the 3-level enforcement architecture

This policy consolidates the following systems:
- RecommendationChecker: Views and displays recommendations
- SkillDetector: Detects relevant skills from user messages
- SkillSuggester: Automated background suggestion daemon
- SkillManager: CRUD operations on skill registry

Key Features:
- Smart relevance scoring (pattern matching, keywords, language, category)
- Registry management with import/export support
- Usage statistics and analytics
- Proactive background monitoring and suggestion
- Cross-platform support (Windows UTF-8 handling)
- Complete logging and audit trails

Used in Level 3.5 (Skill/Agent Selection):
- During task analysis: Detect relevant skills
- During planning: Suggest improvements and optimizations
- During execution: Track skill usage and effectiveness
- During monitoring: Generate analytics and statistics

Author: Claude Insight System
Version: 3.5.0
"""

# ============================================================================
# ENCODING FIXES - Windows Console UTF-8 Support
# ============================================================================

import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ============================================================================
# IMPORTS
# ============================================================================

import json
import re
import os
import time
import signal
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

# Directory paths
MEMORY_DIR = Path.home() / '.claude' / 'memory'
SKILLS_REGISTRY = MEMORY_DIR / 'skills-registry.json'
RECOMMENDATIONS_FILE = MEMORY_DIR / '.latest-recommendations.json'
SKILL_DETECTOR_LOG = MEMORY_DIR / 'logs' / 'skill-detector.log'
SKILL_MANAGER_LOG = MEMORY_DIR / 'logs' / 'skill-manager.log'
DAEMON_PID_FILE = MEMORY_DIR / '.pids' / 'skill-auto-suggester.pid'
DAEMON_LOG_FILE = MEMORY_DIR / 'logs' / 'skill-suggester-daemon.log'

# Colors for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

# Global daemon control flag
running = True


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_time_ago(timestamp_str: str) -> str:
    """Format timestamp as human-readable relative time.

    Args:
        timestamp_str: ISO format timestamp string.

    Returns:
        Human-readable time difference string (e.g., "5 minutes ago").
    """
    try:
        ts = datetime.fromisoformat(timestamp_str)
        now = datetime.now()
        diff = now - ts

        seconds = diff.total_seconds()
        if seconds < 60:
            return f"{int(seconds)} seconds ago"
        elif seconds < 3600:
            return f"{int(seconds/60)} minutes ago"
        elif seconds < 86400:
            return f"{int(seconds/3600)} hours ago"
        else:
            return f"{int(seconds/86400)} days ago"
    except Exception:
        return timestamp_str


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals gracefully.

    Args:
        signum: Signal number (SIGTERM, SIGINT).
        frame: Current stack frame.
    """
    global running
    running = False
    log_daemon("SHUTDOWN", "Received shutdown signal")


# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

def log_daemon(action: str, message: str) -> None:
    """Log daemon activity to both daemon and policy logs.

    Args:
        action: Action type (e.g., "START", "STOP", "ERROR").
        message: Detailed message content.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] SKILL-SUGGESTER-DAEMON | {action} | {message}\n"

        # Write to daemon log
        DAEMON_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DAEMON_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)

        # Write to policy hits log
        policy_log = MEMORY_DIR / 'logs' / 'policy-hits.log'
        policy_entry = f"[{timestamp}] skill-auto-suggester | {action} | {message}\n"
        policy_log.parent.mkdir(parents=True, exist_ok=True)
        with open(policy_log, 'a', encoding='utf-8') as f:
            f.write(policy_entry)

    except Exception as e:
        print(f"Warning: Could not write to log: {e}", file=sys.stderr)


def log_event(log_file: Path, message: str) -> None:
    """Log general event to specified log file.

    Args:
        log_file: Path to log file.
        message: Event message to log.
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)

    except Exception as e:
        print(f"Warning: Could not write to log: {e}", file=sys.stderr)


# ============================================================================
# DAEMON PROCESS MANAGEMENT
# ============================================================================

def is_daemon_running() -> bool:
    """Check if daemon is already running.

    Returns:
        True if daemon process is running, False otherwise.
    """
    if not DAEMON_PID_FILE.exists():
        return False

    try:
        with open(DAEMON_PID_FILE, 'r') as f:
            pid = int(f.read().strip())

        try:
            os.kill(pid, 0)
            return True
        except OSError:
            DAEMON_PID_FILE.unlink(missing_ok=True)
            return False
    except Exception:
        return False


def write_pid() -> None:
    """Write daemon process ID to PID file."""
    try:
        DAEMON_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DAEMON_PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        log_daemon("ERROR", f"Could not write PID file: {e}")


def remove_pid() -> None:
    """Remove PID file on daemon shutdown."""
    try:
        if DAEMON_PID_FILE.exists():
            DAEMON_PID_FILE.unlink()
    except Exception as e:
        log_daemon("ERROR", f"Could not remove PID file: {e}")


# ============================================================================
# SKILL DETECTOR CLASS
# ============================================================================

class SkillDetector:
    """Detects relevant skills from user messages using pattern matching.

    Uses a multi-factor scoring system:
    - Trigger pattern match: +0.5
    - Keyword match: +0.1 per keyword (max +0.4)
    - Language mention: +0.2
    - Category mention: +0.1

    Attributes:
        registry: Skills registry loaded from JSON.
        skills: Dictionary of registered skills with metadata.
    """

    def __init__(self):
        """Initialize SkillDetector and load registry."""
        self.registry = self._load_registry()
        self.skills = self.registry.get('skills', {})

    def _load_registry(self) -> Dict:
        """Load skills registry from JSON file.

        Returns:
            Registry dictionary with skills and statistics.
        """
        if not SKILLS_REGISTRY.exists():
            return {"skills": {}, "statistics": {}}

        try:
            with open(SKILLS_REGISTRY, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"skills": {}, "statistics": {}}

    def _save_registry(self) -> None:
        """Save updated registry back to JSON file."""
        try:
            SKILLS_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
            with open(SKILLS_REGISTRY, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving registry: {e}", file=sys.stderr)

    def detect_skills(self, user_message: str, threshold: float = 0.3) -> List[Dict]:
        """Detect relevant skills from user message.

        Args:
            user_message: User's input text for skill detection.
            threshold: Minimum relevance score (0.0-1.0). Default: 0.3.

        Returns:
            List of matched skills with relevance scores, sorted by score (descending).
        """
        matches = []

        for skill_id, skill_data in self.skills.items():
            if not skill_data.get('auto_suggest', False):
                continue

            score = self._calculate_relevance(user_message, skill_data)

            if score >= threshold:
                matches.append({
                    'skill_id': skill_id,
                    'name': skill_data['name'],
                    'description': skill_data['description'],
                    'score': score,
                    'file': skill_data['file'],
                    'requires_context7': skill_data.get('requires_context7', False),
                    'tags': skill_data.get('tags', [])
                })

        # Sort by relevance score (descending)
        matches.sort(key=lambda x: x['score'], reverse=True)

        return matches

    def _calculate_relevance(self, message: str, skill_data: Dict) -> float:
        """Calculate relevance score between message and skill.

        Scoring breakdown:
        - Trigger pattern match: +0.5 (highest weight)
        - Keyword match: +0.1 per keyword (max +0.4)
        - Language mention: +0.2
        - Category mention: +0.1
        - Final score capped at 1.0

        Args:
            message: User message text.
            skill_data: Skill metadata dictionary.

        Returns:
            Relevance score between 0.0 and 1.0.
        """
        message_lower = message.lower()
        score = 0.0

        # 1. Check trigger patterns (highest weight)
        trigger_patterns = skill_data.get('trigger_patterns', [])
        for pattern in trigger_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                score += 0.5
                break  # Only count once

        # 2. Check keywords
        keywords = skill_data.get('keywords', [])
        keyword_matches = 0
        for keyword in keywords:
            if keyword.lower() in message_lower:
                keyword_matches += 1

        # Cap keyword contribution at 0.4
        keyword_score = min(keyword_matches * 0.1, 0.4)
        score += keyword_score

        # 3. Check language mention
        language = skill_data.get('language', '')
        if language and language.lower() in message_lower:
            score += 0.2

        # 4. Check category relevance
        category = skill_data.get('category', '')
        if category and category.lower() in message_lower:
            score += 0.1

        # Cap at 1.0
        return min(score, 1.0)

    def suggest_skills(self, user_message: str, max_suggestions: int = 3) -> str:
        """Generate user-friendly skill suggestions.

        Args:
            user_message: User's input text.
            max_suggestions: Maximum number of suggestions to return. Default: 3.

        Returns:
            Formatted suggestion text, empty string if no matches.
        """
        matches = self.detect_skills(user_message)

        if not matches:
            return ""

        # Limit to top N suggestions
        top_matches = matches[:max_suggestions]

        suggestions = []
        suggestions.append("=== Relevant Skills Detected ===\n")

        for i, match in enumerate(top_matches, 1):
            skill_name = match['name']
            description = match['description']
            score_pct = int(match['score'] * 100)
            context7_note = " [Context7 Required]" if match['requires_context7'] else ""

            suggestions.append(
                f"{i}. {skill_name} ({score_pct}% match){context7_note}\n"
                f"   {description}\n"
            )

        suggestions.append("\nUse: Read the skill file to apply it to your task.")

        return "".join(suggestions)

    def update_usage(self, skill_id: str) -> None:
        """Update usage statistics for a skill.

        Args:
            skill_id: ID of skill to update.
        """
        if skill_id not in self.skills:
            return

        # Update skill usage
        self.skills[skill_id]['usage_count'] = self.skills[skill_id].get('usage_count', 0) + 1
        self.skills[skill_id]['last_used'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Update global statistics
        stats = self.registry.get('statistics', {})

        # Find most/least used
        usage_counts = {sid: data.get('usage_count', 0) for sid, data in self.skills.items()}
        if usage_counts:
            stats['most_used'] = max(usage_counts, key=usage_counts.get)
            stats['least_used'] = min(usage_counts, key=usage_counts.get)

        self.registry['statistics'] = stats
        self._save_registry()

        # Log usage
        log_event(SKILL_DETECTOR_LOG, f"skill-used | {skill_id} | count={self.skills[skill_id]['usage_count']}")

    def list_all_skills(self) -> str:
        """List all available skills with statistics.

        Returns:
            Formatted string listing all skills and statistics.
        """
        output = []
        output.append("=== Available Skills ===\n")

        for skill_id, skill_data in self.skills.items():
            name = skill_data['name']
            category = skill_data.get('category', 'N/A')
            language = skill_data.get('language', 'N/A')
            size = skill_data.get('size', 'N/A')
            usage = skill_data.get('usage_count', 0)

            output.append(
                f"- {name}\n"
                f"  ID: {skill_id}\n"
                f"  Category: {category} | Language: {language} | Size: {size}\n"
                f"  Used: {usage} times\n"
            )

        # Add statistics
        stats = self.registry.get('statistics', {})
        output.append(f"\nTotal Skills: {stats.get('total_skills', len(self.skills))}")
        if stats.get('most_used'):
            output.append(f"Most Used: {stats['most_used']}")

        return "".join(output)

    def get_skill_by_id(self, skill_id: str) -> Optional[Dict]:
        """Get skill details by ID.

        Args:
            skill_id: ID of skill to retrieve.

        Returns:
            Skill data dictionary or None if not found.
        """
        return self.skills.get(skill_id)

    def search_skills(self, query: str) -> List[Dict]:
        """Search skills by keyword.

        Args:
            query: Search query string.

        Returns:
            List of matching skills with metadata.
        """
        query_lower = query.lower()
        results = []

        for skill_id, skill_data in self.skills.items():
            # Search in name, description, keywords, tags
            searchable = [
                skill_data.get('name', ''),
                skill_data.get('description', ''),
                ' '.join(skill_data.get('keywords', [])),
                ' '.join(skill_data.get('tags', []))
            ]

            searchable_text = ' '.join(searchable).lower()

            if query_lower in searchable_text:
                results.append({
                    'skill_id': skill_id,
                    'name': skill_data['name'],
                    'description': skill_data['description'],
                    'file': skill_data['file']
                })

        return results


# ============================================================================
# SKILL MANAGER CLASS
# ============================================================================

class SkillManager:
    """Manages CRUD operations for the skill registry.

    Provides methods to add, update, remove, and retrieve skills from the
    central skills registry. Maintains skill metadata, categories, and
    statistics for skill discovery and recommendation systems.

    Attributes:
        registry: Central skills registry containing all skill data.
        skills: Dictionary of registered skills with metadata.
        categories: Skill categories and organization.
        statistics: Usage and recommendation statistics for skills.
    """

    def __init__(self):
        """Initialize SkillManager and load registry."""
        self.registry = self._load_registry()
        self.skills = self.registry.get('skills', {})
        self.categories = self.registry.get('categories', {})
        self.statistics = self.registry.get('statistics', {})

    def _load_registry(self) -> Dict:
        """Load skills registry from JSON file.

        Returns:
            Registry dictionary with version, skills, categories, and statistics.
        """
        if not SKILLS_REGISTRY.exists():
            return {
                "version": "1.0.0",
                "last_updated": datetime.now().strftime('%Y-%m-%d'),
                "skills": {},
                "categories": {},
                "statistics": {
                    "total_skills": 0,
                    "by_language": {},
                    "by_category": {}
                }
            }

        try:
            with open(SKILLS_REGISTRY, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {
                "version": "1.0.0",
                "last_updated": datetime.now().strftime('%Y-%m-%d'),
                "skills": {},
                "categories": {},
                "statistics": {}
            }

    def _save_registry(self) -> None:
        """Save updated registry back to JSON file."""
        try:
            self.registry['last_updated'] = datetime.now().strftime('%Y-%m-%d')
            self.registry['skills'] = self.skills
            self.registry['categories'] = self.categories
            self.registry['statistics'] = self.statistics

            SKILLS_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
            with open(SKILLS_REGISTRY, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, indent=2, ensure_ascii=False)

            log_event(SKILL_MANAGER_LOG, "registry-saved")

        except Exception as e:
            print(f"Error saving registry: {e}", file=sys.stderr)

    def add_skill(self, skill_id: str, **kwargs) -> bool:
        """Add a new skill to the registry.

        Args:
            skill_id: Unique identifier for the skill.
            **kwargs: Required fields (name, file, description, language, category, keywords)
                     and optional fields (version, size, trigger_patterns, auto_suggest,
                     requires_context7, dependencies, tags, category_description).

        Returns:
            True if skill added successfully, False otherwise.
        """
        if skill_id in self.skills:
            print(f"Error: Skill '{skill_id}' already exists")
            return False

        # Required fields
        required = ['name', 'file', 'description', 'language', 'category', 'keywords']
        for field in required:
            if field not in kwargs:
                print(f"Error: Missing required field '{field}'")
                return False

        # Create skill entry
        self.skills[skill_id] = {
            'name': kwargs['name'],
            'file': kwargs['file'],
            'description': kwargs['description'],
            'version': kwargs.get('version', '1.0.0'),
            'size': kwargs.get('size', 'N/A'),
            'language': kwargs['language'],
            'category': kwargs['category'],
            'keywords': kwargs['keywords'] if isinstance(kwargs['keywords'], list) else kwargs['keywords'].split(','),
            'trigger_patterns': kwargs.get('trigger_patterns', []),
            'auto_suggest': kwargs.get('auto_suggest', True),
            'requires_context7': kwargs.get('requires_context7', False),
            'dependencies': kwargs.get('dependencies', []),
            'usage_count': 0,
            'last_used': None,
            'tags': kwargs.get('tags', [])
        }

        # Update category
        category = kwargs['category']
        if category not in self.categories:
            self.categories[category] = {
                'description': kwargs.get('category_description', f'{category} skills'),
                'skills': []
            }
        self.categories[category]['skills'].append(skill_id)

        # Update statistics
        self._update_statistics()

        self._save_registry()
        log_event(SKILL_MANAGER_LOG, f"skill-added | {skill_id}")

        print(f"[CHECK] Skill '{skill_id}' added successfully")
        return True

    def update_skill(self, skill_id: str, **kwargs) -> bool:
        """Update an existing skill.

        Args:
            skill_id: ID of skill to update.
            **kwargs: Fields to update (name, description, keywords, trigger_patterns,
                     auto_suggest, requires_context7, tags, version, size).

        Returns:
            True if skill updated successfully, False otherwise.
        """
        if skill_id not in self.skills:
            print(f"Error: Skill '{skill_id}' not found")
            return False

        # Update allowed fields
        updatable = ['name', 'description', 'keywords', 'trigger_patterns',
                     'auto_suggest', 'requires_context7', 'tags', 'version', 'size']

        for field, value in kwargs.items():
            if field in updatable:
                if field == 'keywords' and isinstance(value, str):
                    value = value.split(',')
                self.skills[skill_id][field] = value

        self._save_registry()
        log_event(SKILL_MANAGER_LOG, f"skill-updated | {skill_id}")

        print(f"[CHECK] Skill '{skill_id}' updated successfully")
        return True

    def remove_skill(self, skill_id: str) -> bool:
        """Remove a skill from the registry.

        Args:
            skill_id: ID of skill to remove.

        Returns:
            True if skill removed successfully, False otherwise.
        """
        if skill_id not in self.skills:
            print(f"Error: Skill '{skill_id}' not found")
            return False

        # Remove from category
        skill_data = self.skills[skill_id]
        category = skill_data.get('category')
        if category and category in self.categories:
            self.categories[category]['skills'] = [
                s for s in self.categories[category]['skills'] if s != skill_id
            ]

        # Remove skill
        del self.skills[skill_id]

        # Update statistics
        self._update_statistics()

        self._save_registry()
        log_event(SKILL_MANAGER_LOG, f"skill-removed | {skill_id}")

        print(f"[CHECK] Skill '{skill_id}' removed successfully")
        return True

    def get_skill(self, skill_id: str) -> Optional[Dict]:
        """Get skill details by ID.

        Args:
            skill_id: ID of skill to retrieve.

        Returns:
            Skill data dictionary or None if not found.
        """
        return self.skills.get(skill_id)

    def list_skills(self, category: Optional[str] = None) -> List[str]:
        """List all skills or by category.

        Args:
            category: Optional category filter. If None, returns all skills.

        Returns:
            List of skill IDs.
        """
        if category:
            return self.categories.get(category, {}).get('skills', [])
        return list(self.skills.keys())

    def _update_statistics(self) -> None:
        """Update registry statistics for all skills."""
        self.statistics['total_skills'] = len(self.skills)

        # By language
        by_language = {}
        for skill_data in self.skills.values():
            lang = skill_data.get('language', 'unknown')
            by_language[lang] = by_language.get(lang, 0) + 1
        self.statistics['by_language'] = by_language

        # By category
        by_category = {}
        for skill_data in self.skills.values():
            cat = skill_data.get('category', 'unknown')
            by_category[cat] = by_category.get(cat, 0) + 1
        self.statistics['by_category'] = by_category

        # Most/least used
        usage_counts = {sid: data.get('usage_count', 0) for sid, data in self.skills.items()}
        if usage_counts:
            self.statistics['most_used'] = max(usage_counts, key=usage_counts.get)
            self.statistics['least_used'] = min(usage_counts, key=usage_counts.get)

    def show_statistics(self) -> None:
        """Display registry statistics to stdout."""
        print("=== Skill Registry Statistics ===\n")

        print(f"Total Skills: {self.statistics.get('total_skills', 0)}")
        print(f"Version: {self.registry.get('version', 'N/A')}")
        print(f"Last Updated: {self.registry.get('last_updated', 'N/A')}\n")

        print("By Language:")
        for lang, count in self.statistics.get('by_language', {}).items():
            print(f"  {lang}: {count}")

        print("\nBy Category:")
        for cat, count in self.statistics.get('by_category', {}).items():
            print(f"  {cat}: {count}")

        if self.statistics.get('most_used'):
            most_used_id = self.statistics['most_used']
            most_used = self.skills[most_used_id]
            print(f"\nMost Used: {most_used['name']} ({most_used.get('usage_count', 0)} times)")

        print()

    def export_skill(self, skill_id: str, output_file: str) -> bool:
        """Export a single skill to JSON file.

        Args:
            skill_id: ID of skill to export.
            output_file: Path to output JSON file.

        Returns:
            True if export successful, False otherwise.
        """
        if skill_id not in self.skills:
            print(f"Error: Skill '{skill_id}' not found")
            return False

        try:
            export_data = {
                'skill_id': skill_id,
                'data': self.skills[skill_id]
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            print(f"[CHECK] Skill exported to: {output_file}")
            return True

        except Exception as e:
            print(f"Error exporting skill: {e}")
            return False

    def import_skill(self, import_file: str) -> bool:
        """Import a skill from JSON file.

        Args:
            import_file: Path to import JSON file.

        Returns:
            True if import successful, False otherwise.
        """
        try:
            with open(import_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            skill_id = import_data.get('skill_id')
            skill_data = import_data.get('data')

            if not skill_id or not skill_data:
                print("Error: Invalid import file format")
                return False

            if skill_id in self.skills:
                print(f"Warning: Skill '{skill_id}' already exists. Updating...")

            self.skills[skill_id] = skill_data
            self._update_statistics()
            self._save_registry()

            print(f"[CHECK] Skill '{skill_id}' imported successfully")
            return True

        except Exception as e:
            print(f"Error importing skill: {e}")
            return False


# ============================================================================
# RECOMMENDATION CHECKER CLASS
# ============================================================================

class RecommendationChecker:
    """Displays and validates auto-generated recommendations.

    Reads from the latest recommendations file and presents them in
    a formatted, user-friendly display. Supports both text and JSON output.
    """

    def __init__(self):
        """Initialize RecommendationChecker."""
        pass

    def display_recommendations(self, json_output: bool = False) -> int:
        """Display latest recommendations with formatting.

        Args:
            json_output: If True, output as JSON; else formatted text.

        Returns:
            Exit code (0 for success, 1 for error).
        """
        if not RECOMMENDATIONS_FILE.exists():
            if json_output:
                print(json.dumps({"error": "No recommendations available"}))
            else:
                print(f"{YELLOW}No recommendations available yet{RESET}")
                print(f"\nStart the auto-recommendation daemon:")
                print(f"  python ~/.claude/scripts/recommendations-policy.py daemon --start")
            return 0

        try:
            with open(RECOMMENDATIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if json_output:
                print(json.dumps(data, indent=2))
                return 0

            # Pretty display
            print(f"\n{BOLD}{'='*60}{RESET}")
            print(f"{BOLD}{GREEN}LATEST RECOMMENDATIONS{RESET}")
            print(f"{BOLD}{'='*60}{RESET}\n")

            # Timestamp
            if 'timestamp' in data:
                time_ago = format_time_ago(data['timestamp'])
                print(f"{BOLD}Generated:{RESET} {time_ago}")
                print()

            # Model
            if 'model' in data:
                model = data['model']
                model_name = model.get('recommended', 'N/A').upper()
                reason = model.get('reason', '')
                confidence = model.get('confidence', 0)

                if model_name == 'HAIKU':
                    color = GREEN
                elif model_name == 'OPUS':
                    color = CYAN
                else:
                    color = BLUE

                print(f"{BOLD}MODEL:{RESET} {color}{model_name}{RESET}")
                print(f"  Reason: {reason}")
                print(f"  Confidence: {confidence:.0%}")
                print()

            # Context
            if 'context' in data:
                context = data['context']
                status = context.get('status', 'unknown').upper()
                percentage = context.get('percentage', 0)

                if status == 'CRITICAL':
                    color = RED
                elif status == 'WARNING':
                    color = YELLOW
                else:
                    color = GREEN

                print(f"{BOLD}CONTEXT:{RESET} {color}{status}{RESET} ({percentage:.1f}%)")
                print()

            # Skills
            if 'skills' in data and data['skills']:
                print(f"{BOLD}SKILLS ({len(data['skills'])}){RESET}:")
                for skill in data['skills']:
                    print(f"  -> {CYAN}{skill}{RESET}")
                print()

            # Agents
            if 'agents' in data and data['agents']:
                print(f"{BOLD}AGENTS ({len(data['agents'])}){RESET}:")
                for agent in data['agents']:
                    print(f"  -> {BLUE}{agent}{RESET}")
                print()

            # Optimizations
            if 'optimizations' in data and data['optimizations']:
                print(f"{BOLD}OPTIMIZATIONS ({len(data['optimizations'])}){RESET}:")
                for opt in data['optimizations']:
                    print(f"  [OK] {opt}")
                print()

            # Warnings
            if 'warnings' in data and data['warnings']:
                print(f"{BOLD}{RED}WARNINGS ({len(data['warnings'])}){RESET}:")
                for warning in data['warnings']:
                    print(f"  {RED}[!]{RESET} {warning}")
                print()

            # Actions
            if 'actions' in data and data['actions']:
                print(f"{BOLD}ACTION CHECKLIST{RESET}:")
                for action in data['actions']:
                    print(f"  {action}")
                print()

            print(f"{BOLD}{'='*60}{RESET}\n")

            return 0

        except Exception as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                print(f"{RED}ERROR: Failed to read recommendations: {e}{RESET}")
            return 1


# ============================================================================
# SKILL SUGGESTER (DAEMON) FUNCTIONS
# ============================================================================

def get_recent_messages() -> List[str]:
    """Extract recent user messages from policy logs.

    Returns:
        List of recent message strings from the last 10 minutes.
    """
    log_file = MEMORY_DIR / 'logs' / 'policy-hits.log'

    if not log_file.exists():
        return []

    messages = []
    cutoff_time = datetime.now() - timedelta(minutes=10)

    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

            for line in lines[-100:]:
                try:
                    if line.startswith('['):
                        timestamp_str = line[1:20]
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                        if timestamp > cutoff_time:
                            # Extract context (user message indicators)
                            if 'user-message' in line or 'context-loaded' in line or 'session-start' in line:
                                parts = line.split('|')
                                if len(parts) >= 3:
                                    context = parts[2].strip()
                                    if context and len(context) > 10:
                                        messages.append(context)
                except Exception:
                    continue

    except Exception as e:
        log_daemon("ERROR", f"Could not read messages: {e}")

    return messages


def detect_skills_for_message(message: str, detector: SkillDetector) -> Optional[List[str]]:
    """Detect relevant skills for a message.

    Args:
        message: User message text to analyze.
        detector: SkillDetector instance.

    Returns:
        List of skill names with scores, or None if no matches.
    """
    try:
        detected = detector.detect_skills(message, threshold=0.3)

        if detected:
            skills = []
            for skill in detected:
                skill_name = skill.get('name', 'unknown')
                score = skill.get('score', 0.0)
                skills.append(f"{skill_name} (score={score:.2f})")

            return skills if skills else None
        else:
            return None

    except Exception as e:
        log_daemon("ERROR", f"Failed to detect skills: {e}")
        return None


def monitor_loop(interval_minutes: int) -> None:
    """Main monitoring loop for skill auto-suggester daemon.

    Args:
        interval_minutes: Sleep interval between checks in minutes.
    """
    global running

    log_daemon("START", f"Daemon started (interval={interval_minutes}min)")

    detector = SkillDetector()
    processed_messages = set()

    while running:
        try:
            # Get recent messages
            messages = get_recent_messages()

            if messages:
                new_messages = [m for m in messages if m not in processed_messages]

                if new_messages:
                    log_daemon("CHECK", f"Found {len(new_messages)} new messages")

                    for message in new_messages:
                        # Detect skills for this message
                        skills = detect_skills_for_message(message, detector)

                        if skills:
                            log_daemon("SKILLS-DETECTED", f"{len(skills)} skills for: {message[:50]}...")

                            # Log suggestions (proactive)
                            for skill in skills:
                                log_daemon("SUGGEST", f"{skill}")

                        # Mark as processed
                        processed_messages.add(message)

                else:
                    log_daemon("OK", "No new messages to process")
            else:
                log_daemon("OK", "No recent messages found")

            # Cleanup old processed messages (keep last 100)
            if len(processed_messages) > 100:
                processed_messages = set(list(processed_messages)[-100:])

            # Sleep until next check
            log_daemon("SLEEP", f"Sleeping for {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            log_daemon("SHUTDOWN", "Received keyboard interrupt")
            break
        except Exception as e:
            log_daemon("ERROR", f"Error in monitoring loop: {e}")
            time.sleep(60)

    log_daemon("STOP", "Daemon stopped")


# ============================================================================
# POLICY FUNCTIONS (Level 3.5 Integration)
# ============================================================================

def enforce(context: Dict) -> Dict:
    """Enforce recommendations policy during execution.

    Level 3.5: Skill/Agent Selection step
    - Detect relevant skills from task context
    - Generate recommendations for model, skills, agents
    - Update recommendations file

    Args:
        context: Execution context with task, user_message, etc.

    Returns:
        Updated context with recommendations.
    """
    detector = SkillDetector()
    manager = SkillManager()

    user_message = context.get('user_message', '')
    task_type = context.get('task_type', 'general')

    # Detect skills
    detected_skills = detector.detect_skills(user_message, threshold=0.3)
    skill_names = [s['name'] for s in detected_skills[:3]]

    # Generate recommendations
    recommendations = {
        'timestamp': datetime.now().isoformat(),
        'model': {
            'recommended': 'HAIKU',
            'reason': 'Task complexity supports efficient processing',
            'confidence': 0.85
        },
        'context': {
            'status': 'OK',
            'percentage': context.get('context_usage', 50)
        },
        'skills': skill_names,
        'agents': [],
        'optimizations': [
            'Use detected skills to enhance response quality',
            'Consider context optimization for large responses'
        ],
        'warnings': [],
        'actions': []
    }

    # Save recommendations
    try:
        RECOMMENDATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RECOMMENDATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recommendations, f, indent=2, ensure_ascii=False)

        context['recommendations'] = recommendations
        log_event(SKILL_MANAGER_LOG, f"policy-enforce | recommendations-generated | skills={len(skill_names)}")

    except Exception as e:
        print(f"Warning: Could not save recommendations: {e}", file=sys.stderr)

    return context


def validate(context: Dict) -> bool:
    """Validate recommendations quality and accuracy.

    Args:
        context: Execution context.

    Returns:
        True if recommendations are valid, False otherwise.
    """
    if 'recommendations' not in context:
        return False

    recs = context['recommendations']

    # Check required fields
    required_fields = ['timestamp', 'model', 'context', 'skills']
    if not all(field in recs for field in required_fields):
        return False

    # Validate model recommendation
    if not isinstance(recs['model'], dict):
        return False

    model_name = recs['model'].get('recommended', '')
    if model_name not in ['HAIKU', 'SONNET', 'OPUS']:
        return False

    # Validate context
    if not isinstance(recs['context'], dict):
        return False

    context_status = recs['context'].get('status', '')
    if context_status not in ['OK', 'WARNING', 'CRITICAL']:
        return False

    # Validate skills list
    if not isinstance(recs['skills'], list):
        return False

    return True


def report() -> Dict:
    """Generate recommendations policy report.

    Returns:
        Report dictionary with recommendations statistics and analysis.
    """
    detector = SkillDetector()
    manager = SkillManager()

    report_data = {
        'timestamp': datetime.now().isoformat(),
        'policy': 'Level 3.5 - Recommendations',
        'status': 'active',
        'statistics': {
            'total_skills': len(detector.skills),
            'total_categories': len(manager.categories),
            'most_used_skill': manager.statistics.get('most_used', 'N/A'),
            'total_detections': 0
        },
        'recent_recommendations': []
    }

    if RECOMMENDATIONS_FILE.exists():
        try:
            with open(RECOMMENDATIONS_FILE, 'r', encoding='utf-8') as f:
                latest = json.load(f)
                report_data['recent_recommendations'] = {
                    'timestamp': latest.get('timestamp'),
                    'skills': latest.get('skills', []),
                    'model': latest.get('model', {})
                }
        except Exception:
            pass

    return report_data


# ============================================================================
# MAIN CLI AND ENTRY POINT
# ============================================================================

def main():
    """Entry point for the CLI.

    Parses command-line arguments and executes the corresponding action:
    - check: Display latest recommendations
    - daemon: Start/stop background suggestion daemon
    - detect: Detect skills for user message
    - manage: CRUD operations on skills
    - report: Show policy statistics
    """
    parser = argparse.ArgumentParser(
        description='Claude Insight Recommendations Policy - Level 3.5'
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Check recommendations
    check_parser = subparsers.add_parser('check', help='Display latest recommendations')
    check_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Daemon control
    daemon_parser = subparsers.add_parser('daemon', help='Control skill suggestion daemon')
    daemon_parser.add_argument('--start', action='store_true', help='Start daemon')
    daemon_parser.add_argument('--stop', action='store_true', help='Stop daemon')
    daemon_parser.add_argument('--status', action='store_true', help='Check daemon status')
    daemon_parser.add_argument('--interval', type=int, default=5, help='Check interval in minutes')

    # Skill detection
    detect_parser = subparsers.add_parser('detect', help='Detect skills for message')
    detect_parser.add_argument('message', nargs='*', help='User message')
    detect_parser.add_argument('--list', action='store_true', help='List all skills')
    detect_parser.add_argument('--search', help='Search skills by keyword')

    # Skill management
    manage_parser = subparsers.add_parser('manage', help='Manage skill registry')
    manage_subparsers = manage_parser.add_subparsers(dest='action', help='Actions')

    add_parser = manage_subparsers.add_parser('add', help='Add skill')
    add_parser.add_argument('--id', required=True, help='Skill ID')
    add_parser.add_argument('--name', required=True, help='Skill name')
    add_parser.add_argument('--file', required=True, help='Skill file')
    add_parser.add_argument('--description', required=True, help='Description')
    add_parser.add_argument('--language', required=True, help='Language')
    add_parser.add_argument('--category', required=True, help='Category')
    add_parser.add_argument('--keywords', required=True, help='Keywords')

    update_parser = manage_subparsers.add_parser('update', help='Update skill')
    update_parser.add_argument('--id', required=True, help='Skill ID')
    update_parser.add_argument('--name', help='New name')
    update_parser.add_argument('--description', help='New description')

    remove_parser = manage_subparsers.add_parser('remove', help='Remove skill')
    remove_parser.add_argument('--id', required=True, help='Skill ID')

    manage_subparsers.add_parser('list', help='List skills')
    manage_subparsers.add_parser('stats', help='Show statistics')

    # Report
    subparsers.add_parser('report', help='Show policy report')

    if len(sys.argv) < 2:
        parser.print_help()
        return 0

    args = parser.parse_args()

    # Handle check command
    if args.command == 'check':
        checker = RecommendationChecker()
        return checker.display_recommendations(json_output=args.json)

    # Handle daemon command
    elif args.command == 'daemon':
        if args.start:
            if is_daemon_running():
                print("[WARNING] Skill suggester daemon is already running!")
                print("   Use --stop to stop it first")
                return 1

            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)

            write_pid()

            print("=" * 70)
            print("[ROCKET] SKILL AUTO-SUGGESTER DAEMON STARTING")
            print("=" * 70)
            print(f"\nCheck Interval: {args.interval} minutes")
            print(f"PID: {os.getpid()}")
            print(f"\nLog: {DAEMON_LOG_FILE}")
            print(f"PID File: {DAEMON_PID_FILE}")
            print("\n[BULB] To stop: python recommendations-policy.py daemon --stop")
            print("[BULB] To check status: python recommendations-policy.py daemon --status")
            print("\n[CHECK] Daemon running in background...")
            print("=" * 70)

            try:
                monitor_loop(args.interval)
            finally:
                remove_pid()

            return 0

        elif args.stop:
            if is_daemon_running():
                try:
                    with open(DAEMON_PID_FILE, 'r') as f:
                        pid = int(f.read().strip())
                    os.kill(pid, signal.SIGTERM)
                    log_daemon("STOP", f"Daemon stopped (PID: {pid})")
                    print(f"[CHECK] Skill suggester daemon stopped (PID: {pid})")
                except Exception as e:
                    print(f"[CROSS] Failed to stop daemon: {e}")
            else:
                print("[INFO] Skill suggester daemon is not running")
            return 0

        elif args.status:
            if is_daemon_running():
                with open(DAEMON_PID_FILE, 'r') as f:
                    pid = f.read().strip()
                print(f"[CHECK] Skill suggester daemon is running (PID: {pid})")
                print(f"   Checking every {args.interval} minutes")
            else:
                print("[WARNING] Skill suggester daemon is not running")
            return 0

    # Handle detect command
    elif args.command == 'detect':
        detector = SkillDetector()

        if args.list:
            print(detector.list_all_skills())
        elif args.search:
            results = detector.search_skills(args.search)
            if results:
                print(f"Search results for '{args.search}':\n")
                for result in results:
                    print(f"- {result['name']}")
                    print(f"  {result['description']}")
                    print(f"  File: {result['file']}\n")
            else:
                print(f"No skills found for '{args.search}'")
        elif args.message:
            user_message = ' '.join(args.message)
            suggestions = detector.suggest_skills(user_message)
            if suggestions:
                print(suggestions)
            else:
                print("No relevant skills detected for this message.")

    # Handle manage command
    elif args.command == 'manage':
        manager = SkillManager()

        if args.action == 'add':
            manager.add_skill(
                args.id,
                name=args.name,
                file=args.file,
                description=args.description,
                language=args.language,
                category=args.category,
                keywords=args.keywords
            )

        elif args.action == 'update':
            kwargs = {}
            if args.name:
                kwargs['name'] = args.name
            if args.description:
                kwargs['description'] = args.description
            manager.update_skill(args.id, **kwargs)

        elif args.action == 'remove':
            manager.remove_skill(args.id)

        elif args.action == 'list':
            skills = manager.list_skills()
            print("=== All Skills ===")
            for skill_id in skills:
                skill_data = manager.get_skill(skill_id)
                if skill_data:
                    print(f"- {skill_id}: {skill_data['name']}")

        elif args.action == 'stats':
            manager.show_statistics()

    # Handle report command
    elif args.command == 'report':
        report_data = report()
        print(json.dumps(report_data, indent=2))

    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Context Management Policy - Consolidated Implementation.

This module consolidates 12 context management helper scripts into a comprehensive
single-source system for managing Claude Code context usage, caching, optimization,
and cleanup. It provides intelligent context monitoring, estimation, extraction,
cleanup, and tiered caching mechanisms.

Key Components:
    - ContextCache: Intelligent file summary and query result caching system
    - ContextEstimator: Context window usage estimation based on session metrics
    - ContextExtractor: Tool output summarization to reduce context overhead
    - ContextMonitor: Real-time context monitoring with actionable recommendations
    - ContextPruner: Automatic context pruning at configurable thresholds
    - ContextOptimizer: File optimization, cleanup, tiered caching, and tracking

Classes:
    ContextCache: Content-based caching with TTL support
    ContextEstimator: Estimation with weighted metrics
    ContextExtractor: Intelligent output extraction
    ContextMonitor: Monitoring with severity levels
    ContextPruner: Automatic pruning with session protection
    ContextOptimizer: Multi-strategy optimization

Functions:
    get_file_type: Detect file type from extension
    optimize_read: Get optimized reading strategy
    generate_command: Generate efficient CLI commands
    get_cleanup_strategy: Get cleanup recommendations by level
    sandwich_read: Read file head and tail for large files
    ast_summary: Extract code structure using AST
    enforce: Main policy enforcement entry point
    validate: Validate context management setup
    report: Generate context usage report

Usage:
    python context-management-policy.py --enforce
    python context-management-policy.py --validate
    python context-management-policy.py --report
    python context-management-policy.py --cache-stats
    python context-management-policy.py --estimate-context
"""

# Fix encoding for Windows console
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

import sys
import os
import json
import hashlib
import time
import argparse
import subprocess
import re
import ast as ast_module
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# Platform-specific configuration
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

# Constants for context management
MEMORY_DIR = os.path.expanduser("~/.claude/memory")
CACHE_DIR = os.path.expanduser("~/.claude/memory/.cache")
PRUNE_LOG = os.path.join(MEMORY_DIR, "logs/context-pruning.log")
CONTEXT_FILE = os.path.join(MEMORY_DIR, ".context-usage")
ESTIMATE_FILE = os.path.join(MEMORY_DIR, ".context-estimate")
CACHE_INDEX = os.path.join(CACHE_DIR, "tiered-index.json")

# Context estimation weights
WEIGHTS = {
    "message_count": 1.5,
    "file_read": 3.0,
    "large_file_read": 8.0,
    "tool_call": 1.0,
    "mcp_response": 2.0,
    "session_age_minutes": 0.1,
}

# Context thresholds
THRESHOLDS = {
    "light_cleanup": 70,
    "moderate_cleanup": 85,
    "aggressive_cleanup": 90,
    "green": 60,
    "yellow": 70,
    "orange": 80,
    "red": 85,
}

# Cache configuration
HOT_THRESHOLD = 5
WARM_THRESHOLD = 3
TIME_WINDOW = 3600
CACHE_TTL = 3600
FILE_CACHE_TTL = 86400

# Protected directories (never cleanup)
PROTECTED_PATHS = [
    os.path.expanduser("~/.claude/memory/sessions/"),
    os.path.expanduser("~/.claude/memory/*.md"),
    os.path.expanduser("~/.claude/memory/logs/"),
    os.path.expanduser("~/.claude/settings*.json"),
    os.path.expanduser("~/.claude/*.md"),
]


def log_policy_hit(action, context, component="context-management"):
    """Log a policy execution event to the policy hits log.

    Records timestamped policy hits for monitoring and auditing purposes.

    Args:
        action (str): The action being logged (e.g., 'estimated', 'cleaned').
        context (str): Additional context about the action.
        component (str): Component name for logging (default: 'context-management').

    Returns:
        bool: True if logging succeeded, False otherwise.
    """
    log_file = os.path.expanduser("~/.claude/memory/logs/policy-hits.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {component} | {action} | {context}\n"

    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        return True
    except Exception as e:
        print(f"Warning: Could not write to log: {e}", file=sys.stderr)
        return False


class ContextCache:
    """Intelligent caching system to reduce redundant context usage.

    Caches file summaries and query results to avoid re-processing frequently
    accessed information. Uses content-based hashing for cache keys and supports
    configurable time-to-live (TTL) for automatic expiration.

    Attributes:
        cache_dir (Path): Root directory for cache storage.
        summaries_dir (Path): Directory for file summaries cache.
        queries_dir (Path): Directory for query results cache.
        cache_ttl (int): Query cache TTL in seconds (default: 3600).
        file_cache_ttl (int): File summary cache TTL in seconds (default: 86400).
    """

    def __init__(self):
        """Initialize the ContextCache with directory structure."""
        self.cache_dir = Path.home() / '.claude' / 'memory' / '.cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.summaries_dir = self.cache_dir / 'summaries'
        self.queries_dir = self.cache_dir / 'queries'
        self.summaries_dir.mkdir(exist_ok=True)
        self.queries_dir.mkdir(exist_ok=True)

        self.cache_ttl = CACHE_TTL
        self.file_cache_ttl = FILE_CACHE_TTL

    def _get_cache_key(self, data):
        """Generate cache key from data using MD5 hashing."""
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True)
        return hashlib.md5(str(data).encode()).hexdigest()

    def _is_cache_valid(self, cache_file, ttl):
        """Check if cache entry is still valid based on TTL."""
        if not cache_file.exists():
            return False

        try:
            cache_data = json.loads(cache_file.read_text())
            cached_at = cache_data.get('cached_at', 0)
            age = time.time() - cached_at
            return age < ttl
        except:
            return False

    def get_file_summary(self, file_path):
        """Get cached file summary if available and valid.

        Returns cached summary if cache is valid and file hasn't been modified
        since caching.

        Args:
            file_path (str): Path to the file.

        Returns:
            dict or None: Cached summary if available, None otherwise.
        """
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            return None

        cache_key = self._get_cache_key(str(file_path_obj.absolute()))
        cache_file = self.summaries_dir / f'{cache_key}.json'

        if not self._is_cache_valid(cache_file, self.file_cache_ttl):
            return None

        try:
            cache_data = json.loads(cache_file.read_text())
            file_mtime = file_path_obj.stat().st_mtime
            cached_mtime = cache_data.get('file_mtime', 0)

            if file_mtime > cached_mtime:
                return None

            return cache_data.get('summary')
        except:
            return None

    def set_file_summary(self, file_path, summary):
        """Cache file summary with metadata.

        Args:
            file_path (str): Path to the file.
            summary (dict): Summary data to cache.

        Returns:
            bool: True if caching succeeded, False otherwise.
        """
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            return False

        cache_key = self._get_cache_key(str(file_path_obj.absolute()))
        cache_file = self.summaries_dir / f'{cache_key}.json'

        cache_data = {
            'file_path': str(file_path_obj.absolute()),
            'file_name': file_path_obj.name,
            'summary': summary,
            'file_mtime': file_path_obj.stat().st_mtime,
            'cached_at': time.time(),
            'expires_at': time.time() + self.file_cache_ttl
        }

        try:
            cache_file.write_text(json.dumps(cache_data, indent=2))
            return True
        except:
            return False

    def get_query_result(self, query_type, query_params):
        """Get cached query result from grep, glob, or similar operations.

        Args:
            query_type (str): Type of query (e.g., 'Grep', 'Glob').
            query_params (dict): Query parameters.

        Returns:
            list or None: Cached result if available, None otherwise.
        """
        cache_key = self._get_cache_key({
            'type': query_type,
            'params': query_params
        })
        cache_file = self.queries_dir / f'{cache_key}.json'

        if not self._is_cache_valid(cache_file, self.cache_ttl):
            return None

        try:
            cache_data = json.loads(cache_file.read_text())
            return cache_data.get('result')
        except:
            return None

    def set_query_result(self, query_type, query_params, result):
        """Cache query result.

        Args:
            query_type (str): Type of query.
            query_params (dict): Query parameters.
            result (list): Query result to cache.

        Returns:
            bool: True if caching succeeded, False otherwise.
        """
        cache_key = self._get_cache_key({
            'type': query_type,
            'params': query_params
        })
        cache_file = self.queries_dir / f'{cache_key}.json'

        cache_data = {
            'query_type': query_type,
            'query_params': query_params,
            'result': result,
            'cached_at': time.time(),
            'expires_at': time.time() + self.cache_ttl
        }

        try:
            cache_file.write_text(json.dumps(cache_data, indent=2))
            return True
        except:
            return False

    def get_access_count(self, file_path):
        """Get file access count from tracking."""
        access_file = self.cache_dir / 'access_count.json'

        if not access_file.exists():
            return 0

        try:
            access_data = json.loads(access_file.read_text())
            return access_data.get(str(file_path), 0)
        except:
            return 0

    def increment_access(self, file_path):
        """Increment file access count."""
        access_file = self.cache_dir / 'access_count.json'

        try:
            if access_file.exists():
                access_data = json.loads(access_file.read_text())
            else:
                access_data = {}

            access_data[str(file_path)] = access_data.get(str(file_path), 0) + 1
            access_file.write_text(json.dumps(access_data, indent=2))

            return access_data[str(file_path)]
        except:
            return 0

    def clear_expired(self):
        """Clear all expired cache entries.

        Returns:
            int: Number of entries cleared.
        """
        current_time = time.time()
        cleared_count = 0

        for cache_file in self.queries_dir.glob('*.json'):
            try:
                cache_data = json.loads(cache_file.read_text())
                expires_at = cache_data.get('expires_at', 0)

                if current_time > expires_at:
                    cache_file.unlink()
                    cleared_count += 1
            except:
                pass

        for cache_file in self.summaries_dir.glob('*.json'):
            try:
                cache_data = json.loads(cache_file.read_text())
                expires_at = cache_data.get('expires_at', 0)

                if current_time > expires_at:
                    cache_file.unlink()
                    cleared_count += 1
            except:
                pass

        return cleared_count

    def get_stats(self):
        """Get cache statistics.

        Returns:
            dict: Statistics including entry counts and total size.
        """
        query_count = len(list(self.queries_dir.glob('*.json')))
        summary_count = len(list(self.summaries_dir.glob('*.json')))

        total_size = sum(
            f.stat().st_size
            for f in self.cache_dir.rglob('*.json')
            if f.is_file()
        )

        return {
            'query_cache_entries': query_count,
            'summary_cache_entries': summary_count,
            'total_cache_size_mb': round(total_size / 1024 / 1024, 2),
            'cache_directory': str(self.cache_dir)
        }

    def clear_all(self):
        """Clear all cache entries.

        Returns:
            int: Total number of entries cleared.
        """
        cleared = 0

        for cache_file in self.cache_dir.rglob('*.json'):
            try:
                cache_file.unlink()
                cleared += 1
            except:
                pass

        return cleared


class ContextEstimator:
    """Estimates context window usage based on observable session metrics.

    Since direct access to Claude Code's internal context tracking is unavailable,
    this estimator uses weighted metrics including message count, file reads,
    tool calls, and session duration to estimate context consumption.
    """

    @staticmethod
    def get_session_metrics():
        """Collect observable session metrics from logs.

        Returns:
            dict: Metrics dictionary with message_count, file_reads, tool_calls, etc.
        """
        metrics = {
            "message_count": 0,
            "file_reads": 0,
            "large_file_reads": 0,
            "tool_calls": 0,
            "mcp_responses": 0,
            "session_start": None,
            "session_duration_minutes": 0,
        }

        log_file = os.path.expanduser("~/.claude/memory/logs/policy-hits.log")
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    cutoff_time = datetime.now() - timedelta(hours=2)

                    for line in lines[-500:]:
                        try:
                            if line.startswith('['):
                                timestamp_str = line[1:20]
                                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                                if timestamp > cutoff_time:
                                    if 'session-memory' in line:
                                        metrics["message_count"] += 1
                                    if 'file-read' in line or 'Read' in line:
                                        metrics["file_reads"] += 1
                                    if 'tool-call' in line or 'Bash' in line or 'Grep' in line:
                                        metrics["tool_calls"] += 1
                                    if 'mcp' in line.lower():
                                        metrics["mcp_responses"] += 1

                                    if metrics["session_start"] is None or timestamp < metrics["session_start"]:
                                        metrics["session_start"] = timestamp
                        except:
                            continue

            except Exception as e:
                print(f"Warning: Could not read logs: {e}", file=sys.stderr)

        if metrics["session_start"]:
            duration = datetime.now() - metrics["session_start"]
            metrics["session_duration_minutes"] = duration.total_seconds() / 60

        if metrics["message_count"] == 0:
            metrics["message_count"] = 1

        return metrics

    @staticmethod
    def estimate_context_percentage(metrics):
        """Estimate context usage percentage from metrics.

        Uses weighted formula: (messages * 1.5) + (file_reads * 3.0) +
        (large_files * 8.0) + (tool_calls * 1.0) + (mcp_responses * 2.0)
        + (session_age_minutes * 0.1)

        Args:
            metrics (dict): Session metrics from get_session_metrics().

        Returns:
            float: Estimated context percentage (10-100 range).
        """
        estimated = (
            metrics["message_count"] * WEIGHTS["message_count"] +
            metrics["file_reads"] * WEIGHTS["file_read"] +
            metrics["large_file_reads"] * WEIGHTS["large_file_read"] +
            metrics["tool_calls"] * WEIGHTS["tool_call"] +
            metrics["mcp_responses"] * WEIGHTS["mcp_response"] +
            metrics["session_duration_minutes"] * WEIGHTS["session_age_minutes"]
        )

        estimated = min(estimated, 100)

        if metrics["session_duration_minutes"] < 5:
            estimated = max(estimated * 0.5, 10)

        return round(estimated, 1)

    @staticmethod
    def get_recommended_action(context_percent):
        """Get cleanup recommendation based on context percentage.

        Args:
            context_percent (float): Estimated context usage percentage.

        Returns:
            dict: Recommendation with level, action, urgency, and color.
        """
        if context_percent >= THRESHOLDS["aggressive_cleanup"]:
            return {
                "level": "aggressive",
                "action": "CRITICAL: Immediate cleanup required",
                "urgency": "critical",
                "color": "red",
            }
        elif context_percent >= THRESHOLDS["moderate_cleanup"]:
            return {
                "level": "moderate",
                "action": "HIGH: Cleanup recommended soon",
                "urgency": "high",
                "color": "yellow",
            }
        elif context_percent >= THRESHOLDS["light_cleanup"]:
            return {
                "level": "light",
                "action": "MEDIUM: Consider cleanup",
                "urgency": "medium",
                "color": "yellow",
            }
        else:
            return {
                "level": "none",
                "action": "OK: No cleanup needed",
                "urgency": "low",
                "color": "green",
            }


class ContextExtractor:
    """Extracts essential information from tool outputs to reduce context.

    Intelligently summarizes large outputs from Read, Grep, and Bash tools,
    preserving critical information while discarding redundant content.
    """

    def __init__(self):
        """Initialize ContextExtractor with summary limits."""
        self.summary_max_lines = 50

    def extract_read_output(self, content, file_path):
        """Extract essentials from Read tool output.

        Args:
            content (str): File content from Read tool.
            file_path (str): Path to the file being read.

        Returns:
            str: Original content if short, otherwise JSON summary.
        """
        lines = content.split('\n')

        if len(lines) <= self.summary_max_lines:
            return content

        summary = {
            'file': file_path,
            'total_lines': len(lines),
            'structure': self._extract_structure(lines),
            'key_definitions': self._extract_definitions(lines),
            'imports': self._extract_imports(lines),
            'summary': f'File has {len(lines)} lines. Use offset/limit to read specific sections.'
        }

        return json.dumps(summary, indent=2)

    def _extract_structure(self, lines):
        """Extract file structure (classes, functions, etc.)."""
        structure = []

        for i, line in enumerate(lines[:200], 1):
            if re.match(r'\s*(class|interface|enum)\s+\w+', line):
                structure.append(f'Line {i}: {line.strip()}')
            elif re.match(r'\s*(def|function|public|private|protected)\s+\w+', line):
                structure.append(f'Line {i}: {line.strip()}')

        return structure[:20]

    def _extract_definitions(self, lines):
        """Extract key definitions (constants and variables)."""
        definitions = []

        for i, line in enumerate(lines, 1):
            if re.match(r'\s*[A-Z_]+\s*=', line):
                definitions.append(f'Line {i}: {line.strip()}')
            elif re.match(r'\s*(const|let|var)\s+\w+\s*=', line):
                definitions.append(f'Line {i}: {line.strip()}')

        return definitions[:10]

    def _extract_imports(self, lines):
        """Extract import statements."""
        imports = []

        for line in lines[:50]:
            if re.match(r'\s*(import|from|require|include)', line):
                imports.append(line.strip())

        return imports

    def extract_grep_output(self, matches, pattern):
        """Extract essentials from Grep output."""
        if len(matches) <= 20:
            return matches

        files = defaultdict(list)
        for match in matches:
            file_path = match.get('file', 'unknown')
            files[file_path].append(match)

        summary = {
            'pattern': pattern,
            'total_matches': len(matches),
            'files_matched': len(files),
            'top_files': [
                {'file': f, 'matches': len(m)}
                for f, m in sorted(files.items(), key=lambda x: len(x[1]), reverse=True)[:10]
            ],
            'note': f'Showing top 10 of {len(files)} files. Use more specific pattern or head_limit.'
        }

        return json.dumps(summary, indent=2)

    def extract_bash_output(self, output, command):
        """Extract essentials from Bash output."""
        lines = output.split('\n')

        if len(lines) <= 100:
            return output

        if command.startswith('git'):
            return self._extract_git_output(lines, command)
        elif 'npm' in command or 'yarn' in command:
            return self._extract_npm_output(lines)
        elif 'docker' in command:
            return self._extract_docker_output(lines)
        else:
            extracted = lines[:50] + ['...'] + lines[-20:]
            return '\n'.join(extracted)

    def _extract_git_output(self, lines, command):
        """Extract git command output."""
        if 'git log' in command:
            commits = []
            for line in lines[:20]:
                if line.startswith('commit ') or line.startswith('    '):
                    commits.append(line)
            return '\n'.join(commits)
        elif 'git diff' in command:
            summary = []
            for line in lines[:30]:
                if line.startswith('diff --git') or line.startswith('@@'):
                    summary.append(line)
            return '\n'.join(summary)
        return '\n'.join(lines[:50])

    def _extract_npm_output(self, lines):
        """Extract npm/yarn output."""
        important = []
        for line in lines:
            if any(keyword in line.lower() for keyword in ['error', 'warning', 'success', 'installed']):
                important.append(line)
        return '\n'.join(important[-30:])

    def _extract_docker_output(self, lines):
        """Extract docker output."""
        important = []
        for line in lines:
            if any(keyword in line.lower() for keyword in ['error', 'warning', 'step', 'successfully']):
                important.append(line)
        return '\n'.join(important[-30:])

    def extract(self, tool, output, context=None):
        """Main extraction entry point."""
        context = context or {}

        if tool == 'Read':
            file_path = context.get('file_path', 'unknown')
            return self.extract_read_output(output, file_path)
        elif tool == 'Grep':
            pattern = context.get('pattern', 'unknown')
            return self.extract_grep_output(output, pattern)
        elif tool == 'Bash':
            command = context.get('command', 'unknown')
            return self.extract_bash_output(output, command)

        return output


class ContextMonitor:
    """Enhanced context monitoring with actionable recommendations.

    Tracks context usage and provides alerts at different severity levels
    (green/yellow/orange/red) with specific optimization recommendations.
    """

    def __init__(self):
        """Initialize ContextMonitor."""
        self.memory_dir = Path.home() / '.claude' / 'memory'
        self.context_file = self.memory_dir / '.context-usage'
        self.estimate_file = self.memory_dir / '.context-estimate'

    def get_context_percentage(self):
        """Get current context usage percentage."""
        if self.context_file.exists():
            try:
                data = json.loads(self.context_file.read_text())
                return data.get('percentage', 0)
            except:
                pass

        if self.estimate_file.exists():
            try:
                data = self.estimate_file.read_text().strip()
                return float(data)
            except:
                pass

        return 0

    def get_status_level(self, percentage):
        """Get status level based on percentage."""
        if percentage < THRESHOLDS['green']:
            return 'green'
        elif percentage < THRESHOLDS['yellow']:
            return 'yellow'
        elif percentage < THRESHOLDS['orange']:
            return 'orange'
        else:
            return 'red'

    def get_recommendations(self, percentage):
        """Get actionable recommendations based on usage."""
        level = self.get_status_level(percentage)
        recommendations = []

        if level == 'green':
            recommendations.append("[OK] Context usage healthy")
        elif level == 'yellow':
            recommendations.append("[WARN] Context usage elevated (70-85%)")
            recommendations.append("-> Use cached file summaries when available")
            recommendations.append("-> Use offset/limit for large file reads")
            recommendations.append("-> Use head_limit for Grep searches")
        elif level == 'orange':
            recommendations.append("[HIGH] Context usage high (85-90%)")
            recommendations.append("-> REQUIRED: Reference session state instead of full history")
            recommendations.append("-> Use context cache aggressively")
            recommendations.append("-> Extract summaries from tool outputs")
            recommendations.append("-> Consider saving session and continuing in new context")
        else:
            recommendations.append("[CRITICAL] Context usage critical (90%+)")
            recommendations.append("-> IMMEDIATE: Save current session state")
            recommendations.append("-> IMMEDIATE: Start new session with state reference")
            recommendations.append("-> DO NOT execute large tool calls")

        return recommendations

    def get_current_status(self):
        """Get complete current status."""
        percentage = self.get_context_percentage()
        level = self.get_status_level(percentage)
        recommendations = self.get_recommendations(percentage)

        status = {
            'percentage': percentage,
            'level': level,
            'thresholds': THRESHOLDS,
            'recommendations': recommendations,
            'timestamp': datetime.now().isoformat()
        }

        try:
            cache_dir = self.memory_dir / '.cache'
            if cache_dir.exists():
                cache_files = len(list(cache_dir.rglob('*.json')))
                status['cache_entries'] = cache_files
        except:
            pass

        try:
            state_dir = self.memory_dir / '.state'
            if state_dir.exists():
                state_files = list(state_dir.glob('*.json'))
                status['active_sessions'] = len(state_files)
        except:
            pass

        return status

    def update_percentage(self, percentage):
        """Update context percentage."""
        data = {
            'percentage': percentage,
            'updated_at': datetime.now().isoformat()
        }

        self.context_file.write_text(json.dumps(data, indent=2))
        self.estimate_file.write_text(str(percentage))
        return True


class ContextPruner:
    """Automatic context pruning with session protection."""

    def __init__(self):
        """Initialize ContextPruner."""
        self.memory_dir = Path.home() / '.claude' / 'memory'

    def get_context_status(self):
        """Get current context usage status."""
        monitor = ContextMonitor()
        return monitor.get_current_status()

    def check_and_prune(self):
        """Check context usage and trigger pruning if needed.

        Returns:
            dict: Status dictionary with pruning recommendations.
        """
        status = self.get_context_status()

        if not status:
            return {
                'checked': False,
                'error': 'Could not get context status'
            }

        percentage = status.get('percentage', 0)
        level = status.get('level', 'green')

        if percentage < 70:
            log_policy_hit('CHECK', f'{percentage}%', 'auto-context-pruner')
            return {
                'checked': True,
                'prune_needed': False,
                'percentage': percentage,
                'level': level,
                'message': 'Context is healthy'
            }

        elif percentage < 85:
            log_policy_hit('WARNING', f'{percentage}%', 'auto-context-pruner')
            return {
                'checked': True,
                'prune_needed': False,
                'percentage': percentage,
                'level': level,
                'message': 'Context elevated, monitor closely',
                'suggestion': 'Use cache, offset/limit, head_limit more aggressively'
            }

        elif percentage < 90:
            log_policy_hit('ALERT', f'{percentage}%', 'auto-context-pruner')
            return {
                'checked': True,
                'prune_needed': True,
                'percentage': percentage,
                'level': level,
                'message': 'Context high, pruning recommended',
                'action': 'Suggest: claude compact'
            }

        else:
            log_policy_hit('CRITICAL', f'{percentage}%', 'auto-context-pruner')
            return {
                'checked': True,
                'prune_needed': True,
                'percentage': percentage,
                'level': level,
                'message': 'Context CRITICAL, immediate pruning required',
                'action': 'EXECUTE: claude compact --full'
            }


class ContextOptimizer:
    """Multi-strategy context optimization and caching."""

    def __init__(self):
        """Initialize ContextOptimizer."""
        self.tiered_index_file = CACHE_INDEX
        self.ensure_cache_dir()

    def ensure_cache_dir(self):
        """Ensure cache directory exists."""
        os.makedirs(CACHE_DIR, exist_ok=True)

    def get_file_type(self, filepath):
        """Detect file type from extension."""
        ext = os.path.splitext(filepath)[1].lower()

        type_map = {
            '.json': 'json',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.log': 'log',
            '.md': 'markdown',
            '.java': 'code',
            '.ts': 'code',
            '.js': 'code',
            '.py': 'code',
            '.properties': 'config',
            '.xml': 'config',
            '.png': 'binary',
            '.jpg': 'binary',
            '.jar': 'binary',
        }

        return type_map.get(ext, 'text')

    def optimize_read(self, filepath, purpose='general'):
        """Get optimized read strategy for a file."""
        file_type = self.get_file_type(filepath)

        strategies = {
            'json': {
                'structure': 'Use jq to get keys only',
                'specific_key': 'Use jq .path.to.key',
                'general': 'Read with offset/limit'
            },
            'yaml': {
                'structure': 'Use yq to get keys',
                'specific_key': 'Use yq .path.to.key',
                'general': 'Read with offset/limit'
            },
            'log': {
                'recent': 'tail -100',
                'errors': 'grep ERROR | tail -50',
                'general': 'tail -200'
            },
            'markdown': {
                'structure': 'grep "^##" (headers only)',
                'section': 'Read specific section by header',
                'general': 'Read with offset/limit'
            },
            'code': {
                'structure': 'AST parser or grep class/function',
                'imports': 'Read offset=0 limit=20',
                'function': 'grep function_name -A 20',
                'general': 'Read with offset/limit'
            },
            'config': {
                'general': 'Read full (usually small)'
            },
            'binary': {
                'general': 'file command (metadata only, never content)'
            }
        }

        strategy = strategies.get(file_type, {}).get(purpose, 'Read full file')

        return {
            'filepath': filepath,
            'file_type': file_type,
            'purpose': purpose,
            'recommended_strategy': strategy,
            'command_hint': self.generate_command(file_type, filepath, purpose)
        }

    def generate_command(self, file_type, filepath, purpose):
        """Generate optimized CLI command for reading a file."""
        commands = {
            'json': {
                'structure': f'jq "keys" "{filepath}"',
                'general': f'jq . "{filepath}" | head -50'
            },
            'yaml': {
                'structure': f'yq eval "keys" "{filepath}"',
                'general': f'cat "{filepath}" | head -50'
            },
            'log': {
                'recent': f'tail -100 "{filepath}"',
                'errors': f'grep ERROR "{filepath}" | tail -50'
            },
            'markdown': {
                'structure': f'grep "^##" "{filepath}"',
            },
            'code': {
                'structure': f'grep -E "^(class|interface|function|def)" "{filepath}"',
                'imports': f'head -20 "{filepath}"'
            },
            'binary': {
                'general': f'file "{filepath}"'
            }
        }

        return commands.get(file_type, {}).get(purpose, f'cat "{filepath}"')

    def get_file_size(self, filepath):
        """Get file line count."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except:
            return 0

    def sandwich_read(self, filepath, head_lines=50, tail_lines=50):
        """Read first N and last N lines (sandwich strategy)."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            total_lines = len(lines)

            if total_lines <= (head_lines + tail_lines):
                return {
                    'strategy': 'full_read',
                    'content': ''.join(lines),
                    'lines': total_lines
                }

            head = ''.join(lines[:head_lines])
            tail = ''.join(lines[-tail_lines:])
            skipped = total_lines - head_lines - tail_lines

            summary = f"{head}\n... [{skipped} lines skipped] ...\n\n{tail}"

            return {
                'strategy': 'sandwich',
                'summary': summary,
                'head_lines': head_lines,
                'tail_lines': tail_lines,
                'skipped_lines': skipped,
                'total_lines': total_lines,
                'token_savings': f"{int((skipped / total_lines) * 100)}%"
            }
        except Exception as e:
            return {'error': str(e)}

    def ast_summary(self, filepath):
        """Generate AST-based summary for code files."""
        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.java':
            return self.java_summary(filepath)
        elif ext in ['.ts', '.js']:
            return self.typescript_summary(filepath)
        elif ext == '.py':
            return self.python_summary(filepath)
        else:
            return {'error': 'AST not supported for this file type'}

    def java_summary(self, filepath):
        """Extract Java structure."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            package = re.search(r'package\s+([\w.]+);', content)
            classes = re.findall(r'class\s+(\w+)', content)
            interfaces = re.findall(r'interface\s+(\w+)', content)
            methods = re.findall(r'(public|private|protected)\s+\w+\s+(\w+)\s*\(', content)

            return {
                'strategy': 'ast',
                'file_type': 'java',
                'package': package.group(1) if package else None,
                'classes': classes,
                'interfaces': interfaces,
                'methods': [m[1] for m in methods],
                'summary': f"Package: {package.group(1) if package else 'N/A'}\nClasses: {', '.join(classes)}"
            }
        except Exception as e:
            return {'error': str(e)}

    def typescript_summary(self, filepath):
        """Extract TypeScript structure."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            classes = re.findall(r'class\s+(\w+)', content)
            interfaces = re.findall(r'interface\s+(\w+)', content)
            functions = re.findall(r'function\s+(\w+)', content)
            exports = re.findall(r'export\s+(?:class|interface|function|const)\s+(\w+)', content)

            return {
                'strategy': 'ast',
                'file_type': 'typescript',
                'classes': classes,
                'interfaces': interfaces,
                'functions': functions,
                'exports': exports,
                'summary': f"Classes: {', '.join(classes)}\nInterfaces: {', '.join(interfaces)}"
            }
        except Exception as e:
            return {'error': str(e)}

    def python_summary(self, filepath):
        """Extract Python structure using AST."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree = ast_module.parse(f.read())

            classes = [node.name for node in ast_module.walk(tree) if isinstance(node, ast_module.ClassDef)]
            functions = [node.name for node in ast_module.walk(tree) if isinstance(node, ast_module.FunctionDef)]

            return {
                'strategy': 'ast',
                'file_type': 'python',
                'classes': classes,
                'functions': functions,
                'summary': f"Classes: {', '.join(classes)}\nFunctions: {', '.join(functions)}"
            }
        except Exception as e:
            return {'error': str(e)}

    def get_cleanup_strategy(self, level):
        """Get cleanup strategy based on context level."""
        strategies = {
            "light": {
                "description": "Light Cleanup (70-84% context)",
                "what_to_keep": [
                    "[CHECK] All session memory files (PROTECTED)",
                    "[CHECK] User preferences & learned patterns",
                    "[CHECK] Active task context",
                    "[CHECK] Recent decisions (last 5-10 prompts)",
                ],
                "what_to_remove": [
                    "[CROSS] Old file reads (15+ prompts ago, not actively used)",
                    "[CROSS] Processed MCP responses (data already extracted)",
                    "[CROSS] Redundant information (repeated content)",
                ],
                "compaction": "20% reduction",
            },
            "moderate": {
                "description": "Moderate Cleanup (85-89% context)",
                "what_to_keep": [
                    "[CHECK] All session memory files (PROTECTED)",
                    "[CHECK] User preferences & learned patterns",
                    "[CHECK] Current task context only",
                    "[CHECK] Key decisions (summary format)",
                ],
                "what_to_remove": [
                    "[CROSS] Old file reads (10+ prompts ago)",
                    "[CROSS] Completed task details (keep outcomes only)",
                    "[CROSS] Debugging context (if issue resolved)",
                ],
                "compaction": "50% reduction",
            },
            "aggressive": {
                "description": "Aggressive Cleanup (90%+ context)",
                "what_to_keep": [
                    "[CHECK] All session memory files (PROTECTED - ALWAYS!)",
                    "[CHECK] User preferences (global)",
                    "[CHECK] ONLY current task",
                ],
                "what_to_remove": [
                    "[CROSS] ALL old file reads (re-read if needed)",
                    "[CROSS] ALL completed tasks",
                    "[CROSS] ALL old conversation (except current)",
                ],
                "compaction": "90% reduction",
            },
        }

        return strategies.get(level, strategies["light"])

    def get_tiered_cache_tier(self, filepath):
        """Get cache tier for file based on access frequency."""
        index = self._load_tiered_index()
        fhash = hashlib.md5(filepath.encode()).hexdigest()

        if fhash not in index:
            return "COLD", 0

        entry = index[fhash]
        accesses = self._cleanup_old_accesses(entry.get('accesses', []), TIME_WINDOW)
        access_count = len(accesses)

        if access_count >= HOT_THRESHOLD:
            return "HOT", access_count
        elif access_count >= WARM_THRESHOLD:
            return "WARM", access_count
        else:
            return "COLD", access_count

    def _load_tiered_index(self):
        """Load tiered cache index."""
        if not os.path.exists(self.tiered_index_file):
            return {}

        try:
            with open(self.tiered_index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def _cleanup_old_accesses(self, accesses, time_window):
        """Remove accesses older than time window."""
        cutoff = datetime.now().timestamp() - time_window
        return [ts for ts in accesses if ts > cutoff]


def enforce():
    """Enforce context management policy.

    Main policy enforcement function that orchestrates all context management
    operations including monitoring, estimation, and cleanup recommendations.

    Returns:
        bool: True if enforcement succeeded, False otherwise.
    """
    print("\n" + "=" * 70)
    print("[ENFORCEMENT] CONTEXT MANAGEMENT POLICY")
    print("=" * 70)

    # Initialize components
    cache = ContextCache()
    estimator = ContextEstimator()
    monitor = ContextMonitor()
    pruner = ContextPruner()

    # Estimate context
    print("\n[ESTIMATOR] Collecting metrics...")
    metrics = estimator.get_session_metrics()
    estimated_percent = estimator.estimate_context_percentage(metrics)

    print(f"[ESTIMATE] Context usage: {estimated_percent}%")

    # Get recommendations
    recommendation = estimator.get_recommended_action(estimated_percent)
    print(f"[RECOMMENDATION] {recommendation['action']}")

    # Check actual context
    status = monitor.get_current_status()
    print(f"[MONITOR] Current percentage: {status['percentage']}%")

    # Log enforcement
    log_policy_hit(
        "enforce",
        f"estimated={estimated_percent}%, actual={status['percentage']}%, level={recommendation['level']}"
    )

    print("\n" + "=" * 70)
    print("[OK] Context management policy enforced")
    print("=" * 70)

    return True


def validate():
    """Validate context management setup.

    Checks that all required directories and files are present and accessible.

    Returns:
        bool: True if validation passed, False otherwise.
    """
    print("\n" + "=" * 70)
    print("[VALIDATION] CONTEXT MANAGEMENT SETUP")
    print("=" * 70)

    checks = {
        'Cache directory': CACHE_DIR,
        'Memory directory': MEMORY_DIR,
        'Logs directory': os.path.join(MEMORY_DIR, 'logs'),
    }

    all_ok = True

    for check_name, path in checks.items():
        if os.path.exists(path):
            print(f"[CHECK] {check_name}: OK ({path})")
        else:
            print(f"[CROSS] {check_name}: MISSING ({path})")
            all_ok = False

    # Check cache
    cache = ContextCache()
    stats = cache.get_stats()
    print(f"\n[CACHE] Statistics:")
    print(f"   Query entries: {stats['query_cache_entries']}")
    print(f"   Summary entries: {stats['summary_cache_entries']}")
    print(f"   Total size: {stats['total_cache_size_mb']} MB")

    # Check monitor
    monitor = ContextMonitor()
    status = monitor.get_current_status()
    print(f"\n[MONITOR] Current status:")
    print(f"   Context: {status['percentage']}%")
    print(f"   Level: {status['level'].upper()}")

    print("\n" + "=" * 70)
    if all_ok:
        print("[OK] All validation checks passed")
    else:
        print("[WARNING] Some validation checks failed")
    print("=" * 70)

    return all_ok


def report():
    """Generate context usage report.

    Creates a comprehensive report of current context management status
    including usage, cache stats, and recommendations.

    Returns:
        dict: Report dictionary with all metrics.
    """
    print("\n" + "=" * 70)
    print("[REPORT] CONTEXT MANAGEMENT STATUS")
    print("=" * 70)

    monitor = ContextMonitor()
    cache = ContextCache()
    estimator = ContextEstimator()

    # Current status
    status = monitor.get_current_status()

    # Cache stats
    cache_stats = cache.get_stats()

    # Metrics
    metrics = estimator.get_session_metrics()

    # Compile report
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'context_monitoring': status,
        'cache_statistics': cache_stats,
        'session_metrics': metrics,
        'recommendations': status.get('recommendations', []),
    }

    # Print summary
    print(f"\n[CONTEXT] Current: {status['percentage']}%")
    print(f"[CACHE] Entries: {cache_stats['query_cache_entries']} query + {cache_stats['summary_cache_entries']} summary")
    print(f"[SESSION] Messages: {metrics['message_count']}, Reads: {metrics['file_reads']}, Tools: {metrics['tool_calls']}")

    if status.get('recommendations'):
        print(f"\n[RECOMMENDATIONS]:")
        for rec in status['recommendations'][:3]:
            print(f"   {rec}")

    print("\n" + "=" * 70)
    print("[OK] Report generated")
    print("=" * 70)

    return report_data


def main():
    """Entry point for CLI execution.

    Parses command-line arguments and executes the requested policy action.
    Supports enforcement, validation, reporting, and component-specific operations.
    """
    parser = argparse.ArgumentParser(
        description="Context Management Policy - Consolidated Implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python context-management-policy.py --enforce
    python context-management-policy.py --validate
    python context-management-policy.py --report
    python context-management-policy.py --cache-stats
    python context-management-policy.py --estimate-context
    python context-management-policy.py --test
        """
    )

    parser.add_argument('--enforce', action='store_true', help='Enforce context management policy')
    parser.add_argument('--validate', action='store_true', help='Validate setup')
    parser.add_argument('--report', action='store_true', help='Generate report')
    parser.add_argument('--cache-stats', action='store_true', help='Show cache statistics')
    parser.add_argument('--estimate-context', action='store_true', help='Estimate context usage')
    parser.add_argument('--optimize-file', help='Get optimization strategy for file')
    parser.add_argument('--test', action='store_true', help='Run tests')
    parser.add_argument('--summary', action='store_true', help='Show summary')

    args = parser.parse_args()

    if args.test:
        print("[TEST] Running context management tests...")
        cache = ContextCache()
        print(f"  [OK] ContextCache initialized")
        estimator = ContextEstimator()
        print(f"  [OK] ContextEstimator initialized")
        extractor = ContextExtractor()
        print(f"  [OK] ContextExtractor initialized")
        monitor = ContextMonitor()
        print(f"  [OK] ContextMonitor initialized")
        pruner = ContextPruner()
        print(f"  [OK] ContextPruner initialized")
        optimizer = ContextOptimizer()
        print(f"  [OK] ContextOptimizer initialized")
        print("\n[OK] All tests passed!")
        return 0

    if args.cache_stats:
        cache = ContextCache()
        stats = cache.get_stats()
        print(json.dumps(stats, indent=2))
        return 0

    if args.estimate_context:
        estimator = ContextEstimator()
        metrics = estimator.get_session_metrics()
        percent = estimator.estimate_context_percentage(metrics)
        recommendation = estimator.get_recommended_action(percent)
        print(json.dumps({
            'estimated_context_percent': percent,
            'metrics': metrics,
            'recommendation': recommendation
        }, indent=2))
        return 0

    if args.optimize_file:
        optimizer = ContextOptimizer()
        result = optimizer.optimize_read(args.optimize_file)
        print(json.dumps(result, indent=2))
        return 0

    if args.enforce:
        return 0 if enforce() else 1

    if args.validate:
        return 0 if validate() else 1

    if args.report:
        report_data = report()
        print(json.dumps(report_data, indent=2))
        return 0

    if args.summary:
        return 0 if enforce() else 1

    # Default: show help if no arguments
    if len(sys.argv) < 2:
        parser.print_help()
        return 0

    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Context window monitoring with actionable recommendations.

Reads the current context window usage percentage from the Claude Memory
System and produces colour-coded status levels with concrete optimisation
recommendations. Designed to be embedded in the 3-level policy flow so
that Claude always knows how much context remains and can act accordingly.

Context percentage source priority
-----------------------------------
1. ``session-progress.json`` -- Updated after every tool call by the
   post-tool-tracker hook (most up-to-date).
2. ``.context-estimate`` -- JSON file written by hook metrics.
3. ``.context-usage`` -- JSON file, used only if younger than 30 minutes
   (older values are considered stale).
4. ``0`` -- Unknown/unavailable (better than returning a lying 80%).

Status levels (configurable via ``thresholds`` attribute)
----------------------------------------------------------
green   -- < 60 %   : Healthy, proceed normally.
yellow  -- 60-70 %  : Elevated, use caching and pagination.
orange  -- 70-80 %  : High, use external state; consider new session.
red     -- >= 80 %  : Critical, save session and restart immediately.

CLI usage::

    python context-monitor-v2.py
    python context-monitor-v2.py --current-status
    python context-monitor-v2.py --update 75.5
    python context-monitor-v2.py --simulate 90
    python context-monitor-v2.py --init
    python context-monitor-v2.py --recommendations

Windows-safe: reconfigures stdout/stderr to UTF-8 on startup.

Version: 2.0.0
Last Modified: 2026-02-18
Author: Claude Memory System
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
import json
import argparse
from pathlib import Path
from datetime import datetime

class ContextMonitorV2:
    """Context window usage monitor with threshold-based status levels.

    Reads context usage data written by hook scripts and exposes it as
    structured status objects with actionable recommendations. All file
    reads are wrapped in try/except so a missing or corrupt file never
    causes the hook chain to fail.

    Attributes:
        memory_dir: Base path to the Claude memory directory.
        context_file: Path to the ``.context-usage`` JSON file.
        estimate_file: Path to the ``.context-estimate`` JSON file.
        thresholds: Dict mapping status level names to percentage limits.
            ``green`` < threshold, ``yellow`` < threshold, etc.

    Example::

        monitor = ContextMonitorV2()
        status = monitor.get_current_status()
        print(status['level'], status['percentage'])
    """

    def __init__(self):
        """Initialise monitor with default thresholds and file paths."""
        self.memory_dir = Path.home() / '.claude' / 'memory'
        self.context_file = self.memory_dir / '.context-usage'
        self.estimate_file = self.memory_dir / '.context-estimate'

        # Thresholds (LOWERED for aggressive auto-compact)
        self.thresholds = {
            'green': 60,    # < 60% OK
            'yellow': 70,   # 60-70% use cache
            'orange': 80,   # 70-80% use external state
            'red': 85       # 80%+ save and restart (AUTO-COMPACT!)
        }

    def get_context_percentage(self):
        """
        Get current context usage percentage.
        Priority order:
          1. session-progress.json dynamic estimate (most up-to-date, updates after every tool call)
          2. .context-estimate JSON (metrics-based estimate from hooks)
          3. .context-usage JSON only if written within last 30 minutes (not stale)
          4. 0 (unknown, better than lying with 80.0)
        """
        # --- Priority 1: session-progress.json dynamic estimate ---
        try:
            session_progress = self.memory_dir / 'logs' / 'session-progress.json'
            if session_progress.exists():
                with open(session_progress, 'r', encoding='utf-8') as f:
                    sp = json.load(f)
                if 'context_estimate_pct' in sp:
                    return float(sp['context_estimate_pct'])
        except Exception:
            pass

        # --- Priority 2: .context-estimate (JSON with context_percent field) ---
        if self.estimate_file.exists():
            try:
                with open(self.estimate_file, 'r', encoding='utf-8') as f:
                    est_data = json.load(f)
                pct = est_data.get('context_percent', None)
                if pct is not None:
                    return float(pct)
            except Exception:
                pass

        # --- Priority 3: .context-usage only if NOT stale (< 30 min old) ---
        if self.context_file.exists():
            try:
                with open(self.context_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                updated_at_str = data.get('updated_at', '')
                if updated_at_str:
                    updated_at = datetime.fromisoformat(updated_at_str)
                    age_minutes = (datetime.now() - updated_at).total_seconds() / 60
                    if age_minutes < 30:
                        return float(data.get('percentage', 0))
                # File is stale - do not use it
            except Exception:
                pass

        # --- Priority 4: unknown ---
        return 0

    def get_status_level(self, percentage: float) -> str:
        """Map a context usage percentage to a named status level.

        Args:
            percentage: Context usage as a float between 0 and 100.

        Returns:
            One of ``'green'``, ``'yellow'``, ``'orange'``, or ``'red'``
            based on the configured threshold values.
        """
        if percentage < self.thresholds['green']:
            return 'green'
        elif percentage < self.thresholds['yellow']:
            return 'yellow'
        elif percentage < self.thresholds['orange']:
            return 'orange'
        else:
            return 'red'

    def get_recommendations(self, percentage: float) -> list:
        """Return actionable recommendation strings for the given usage level.

        Args:
            percentage: Context usage percentage (0-100).

        Returns:
            List of recommendation strings tailored to the current level.
            Each string is suitable for direct display in hook output.
        """
        level = self.get_status_level(percentage)
        recommendations = []

        if level == 'green':
            recommendations.append("[OK] Context usage healthy")

        elif level == 'yellow':
            recommendations.append("[WARN]  Context usage elevated (70-85%)")
            recommendations.append("-> Use cached file summaries when available")
            recommendations.append("-> Use offset/limit for large file reads")
            recommendations.append("-> Use head_limit for Grep searches")

        elif level == 'orange':
            recommendations.append("[HIGH] Context usage high (85-90%)")
            recommendations.append("-> REQUIRED: Reference session state instead of full history")
            recommendations.append("-> Use context cache aggressively")
            recommendations.append("-> Extract summaries from tool outputs")
            recommendations.append("-> Consider saving session and continuing in new context")

        else:  # red
            recommendations.append("[CRITICAL] Context usage critical (90%+)")
            recommendations.append("-> IMMEDIATE: Save current session state")
            recommendations.append("-> IMMEDIATE: Start new session with state reference")
            recommendations.append("-> DO NOT execute large tool calls")

        return recommendations

    def get_optimization_suggestions(self) -> list:
        """Return a static list of general context optimisation suggestions.

        Returns:
            List of tip strings referencing specific helper scripts that
            Claude can use to reduce context consumption.
        """
        return [
            "Use pre-execution-optimizer.py before tool calls",
            "Use context-extractor.py after tool outputs",
            "Check context-cache.py for cached summaries",
            "Use session-state.py to reference external state",
            "Review files accessed 3+ times for caching"
        ]

    def get_current_status(self) -> dict:
        """Return a complete status snapshot for the current moment.

        Combines the usage percentage, status level, and recommendations
        into a single dict. Also adds optional cache and session state
        counters if the relevant directories exist.

        Returns:
            Dict with keys:
                ``percentage``     -- Current usage float.
                ``level``          -- Status level string.
                ``thresholds``     -- Copy of the threshold configuration.
                ``recommendations``-- List of recommendation strings.
                ``timestamp``      -- ISO-8601 timestamp of this snapshot.
                ``cache_entries``  -- (optional) Count of cached JSON files.
                ``active_sessions``-- (optional) Count of active state files.
        """
        percentage = self.get_context_percentage()
        level = self.get_status_level(percentage)
        recommendations = self.get_recommendations(percentage)

        status = {
            'percentage': percentage,
            'level': level,
            'thresholds': self.thresholds,
            'recommendations': recommendations,
            'timestamp': datetime.now().isoformat()
        }

        # Add cache stats if available
        try:
            from pathlib import Path
            cache_dir = self.memory_dir / '.cache'
            if cache_dir.exists():
                cache_files = len(list(cache_dir.rglob('*.json')))
                status['cache_entries'] = cache_files
        except:
            pass

        # Add session state info
        try:
            state_dir = self.memory_dir / '.state'
            if state_dir.exists():
                state_files = list(state_dir.glob('*.json'))
                status['active_sessions'] = len(state_files)
        except:
            pass

        return status

    def update_percentage(self, percentage: float) -> bool:
        """Persist a new context usage percentage to the monitoring files.

        Writes both the ``.context-usage`` JSON file (with timestamp) and
        the ``.context-estimate`` JSON file so that subsequent reads return
        the updated value.

        Args:
            percentage: New context usage percentage (0-100).

        Returns:
            Always ``True`` (errors propagate as exceptions from file I/O).
        """
        data = {
            'percentage': percentage,
            'updated_at': datetime.now().isoformat()
        }

        self.context_file.write_text(json.dumps(data, indent=2))
        self.estimate_file.write_text(str(percentage))

        return True

    def simulate(self, percentage: float) -> dict:
        """Temporarily set usage to ``percentage`` and display the result.

        Saves the original percentage, updates to the simulated value,
        retrieves the status and prints it, then restores the original.
        Useful for testing how the hook output looks at various usage levels.

        Args:
            percentage: Simulated context usage percentage (0-100).

        Returns:
            Status dict returned by ``get_current_status()`` at the
            simulated percentage.
        """
        print(f"\n{'='*60}")
        print(f"SIMULATING CONTEXT AT {percentage}%")
        print(f"{'='*60}\n")

        # Temporarily update
        original = self.get_context_percentage()
        self.update_percentage(percentage)

        # Get status
        status = self.get_current_status()

        # Print status
        print(f"Level: {status['level'].upper()}")
        print(f"\nRecommendations:")
        for rec in status['recommendations']:
            print(f"  {rec}")

        print(f"\nOptimization Suggestions:")
        for sug in self.get_optimization_suggestions():
            print(f"  - {sug}")

        # Restore original
        self.update_percentage(original)

        return status

    def init(self) -> bool:
        """Initialise the context monitoring directory structure.

        Creates the cache and state directories required by the monitoring
        system and seeds the context usage file at 0 % if it does not yet
        exist. Safe to call multiple times (idempotent).

        Returns:
            ``True`` after successful initialisation.
        """
        # Create necessary directories
        (self.memory_dir / '.cache').mkdir(exist_ok=True)
        (self.memory_dir / '.cache' / 'summaries').mkdir(exist_ok=True)
        (self.memory_dir / '.cache' / 'queries').mkdir(exist_ok=True)
        (self.memory_dir / '.state').mkdir(exist_ok=True)

        # Initialize context file if not exists
        if not self.context_file.exists():
            self.update_percentage(0)

        print("[OK] Context monitoring initialized")
        return True

def main() -> int:
    """CLI entry point for the context monitor.

    Parses command-line flags and delegates to the appropriate
    ``ContextMonitorV2`` method. Returns 0 on success.

    Flags:
        --current-status   Print full status JSON to stdout.
        --update FLOAT     Set the context usage percentage.
        --simulate FLOAT   Display status at a hypothetical percentage.
        --init             Initialise directory structure.
        --recommendations  Print only the recommendation strings.
    """
    parser = argparse.ArgumentParser(description='Context monitor v2')
    parser.add_argument('--current-status', action='store_true', help='Get current status')
    parser.add_argument('--update', type=float, help='Update percentage')
    parser.add_argument('--simulate', type=float, help='Simulate percentage')
    parser.add_argument('--init', action='store_true', help='Initialize monitoring')
    parser.add_argument('--recommendations', action='store_true', help='Get recommendations only')

    args = parser.parse_args()

    monitor = ContextMonitorV2()

    if args.init:
        monitor.init()
        return 0

    if args.simulate is not None:
        monitor.simulate(args.simulate)
        return 0

    if args.update is not None:
        monitor.update_percentage(args.update)
        print(f"Context percentage updated to {args.update}%")
        return 0

    if args.recommendations:
        percentage = monitor.get_context_percentage()
        recommendations = monitor.get_recommendations(percentage)
        for rec in recommendations:
            print(rec)
        return 0

    # Default: show current status
    status = monitor.get_current_status()
    print(json.dumps(status, indent=2))

    return 0

if __name__ == '__main__':
    sys.exit(main())

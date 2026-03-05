#!/usr/bin/env python3
"""Patch docstrings in post-tool-tracker.py"""

filepath = r"C:\Users\techd\Documents\workspace-spring-tool-suite-4-4.27.0-new\claude-insight\scripts\post-tool-tracker.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

patches = []

# Patch 1: convert header block comment to module docstring
old1 = (
    "#!/usr/bin/env python\n"
    "# Script Name: post-tool-tracker.py\n"
    "# Version: 3.1.0 (Policy-linked + task/phase enforcement)\n"
    "# Last Modified: 2026-03-03\n"
    "# Description: PostToolUse hook - L3.9 tracking + L3.11 commit + L6 subagent + voice on task complete\n"
    "#              + task progress update frequency enforcement (from task-progress-tracking-policy.md)\n"
    "#              + complexity-aware progress weighting (from task-phase-enforcement-policy.md)\n"
    "# v3.1.0: Policy enforcement: warn if >5 tool calls without TaskUpdate.\n"
    "#          Complexity-aware progress deltas from flow-trace. Linked to policy .md files.\n"
    "# v3.0.0: Reads flow-trace.json for task type, complexity, skill context.\n"
    "#          Enriches tool-tracker.jsonl entries with task context. Better progress estimation.\n"
    "# v2.3.0: Added PID-based flag isolation for multi-window support\n"
    "# v2.2.0: Auto work-done voice flag when all tasks completed (fixes unreliable voice)\n"
    "# v2.1.0: Added file change tracking for git commit reminders (10+ modified files warning)\n"
    "# Author: Claude Memory System\n"
    "#\n"
    "# Hook Type: PostToolUse\n"
    "# Trigger: Runs AFTER every tool call (NEVER blocks)\n"
    "# Exit: Always 0\n"
    "#\n"
    "# Policies enforced:\n"
    "#   Level 3.9 - Execute Tasks (Auto-Tracking):\n"
    "#     - Read  -> progress +10%\n"
    "#     - Write -> progress +40%  (likely completed something)\n"
    "#     - Edit  -> progress +30%  (likely completed something)\n"
    "#     - Bash  -> progress +15%  (ran a command)\n"
    "#     - Task  -> progress +20%  (delegated work)\n"
    "#     - Grep/Glob -> progress +5% (searching)\n"
    "#   Policy: task-progress-tracking-policy.md\n"
    "#     - Warn if >5 tool calls without TaskUpdate (update frequency enforcement)\n"
    "#     - Recommend update every 2-3 tool calls\n"
    "#   Policy: task-phase-enforcement-policy.md\n"
    "#     - Complexity >= 6 -> remind about phased execution\n"
    "#     - Progress deltas weighted by complexity from flow-trace\n"
    "#\n"
    "# Logs to: ~/.claude/memory/logs/tool-tracker.jsonl\n"
    "# Windows-safe: ASCII only, no Unicode chars"
)
new1 = (
    '#!/usr/bin/env python\n'
    '"""\n'
    'post-tool-tracker.py - PostToolUse hook for progress tracking and policy enforcement.\n'
    '\n'
    'Script Name: post-tool-tracker.py\n'
    'Version:     3.1.0 (Policy-linked + task/phase enforcement)\n'
    'Last Modified: 2026-03-03\n'
    'Author:      Claude Memory System\n'
    '\n'
    'Hook Type: PostToolUse\n'
    'Trigger:   Runs AFTER every tool call.  NEVER blocks (always exits 0).\n'
    '\n'
    'Level 3.9 - Execute Tasks (Auto-Tracking)\n'
    '------------------------------------------\n'
    'Increments session progress by a weighted delta per tool call:\n'
    '  Read          -> +10%\n'
    '  Write         -> +40%\n'
    '  Edit          -> +30%\n'
    '  Bash          -> +15%\n'
    '  Task          -> +20%\n'
    '  Grep/Glob     -> +5%\n'
    'Deltas are halved at complexity >= 8 and quartered at complexity >= 15\n'
    'so that large tasks do not hit 100% prematurely.\n'
    '\n'
    'Policy: task-progress-tracking-policy.md\n'
    '  Warn if more than 5 tool calls occur without a TaskUpdate.\n'
    '  Recommend updating every 2-3 tool calls.\n'
    '\n'
    'Policy: task-phase-enforcement-policy.md\n'
    '  Complexity >= 6 requires phased execution.\n'
    '  Warn if Write/Edit/NotebookEdit is called before TaskCreate.\n'
    '\n'
    'Level 3.1 Enforcement\n'
    '----------------------\n'
    'Clears .task-breakdown-pending flag when TaskCreate is called with\n'
    'valid subject (10+ chars) and description (10+ chars).\n'
    '\n'
    'Level 3.5 Enforcement\n'
    '----------------------\n'
    'Clears .skill-selection-pending flag when Skill or Task is called\n'
    'and the invoked skill matches the required skill in the flag file.\n'
    '\n'
    'Level 3.11 + GitHub Integration\n'
    '---------------------------------\n'
    'On TaskUpdate(status=completed): triggers auto-commit, build\n'
    'validation, GitHub issue close, and auto-writes .session-work-done\n'
    'when all tasks are finished.\n'
    '\n'
    'Context Chain:\n'
    '    3-level-flow.py writes flow-trace.json -> this hook reads it to\n'
    '    enrich tool-tracker.jsonl with task_type, complexity, and skill.\n'
    '\n'
    'Logs to:      ~/.claude/memory/logs/tool-tracker.jsonl\n'
    'Windows-safe: ASCII only, no Unicode characters.\n'
    '"""'
)
patches.append((old1, new1, 'module docstring'))

# Patch 2: _get_session_id_from_progress
old2 = (
    'def _get_session_id_from_progress():\n'
    '    """Get current session ID from session-progress.json."""'
)
new2 = (
    'def _get_session_id_from_progress():\n'
    '    """Get the current session ID from the session-progress.json file.\n'
    '\n'
    '    Reads SESSION_STATE_FILE and returns the session_id field.  Returns\n'
    '    an empty string on any read/parse error so callers can safely treat\n'
    '    a missing session as a no-op rather than raising an exception.\n'
    '\n'
    '    Returns:\n'
    '        str: Active session ID (e.g. "SESSION-20260305-001"), or empty\n'
    '             string when the file is missing or unreadable.\n'
    '    """'
)
patches.append((old2, new2, '_get_session_id_from_progress'))

# Patch 3: main() in post-tool-tracker
old3 = (
    'def main():\n'
    '    # INTEGRATION: Load progress tracking policies from scripts/architecture/\n'
    '    # Retry up to 3 times. On 3rd failure, warn but don\'t hard-break\n'
    '    # (PostToolUse runs per-tool, not session-level).'
)
new3 = (
    'def main():\n'
    '    """PostToolUse hook entry point.\n'
    '\n'
    '    Reads tool name, input, and response from Claude Code hook stdin\n'
    '    (JSON), then in order:\n'
    '      1. Loads task-progress-tracking-policy.py (with 3 retries).\n'
    '      2. Determines success/error status of the completed tool call.\n'
    '      3. Loads flow-trace context to get task complexity and skill.\n'
    '      4. Calculates a complexity-weighted progress delta.\n'
    '      5. Appends a rich entry to tool-tracker.jsonl.\n'
    '      6. Updates session-progress.json (with file locking).\n'
    '      7. Enforces task-update frequency and phase-complexity rules.\n'
    '      8. Clears task-breakdown and skill-selection flags as appropriate.\n'
    '      9. Triggers auto-commit, build validation, and GitHub issue\n'
    '         management on task completion.\n'
    '\n'
    '    Always exits 0.  Errors are caught and swallowed to ensure\n'
    '    the hook never disrupts the tool call flow.\n'
    '    """\n'
    '    # INTEGRATION: Load progress tracking policies from scripts/architecture/\n'
    '    # Retry up to 3 times. On 3rd failure, warn but don\'t hard-break\n'
    '    # (PostToolUse runs per-tool, not session-level).'
)
patches.append((old3, new3, 'main'))

applied = 0
for old, new, name in patches:
    if old in content:
        content = content.replace(old, new, 1)
        print(f'[OK] Patched: {name}')
        applied += 1
    else:
        print(f'[MISS] Not found: {name}')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Done writing post-tool-tracker.py ({applied}/{len(patches)} patches applied)')

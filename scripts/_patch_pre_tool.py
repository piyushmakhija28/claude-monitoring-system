#!/usr/bin/env python3
"""Patch docstrings in pre-tool-enforcer.py"""
import sys

filepath = r"C:\Users\techd\Documents\workspace-spring-tool-suite-4-4.27.0-new\claude-insight\scripts\pre-tool-enforcer.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

patches = []

# Patch 1: convert header block comment to module docstring
old1 = (
    "#!/usr/bin/env python\n"
    "# Script Name: pre-tool-enforcer.py\n"
    "# Version: 3.2.0 (Policy-linked + failure-kb.json integration)\n"
    "# Last Modified: 2026-03-03\n"
    "# Description: PreToolUse hook - L3.1/3.5 blocking + L3.6 hints + L3.7 prevention\n"
    "#              + L3.5+ dynamic per-file skill context switching\n"
    "#              + flow-trace.json context chaining for task-aware enforcement\n"
    "# v3.1.0: Reads flow-trace.json for task type, complexity, skill/agent context.\n"
    "#          Provides task-aware optimization hints. Full context chain from 3-level-flow.\n"
    "# v3.0.0: Dynamic per-file skill/agent selection - switches skill context per tool call\n"
    "#          based on target file extension/name. Mixed-stack projects get correct skill per file.\n"
    "# v2.3.0: Added window-isolation helpers for PID-specific flag isolation\n"
    "# v2.2.0: Checkpoint blocking disabled - hook shows table, Claude auto-proceeds (no ok/proceed needed)\n"
    "# v2.1.0: Enhanced optimization hints with consistent [OPTIMIZATION] format and clearer guidance\n"
    "# Author: Claude Memory System\n"
    "#\n"
    "# Hook Type: PreToolUse\n"
    "# Trigger: Runs BEFORE every tool call\n"
    "# Exit 0 = Allow tool (may print hints to stdout)\n"
    "# Exit 1 = BLOCK tool (prints reason to stderr)\n"
    "#\n"
    "# Policies enforced:\n"
    "#   Level 3.3 - Review Checkpoint:\n"
    "#     - DISABLED (v2.2.0): Hook shows checkpoint table, Claude auto-proceeds. No blocking.\n"
    "#     - Flag file .checkpoint-pending-*.json is NEVER written (removed from 3-level-flow.py)\n"
    "#   Level 3.1 - Task Breakdown (Loophole #7 Fix):\n"
    "#     - Write/Edit/NotebookEdit: BLOCK if .task-breakdown-pending.json exists (same session+PID)\n"
    "#     - Bash/Task NOT blocked: investigation and exploration allowed before TaskCreate\n"
    "#     - Cleared when TaskCreate is called (post-tool-tracker.py)\n"
    "#   Level 3.5 - Skill/Agent Selection (Loophole #7 Fix):\n"
    "#     - Write/Edit/NotebookEdit: BLOCK if .skill-selection-pending.json exists (same session+PID)\n"
    "#     - Bash/Task NOT blocked: Bash needed for git/tests, Task IS how Step 3.5 is done\n"
    "#     - Cleared when Skill or Task tool is called (post-tool-tracker.py)\n"
    "#   Level 3.6 - Tool Usage Optimization:\n"
    "#     - Grep: warn if missing head_limit\n"
    "#     - Read: warn if missing offset+limit (for large files)\n"
    "#   Level 3.7 - Failure Prevention:\n"
    "#     - Bash: BLOCK Windows-only commands (del, copy, dir, xcopy, etc.)\n"
    "#     - Write/Edit/NotebookEdit: BLOCK Unicode chars in .py files on Windows\n"
    "#\n"
    "# Windows-safe: ASCII only, no Unicode chars"
)
new1 = (
    '#!/usr/bin/env python\n'
    '"""\n'
    'pre-tool-enforcer.py - PreToolUse hook that enforces policy before every tool call.\n'
    '\n'
    'Script Name: pre-tool-enforcer.py\n'
    'Version:     3.2.0 (Policy-linked + failure-kb.json integration)\n'
    'Last Modified: 2026-03-03\n'
    'Author:      Claude Memory System\n'
    '\n'
    'Hook Type: PreToolUse\n'
    'Trigger:   Runs BEFORE every tool call.\n'
    'Exit 0   = Allow tool (may print optimization hints to stdout).\n'
    'Exit 1/2 = BLOCK tool (prints blocking reason to stderr).\n'
    '\n'
    'Policies enforced\n'
    '-----------------\n'
    'Level 3.3 - Review Checkpoint:\n'
    '    DISABLED (v2.2.0): Hook shows checkpoint table; Claude auto-proceeds.\n'
    '    Flag .checkpoint-pending-*.json is never written.\n'
    '\n'
    'Level 3.1 - Task Breakdown (Loophole #7 Fix):\n'
    '    Write/Edit/NotebookEdit are BLOCKED while .task-breakdown-pending.json\n'
    '    exists for the current session+PID.\n'
    '    Bash/Task NOT blocked (investigation allowed before TaskCreate).\n'
    '    Flag cleared by post-tool-tracker.py when TaskCreate is called.\n'
    '\n'
    'Level 3.5 - Skill/Agent Selection (Loophole #7 Fix):\n'
    '    Write/Edit/NotebookEdit are BLOCKED while .skill-selection-pending.json\n'
    '    exists for the current session+PID.\n'
    '    Bash/Task NOT blocked (Bash needed for git/tests; Task IS step 3.5).\n'
    '    Flag cleared by post-tool-tracker.py when Skill or Task is called.\n'
    '\n'
    'Level 3.5+ Dynamic Skill Context:\n'
    '    Detects file extension/name on every Read/Write/Edit/Grep/Glob call\n'
    '    and injects the matching skill/agent hint to stdout.\n'
    '\n'
    'Level 3.6 - Tool Usage Optimization:\n'
    '    Grep: warn if head_limit is missing.\n'
    '    Read: warn if offset+limit are missing for large-file reads.\n'
    '\n'
    'Level 3.7 - Failure Prevention:\n'
    '    Bash: BLOCK Windows-only commands (del, copy, dir, xcopy, ...).\n'
    '    Write/Edit/NotebookEdit: BLOCK Unicode chars in .py files on Windows.\n'
    '\n'
    'Context Chain:\n'
    '    3-level-flow.py writes flow-trace.json -> this hook reads it to\n'
    '    provide task-aware optimization hints (v3.1.0+).\n'
    '\n'
    'Windows-safe: ASCII only, no Unicode characters.\n'
    '"""'
)
patches.append((old1, new1, 'module docstring'))

# Patch 2: check_bash
old2 = (
    'def check_bash(command):\n'
    '    """Level 3.7: Detect Windows-only commands that fail in bash.\n'
    '    Policy: policies/03-execution-system/failure-prevention/common-failures-prevention.md\n'
    '    KB: scripts/architecture/03-execution-system/failure-prevention/failure-kb.json (bash_windows_command)"""'
)
new2 = (
    'def check_bash(command):\n'
    '    """Level 3.7: Detect and block Windows-only shell commands.\n'
    '\n'
    '    Scans the command string for Windows-only prefixes listed in WINDOWS_CMDS.\n'
    '    Matches at the start of the command or after newline, semicolon, or &&\n'
    '    chaining operators so piped multi-step commands are caught.\n'
    '\n'
    '    Policy:    policies/03-execution-system/failure-prevention/\n'
    '               common-failures-prevention.md\n'
    '    KB source: scripts/architecture/03-execution-system/failure-prevention/\n'
    '               failure-kb.json (pattern: bash_windows_command)\n'
    '\n'
    '    Args:\n'
    "        command: Full Bash command string from tool_input['command'].\n"
    '\n'
    '    Returns:\n'
    '        tuple: (hints, blocks) where blocks is non-empty when a Windows\n'
    '               command is detected and the tool call must be rejected.\n'
    '    """'
)
patches.append((old2, new2, 'check_bash'))

# Patch 3: check_write_edit
old3 = (
    'def check_write_edit(tool_name, tool_input):\n'
    '    """Level 3.7: Check Python files for Unicode before writing."""'
)
new3 = (
    'def check_write_edit(tool_name, tool_input):\n'
    '    """Level 3.7: Block Unicode characters in Python files on Windows.\n'
    '\n'
    '    Extracts the file content from Write, Edit, or NotebookEdit tool inputs\n'
    '    and delegates to check_python_unicode() for any .py target file.  Only\n'
    '    .py files are checked; other file types are allowed unconditionally.\n'
    '\n'
    '    Policy:    policies/03-execution-system/failure-prevention/\n'
    '               common-failures-prevention.md\n'
    '\n'
    '    Args:\n'
    "        tool_name: Name of the tool being called ('Write', 'Edit', or\n"
    "                   'NotebookEdit').\n"
    '        tool_input: Dict of tool parameters containing file_path/notebook_path\n'
    '                    and the new content or new_string/new_source field.\n'
    '\n'
    '    Returns:\n'
    '        tuple: (hints, blocks) where blocks is non-empty when dangerous\n'
    '               Unicode characters are found in a .py file.\n'
    '    """'
)
patches.append((old3, new3, 'check_write_edit'))

# Patch 4: check_python_unicode
old4 = (
    'def check_python_unicode(content):\n'
    '    """Level 3.7: Detect Unicode chars in Python files (crash on Windows cp1252).\n'
    '    Policy: policies/03-execution-system/failure-prevention/common-failures-prevention.md\n'
    '    Architecture: scripts/architecture/03-execution-system/failure-prevention/windows-python-unicode-checker.py"""'
)
new4 = (
    'def check_python_unicode(content):\n'
    '    """Level 3.7: Detect Unicode characters that crash Python on Windows cp1252.\n'
    '\n'
    '    Iterates over UNICODE_DANGER to find emoji, smart-quote, arrow, and other\n'
    '    non-ASCII codepoints that the Windows cp1252 console cannot encode without\n'
    '    raising UnicodeEncodeError.  Returns a blocking message with up to five\n'
    '    sample offending characters so the developer knows what to replace.\n'
    '\n'
    '    Policy:    policies/03-execution-system/failure-prevention/\n'
    '               common-failures-prevention.md\n'
    '    Arch ref:  scripts/architecture/03-execution-system/failure-prevention/\n'
    '               windows-python-unicode-checker.py\n'
    '\n'
    '    Args:\n'
    '        content: String content of the Python file about to be written.\n'
    '\n'
    '    Returns:\n'
    '        list: Block message strings (empty list means no violations found).\n'
    '    """'
)
patches.append((old4, new4, 'check_python_unicode'))

# Patch 5: check_dynamic_skill_context
old5 = (
    'def check_dynamic_skill_context(tool_name, tool_input):\n'
    '    """\n'
    '    Level 3.5+ Dynamic: Detect file type and inject appropriate skill/agent context.\n'
    '\n'
    '    Runs on Read/Write/Edit/Grep/Glob - any tool that targets a specific file.\n'
    '    Prints a [SKILL-CONTEXT] hint to stdout so Claude gets file-appropriate guidance.\n'
    '\n'
    '    Does NOT block (hints only). Does NOT override session-level selection.\n'
    '    Adds per-file context ON TOP of the primary skill/agent.\n'
    '\n'
    '    Returns list of hint strings.\n'
    '    """'
)
new5 = (
    'def check_dynamic_skill_context(tool_name, tool_input):\n'
    '    """Level 3.5+ Dynamic: inject skill/agent context based on target file type.\n'
    '\n'
    '    Extracts the target file path from any Read, Write, Edit, NotebookEdit,\n'
    '    Grep, or Glob tool call, then resolves the most appropriate skill or agent\n'
    '    via a priority chain:\n'
    '      1. Special filename map (FILENAME_SKILL_MAP)\n'
    '      2. Directory path patterns (DIR_PATTERN_SKILL_MAP)\n'
    '      3. File extension map (FILE_EXT_SKILL_MAP)\n'
    '      4. YAML/XML content heuristics\n'
    '\n'
    '    Emits a [SKILL-CONTEXT] hint to stdout so Claude applies correct patterns\n'
    '    for the specific file.  Does NOT block; does NOT override the session-level\n'
    '    skill already selected by 3-level-flow.py.  Deduplicates consecutive\n'
    '    identical hints via the _last_skill_hint module-level cache.\n'
    '\n'
    '    Args:\n'
    "        tool_name: Name of the tool being called ('Read', 'Write', etc.).\n"
    '        tool_input: Dict of tool parameters containing the file path key.\n'
    '\n'
    '    Returns:\n'
    '        list: Hint strings to print to stdout.  Empty when no skill matched\n'
    '              or the same hint was emitted for the previous tool call.\n'
    '    """'
)
patches.append((old5, new5, 'check_dynamic_skill_context'))

# Patch 6: main() in pre-tool-enforcer
old6 = (
    'def main():\n'
    '    # CONTEXT CHAIN: Load flow-trace context from 3-level-flow (cached per invocation)\n'
    '    # This gives pre-tool-enforcer awareness of task type, complexity, skill, model\n'
    '    flow_ctx = _load_flow_trace_context()'
)
new6 = (
    'def main():\n'
    '    """PreToolUse hook entry point.\n'
    '\n'
    '    Reads tool name and input from Claude Code hook stdin (JSON), then runs\n'
    '    all enforcement checks in order:\n'
    '      1. Checkpoint pending (Level 3.3)\n'
    '      2. Task breakdown pending (Level 3.1)\n'
    '      3. Skill/agent selection pending (Level 3.5)\n'
    '      4. Dynamic skill context hints (Level 3.5+)\n'
    '      5. Failure-KB hints (Level 3.7)\n'
    '      6. Tool-specific checker: Bash / Write-Edit / Grep / Read\n'
    '\n'
    '    Hints are written to stdout (non-blocking, shown as context to Claude).\n'
    '    Blocks are written to stderr and the process exits with code 2 (the\n'
    '    blocking exit code per Claude Code hook protocol).\n'
    '\n'
    '    Never raises exceptions; all errors are silently swallowed so a broken\n'
    '    hook never disrupts the underlying tool call.\n'
    '    """\n'
    '    # CONTEXT CHAIN: Load flow-trace context from 3-level-flow (cached per invocation)\n'
    '    # This gives pre-tool-enforcer awareness of task type, complexity, skill, model\n'
    '    flow_ctx = _load_flow_trace_context()'
)
patches.append((old6, new6, 'main'))

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

print(f'Done writing pre-tool-enforcer.py ({applied}/{len(patches)} patches applied)')

#!/usr/bin/env python3
"""Patch remaining undocumented functions in all four target scripts."""
from pathlib import Path

scripts_dir = Path(r"C:\Users\techd\Documents\workspace-spring-tool-suite-4-4.27.0-new\claude-insight\scripts")

# -------------------------------------------------------------------------
# 3-level-flow.py
# -------------------------------------------------------------------------
fp = scripts_dir / "3-level-flow.py"
src = fp.read_text(encoding='utf-8')

patches_3lf = [
    (
        'def show_help():\n'
        '    print(f"{SCRIPT_NAME} v{VERSION}")',
        'def show_help():\n'
        '    """Print usage information and exit."""\n'
        '    print(f"{SCRIPT_NAME} v{VERSION}")',
        'show_help',
    ),
    (
        'def emit_hook_execution(',
        None,  # handled below via grep
        'emit_hook_execution (3lf)',
    ),
]

# Use a safer line-by-line approach for emit functions
import re

def add_docstring_after_def(src, func_name, docstring):
    """Add docstring to the first occurrence of def func_name(...)."""
    pattern = r'(def ' + re.escape(func_name) + r'\([^)]*\):\n)'
    replacement = r'\1' + '    ' + docstring + '\n'
    new_src, count = re.subn(pattern, replacement, src, count=1)
    return new_src, count

# show_help
old = 'def show_help():\n    print(f"{SCRIPT_NAME} v{VERSION}")'
new = 'def show_help():\n    """Print usage information for the script."""\n    print(f"{SCRIPT_NAME} v{VERSION}")'
if old in src:
    src = src.replace(old, new, 1)
    print('[OK] 3-level-flow.py: show_help')
else:
    print('[MISS] 3-level-flow.py: show_help')

# emit_hook_execution (3lf)
doc_emit_hook = '"""Emit a structured hook-execution event to the trace pipeline."""'
src, n = add_docstring_after_def(src, 'emit_hook_execution', doc_emit_hook)
print(f'[{"OK" if n else "MISS"}] 3-level-flow.py: emit_hook_execution (added={n})')

# emit_policy_step
doc_emit_policy = '"""Emit a structured policy-step event to the trace pipeline."""'
src, n = add_docstring_after_def(src, 'emit_policy_step', doc_emit_policy)
print(f'[{"OK" if n else "MISS"}] 3-level-flow.py: emit_policy_step (added={n})')

# emit_flag_lifecycle (3lf)
doc_emit_flag = '"""Emit a structured flag lifecycle event (create/clear) to the trace pipeline."""'
src, n = add_docstring_after_def(src, 'emit_flag_lifecycle', doc_emit_flag)
print(f'[{"OK" if n else "MISS"}] 3-level-flow.py: emit_flag_lifecycle (added={n})')

# emit_enforcement_event (3lf)
doc_emit_enf = '"""Emit a structured enforcement event (block/allow) to the trace pipeline."""'
src, n = add_docstring_after_def(src, 'emit_enforcement_event', doc_emit_enf)
print(f'[{"OK" if n else "MISS"}] 3-level-flow.py: emit_enforcement_event (added={n})')

fp.write_text(src, encoding='utf-8')

# -------------------------------------------------------------------------
# pre-tool-enforcer.py
# -------------------------------------------------------------------------
fp2 = scripts_dir / "pre-tool-enforcer.py"
src2 = fp2.read_text(encoding='utf-8')

src2, n = add_docstring_after_def(src2, 'emit_hook_execution',
    '"""Emit a structured hook-execution event for the tool being checked."""')
print(f'[{"OK" if n else "MISS"}] pre-tool-enforcer.py: emit_hook_execution (added={n})')

src2, n = add_docstring_after_def(src2, 'emit_enforcement_event',
    '"""Emit a structured enforcement event (hint or block) for the current tool."""')
print(f'[{"OK" if n else "MISS"}] pre-tool-enforcer.py: emit_enforcement_event (added={n})')

src2, n = add_docstring_after_def(src2, 'emit_flag_lifecycle',
    '"""Emit a structured flag lifecycle event (read/clear) for enforcement flags."""')
print(f'[{"OK" if n else "MISS"}] pre-tool-enforcer.py: emit_flag_lifecycle (added={n})')

fp2.write_text(src2, encoding='utf-8')

# -------------------------------------------------------------------------
# post-tool-tracker.py
# -------------------------------------------------------------------------
fp3 = scripts_dir / "post-tool-tracker.py"
src3 = fp3.read_text(encoding='utf-8')

src3, n = add_docstring_after_def(src3, 'emit_hook_execution',
    '"""Emit a structured hook-execution event after a tool call completes."""')
print(f'[{"OK" if n else "MISS"}] post-tool-tracker.py: emit_hook_execution (added={n})')

src3, n = add_docstring_after_def(src3, 'emit_context_sample',
    '"""Emit a structured context-usage sample entry to the trace pipeline."""')
print(f'[{"OK" if n else "MISS"}] post-tool-tracker.py: emit_context_sample (added={n})')

src3, n = add_docstring_after_def(src3, 'emit_flag_lifecycle',
    '"""Emit a structured flag lifecycle event (clear) after a tool call."""')
print(f'[{"OK" if n else "MISS"}] post-tool-tracker.py: emit_flag_lifecycle (added={n})')

fp3.write_text(src3, encoding='utf-8')

# -------------------------------------------------------------------------
# auto-fix-enforcer.py  __init__
# -------------------------------------------------------------------------
fp4 = scripts_dir / "auto-fix-enforcer.py"
src4 = fp4.read_text(encoding='utf-8')

old4 = (
    '    def __init__(self):\n'
    '        # Use ide_paths for IDE self-contained installations (with fallback for standalone mode)'
)
new4 = (
    '    def __init__(self):\n'
    '        """Initialise paths and empty failure/fix tracking lists.\n'
    '\n'
    '        Attempts to import ide_paths for IDE-embedded installations.\n'
    '        Falls back to ~/.claude/scripts/ and ~/.claude/memory/ when\n'
    '        ide_paths is not available (standalone mode).\n'
    '        """\n'
    '        # Use ide_paths for IDE self-contained installations (with fallback for standalone mode)'
)
if old4 in src4:
    src4 = src4.replace(old4, new4, 1)
    print('[OK] auto-fix-enforcer.py: __init__')
else:
    print('[MISS] auto-fix-enforcer.py: __init__')

fp4.write_text(src4, encoding='utf-8')

print('\nAll remaining patches done.')

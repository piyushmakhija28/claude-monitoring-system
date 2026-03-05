#!/usr/bin/env python3
"""Patch docstrings in auto-fix-enforcer.py"""

filepath = r"C:\Users\techd\Documents\workspace-spring-tool-suite-4-4.27.0-new\claude-insight\scripts\auto-fix-enforcer.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

patches = []

# Patch 1: check_all_systems - expand existing one-liner
old1 = (
    '    def check_all_systems(self):\n'
    '        """Check ALL systems and collect failures"""'
)
new1 = (
    '    def check_all_systems(self):\n'
    '        """Run all 7 system health checks and collect any failures.\n'
    '\n'
    '        Executes each _check_*() sub-method in order:\n'
    '          1. _check_python()               - Python binary availability\n'
    '          2. _check_critical_files()        - Presence of blocking-policy-enforcer.py\n'
    '          3. _check_blocking_enforcer()     - Blocking-state.json initialisation\n'
    '          4. _check_session_state()         - Required session state flags\n'
    '          5. _check_daemons()               - Daemon PID file status (informational)\n'
    '          6. _check_git_repos()             - Git clean/dirty status (informational)\n'
    '          7. _check_windows_python_unicode() - Unicode characters in .py files\n'
    '\n'
    '        Failures are appended to self.failures.  The method returns\n'
    '        True only when self.failures is empty after all checks.\n'
    '\n'
    '        Returns:\n'
    '            bool: True if all checks passed (no failures collected).\n'
    '        """'
)
patches.append((old1, new1, 'check_all_systems'))

# Patch 2: _check_python
old2 = (
    '    def _check_python(self):\n'
    '        """Check if Python is available"""'
)
new2 = (
    '    def _check_python(self):\n'
    '        """Check [1/7]: Verify that the Python binary is available in PATH.\n'
    '\n'
    '        Runs "python --version" with a 5-second timeout.  A non-zero exit\n'
    '        code or an exception appends a CRITICAL failure to self.failures.\n'
    '\n'
    '        Returns:\n'
    '            bool: True if Python is accessible; False otherwise.\n'
    '        """'
)
patches.append((old2, new2, '_check_python'))

# Patch 3: _check_critical_files
old3 = (
    '    def _check_critical_files(self):\n'
    '        """Check if critical system files exist in ~/.claude/scripts/"""'
)
new3 = (
    '    def _check_critical_files(self):\n'
    '        """Check [2/7]: Verify that critical system files exist in scripts_path.\n'
    '\n'
    '        Currently one CRITICAL file is required: blocking-policy-enforcer.py.\n'
    '        Optional files (plan-detector.py, session-start.sh) are reported as\n'
    '        informational warnings and do not block the session.\n'
    '\n'
    '        Appends a CRITICAL failure to self.failures if any required file is\n'
    '        missing from self.scripts_path (~/.claude/scripts/ by default).\n'
    '        """'
)
patches.append((old3, new3, '_check_critical_files'))

# Patch 4: _check_blocking_enforcer
old4 = (
    '    def _check_blocking_enforcer(self):\n'
    '        """Check if blocking enforcer is initialized"""'
)
new4 = (
    '    def _check_blocking_enforcer(self):\n'
    '        """Check [3/7]: Verify the blocking-enforcer state file is initialised.\n'
    '\n'
    '        Reads .blocking-state.json from self.memory_path.  If the file is\n'
    '        missing, attempts _auto_fix_blocking_enforcer() to create it.  If\n'
    '        the file exists but session_started is False, appends a CRITICAL\n'
    '        failure.  On read errors appends a HIGH priority failure.\n'
    '\n'
    '        Returns:\n'
    '            bool: True when the enforcer state is present and valid.\n'
    '        """'
)
patches.append((old4, new4, '_check_blocking_enforcer'))

# Patch 5: _check_session_state
old5 = (
    '    def _check_session_state(self):\n'
    '        """Check session state"""'
)
new5 = (
    '    def _check_session_state(self):\n'
    '        """Check [4/7]: Validate required flags in the blocking-state.json.\n'
    '\n'
    '        Reads .blocking-state.json and verifies that session_started and\n'
    '        context_checked are True.  Missing flags emit a WARNING printed to\n'
    '        stdout but do NOT append to self.failures (non-blocking).\n'
    '\n'
    '        Returns:\n'
    '            bool: True after the check completes (even on missing flags);\n'
    '                  False only on file read exceptions.\n'
    '        """'
)
patches.append((old5, new5, '_check_session_state'))

# Patch 6: _check_daemons
old6 = (
    '    def _check_daemons(self):\n'
    '        """Check daemon status"""'
)
new6 = (
    '    def _check_daemons(self):\n'
    '        """Check [5/7]: Report running vs stopped daemon count (informational).\n'
    '\n'
    '        Reads PID files from memory_path/.pids/ and uses "tasklist /FI PID"\n'
    '        to verify each process is alive.  Daemons being stopped is a WARNING,\n'
    '        not a CRITICAL failure.  The system works without daemons; only\n'
    '        automation features are reduced.\n'
    '\n'
    '        Returns:\n'
    '            bool: Always True (daemon status is never blocking).\n'
    '        """'
)
patches.append((old6, new6, '_check_daemons'))

# Patch 7: _check_git_repos
old7 = (
    '    def _check_git_repos(self):\n'
    '        """Check git repository status"""'
)
new7 = (
    '    def _check_git_repos(self):\n'
    '        """Check [6/7]: Report git repository cleanliness (informational).\n'
    '\n'
    '        Runs "git rev-parse --git-dir" to detect a git repo, then\n'
    '        "git status --porcelain" to detect uncommitted changes.  Dirty\n'
    '        repos emit a WARNING but do NOT append to self.failures.\n'
    '\n'
    '        Returns:\n'
    '            bool: Always True (git status is never blocking).\n'
    '        """'
)
patches.append((old7, new7, '_check_git_repos'))

# Patch 8: _check_windows_python_unicode
old8 = (
    '    def _check_windows_python_unicode(self):\n'
    '        """Check Python files for Unicode characters on Windows (CRITICAL)"""'
)
new8 = (
    '    def _check_windows_python_unicode(self):\n'
    '        """Check [7/7]: Detect and auto-fix Unicode in Python files on Windows.\n'
    '\n'
    '        Skipped on non-Windows platforms.  On Windows, runs\n'
    '        windows-python-unicode-checker.py --scan-dir against self.memory_path\n'
    '        and attempts to auto-fix each offending .py file.  Non-zero exit from\n'
    '        the checker triggers per-file fix attempts using --fix --no-backup.\n'
    '        Timeouts and exceptions are treated as non-blocking warnings.\n'
    '\n'
    '        Returns:\n'
    '            bool: Always True (Unicode scan errors are non-blocking).\n'
    '        """'
)
patches.append((old8, new8, '_check_windows_python_unicode'))

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

print(f'Done writing auto-fix-enforcer.py ({applied}/{len(patches)} patches applied)')

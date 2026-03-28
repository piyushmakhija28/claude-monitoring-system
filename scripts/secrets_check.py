"""Pre-flight scanner for hardcoded secrets in Python source files.

Scans all .py files in scripts/ and src/ for patterns that suggest
hardcoded API keys, tokens, or passwords.

Exit code 0: no secrets found.
Exit code 1: secrets found (CI gate).

Usage:
    python scripts/secrets_check.py
    python scripts/secrets_check.py --json  (emit JSON report to stdout)
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Pattern definitions
# Each entry: (pattern_name, compiled_regex)
# ---------------------------------------------------------------------------
_RAW_PATTERNS = [
    (
        "anthropic_api_key_assignment",
        r"""anthropic_api_key\s*=\s*["\']sk-ant-[a-zA-Z0-9]""",
    ),
    (
        "ANTHROPIC_API_KEY_uppercase_assignment",
        r"""ANTHROPIC_API_KEY\s*=\s*["\'][^{$]""",
    ),
    (
        "github_token_assignment",
        r"""github.*token\s*=\s*["\']gh[ps]_[a-zA-Z0-9]""",
    ),
    (
        "generic_api_key",
        r"""api_key\s*=\s*["\'][a-zA-Z0-9]{20,}["\']""",
    ),
    (
        "password_literal",
        r"""password\s*=\s*["\'][^"\']{8,}["\']""",
    ),
    (
        "secret_literal",
        r"""secret\s*=\s*["\'][^"\']{8,}["\']""",
    ),
]

PATTERNS = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in _RAW_PATTERNS]


def _is_test_file(path):
    # type: (Path) -> bool
    """Return True if the path is inside a test directory or is a test file."""
    parts = path.parts
    return any(part in ("tests", "test_") for part in parts) or path.name.startswith("test_")


def _scan_file(file_path, project_root):
    # type: (Path, Path) -> list
    """Scan a single Python file for secret patterns.

    Args:
        file_path: Absolute path to the file to scan.
        project_root: Project root used to compute relative paths.

    Returns:
        List of finding dicts, each with keys:
          file, line, pattern_name, redacted_match
    """
    findings = []
    try:
        with open(str(file_path), "r", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                for pattern_name, regex in PATTERNS:
                    match = regex.search(line)
                    if match:
                        matched_text = match.group(0)
                        redacted = matched_text[:20] + "..." if len(matched_text) > 20 else matched_text
                        try:
                            rel_path = str(file_path.relative_to(project_root))
                        except ValueError:
                            rel_path = str(file_path)
                        findings.append(
                            {
                                "file": rel_path,
                                "line": lineno,
                                "pattern_name": pattern_name,
                                "redacted_match": redacted,
                            }
                        )
    except OSError as exc:
        sys.stderr.write("WARNING: Could not read {}: {}\n".format(file_path, exc))
    return findings


def _collect_python_files(project_root):
    # type: (Path) -> list
    """Collect all .py files under scripts/ and src/ that are not test files.

    Also excludes this scanner file itself to prevent self-matches.

    Args:
        project_root: Root directory of the project.

    Returns:
        Sorted list of Path objects.
    """
    this_file = Path(__file__).resolve()
    scan_dirs = [project_root / "scripts", project_root / "src"]
    collected = []
    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for py_file in scan_dir.rglob("*.py"):
            resolved = py_file.resolve()
            if resolved == this_file:
                continue
            if _is_test_file(resolved):
                continue
            collected.append(resolved)
    return sorted(collected)


def run_scan(project_root):
    # type: (Path) -> list
    """Run the full secrets scan and return a list of all findings.

    Args:
        project_root: Root directory of the project.

    Returns:
        List of finding dicts (may be empty if no secrets found).
    """
    all_findings = []
    py_files = _collect_python_files(project_root)
    for py_file in py_files:
        findings = _scan_file(py_file, project_root)
        all_findings.extend(findings)
    return all_findings


def main():
    # type: () -> int
    """Entry point for CLI usage.

    Returns:
        0 if no secrets found, 1 if secrets were detected.
    """
    parser = argparse.ArgumentParser(description="Scan Python source files for hardcoded secrets.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit full JSON report to stdout in addition to stderr summary.",
    )
    args = parser.parse_args()

    # Auto-detect project root from this file's location.
    # This file lives at <project_root>/scripts/secrets_check.py
    project_root = Path(__file__).resolve().parent.parent

    findings = run_scan(project_root)

    if findings:
        sys.stderr.write("SECRETS CHECK FAILED: {} potential hardcoded secret(s) found.\n".format(len(findings)))
        for f in findings:
            sys.stderr.write("  [{pattern_name}] {file}:{line} -> {redacted_match}\n".format(**f))
        if args.json:
            sys.stdout.write(json.dumps({"status": "failed", "findings": findings}, indent=2))
            sys.stdout.write("\n")
        return 1

    sys.stderr.write(
        "Secrets check passed: no hardcoded secrets detected in {} file(s).\n".format(
            len(_collect_python_files(project_root))
        )
    )
    if args.json:
        sys.stdout.write(json.dumps({"status": "passed", "findings": []}, indent=2))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

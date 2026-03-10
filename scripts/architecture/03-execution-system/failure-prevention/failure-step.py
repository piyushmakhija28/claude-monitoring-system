#!/usr/bin/env python3
"""
Level 3 Step 11 - Code Review & CI/CD Integration

Enhanced failure prevention with:
- PR merge conflict detection
- CI/CD pipeline status checking
- Skill/agent integration in review logic
"""

import json
import sys
import os
import subprocess
from pathlib import Path


def check_git_merge_conflicts():
    """Check for merge conflicts in current branch."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )

        conflicts = []
        for line in result.stdout.split('\n'):
            if line.startswith('UU ') or line.startswith('DD ') or line.startswith('AA '):
                # Unmerged paths
                conflicts.append(line[3:].strip())

        return {
            "has_conflicts": len(conflicts) > 0,
            "conflict_count": len(conflicts),
            "conflict_files": conflicts,
        }
    except Exception as e:
        return {
            "has_conflicts": False,
            "conflict_count": 0,
            "error": str(e),
        }


def check_github_actions_status():
    """Check GitHub Actions CI/CD status."""
    try:
        # Try to get latest workflow run status
        result = subprocess.run(
            ["gh", "run", "list", "--limit", "1", "--json", "status,conclusion,name"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout:
            try:
                runs = json.loads(result.stdout)
                if runs:
                    run = runs[0]
                    return {
                        "ci_status": run.get("status", "unknown"),
                        "ci_conclusion": run.get("conclusion", "unknown"),
                        "ci_available": True,
                    }
            except:
                pass

        return {
            "ci_status": "unknown",
            "ci_conclusion": "unknown",
            "ci_available": False,
        }
    except Exception as e:
        return {
            "ci_status": "unknown",
            "ci_conclusion": "unknown",
            "ci_available": False,
            "error": str(e),
        }


def check_code_quality_metrics():
    """Check for basic code quality metrics."""
    try:
        cwd = Path.cwd()

        metrics = {
            "python_files": 0,
            "test_files": 0,
            "doc_files": 0,
            "large_files": [],
        }

        # Count files
        for py_file in cwd.rglob("*.py"):
            if "test" in py_file.name.lower():
                metrics["test_files"] += 1
            else:
                metrics["python_files"] += 1

            # Check file size
            size_kb = py_file.stat().st_size / 1024
            if size_kb > 500:  # Large files
                metrics["large_files"].append({
                    "path": str(py_file.relative_to(cwd)),
                    "size_kb": round(size_kb, 1)
                })

        # Count docs
        metrics["doc_files"] = len(list(cwd.glob("*.md"))) + len(list(cwd.glob("docs/**/*.md")))

        return metrics
    except Exception as e:
        return {
            "error": str(e),
            "python_files": 0,
            "test_files": 0,
            "doc_files": 0,
        }


def check_memory_usage():
    """Check memory directory size."""
    try:
        cwd = Path.cwd()
        memory_dir = cwd / ".claude" / "memory" if (cwd / ".claude" / "memory").exists() else None

        if not memory_dir:
            return {"memory_size_mb": 0, "archive_recommended": False}

        total_size = sum(f.stat().st_size for f in memory_dir.rglob("*") if f.is_file()) / (1024 * 1024)

        return {
            "memory_size_mb": round(total_size, 1),
            "archive_recommended": total_size > 1000,
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    """Run comprehensive Step 11 checks."""

    # Run all checks
    merge_conflicts = check_git_merge_conflicts()
    github_ci = check_github_actions_status()
    code_quality = check_code_quality_metrics()
    memory_usage = check_memory_usage()

    # Determine overall status
    warnings = []
    blocking_issues = []

    # Check for blocking merge conflicts
    if merge_conflicts.get("has_conflicts"):
        blocking_issues.append(
            f"Merge conflicts detected in {merge_conflicts['conflict_count']} file(s): "
            f"{', '.join(merge_conflicts['conflict_files'][:3])}"
        )

    # Check CI/CD status
    if github_ci.get("ci_available"):
        if github_ci.get("ci_status") == "in_progress":
            warnings.append("CI/CD pipeline still running - wait for completion before merging")
        elif github_ci.get("ci_conclusion") == "failure":
            blocking_issues.append("CI/CD pipeline failed - fix issues before merging")
        elif github_ci.get("ci_conclusion") == "cancelled":
            warnings.append("CI/CD pipeline was cancelled - rerun checks")

    # Check code quality
    if code_quality.get("test_files", 0) == 0:
        warnings.append("No test files found - add tests for better coverage")

    if len(code_quality.get("large_files", [])) > 5:
        warnings.append(f"{len(code_quality['large_files'])} large files detected - consider refactoring")

    # Check memory
    if memory_usage.get("archive_recommended"):
        warnings.append(f"Memory usage high ({memory_usage['memory_size_mb']}MB) - archive sessions")

    # Build output
    output = {
        "step": "Step 11: Code Review & CI/CD Integration",
        "merge_conflicts": merge_conflicts,
        "github_ci": github_ci,
        "code_quality": code_quality,
        "memory_usage": memory_usage,
        "warnings": warnings,
        "blocking_issues": blocking_issues,
        "can_proceed_to_merge": len(blocking_issues) == 0,
        "status": "BLOCKED" if blocking_issues else "OK"
    }

    print(json.dumps(output, indent=2))
    sys.exit(0 if output["status"] == "OK" else 1)


if __name__ == "__main__":
    main()

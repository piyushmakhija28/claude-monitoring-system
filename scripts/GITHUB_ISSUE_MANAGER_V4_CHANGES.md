# GitHub Issue Manager v4.0 - Implementation Guide
## Changes Required from v3.0 → v4.0

**Policy Being Implemented:** github-issues-integration-policy-v3-improved.md
**File to Update:** github_issue_manager.py
**Version:** v3.0.0 → v4.0.0

---

## High-Level Changes

### 1. Issue Creation Strategy (BREAKING)

**OLD (v3.0):**
```python
def create_github_issue(task_id):
    # Creates one issue per task
    # Title: [TASK-{task_id}] {subject}
    # One issue per task breakdown
```

**NEW (v4.0):**
```python
def create_github_issue_for_session(prompt_data, task_list):
    # Creates ONE issue per user prompt/problem statement
    # Title: {type}: {problem_statement}
    # Aggregates all tasks into single issue
    # Reuses issue if problem already has one
```

---

## Function Changes Required

### Change 1: Problem Deduplication

**Add new function:**

```python
def _extract_problem_statement(prompt_or_task):
    """
    Extract problem statement from user prompt.

    Purpose: Detect if this problem already has an issue created.
    Prevents duplicate issues for same problem.

    Returns: Problem key (e.g., "model-selection", "auth-system")
    """
    prompt_lower = prompt_or_task.lower()

    # Keywords mapping to problem keys
    keywords = {
        'model selection': 'model-selection',
        'complexity': 'model-selection',
        'auth': 'authentication',
        'jwt': 'authentication',
        'context': 'context-management',
        'session': 'session-management',
        'github issue': 'github-integration',
        'branch': 'github-integration',
        'commit': 'github-integration',
    }

    for keyword, key in keywords.items():
        if keyword in prompt_lower:
            return key

    # Fallback: hash first N words
    words = prompt_lower.split()[:3]
    return '-'.join(words)


def _issue_exists_for_problem(problem_key):
    """
    Check if issue already exists for this problem.

    Searches in:
    - Current session's mapping
    - Open issues with matching labels

    Returns: issue_number or None
    """
    mapping = _load_issues_mapping()

    # Check if any task points to problem with this key
    for task_id, issue_data in mapping.get('task_to_issue', {}).items():
        if issue_data.get('problem_key') == problem_key:
            if issue_data.get('status') == 'open':
                return issue_data.get('issue_number')

    return None


def _append_to_existing_issue(issue_number, new_task_description):
    """
    Instead of creating new issue, append to existing one.

    Example:
    Issue #42: "bugfix: Model selection issue"

    Has task 1 description, now add task 2 description to same issue.
    """
    # Use gh issue comment to append task to existing issue
    comment = f"""
## Additional Task

{new_task_description}

---
Added by Claude Memory System (v4.0)
"""

    try:
        subprocess.run(
            ['gh', 'issue', 'comment', str(issue_number), '--body', comment],
            timeout=GH_TIMEOUT,
            capture_output=True
        )
        return True
    except Exception:
        return False
```

---

### Change 2: Semantic Branch Naming

**Replace:**
```python
# OLD: uses issue_id in branch name
branch_name = f"fix/{issue_id}"
branch_name = f"feature/{issue_id}"
```

**With:**
```python
def _generate_semantic_branch_name(issue_type, problem_statement):
    """
    Generate semantic branch name based on problem.

    OLD: fix/86, feature/42
    NEW: bugfix/model-selection, feature/jwt-auth

    Args:
        issue_type: 'bugfix', 'feature', 'refactor', 'perf', 'docs', 'enhancement'
        problem_statement: Original problem description

    Returns: Semantic branch name
    """
    # Extract key words from problem
    words = problem_statement.lower().split()
    key_words = [w for w in words if len(w) > 3][:2]  # Skip small words
    problem_key = '-'.join(key_words)

    return f"{issue_type}/{problem_key}"


# Example usage:
branch_name = _generate_semantic_branch_name('bugfix', 'Model selection defaulting to HAIKU')
# Returns: 'bugfix/model-selection'
```

---

### Change 3: Rich Issue Titles (No [TASK-X])

**OLD:**
```python
title = f"[TASK-{task_id}] {task_subject}"
# Result: "[TASK-001] Fix model selection by improving complexity scoring"
```

**NEW:**
```python
def _generate_issue_title(issue_type, prompt):
    """
    Generate semantic issue title.

    Format: {type}: {problem_statement}
    """
    # Detect issue type from prompt
    type_keywords = {
        'fix': ['fix', 'bug', 'error', 'broken', 'crash'],
        'feature': ['add', 'implement', 'new', 'create'],
        'refactor': ['refactor', 'cleanup', 'simplify', 'reorganize'],
        'perf': ['optimize', 'improve', 'faster', 'performance'],
        'docs': ['doc', 'document', 'readme', 'guide'],
    }

    issue_type = 'feature'  # default
    for type_key, keywords in type_keywords.items():
        if any(kw in prompt.lower() for kw in keywords):
            issue_type = type_key
            break

    # Extract problem statement (first sentence or key phrase)
    problem = _extract_problem_statement(prompt)

    return f"{issue_type}: {problem}"

# Example result: "bugfix: Model selection defaulting to HAIKU for complex tasks"
```

---

### Change 4: Problem-Centric Issue Description

**OLD:**
```python
# Task-centric format
body = f"""
## Story
{task_description}

## Task Overview
| Task ID | {task_id} |
...
"""
```

**NEW:**
```python
def _generate_issue_body(prompt, task_list, complexity, model):
    """
    Generate problem-centric issue description.

    Includes:
    - Problem statement
    - Context & background
    - Solution approach (from task descriptions)
    - Success criteria
    """

    # Extract information from prompt
    problem_statement = _extract_problem_statement(prompt)
    context = _extract_context(prompt)

    # Build success criteria from tasks
    criteria = []
    for task in task_list:
        criteria.append(f"- [ ] {task['subject']}")

    body = f"""## Problem Statement

{context}

## Context & Background

{_infer_root_cause(prompt)}

## Solution Approach

{_describe_approach(task_list)}

## Success Criteria

{''.join(criteria)}

## Related Tasks

{len(task_list)} task(s) created for this problem

## Session Context

- **Complexity:** {complexity}/25
- **Model:** {model}
- **Created:** {datetime.now().isoformat()}

---
_Auto-created by Claude Memory System (v4.0) | https://github.com/piyushmakhija28/claude-insight_
"""

    return body
```

---

### Change 5: Semantic Labels (Not Task-Based)

**OLD:**
```python
labels = [
    'task-auto-created',
    'level-3-execution',
    'bugfix',
    'priority-medium',
    'complexity-medium'
]
```

**NEW:**
```python
def _generate_semantic_labels(issue_type, complexity):
    """
    Generate semantic labels based on issue type and complexity.

    Type Labels: bugfix, feature, refactor, perf, docs, enhancement
    Priority: p0-critical, p1-high, p2-medium, p3-low
    Status: in-progress
    """

    labels = []

    # Type label
    labels.append(issue_type)

    # Priority based on complexity
    if complexity >= 18:
        labels.append('p0-critical')
    elif complexity >= 12:
        labels.append('p1-high')
    elif complexity >= 6:
        labels.append('p2-medium')
    else:
        labels.append('p3-low')

    # Status
    labels.append('in-progress')

    return labels

# Example result: ['bugfix', 'p1-high', 'in-progress']
```

---

### Change 6: Rich Closing Narrative (With Commits)

**OLD:**
```python
def _build_close_comment(task_id, issue_data):
    # Simple close comment
    # Not much storytelling
```

**NEW:**
```python
def _build_rich_closing_comment(issue_number, session_data):
    """
    Build rich closing comment with full narrative.

    Includes:
    - What was the problem
    - How we investigated it
    - What solution we found
    - Commits that fixed it (with IDs!)
    - Files changed
    - How it was verified
    """

    commits = session_data.get('commits', [])
    files_changed = session_data.get('files_modified', [])

    # Build commits table with IDs
    commits_table = "| Commit ID | Message |\n|-----------|----------|\n"
    for commit in commits:
        commits_table += f"| `{commit['id']}` | {commit['message']} |\n"

    # Build files table
    files_table = "| File | Changes |\n|------|----------|\n"
    for file in files_changed:
        changes = f"+{file.get('added', 0)} -{file.get('deleted', 0)}"
        files_table += f"| `{file['path']}` | {changes} |\n"

    body = f"""## Resolution Story

{session_data.get('narrative', 'Fixed and closed.')}

## Problem Summary

| Field | Value |
|-------|-------|
| **Problem** | {session_data.get('problem_statement', 'N/A')} |
| **Root Cause** | {session_data.get('root_cause', 'N/A')} |
| **Solution** | {session_data.get('solution', 'N/A')} |

## Commits

{commits_table}

## Files Changed

{files_table}

## Verification

{session_data.get('verification', '- [x] Manual testing passed')}

---
_Closed by Claude Memory System (v4.0) | {datetime.now().isoformat()}_
"""

    return body
```

---

### Change 7: Single Branch Per Problem

**NEW:**
```python
def _get_or_create_branch(problem_key, issue_type):
    """
    Get existing branch for this problem, or create new one.

    KEY CHANGE: Don't create new branch for every task.
    If branch for this problem exists, reuse it!
    """

    expected_branch = _generate_semantic_branch_name(issue_type, problem_key)

    # Check if branch already exists
    try:
        result = subprocess.run(
            ['git', 'branch', '-a'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if expected_branch in result.stdout:
            # Branch exists, return it
            return expected_branch
    except Exception:
        pass

    # Branch doesn't exist, create new one
    try:
        subprocess.run(
            ['git', 'checkout', '-b', expected_branch],
            timeout=5,
            capture_output=True
        )
        return expected_branch
    except Exception:
        return None
```

---

## Migration Path (v3.0 → v4.0)

### Step 1: Deploy Policy
- [x] Create github-issues-integration-policy-v3-improved.md
- [ ] Update documentation

### Step 2: Update Script
- [ ] Create github_issue_manager_v4.py (new file or in-place replace)
- [ ] Implement all 7 changes above
- [ ] Add test cases

### Step 3: Test
- [ ] Test with sample problem statement
- [ ] Verify one issue created (not multiple)
- [ ] Verify semantic branch naming
- [ ] Verify semantic labels
- [ ] Test closing with rich narrative

### Step 4: Deploy
- [ ] Merge to main
- [ ] Update hook-downloader if needed
- [ ] Announce change to users

---

## Code Template (v4.0)

```python
#!/usr/bin/env python
# Script Name: github_issue_manager.py
# Version: 4.0.0 (v3.0 → v4.0: BREAKING CHANGES)
# Last Modified: 2026-03-03
# Description: GitHub Issues + Branch integration for Level 3 Execution v3.0
#              CHANGED: One issue per problem statement (not per task)
#              CHANGED: Semantic branch naming (not issue-id based)
#              CHANGED: Problem-centric issue descriptions
#              CHANGED: Rich closing narratives with commit IDs
#              CHANGED: Semantic labels (not task-based)
#
# Policy Implemented: github-issues-integration-policy-v3-improved.md
# Author: Claude Memory System
#
# Safety: Same as v3.0 (max 10 ops/session, 15s timeout, non-blocking)

import sys, os, json, subprocess
from pathlib import Path
from datetime import datetime

# ===== CORE STRUCTURE CHANGES =====

def create_github_issue_for_session(prompt, task_list, complexity, model):
    """
    [CHANGED from v3.0] Creates ONE issue per problem statement.
    Previously created one issue per task. Now aggregates all.
    """
    # See implementation details above
    pass


def _extract_problem_statement(prompt):
    """[NEW in v4.0] Extract semantic problem key"""
    pass


def _issue_exists_for_problem(problem_key):
    """[NEW in v4.0] Check if issue already created for this problem"""
    pass


def _generate_semantic_branch_name(issue_type, problem_statement):
    """[CHANGED from v3.0] Use problem-based naming instead of issue-id"""
    pass


def _generate_issue_title(issue_type, prompt):
    """[CHANGED from v3.0] Remove [TASK-X] prefix"""
    pass


def _generate_issue_body(prompt, task_list, complexity, model):
    """[CHANGED from v3.0] Problem-centric instead of task-centric"""
    pass


def _generate_semantic_labels(issue_type, complexity):
    """[CHANGED from v3.0] Use semantic labels, not task-based"""
    pass


def _build_rich_closing_comment(issue_number, session_data):
    """[CHANGED from v3.0] Include commits, RCA, verification"""
    pass


def _get_or_create_branch(problem_key, issue_type):
    """[NEW in v4.0] Reuse branch if exists, don't create per task"""
    pass

# Continue with remaining v3.0 functions...
```

---

## Backward Compatibility

**WARNING: This is a BREAKING change.**

Old behavior:
- 1 prompt → 3 tasks → 3 issues
- Branch per task (fix/1, fix/2, fix/3)
- Task-centric descriptions

New behavior:
- 1 prompt → 3 tasks → 1 issue
- Single branch for problem
- Problem-centric description

**Action Required:**
- Close old v2.0/v3.0 issues if still open
- Use new v4.0 format for all future issues
- No need to migrate old closed issues

---

## Testing Checklist

- [ ] Issue created with semantic title (no [TASK-X])
- [ ] Issue created with problem-centric body
- [ ] Multiple tasks aggregated in one issue
- [ ] Semantic labels applied (bugfix, p1-high, etc.)
- [ ] Semantic branch created (bugfix/model-selection)
- [ ] Branch reused if problem has existing branch
- [ ] Closing comment includes commit IDs
- [ ] Closing comment includes files changed
- [ ] Closing comment includes RCA
- [ ] Closing comment includes verification

---

**Ready for Implementation** ✅

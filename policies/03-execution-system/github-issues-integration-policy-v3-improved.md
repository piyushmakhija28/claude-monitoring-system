# GitHub Issues Integration Policy v3.0 - IMPROVED
## Smart Issue Aggregation & Proper Storytelling

**Version:** 3.0.0 (BREAKING CHANGES FROM v2.0)
**Part of:** Level 3: Execution System (12 Steps)
**Status:** ACTIVE - Replaces v2.0
**Date:** 2026-03-03

---

## Core Philosophy Change (v3.0)

### ❌ Old (v2.0): Task-Centric
```
1 Problem Statement
  ↓
  3 Tasks Created
  ↓
  3 GitHub Issues (one per task)
  ↓
  Confusing & redundant ❌
```

### ✅ New (v3.0): Problem-Centric
```
1 Problem Statement
  ↓
  N Tasks Created (internal only)
  ↓
  1 Meaningful GitHub Issue (covers full problem)
  ↓
  1 Branch (smart naming)
  ↓
  1 PR (complete solution)
  ↓
  1 Closing Story (full narrative)
```

---

## Issue Creation Strategy (CHANGED)

### When to Create Issues

**CREATE ISSUE** in these cases:
- User sends a problem statement / feature request / bug report
- Multiple tasks breakdown from ONE problem
- Work spans multiple commits/files

**DO NOT CREATE ISSUES** for:
- Each individual task
- Internal subtasks
- Refactoring that doesn't address user-stated problem

### Issue Title Format (IMPROVED)

```
{LABEL}: {Problem Statement}
```

**Examples:**
```
fix: Model selection defaulting to HAIKU for complex tasks
feature: Implement user authentication with JWT
refactor: Simplify context management in Level 1 system
docs: Add architecture diagram to README
enhancement: Improve complexity scoring accuracy
```

**NOT these (old format):**
```
❌ [TASK-1] Fix model selection...
❌ [TASK-2] Update complexity scoring...
❌ [TASK-3] Add tests...
```

---

## Issue Description (NEW - Problem-Centric)

### Format

```markdown
## Problem Statement

{What is the actual problem from user perspective?
 Why does it matter? What's broken?}

## Context & Background

{Why is this happening? What's the root cause theory?
 Any relevant history or related issues?}

## Solution Approach

{High-level how we'll solve this.
 What areas need to be investigated/changed?}

## Success Criteria

- [ ] {Measurable outcome 1}
- [ ] {Measurable outcome 2}
- [ ] {Measurable outcome 3}

## Related Tasks

{If multiple internal tasks, list them}

---
_Created by Claude Memory System | {timestamp}_
```

### Real Example

```markdown
## Problem Statement

The model selection policy isn't working correctly.
Tasks are complexity 10+ (real API/auth work) but
getting HAIKU instead of SONNET/OPUS.

Expected: Complex work → SONNET/OPUS
Actual: Complex work → HAIKU (wrong)

## Context & Background

The complexity scoring function uses 1-10 scale, but
model selection thresholds expect 1-25 scale. This
mismatch causes all scores to map to HAIKU range.

## Solution Approach

1. Expand complexity scale from 1-10 → 1-25
2. Add task-type weights (Auth=8, API=7, etc.)
3. Add integration/cross-cutting detection
4. Verify with real test cases

## Success Criteria

- [ ] SIMPLE tasks (typos, readme) → HAIKU
- [ ] MODERATE (bug fix, enhancement) → SONNET
- [ ] COMPLEX (API, auth, refactor) → SONNET/OPUS
- [ ] All task types properly scored
- [ ] Tests added for edge cases
```

---

## Issue Labels (SEMANTIC, NOT TASK-BASED)

### Type Labels (Mutually Exclusive)

| Label | When to Use |
|-------|-------------|
| `bugfix` | Fixing broken behavior |
| `feature` | New capability/functionality |
| `refactor` | Improving code without user-visible change |
| `docs` | Documentation only |
| `enhancement` | Improving existing feature |
| `perf` | Performance optimization |
| `test` | Test coverage/infrastructure |
| `chore` | Maintenance, setup, etc. |

### Priority Labels (Based on Complexity)

| Label | Complexity | Impact |
|-------|-----------|--------|
| `p0-critical` | >= 18 | Blocking, must fix now |
| `p1-high` | 12-17 | Important, fix soon |
| `p2-medium` | 6-11 | Regular priority |
| `p3-low` | 0-5 | Nice to have |

### Status Labels (Auto-Applied)

| Label | Meaning |
|-------|---------|
| `in-progress` | Work started |
| `blocked` | Waiting on something |
| `review` | PR in review |
| `approved` | Ready to merge |

### Area Labels (Optional)

```
areas:
- context-management
- model-selection
- task-tracking
- github-integration
- 3-level-architecture
- performance
```

---

## Branch Naming (PROBLEM-BASED)

### Format

```
{type}/{problem-key}
```

Where:
- `type` = bugfix, feature, refactor, perf, docs
- `problem-key` = semantic name of what's being fixed

**Examples:**
```
bugfix/model-selection
feature/jwt-auth
refactor/context-manager
perf/complexity-scoring
docs/architecture-guide
```

**NOT these (old task-based):**
```
❌ fix/1
❌ fix/86
❌ fix/87
❌ feature/task-123
```

### Single Branch Per Problem

- All tasks for one problem → **ONE branch**
- Multiple commits in one branch
- One PR from that branch
- Multiple commits before merge is OK!

---

## Issue Closing with Storytelling (NEW)

### When to Close

Close when:
- All tasks for the problem are completed
- All commits are in the PR
- PR is merged to main
- Verification is done

### Closing Comment Format (NARRATIVE)

```markdown
## Resolution Story

{Write a narrative paragraph explaining:
 - What was the actual problem (restated for clarity)
 - How you investigated it (which files, what you learned)
 - What solution was found (the fix)
 - How it was verified (tests, manual checks)
 - Why this solution was chosen}

## Problem Summary

| Field | Value |
|-------|-------|
| **Problem** | {Original problem statement} |
| **Root Cause** | {Why it was happening} |
| **Solution** | {How it was fixed} |
| **Impact** | {User-visible improvement} |

## Files Changed

| File | Change Type | Lines |
|------|------------|-------|
| `file1.py` | Modified | +45, -12 |
| `file2.py` | Created | +120 |
| `test_file.py` | Added | +80 |

## Commits

| Commit ID | Message |
|-----------|---------|
| `abc1234` | fix: Expand complexity scoring 1-10 → 1-25 |
| `def5678` | test: Add complexity scoring tests |
| `ghi9012` | docs: Update model selection guide |

## Verification

- [x] HAIKU: Simple tasks (<=4) correctly selected
- [x] SONNET: Moderate tasks (5-19) correctly selected
- [x] OPUS: Complex tasks (>=20) correctly selected
- [x] All edge cases tested
- [x] No regressions in other parts
- [x] PR reviewed and approved

## Testing

```
BEFORE:
  API task (complexity should be 10+) → got HAIKU ❌

AFTER:
  API task (complexity 12) → gets SONNET ✅
  Auth task (complexity 8) → gets SONNET ✅
  Typo fix (complexity 2) → gets HAIKU ✅
```

---
_Closed by Claude Memory System | {timestamp}_
```

### Real Closing Example

```markdown
## Resolution Story

The model selection policy was broken because the
complexity scoring function used a 1-10 scale while
the policy thresholds expected 1-25. This caused all
tasks, regardless of difficulty, to score in the
HAIKU range (0-4 normalized).

We investigated by reading the score function and
policy thresholds, then expanded the scale to 1-25
and added task-type weights. API/auth tasks now
score 7-8 (correctly → SONNET), while typos stay
at 1-2 (correctly → HAIKU).

Verification: Tested with real task examples and
confirmed HAIKU/SONNET/OPUS are correctly selected
per complexity level.

## Problem Summary

| Field | Value |
|-------|-------|
| **Problem** | Tasks getting wrong model (HAIKU for complex work) |
| **Root Cause** | Score function used 1-10, policy wanted 1-25 |
| **Solution** | Expanded scale + added task-type weights |
| **Impact** | Now complex work gets correct (faster) model |

## Files Changed

| File | Change Type |
|------|------------|
| `prompt-generator.py` | +45 lines |
| `test_complexity.py` | +80 lines |

## Commits

| Commit | Message |
|--------|---------|
| `d08ec84` | fix: Expand complexity scoring 1-10 → 1-25 scale |
```

---

## Script Changes Required

### github_issue_manager.py (v4.0)

#### Change 1: One Issue Per Session

```python
def create_github_issue_for_session(prompt, task_list, complexity, model):
    """
    Create ONE issue per user prompt/problem statement.
    Aggregates ALL tasks into single issue.

    CHANGED: No longer creates issue per task.
    CHANGED: Uses problem-centric format instead of task-centric.
    """

    issue_title = f"{detect_issue_type(prompt)}: {extract_problem_statement(prompt)}"

    issue_body = f"""
## Problem Statement

{extract_context(prompt)}

## Solution Approach

{describe_approach(task_list)}

## Success Criteria

{generate_criteria(task_list)}

## Related Tasks

{task_list}  # Just reference, don't create separate issues
"""

    return create_issue(issue_title, issue_body, labels)
```

#### Change 2: Semantic Branch Naming

```python
def create_branch_for_issue(issue_title, issue_type):
    """
    Create smart branch name based on problem, not issue ID.

    OLD: fix/86
    NEW: bugfix/model-selection
    """

    problem_key = extract_semantic_key(issue_title)
    branch_name = f"{issue_type}/{problem_key}"

    # Create ONE branch for all tasks
    # Multiple commits OK

    return branch_name
```

#### Change 3: Rich Closing Narrative

```python
def close_github_issue_with_story(issue_number, session_data):
    """
    Close issue with full storytelling.
    Include: commits, files changed, root cause, solution, verification.

    CHANGED: From simple close to comprehensive narrative.
    """

    closing_comment = f"""
## Resolution Story

{session_data['narrative']}

## Problem Summary
{problem_table(session_data)}

## Files Changed
{files_changed_table(session_data)}

## Commits
{commits_table(session_data)}

## Verification
{verification_checklist(session_data)}
"""

    return close_issue(issue_number, closing_comment)
```

---

## Workflow Comparison

### Old (v2.0)
```
User: "Fix model selection"
  ↓
  Task 1: Expand complexity scale
  Task 2: Add task-type weights
  Task 3: Add tests
  ↓
  Issue #86 created (Task 1)
  Issue #87 created (Task 2)
  Issue #88 created (Task 3)
  ↓
  Confusing! Which issue is the real fix? ❌
```

### New (v3.0)
```
User: "Fix model selection"
  ↓
  Task 1: Expand complexity scale
  Task 2: Add task-type weights
  Task 3: Add tests
  ↓
  Issue #42: "bugfix: Model selection defaulting to HAIKU"
  (All 3 tasks described in one issue)
  ↓
  Branch: bugfix/model-selection
  ↓
  All 3 commits in one branch
  ↓
  1 PR from that branch
  ↓
  1 merge to main
  ↓
  Issue #42 closes with full story ✅
```

---

## Migration from v2.0 → v3.0

### For Existing Open Issues

```bash
# For each open issue from v2.0:
# 1. Check if multiple issues cover same problem
# 2. Consolidate into one issue
# 3. Rewrite title in new format (no [TASK-X])
# 4. Update description with problem statement
# 5. Merge branches into one
# 6. Update labels to semantic ones
```

### For github_issue_manager.py

Priority changes:
1. ✅ Detect if issue already exists for this problem
2. ✅ Reuse issue instead of creating new one
3. ✅ Append tasks to existing issue (don't create separate)
4. ✅ Use semantic branch naming
5. ✅ Rich closing narrative

---

## Configuration

### In settings.json

```json
{
  "github": {
    "issues": {
      "strategy": "problem-centric",
      "v3_semantic_labels": true,
      "smart_branch_naming": true,
      "one_issue_per_problem": true,
      "include_commit_ids": true,
      "narrative_closing": true
    }
  }
}
```

---

## Benefits of v3.0

| Aspect | v2.0 | v3.0 |
|--------|------|------|
| **Issues per problem** | 3 ❌ | 1 ✅ |
| **Issue clarity** | Confusing | Crystal clear |
| **Branch naming** | fix/1, fix/2 | bugfix/model-selection |
| **Closing story** | Generic | Rich narrative |
| **Commit tracking** | Not linked | Fully linked |
| **Problem understanding** | Hard | Easy |
| **Code review quality** | Harder | Easier |
| **Repository cleanliness** | Cluttered | Organized |

---

## Implementation Priority

### Phase 1 (Immediate)
- [ ] Update github_issue_manager.py (v4.0)
- [ ] Deploy policy v3.0
- [ ] Test with next problem statement

### Phase 2 (Follow-up)
- [ ] Migrate existing issues to v3.0 format
- [ ] Clean up old branches
- [ ] Update documentation

### Phase 3 (Optimization)
- [ ] Add problem deduplication (detect if same issue exists)
- [ ] Improve narrative generation
- [ ] Add analytics dashboard

---

**Version:** 3.0.0
**Status:** READY FOR IMPLEMENTATION
**Date:** 2026-03-03
**Feedback:** Create issues in claude-insight repo

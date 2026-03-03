# Policy-Script Mapping v1.0
## One-to-One Mapping: Policy MD ↔ Enforcement Script

**Status:** INCOMPLETE - Scripts need renaming/consolidation
**Action:** Create enforcement scripts with SAME NAME as policy files

---

## Mapping Table

| # | Policy File | Enforcement Script | Status | Action |
|----|------------|------------------|--------|--------|
| 1 | `anti-hallucination-enforcement.md` | `anti-hallucination-enforcement.py` | ❌ MISSING | Create |
| 2 | `prompt-generation-policy.md` | `prompt-generation-policy.py` | ⚠️ PARTIAL | Consolidate + rename |
| 3 | `automatic-task-breakdown-policy.md` | `automatic-task-breakdown-policy.py` | ❌ MISSING | Create `task-auto-analyzer.py` → rename |
| 4 | `auto-plan-mode-suggestion-policy.md` | `auto-plan-mode-suggestion-policy.py` | ⚠️ FOUND | `auto-plan-mode-suggester.py` → rename |
| 5 | `intelligent-model-selection-policy.md` | `intelligent-model-selection-policy.py` | ⚠️ FOUND (3x!) | Consolidate: `intelligent-model-selector.py`, `model-selection-enforcer.py`, `model-selection-monitor.py` |
| 6 | `adaptive-skill-registry.md` | `adaptive-skill-registry.py` | ❌ MISSING | Create |
| 7 | `auto-skill-agent-selection-policy.md` | `auto-skill-agent-selection-policy.py` | ⚠️ FOUND | Rename `auto-skill-agent-selector.py` |
| 8 | `core-skills-mandate.md` | `core-skills-mandate.py` | ⚠️ FOUND | Rename `core-skills-enforcer.py` |
| 9 | `tool-usage-optimization-policy.md` | `tool-usage-optimization-policy.py` | ⚠️ FOUND | Consolidate: `tool-usage-optimizer.py`, `auto-tool-wrapper.py` |
| 10 | `task-phase-enforcement-policy.md` | `task-phase-enforcement-policy.py` | ⚠️ FOUND | Rename `task-phase-enforcer.py` |
| 11 | `task-progress-tracking-policy.md` | `task-progress-tracking-policy.py` | ⚠️ FOUND | Rename `task-auto-tracker.py` |
| 12 | `git-auto-commit-policy.md` | `git-auto-commit-policy.py` | ⚠️ FOUND (3x) | Consolidate: `auto-commit.py`, `auto-commit-enforcer.py`, `trigger-auto-commit.py` |
| 13 | `version-release-policy.md` | `version-release-policy.py` | ❌ MISSING | Create |
| 14 | `github-branch-pr-policy.md` | `github-branch-pr-policy.py` | ❌ MISSING | Create (uses github_issue_manager.py) |
| 15 | `github-issues-integration-policy.md` | `github-issues-integration-policy.py` | ⚠️ PARTIAL | Rename `github_issue_manager.py` |
| 16 | `failure-prevention-policy.md` | `failure-prevention-policy.py` | ⚠️ FOUND (3x) | Consolidate: `failure-detector.py`, `failure-detector-v2.py`, `failure-learner.py` |
| 17 | `parallel-execution-policy.md` | `parallel-execution-policy.py` | ❌ MISSING | Create |
| 18 | `proactive-consultation-policy.md` | `proactive-consultation-policy.py` | ❌ MISSING | Create |
| 19 | `file-management-policy.md` | `file-management-policy.py` | ❌ MISSING | Create |
| 20 | `architecture-script-mapping-policy.md` | `architecture-script-mapping-policy.py` | ❌ MISSING | Create (THIS document) |

---

## Priority Fixes

### P0 - CRITICAL (Enforce immediately)
- [ ] `github-issues-integration-policy.py` - Rename github_issue_manager.py
- [ ] `intelligent-model-selection-policy.py` - Consolidate 3 scripts
- [ ] `git-auto-commit-policy.py` - Consolidate 3 scripts
- [ ] `task-phase-enforcement-policy.py` - Link to enforcer
- [ ] `tool-usage-optimization-policy.py` - Link to optimizer

### P1 - HIGH (Create this week)
- [ ] `prompt-generation-policy.py` - Create enforcement wrapper
- [ ] `automatic-task-breakdown-policy.py` - Create enforcement wrapper
- [ ] `auto-skill-agent-selection-policy.py` - Rename selector
- [ ] `version-release-policy.py` - Create enforcement script
- [ ] `failure-prevention-policy.py` - Consolidate 3 scripts

### P2 - MEDIUM (Create next sprint)
- [ ] `anti-hallucination-enforcement.py` - Create
- [ ] `parallel-execution-policy.py` - Create
- [ ] `proactive-consultation-policy.py` - Create
- [ ] `file-management-policy.py` - Create
- [ ] `github-branch-pr-policy.py` - Create wrapper
- [ ] `adaptive-skill-registry.py` - Create
- [ ] `core-skills-mandate.py` - Create

---

## Implementation Strategy

### Phase 1: Naming Consistency (v4.0 - This Sprint)
```
For every policy MD file: Create/rename script with SAME base name

Example:
  github-issues-integration-policy.md
  └─ github-issues-integration-policy.py (enforcement script)
```

### Phase 2: Integration into 3-Level Flow
```
3-level-flow.py will call:
  Step 3.X:
    from scripts.architecture.XX import policy_name_policy
    policy_name_policy.enforce()
```

### Phase 3: Enforcement Verification
```
Each script must implement:
  - enforce() → Run policy checks
  - validate() → Verify compliance
  - report() → Log violations
```

---

## Expected Outcome

```
CURRENT (CHAOS):
Policy: github-issues-integration-policy.md
Script: ??? (unclear which script enforces this)
        ↓ Confusion, inconsistency, weak enforcement

NEW (CLARITY):
Policy: github-issues-integration-policy.md
Script: github-issues-integration-policy.py (1:1 mapping!)
        ↓ Clear, consistent, strong enforcement
        ↓ Easy to audit
        ↓ Easy to extend
```

---

## How This Fixes the System

1. **NO MORE CONFUSION** - Each policy has exactly one enforcement script
2. **EASY MAINTENANCE** - Find policy → Find script with same name
3. **STRONG ENFORCEMENT** - Policy not just docs, actively enforced
4. **CLEAR AUDIT TRAIL** - Can track which policy violations were caught
5. **SCALABILITY** - Easy to add new policies with enforcement
6. **SESSION TRACKING** - Each enforcement produces logs/metrics

---

**Version:** 1.0 (Policy-Script Alignment)
**Status:** REQUIRES IMPLEMENTATION
**Priority:** P0 - CRITICAL for system stability

# Claude Insight - Complete Folder Structure & 1:1 Policy-Script Mapping

**Version:** 5.0.0
**Date:** 2026-03-05
**Purpose:** Document every folder, policy, and script with clear 1:1 mapping

---

## 📁 ROOT LEVEL STRUCTURE

```
claude-insight/
├── policies/                    ← POLICY DOCUMENTATION (what to enforce)
├── scripts/                     ← HOOK & UTILITY SCRIPTS (top-level entry points)
├── src/                         ← FLASK APPLICATION (web dashboard)
├── docs/                        ← SUPPORTING DOCUMENTATION
├── tests/                       ← TEST SUITE
├── CLAUDE.md                    ← Project instructions
└── README.md                    ← Project overview
```

---

## 🎯 POLICIES FOLDER STRUCTURE

```
policies/
│
├── 01-sync-system/              ← LEVEL 1: Context & Session Management
│   ├── context-management/      (Not a policy folder - just documentation)
│   ├── session-management/
│   │   ├── session-chaining-policy.md          → scripts/.../session-chaining-policy.py
│   │   ├── session-memory-policy.md            → scripts/.../session-memory-policy.py
│   │   └── session-pruning-policy.md           → scripts/.../session-pruning-policy.py
│   ├── user-preferences/
│   │   └── user-preferences-policy.md          → scripts/.../user-preferences-policy.py
│   └── pattern-detection/
│       └── cross-project-patterns-policy.md    → scripts/.../cross-project-patterns-policy.py
│
├── 02-standards-system/         ← LEVEL 2: Standards & Rules
│   ├── common-standards-policy.md              → scripts/.../common-standards-policy.py
│   └── coding-standards-enforcement-policy.md  → scripts/.../coding-standards-enforcement-policy.py
│
└── 03-execution-system/         ← LEVEL 3: Execution & Task Management
    ├── 00-prompt-generation/
    │   ├── prompt-generation-policy.md         → scripts/.../prompt-generation-policy.py
    │   └── anti-hallucination-enforcement.md   → scripts/.../anti-hallucination-enforcement.py
    ├── 01-task-breakdown/
    │   └── automatic-task-breakdown-policy.md  → scripts/.../automatic-task-breakdown-policy.py
    ├── 02-plan-mode/
    │   └── auto-plan-mode-suggestion-policy.md → scripts/.../auto-plan-mode-suggestion-policy.py
    ├── 04-model-selection/
    │   └── intelligent-model-selection-policy.md → scripts/.../intelligent-model-selection-policy.py
    ├── 05-skill-agent-selection/
    │   ├── auto-skill-agent-selection-policy.md → scripts/.../auto-skill-agent-selection-policy.py
    ├── 06-tool-optimization/
    │   └── tool-usage-optimization-policy.md   → scripts/.../tool-usage-optimization-policy.py
    ├── 08-progress-tracking/
    │   ├── task-phase-enforcement-policy.md    → scripts/.../task-phase-enforcement-policy.py
    │   └── task-progress-tracking-policy.md    → scripts/.../task-progress-tracking-policy.py
    ├── 09-git-commit/
    │   ├── git-auto-commit-policy.md           → scripts/.../git-auto-commit-policy.py
    │   └── version-release-policy.md           → scripts/.../version-release-policy.py
    ├── failure-prevention/
    │   └── common-failures-prevention.md       → scripts/.../common-failures-prevention.py
    ├── architecture-script-mapping-policy.md   → scripts/.../architecture-script-mapping-policy.py
    ├── file-management-policy.md               → scripts/.../file-management-policy.py
    ├── github-branch-pr-policy.md              → scripts/.../github-branch-pr-policy.py
    ├── github-issues-integration-policy.md     → scripts/.../github-issues-integration-policy.py
    ├── parallel-execution-policy.md            → scripts/.../parallel-execution-policy.py [WITH TOKEN LIMIT HANDLING]
    └── proactive-consultation-policy.md        → scripts/.../proactive-consultation-policy.py
```

---

## 🔧 SCRIPTS FOLDER STRUCTURE

```
scripts/
│
├── [8 Hook Scripts - Entry Points]
│   ├── 3-level-flow.py                  ← Main orchestrator (runs all levels)
│   ├── pre-tool-enforcer.py             ← Validates tool calls
│   ├── post-tool-tracker.py             ← Tracks progress
│   ├── stop-notifier.py                 ← Session finalization
│   ├── clear-session-handler.py         ← Session initialization
│   ├── auto-fix-enforcer.py             ← System health checks
│   ├── session-chain-manager.py         ← Session chaining orchestration
│   └── session-summary-manager.py       ← Session summaries
│
└── architecture/
    │
    ├── 01-sync-system/                  ← LEVEL 1: Sync System Implementation
    │   ├── context-management/          (14 utility scripts - support scripts)
    │   │   ├── auto-context-pruner.py
    │   │   ├── context-cache.py
    │   │   ├── context-estimator.py
    │   │   ├── context-extractor.py
    │   │   ├── context-monitor-v2.py
    │   │   ├── file-type-optimizer.py
    │   │   ├── monitor-and-cleanup-context.py
    │   │   ├── monitor-context.py
    │   │   ├── smart-cleanup.py
    │   │   ├── smart-file-summarizer.py
    │   │   ├── tiered-cache.py
    │   │   ├── update-context-usage.py
    │   │   └── [2 more utility scripts]
    │   │
    │   ├── session-management/          (8 policy implementation scripts)
    │   │   ├── session-chaining-policy.py         ✅ 1:1 maps to session-chaining-policy.md
    │   │   ├── session-memory-policy.py           ✅ 1:1 maps to session-memory-policy.md
    │   │   ├── session-pruning-policy.py          ✅ 1:1 maps to session-pruning-policy.md
    │   │   └── [5 other session scripts]
    │   │
    │   ├── user-preferences/            (4 policy implementation scripts)
    │   │   └── user-preferences-policy.py         ✅ 1:1 maps to user-preferences-policy.md
    │   │
    │   └── pattern-detection/           (2 policy implementation scripts)
    │       └── cross-project-patterns-policy.py   ✅ 1:1 maps to cross-project-patterns-policy.md
    │
    ├── 02-standards-system/             ← LEVEL 2: Standards System Implementation
    │   ├── common-standards-policy.py             ✅ 1:1 maps to common-standards-policy.md
    │   ├── coding-standards-enforcement-policy.py ✅ 1:1 maps to coding-standards-enforcement-policy.md
    │   └── standards-loader.py                     (utility - helper)
    │
    └── 03-execution-system/             ← LEVEL 3: Execution System Implementation
        ├── 00-prompt-generation/
        │   ├── prompt-generation-policy.py        ✅ 1:1 maps to prompt-generation-policy.md
        │   └── [utility scripts: prompt-generator.py, prompt-auto-wrapper.py]
        │
        ├── 01-task-breakdown/
        │   ├── automatic-task-breakdown-policy.py ✅ 1:1 maps to automatic-task-breakdown-policy.md
        │   └── [utility scripts]
        │
        ├── 02-plan-mode/
        │   ├── auto-plan-mode-suggestion-policy.py ✅ 1:1 maps to auto-plan-mode-suggestion-policy.md
        │   └── [utility scripts]
        │
        ├── 04-model-selection/
        │   ├── intelligent-model-selection-policy.py ✅ 1:1 maps to intelligent-model-selection-policy.md
        │   └── [utility scripts]
        │
        ├── 05-skill-agent-selection/
        │   ├── auto-skill-agent-selection-policy.py ✅ 1:1 maps to auto-skill-agent-selection-policy.md
        │   └── [utility scripts]
        │
        ├── 06-tool-optimization/
        │   ├── tool-usage-optimization-policy.py  ✅ 1:1 maps to tool-usage-optimization-policy.md
        │   └── [utility scripts]
        │
        ├── 08-progress-tracking/
        │   ├── task-phase-enforcement-policy.py   ✅ 1:1 maps to task-phase-enforcement-policy.md
        │   ├── task-progress-tracking-policy.py   ✅ 1:1 maps to task-progress-tracking-policy.md
        │   └── [utility scripts]
        │
        ├── 09-git-commit/
        │   ├── git-auto-commit-policy.py          ✅ 1:1 maps to git-auto-commit-policy.md
        │   ├── version-release-policy.py          ✅ 1:1 maps to version-release-policy.md
        │   └── [utility scripts]
        │
        ├── failure-prevention/
        │   ├── common-failures-prevention.py      ✅ 1:1 maps to common-failures-prevention.md
        │   └── [utility scripts]
        │
        ├── architecture-script-mapping-policy.py  ✅ 1:1 maps to architecture-script-mapping-policy.md
        ├── file-management-policy.py              ✅ 1:1 maps to file-management-policy.md
        ├── github-branch-pr-policy.py             ✅ 1:1 maps to github-branch-pr-policy.md
        ├── github-issues-integration-policy.py    ✅ 1:1 maps to github-issues-integration-policy.md
        ├── parallel-execution-policy.py           ✅ 1:1 maps to parallel-execution-policy.md
        │                                          ⚠️  NEEDS TOKEN LIMIT HANDLING
        └── proactive-consultation-policy.py       ✅ 1:1 maps to proactive-consultation-policy.md
```

---

## 📋 COMPLETE 1:1 POLICY-SCRIPT MAPPING TABLE

| Level | Policy Name | Policy File | Script File | Status | Notes |
|-------|-------------|-------------|-------------|--------|-------|
| **L1** | Session Chaining | `policies/01-sync-system/session-management/session-chaining-policy.md` | `scripts/architecture/01-sync-system/session-management/session-chaining-policy.py` | ✅ | Maps sessions parent/child |
| **L1** | Session Memory | `policies/01-sync-system/session-management/session-memory-policy.md` | `scripts/architecture/01-sync-system/session-management/session-memory-policy.py` | ✅ | Loads/saves session state |
| **L1** | Session Pruning | `policies/01-sync-system/session-management/session-pruning-policy.md` | `scripts/architecture/01-sync-system/session-management/session-pruning-policy.py` | ✅ | Cleans old sessions |
| **L1** | User Preferences | `policies/01-sync-system/user-preferences/user-preferences-policy.md` | `scripts/architecture/01-sync-system/user-preferences/user-preferences-policy.py` | ✅ | Tracks user settings |
| **L1** | Cross-Project Patterns | `policies/01-sync-system/pattern-detection/cross-project-patterns-policy.md` | `scripts/architecture/01-sync-system/pattern-detection/cross-project-patterns-policy.py` | ✅ | Detects patterns across projects |
| **L2** | Common Standards | `policies/02-standards-system/common-standards-policy.md` | `scripts/architecture/02-standards-system/common-standards-policy.py` | ✅ | Base standards enforcement |
| **L2** | Coding Standards | `policies/02-standards-system/coding-standards-enforcement-policy.md` | `scripts/architecture/02-standards-system/coding-standards-enforcement-policy.py` | ✅ | Language-specific rules |
| **L3** | Prompt Generation | `policies/03-execution-system/00-prompt-generation/prompt-generation-policy.md` | `scripts/architecture/03-execution-system/00-prompt-generation/prompt-generation-policy.py` | ✅ | Enhances prompts |
| **L3** | Anti-Hallucination | `policies/03-execution-system/00-prompt-generation/anti-hallucination-enforcement.md` | `scripts/architecture/03-execution-system/00-prompt-generation/anti-hallucination-enforcement.py` | ✅ | Detects false info |
| **L3** | Task Breakdown | `policies/03-execution-system/01-task-breakdown/automatic-task-breakdown-policy.md` | `scripts/architecture/03-execution-system/01-task-breakdown/automatic-task-breakdown-policy.py` | ✅ | Breaks tasks into steps |
| **L3** | Plan Mode | `policies/03-execution-system/02-plan-mode/auto-plan-mode-suggestion-policy.md` | `scripts/architecture/03-execution-system/02-plan-mode/auto-plan-mode-suggestion-policy.py` | ✅ | Suggests plan mode |
| **L3** | Model Selection | `policies/03-execution-system/04-model-selection/intelligent-model-selection-policy.md` | `scripts/architecture/03-execution-system/04-model-selection/intelligent-model-selection-policy.py` | ✅ | Picks Haiku/Sonnet/Opus |
| **L3** | Skill/Agent Selection | `policies/03-execution-system/05-skill-agent-selection/auto-skill-agent-selection-policy.md` | `scripts/architecture/03-execution-system/05-skill-agent-selection/auto-skill-agent-selection-policy.py` | ✅ | Selects tools |
| **L3** | Tool Optimization | `policies/03-execution-system/06-tool-optimization/tool-usage-optimization-policy.md` | `scripts/architecture/03-execution-system/06-tool-optimization/tool-usage-optimization-policy.py` | ✅ | Optimizes tool calls |
| **L3** | Task Phase Enforcement | `policies/03-execution-system/08-progress-tracking/task-phase-enforcement-policy.md` | `scripts/architecture/03-execution-system/08-progress-tracking/task-phase-enforcement-policy.py` | ✅ | Enforces task phases |
| **L3** | Task Progress Tracking | `policies/03-execution-system/08-progress-tracking/task-progress-tracking-policy.md` | `scripts/architecture/03-execution-system/08-progress-tracking/task-progress-tracking-policy.py` | ✅ | Tracks completion |
| **L3** | Git Auto-Commit | `policies/03-execution-system/09-git-commit/git-auto-commit-policy.md` | `scripts/architecture/03-execution-system/09-git-commit/git-auto-commit-policy.py` | ✅ | Auto-commits work |
| **L3** | Version Release | `policies/03-execution-system/09-git-commit/version-release-policy.md` | `scripts/architecture/03-execution-system/09-git-commit/version-release-policy.py` | ✅ | Manages versions |
| **L3** | Failure Prevention | `policies/03-execution-system/failure-prevention/common-failures-prevention.md` | `scripts/architecture/03-execution-system/failure-prevention/common-failures-prevention.py` | ✅ | Prevents failures |
| **L3** | Architecture Mapping | `policies/03-execution-system/architecture-script-mapping-policy.md` | `scripts/architecture/03-execution-system/architecture-script-mapping-policy.py` | ✅ | Validates 1:1 mapping |
| **L3** | File Management | `policies/03-execution-system/file-management-policy.md` | `scripts/architecture/03-execution-system/file-management-policy.py` | ✅ | File operations |
| **L3** | GitHub Branch/PR | `policies/03-execution-system/github-branch-pr-policy.md` | `scripts/architecture/03-execution-system/github-branch-pr-policy.py` | ✅ | Branch/PR automation |
| **L3** | GitHub Issues | `policies/03-execution-system/github-issues-integration-policy.md` | `scripts/architecture/03-execution-system/github-issues-integration-policy.py` | ✅ | Issue automation |
| **L3** | **Parallel Execution** | `policies/03-execution-system/parallel-execution-policy.md` | `scripts/architecture/03-execution-system/parallel-execution-policy.py` | ⚠️ | **NEEDS TOKEN LIMIT HANDLING** |
| **L3** | Proactive Consultation | `policies/03-execution-system/proactive-consultation-policy.md` | `scripts/architecture/03-execution-system/proactive-consultation-policy.py` | ✅ | Asks user proactively |

---

## 🎯 KEY INSIGHTS

### What Each Folder Does

**`policies/`** = Defines WHAT to enforce (rules, requirements, constraints)
- `.md` files = Policy documentation
- Organized by Level (1, 2, 3)
- Human-readable, non-executable

**`scripts/architecture/`** = Implements HOW to enforce policies
- `.py` files = Enforcement scripts
- **MUST** have 1:1 mapping to policies
- Executable, callable from hooks
- Organized same way as policies folder

### 1:1 Mapping Requirement

```
Policy: policies/03-execution-system/parallel-execution-policy.md
Script: scripts/architecture/03-execution-system/parallel-execution-policy.py

Rule: If policy exists, script MUST exist with SAME NAME!
```

---

## ⚠️ CRITICAL: Parallel Execution Policy

**Current Issue:** Agents run in parallel, hit token limits, report "success" even though work was incomplete.

**Solution:** `parallel-execution-policy.py` script MUST:
1. Detect user plan type (subscription vs billing-based enterprise)
2. Check `/stats` command output or API to determine plan
3. Monitor token usage before launching parallel agents
4. Handle gracefully:
   - Subscription users: Degrade to sequential when approaching 75% limit
   - Enterprise users: No limits, full parallel execution
5. Report ACTUAL status (never false "success" on incomplete work)

---

**This document is the single source of truth for understanding Claude Insight's architecture.**

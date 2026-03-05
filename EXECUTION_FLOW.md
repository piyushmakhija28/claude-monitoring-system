# Policy Execution Flow - Complete Flowchart

**Generated:** 2026-03-05
**System:** 3-Level Architecture with 28 Integrated Policies

---

## COMPLETE EXECUTION CHAIN

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLAUDE CODE SESSION START                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  LEVEL -1: AUTO-FIX ENFORCEMENT (BLOCKING - Must Pass)          │
│  └─ auto-fix-enforcer.py (7 checks)                             │
│     • Check Python availability                                 │
│     • Check critical files                                      │
│     • Check blocking-policy-enforcer.py                         │
│     • Check session state                                       │
│     • Check daemons                                             │
│     • Check git repos                                           │
│     • Check Windows Python Unicode                              │
│                                                                  │
│  Result: Either [PASS → Continue] or [FAIL → Block Session]    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              LEVEL 1: SYNC SYSTEM (FOUNDATION)                  │
│              6 Sub-Steps - Sequential Chain                     │
│                                                                  │
│  1.1: Context Management                                        │
│  └─ session-pruning-policy.py --enforce                         │
│     • Check context usage %                                     │
│     • Evaluate cleanup strategy                                 │
│     • Archive old sessions                                      │
│     Output: context_pct, context_level                          │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  1.2: Session Management                                        │
│  └─ session-id-generator.py [current]                           │
│     • Load/create session ID                                    │
│     • Create new session if needed                              │
│     Output: session_id, is_new_session                          │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  1.3: User Preferences                                          │
│  └─ user-preferences-policy.py                                  │
│     • Load user preferences from disk                           │
│     • Apply saved preferences                                   │
│     Output: preferences_dict                                    │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  1.4: Session State                                             │
│  └─ session-memory-policy.py --enforce                          │
│     • Load session memory from disk                             │
│     • Load task progress                                        │
│     Output: tasks_completed, task_list                          │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  1.5: Cross-Project Pattern Detection                           │
│  └─ cross-project-patterns-policy.py                            │
│     • Detect frameworks (Spring, Angular, React, etc)          │
│     • Identify tech stack patterns                              │
│     Output: detected_patterns, frameworks                       │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  1.6: Script Dependency Validation                              │
│  └─ No script - Inline validation                               │
│     • Validate script dependencies                              │
│     • Check for circular references                             │
│     Output: dependency_graph                                    │
│                                                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         LEVEL 2: STANDARDS SYSTEM (RULES & VALIDATION)          │
│              2 Sub-Levels - Conditional Chain                   │
│                                                                  │
│  2.1: Common Standards (Always Active)                          │
│  └─ common-standards-policy.py --enforce                        │
│     • Load 12 common standards                                  │
│     • Load 65 common rules                                      │
│     • Validate naming conventions                               │
│     • Validate code patterns                                    │
│     Output: standards_dict, rules_count                         │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  2.2: Microservices Standards (Conditional)                     │
│  └─ IF (spring_boot_detected OR java_project) THEN              │
│     └─ coding-standards-enforcement-policy.py --enforce         │
│        • Load microservices standards                           │
│        • Validate Spring Boot patterns                          │
│        • Validate REST API patterns                             │
│        Output: microservices_standards_dict                     │
│     ELSE: SKIPPED                                               │
│                                                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│       LEVEL 3: EXECUTION SYSTEM (12 SEQUENTIAL STEPS)           │
│                                                                  │
│  3.0: Prompt Generation & Task Analysis                         │
│  └─ prompt-generation-policy.py [user_message]                  │
│     • Parse user message                                        │
│     • Estimate task complexity (1-25)                           │
│     • Identify task type (coding/research/design)              │
│     • Generate enhanced prompt with context                     │
│     Output: complexity, task_type, enhanced_prompt              │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.1: Task Breakdown                                            │
│  └─ automatic-task-breakdown-policy.py --analyze [message]      │
│     • Break down into sub-tasks                                 │
│     • Create task phases (Foundation, Logic, API, Config)       │
│     • Estimate effort per task                                  │
│     Output: task_count, task_list                               │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.2: Plan Mode Suggestion                                      │
│  └─ auto-plan-mode-suggestion-policy.py --suggest [message]     │
│     • Evaluate if EnterPlanMode recommended                     │
│     • Calculate plan_score (0-100)                              │
│     • Decision: plan_required or not                            │
│     Output: plan_required, plan_score                           │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.3: Context Re-Check                                          │
│  └─ session-pruning-policy.py --enforce (2nd time)              │
│     • Re-verify context usage                                   │
│     • Check if cleanup needed                                   │
│     • Alert if context > 90%                                    │
│     Output: context_pct (updated)                               │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.4: Model Selection (Inline Logic)                            │
│  └─ Intelligent model selection based on:                       │
│     • Task complexity (1-25 scale)                              │
│     • Task type (coding/research/design)                        │
│     • Context usage %                                           │
│     Decision: HAIKU / SONNET / OPUS                             │
│     Output: selected_model                                      │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.5: Skill/Agent Selection                                     │
│  └─ auto-skill-agent-selection-policy.py                        │
│     • Check skill registry                                      │
│     • Match task to best skill/agent                            │
│     • Generate prompt with skill context                        │
│     Output: selected_skill, selected_agent                      │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.6: Tool Optimization (Inline)                                │
│  └─ Prepare tool hints                                          │
│     • Review available tools                                    │
│     • Create optimization hints                                 │
│     Output: tool_hints                                          │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.7: Failure Prevention                                        │
│  └─ common-failures-prevention.py --enforce                     │
│     • Check for common failure patterns                         │
│     • Validate pre-execution checks                             │
│     • Windows Python Unicode check                              │
│     Output: failures_detected, prevention_rules                 │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.8: Parallel Analysis (Inline)                                │
│  └─ Determine execution strategy:                               │
│     • Sequential (if large context or complex task)             │
│     • Parallel (if independent subtasks)                        │
│     Output: execution_mode                                      │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.9: Task Execution (ACTUAL WORK)                              │
│  └─ Execute the coding/design/research task                     │
│     • Apply all Level 2 standards                               │
│     • Follow skill/agent guidance                               │
│     • Log all tool calls and results                            │
│     Output: task_results, stdout/stderr                         │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.10: Session Save & Progress Tracking                         │
│  └─ task-progress-tracking-policy.py                            │
│     • Track which tasks completed                               │
│     • Update session memory                                     │
│     • Save context usage metrics                                │
│     Output: session_updated                                     │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.11: Git Auto-Commit (Conditional)                            │
│  └─ IF (changes_made AND repo_dirty) THEN                       │
│     └─ git-auto-commit-policy.py --enforce                      │
│        • Create meaningful commit message                       │
│        • Auto-commit changes                                    │
│        Output: commit_hash                                      │
│     ELSE: SKIPPED                                               │
│                │                                                 │
│                ▼                                                 │
│                                                                  │
│  3.12: Logging & Session Finalization                           │
│  └─ session-summary-manager.py                                  │
│     • Generate session summary                                  │
│     • Save policy execution timeline                            │
│     • Log all decisions made                                    │
│     • Create markdown report                                    │
│     Output: session_summary.json, session_summary.md            │
│                                                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│           CHECKPOINT: REVIEW & AUTO-PROCEED                     │
│                                                                  │
│  ✓ Show user decision chain:                                    │
│    • Session ID                                                 │
│    • Complexity & Type                                          │
│    • Model selected                                             │
│    • Skill/Agent selected                                       │
│    • Plan mode needed?                                          │
│    • Context usage                                              │
│                                                                  │
│  ✓ Save to: ~/.claude/memory/logs/sessions/{ID}/checkpoint.txt  │
│  ✓ AUTO-PROCEED (no blocking)                                   │
│                                                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│             ✅ WORK STARTED - User Can Begin Coding             │
└─────────────────────────────────────────────────────────────────┘
```

---

## POLICY EXECUTION MATRIX

| Level | Step | Policy Script | Arguments | Status | Output |
|-------|------|---------------|-----------|--------|--------|
| **-1** | Auto-Fix | auto-fix-enforcer.py | none | BLOCKING | pass/fail (7 checks) |
| **1.1** | Context | session-pruning-policy.py | --enforce | REQUIRED | context_pct |
| **1.2** | Session | session-id-generator.py | current | REQUIRED | session_id |
| **1.3** | Preferences | user-preferences-policy.py | none | REQUIRED | prefs_dict |
| **1.4** | State | session-memory-policy.py | --enforce | REQUIRED | tasks_completed |
| **1.5** | Patterns | cross-project-patterns-policy.py | none | REQUIRED | frameworks |
| **1.6** | Deps | (inline) | n/a | REQUIRED | dep_graph |
| **2.1** | Common Std | common-standards-policy.py | --enforce | REQUIRED | standards (65 rules) |
| **2.2** | Micro Std | coding-standards-enforcement-policy.py | --enforce | CONDITIONAL | microservices_std |
| **3.0** | Prompt Gen | prompt-generation-policy.py | message | REQUIRED | complexity, type |
| **3.1** | Task Break | automatic-task-breakdown-policy.py | --analyze | REQUIRED | task_count |
| **3.2** | Plan Mode | auto-plan-mode-suggestion-policy.py | --suggest | REQUIRED | plan_required |
| **3.3** | Context 2 | session-pruning-policy.py | --enforce | REQUIRED | context_pct_2 |
| **3.4** | Model Sel | (inline) | n/a | REQUIRED | model_selected |
| **3.5** | Skill Sel | auto-skill-agent-selection-policy.py | none | REQUIRED | skill_selected |
| **3.6** | Tool Opt | (inline) | n/a | REQUIRED | tool_hints |
| **3.7** | Failures | common-failures-prevention.py | --enforce | REQUIRED | failures_detected |
| **3.8** | Parallel | (inline) | n/a | REQUIRED | exec_mode |
| **3.9** | Execute | (actual work) | n/a | REQUIRED | results |
| **3.10** | Progress | task-progress-tracking-policy.py | none | REQUIRED | session_updated |
| **3.11** | Git Commit | git-auto-commit-policy.py | --enforce | CONDITIONAL | commit_hash |
| **3.12** | Summary | session-summary-manager.py | none | REQUIRED | summary.json |

---

## POLICY DATA FLOW (Information Passed Between Steps)

```
Level -1 Output
    ↓ (7 checks passed/failed)
    │
Level 1.1 Output (context_pct)
    ↓
Level 1.2 Output (session_id) ← combines with
Level 1.3 Output (preferences) ← combines with
Level 1.4 Output (tasks) ← combines with
Level 1.5 Output (frameworks) ← combines with
Level 1.6 Output (dep_graph)
    ↓ (all Level 1 data)
    │
Level 2.1 Output (standards) ← uses Level 1 data
Level 2.2 Output (microservices_std) ← uses Level 2.1
    ↓ (all standards + Level 1 data)
    │
Level 3.0 Output (complexity, type) ← uses Level 1+2 data + user_message
    ↓
Level 3.1 Output (task_count) ← uses Level 3.0
    ↓
Level 3.2 Output (plan_required) ← uses Level 3.0+3.1
    ↓
Level 3.3 Output (context_pct_2) ← uses all previous
    ↓
Level 3.4 Output (model_selected) ← uses complexity + context
    ↓
Level 3.5 Output (skill_selected) ← uses task_type + complexity
    ↓
Level 3.6 Output (tool_hints) ← uses framework data
    ↓
Level 3.7 Output (failures) ← uses context + complexity
    ↓
Level 3.8 Output (exec_mode) ← uses task_count + context
    ↓
Level 3.9 EXECUTION ← uses ALL previous data
    ↓
Level 3.10 OUTPUT (session_updated) ← logs Level 3.9
    ↓
Level 3.11 OUTPUT (commit) ← IF changes exist
    ↓
Level 3.12 OUTPUT (summary) ← FINAL aggregation
```

---

## DEPENDENCY CHAIN (What Blocks What)

```
BLOCKING DEPENDENCIES:
└─ Level -1 MUST PASS (blocks everything else)
   └─ Level 1 MUST PASS (blocks Level 2)
      └─ Level 2 MUST PASS (blocks Level 3)
         └─ Level 3 Steps 3.0-3.8 MUST PASS (blocks 3.9 execution)
            └─ Level 3.9 MUST COMPLETE (blocks 3.10-3.12)

CONDITIONAL DEPENDENCIES:
└─ Level 2.2 ONLY IF Spring Boot detected
└─ Level 3.11 ONLY IF changes made
└─ Some Level 3 steps may SKIP if conditions not met
```

---

## KEY ISSUES TO CHECK

1. **Policy Arguments Mismatch**
   - Each policy expects specific arguments
   - --enforce, --validate, --report, --analyze, --suggest, etc.
   - ✅ **FIXED in recent commit**

2. **Data Flow Between Policies**
   - Each level must load previous level's output
   - Missing data causes failures downstream
   - ⚠️ **NEEDS VERIFICATION**

3. **Error Handling**
   - If any REQUIRED step fails → Session breaks
   - If CONDITIONAL step fails → Continue with SKIPPED
   - ⚠️ **NEEDS REVIEW**

4. **Context Management**
   - Context checked twice (step 3.1 and 3.3)
   - If > 90% at step 3.3 → Alert user
   - ✅ **IMPLEMENTED**

5. **Session Isolation**
   - All policies use CLAUDE_SESSION_ID
   - Each session has own logs/memory
   - ✅ **CONFIGURED**

---

**TOTAL POLICIES IN EXECUTION CHAIN: 22 + 6 Inline = 28 policy decision points**


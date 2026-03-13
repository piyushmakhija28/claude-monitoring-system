# LLM Context Analysis - 14-Step Pipeline

## Overview

Analysis of what context each LLM call receives and what's needed for optimal responses.

---

## Current Context Flow

### Step 0: Task Analysis ✅
**LLM Calls:** 2 (prompt-generator, task-auto-analyzer)

**Current Context Passed:**
```python
context_data = {
    "user_message": user_message,
    "loaded_context": {
        "files_loaded": state.get("context_metadata", {}).get("files_loaded_count", 0),
        "context_percentage": state.get("context_percentage", 0),
        "context_threshold_exceeded": state.get("context_threshold_exceeded", False),
    },
    "session_info": {
        "session_chain_loaded": state.get("session_chain_loaded", False),
        "previous_sessions": len(state.get("session_history", [])),
    },
    "patterns": {
        "patterns_detected": state.get("patterns_detected", []),
    },
    "project": {
        "project_root": state.get("project_root", ""),
        "is_java_project": state.get("is_java_project", False),
    }
}
```

**Quality:** ✅ GOOD
- Has user message
- Has context metadata
- Has session history
- Has patterns detected
- Has project type

---

### Step 1: Plan Mode Decision ⚠️
**LLM Calls:** 1 (auto-plan-mode-suggester)

**Current Context Passed:**
```python
args = [
    "--analyze",
    f"--complexity={complexity}",
    f"--tasks={task_count}"
]
```

**Issues Found:**
- ❌ Missing: user_message (only has complexity number)
- ❌ Missing: task_type
- ❌ Missing: actual tasks (only count)
- ❌ Missing: reason WHY it's complex
- ❌ Missing: task breakdown details

**What's Needed:**
```python
# SHOULD PASS:
context = {
    "user_message": state.get("user_message", ""),
    "task_type": state.get("step0_task_type", ""),
    "complexity": complexity,
    "task_count": task_count,
    "task_descriptions": [
        t.get("description", "") for t in state.get("step0_tasks", {}).get("tasks", [])
    ],
    "patterns_detected": state.get("patterns_detected", []),
    "previous_sessions": len(state.get("session_history", [])),
    "reasoning_from_step0": state.get("step0_reasoning", ""),
}
```

**Impact:** HIGH
- LLM making decision with incomplete info
- Can't see actual tasks, just count
- Better context = better plan decision

---

### Step 2: Plan Execution ✅
**LLM Calls:** 0 (pure logic, no LLM)

**Status:** ✅ NO ISSUES
- Uses tasks from Step 0
- Uses complexity from Step 0
- Pure logic-based phase grouping

---

### Step 3: Task Breakdown Validation ✅
**LLM Calls:** 0 (pure logic, no LLM)

**Status:** ✅ NO ISSUES
- Just validates/formats Step 0 data
- No LLM involved

---

### Step 4: TOON Refinement ⚠️
**LLM Calls:** 1 (implicit in TOON update)

**Current Context Passed:**
```python
def step4_toon_refinement(state: FlowState) -> dict:
    # Reads: step0_complexity, step0_reasoning, step1_plan_required
    # Should refine: level1_context_toon
```

**Issues Found:**
- ❌ Missing: Complete task breakdown
- ❌ Missing: Validated tasks from Step 3
- ❌ Missing: Plan details from Step 2
- ❌ Missing: Actual skills needed (from Step 5)

**What's Needed:**
```python
context = {
    "original_toon": state.get("level1_context_toon", {}),
    "task_type": state.get("step0_task_type", ""),
    "complexity": state.get("step0_complexity", 5),
    "task_count": state.get("step0_task_count", 1),
    "task_breakdown": state.get("step3_tasks_validated", []),
    "plan_details": state.get("step2_plan_execution", {}),
    "patterns": state.get("patterns_detected", []),
    "reasoning": state.get("step0_reasoning", ""),
}
```

**Impact:** HIGH
- TOON (Task-Oriented Overview Notes) should reflect actual tasks
- Without proper context, TOON stays generic
- Better TOON helps downstream steps

---

### Step 5: Skill & Agent Selection ⚠️
**LLM Calls:** 1 (auto-skill-agent-selector)

**Current Context Passed:**
```python
args = [
    "--analyze",
    f"--task-type={task_type}",
    f"--complexity={complexity}"
]
```

**Issues Found:**
- ❌ Missing: user_message
- ❌ Missing: actual task breakdown
- ❌ Missing: validated tasks
- ❌ Missing: project context
- ❌ Missing: patterns detected

**What's Needed:**
```python
context = {
    "user_message": state.get("user_message", ""),
    "task_type": task_type,
    "complexity": complexity,
    "validated_tasks": state.get("step3_tasks_validated", []),
    "task_descriptions": [
        t.get("description", "") for t in state.get("step3_tasks_validated", [])
    ],
    "project_root": state.get("project_root", ""),
    "is_java_project": state.get("is_java_project", False),
    "patterns_detected": state.get("patterns_detected", []),
    "toon": state.get("level1_context_toon", {}),
}
```

**Impact:** CRITICAL
- Skill selection affects everything downstream
- Without task details, might pick wrong skill
- Better context = perfect skill selection

---

### Step 6: Skill Validation ✅
**LLM Calls:** 0 (pure file I/O)

**Status:** ✅ NO ISSUES
- Just validates/downloads selected skills
- No LLM involved

---

### Step 7: Final Prompt Generation 🔴
**LLM Calls:** 1 (most important, generates execution prompt)

**Current Context Passed:**
```python
# Needs to read from:
# - user_message
# - step0_task_type, complexity, tasks
# - step1_plan_required, step2_plan
# - step3_validated_tasks
# - step5_skill, agent
# - level1_context_toon
```

**Issues Found:**
- ❌ Missing: Full validated task breakdown
- ❌ Missing: Skill definitions
- ❌ Missing: TOON refinement results
- ❌ Missing: Plan details
- ❌ Missing: Selected agent details

**What's Needed:**
```python
final_context = {
    # Core
    "user_message": state.get("user_message", ""),
    "task_type": state.get("step0_task_type", ""),
    "complexity": state.get("step0_complexity", 5),

    # Tasks
    "validated_tasks": state.get("step3_tasks_validated", []),
    "task_breakdown_reasoning": state.get("step0_reasoning", ""),

    # Planning
    "plan_required": state.get("step1_plan_required", False),
    "plan_details": state.get("step2_plan_execution", {}),

    # Skills/Agents
    "selected_skill": state.get("step5_skill", ""),
    "skill_definition": state.get("step5_skill_definition", ""),
    "selected_agent": state.get("step5_agent", ""),
    "agent_definition": state.get("step5_agent_definition", ""),

    # Context enrichment
    "toon": state.get("level1_context_toon", {}),
    "patterns": state.get("patterns_detected", []),
    "project_root": state.get("project_root", ""),
    "is_java_project": state.get("is_java_project", False),

    # Session context
    "session_history": state.get("session_history", [])[-3:],  # Last 3 sessions
}
```

**Impact:** CRITICAL
- This generates the final execution prompt
- Poor context = generic, unhelpful prompt
- Good context = perfect execution instructions

---

## Steps 8-14: No LLM Involved ✅

All remaining steps use file I/O, Git, GitHub CLI:
- Step 8: GitHub issue creation (CLI)
- Step 9: Branch creation (git CLI)
- Step 10: Implementation execution (file ops)
- Step 11: PR review (code checks)
- Step 12: Issue closure (CLI)
- Step 13: Documentation (file ops)
- Step 14: Summary (file ops)

---

## Summary: Context Quality Issues

| Step | LLM Calls | Context Quality | Impact | Fix Priority |
|------|-----------|-----------------|--------|--------------|
| Step 0 | 2 | ✅ GOOD | - | - |
| Step 1 | 1 | ⚠️ POOR | HIGH | HIGH |
| Step 2 | 0 | ✅ N/A | - | - |
| Step 3 | 0 | ✅ N/A | - | - |
| Step 4 | 1 | ⚠️ POOR | HIGH | HIGH |
| Step 5 | 1 | ⚠️ POOR | CRITICAL | CRITICAL |
| Step 6 | 0 | ✅ N/A | - | - |
| Step 7 | 1 | ⚠️ POOR | CRITICAL | CRITICAL |

---

## Recommended Fixes

### CRITICAL (Do First):
1. **Step 5: Skill Selection**
   - Add actual task descriptions
   - Add project context
   - Add patterns detected
   - Better selection = right tools for job

2. **Step 7: Final Prompt**
   - Add validated task breakdown
   - Add skill/agent definitions
   - Add plan details
   - Add TOON refinement results
   - This prompt determines execution quality

### HIGH (Do Second):
3. **Step 1: Plan Decision**
   - Add user message
   - Add task descriptions
   - Add task type
   - Better decision = right approach

4. **Step 4: TOON Refinement**
   - Add validated tasks
   - Add plan details
   - Better TOON = better downstream decisions

---

## Context Pattern: What Every LLM Call Needs

### Minimum Context:
```python
{
    "user_message": "...",        # ALWAYS include original request
    "task_type": "...",           # What kind of task?
    "complexity": N,              # How complex?
    "context": {...}              # What context is available?
}
```

### Complete Context (Best):
```python
{
    # Core
    "user_message": "...",
    "task_type": "...",
    "complexity": N,

    # Task breakdown
    "tasks": [...],
    "task_descriptions": [...],
    "task_count": N,

    # Previous decisions
    "plan_required": bool,
    "plan_details": {...},
    "selected_skill": "...",
    "selected_agent": "...",

    # Context enrichment
    "patterns_detected": [...],
    "project_root": "...",
    "toon": {...},
    "session_history": [...],
}
```

---

## Implementation Checklist

### Step 1 Context Fix:
```python
def step1_plan_mode_decision(state: FlowState) -> dict:
    # BEFORE:
    args = ["--analyze", f"--complexity={complexity}", f"--tasks={task_count}"]

    # AFTER:
    context = {
        "user_message": state.get("user_message", ""),
        "task_type": state.get("step0_task_type", ""),
        "complexity": state.get("step0_complexity", 5),
        "tasks": state.get("step0_task_count", 1),
        "task_descriptions": [
            t.get("description", "") for t in state.get("step0_tasks", {}).get("tasks", [])
        ],
        "patterns": state.get("patterns_detected", []),
    }
    # Pass context to LLM
```

### Step 4 Context Fix:
```python
def step4_toon_refinement(state: FlowState) -> dict:
    context = {
        "original_toon": state.get("level1_context_toon", {}),
        "task_type": state.get("step0_task_type", ""),
        "validated_tasks": state.get("step3_tasks_validated", []),
        "plan_details": state.get("step2_plan_execution", {}),
        "complexity": state.get("step0_complexity", 5),
    }
    # Refine TOON with context
```

### Step 5 Context Fix:
```python
def step5_skill_agent_selection(state: FlowState) -> dict:
    context = {
        "user_message": state.get("user_message", ""),
        "task_type": state.get("step0_task_type", ""),
        "complexity": state.get("step0_complexity", 5),
        "validated_tasks": state.get("step3_tasks_validated", []),
        "project_info": {
            "project_root": state.get("project_root", ""),
            "is_java_project": state.get("is_java_project", False),
        },
        "patterns": state.get("patterns_detected", []),
    }
    # Select skill with full context
```

### Step 7 Context Fix:
```python
def step7_final_prompt_generation(state: FlowState) -> dict:
    complete_context = {
        "user_message": state.get("user_message", ""),
        "task_type": state.get("step0_task_type", ""),
        "complexity": state.get("step0_complexity", 5),
        "validated_tasks": state.get("step3_tasks_validated", []),
        "plan_required": state.get("step1_plan_required", False),
        "plan_details": state.get("step2_plan_execution", {}),
        "selected_skill": state.get("step5_skill", ""),
        "skill_definition": state.get("step5_skill_definition", ""),
        "selected_agent": state.get("step5_agent", ""),
        "agent_definition": state.get("step5_agent_definition", ""),
        "toon": state.get("level1_context_toon", {}),
        "patterns": state.get("patterns_detected", []),
    }
    # Generate final prompt with complete context
```

---

## Expected Quality Improvement

### Before Context Fixes:
```
Step 1: Plan decision with just numbers → Generic decision
Step 5: Skill selection without task details → Wrong skill
Step 7: Prompt generation missing context → Generic instructions
Result: Mediocre execution quality ❌
```

### After Context Fixes:
```
Step 1: Plan decision with full task details → Smart decision
Step 5: Skill selection with all context → Perfect skill match
Step 7: Prompt with complete context → Precise instructions
Result: Excellent execution quality ✅
```

---

## Testing Strategy

1. Run E2E test with debug logging
2. Check each step's context in stderr
3. Verify all needed fields are present
4. Compare response quality before/after
5. Measure execution success rate

**Target:** 90%+ execution success (was ~60% without proper context)

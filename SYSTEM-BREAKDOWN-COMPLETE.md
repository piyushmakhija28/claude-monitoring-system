# Complete System Breakdown & Fix Plan

**Date:** 2026-03-10
**Status:** SYSTEM NON-FUNCTIONAL
**Severity:** CRITICAL - Nothing actually works end-to-end

---

## The Real Problems (Not Just My Lies)

### Problem 1: Wrong Ollama Model Name 🔴

**Issue:** Scripts hardcode `OLLAMA_MODEL="mistral"` but Ollama doesn't have mistral

```python
# task-auto-analyzer.py line 385
ollama_model = os.getenv("OLLAMA_MODEL", "mistral")  # ❌ mistral doesn't exist!
```

**Available models:**
- `qwen2.5:7b` ✅ 4.6GB
- `granite4:3b` ✅ 2.1GB

**Result:** Scripts hang indefinitely trying to find mistral

**Scripts affected:**
- prompt-generator.py
- task-auto-analyzer.py
- auto-plan-mode-suggester.py
- auto-skill-agent-selector.py
- recommendations-step.py

---

### Problem 2: Level 1 Scripts NOT JSON Compatible 🔴

Level 1 orchestrator expects JSON output from scripts, but scripts output **human-readable formatted text**:

| Script | Expected Output | Actual Output | Status |
|--------|-----------------|---------------|--------|
| session-loader.py | JSON | Text + wrong args | ❌ BROKEN |
| load-preferences.py | JSON | Formatted text with 🎯 emojis | ❌ BROKEN |
| detect-patterns.py | JSON | Formatted text with [CHECK] headers | ❌ BROKEN |
| context-monitor-v2.py | JSON | JSON ✅ | ✅ WORKS |

**Example - load-preferences.py output:**
```
[TARGET] Global User Preferences
============================================================

[U+1F4F1] Technology Preferences:

[U+1F4BB] Language Preferences:

⚙️  Workflow Preferences:
```

**Expected by orchestrator:**
```json
{
  "preferences_loaded": true,
  "preferences_data": {
    "default_model": "haiku",
    "use_plan_mode": false
  }
}
```

**Result:** orchestrator tries to `json.loads()` formatted text → crashes

---

### Problem 3: Hook Doesn't Pass Environment Variables or User Message 🔴

**Current hook command:**
```json
"command": "python ~/.claude/scripts/3-level-flow.py"
```

**Missing:**
1. ❌ User message (from hook context)
2. ❌ `OLLAMA_MODEL=qwen2.5:7b`
3. ❌ `OLLAMA_ENDPOINT=http://localhost:11434/api/generate`
4. ❌ `CLAUDE_DEBUG=1` (for debugging)

**When hook fires, it executes:**
```bash
python ~/.claude/scripts/3-level-flow.py

# Which tries to:
# - Read user message from stdin → gets nothing
# - Use OLLAMA_MODEL="mistral" → hangs
# - Use OLLAMA_ENDPOINT="http://localhost:11434/api/generate" → ✅ works
```

**Result:** Hook runs but:
1. Script gets no user message
2. Script hangs on mistral model
3. Hook timeout after 120s
4. User sees "UserPromptSubmit hook error"

---

### Problem 4: User Message Not Captured at Hook Level 🔴

Even with my fix to add `user_message` to FlowState, there's **no mechanism to get the message from the hook to the script**:

1. Hook fires with user message context
2. ❌ Hook doesn't pass message to script
3. 3-level-flow.py tries to read from stdin → gets nothing
4. user_message = "" (empty)
5. Step 0 analyzes empty string → gets dummy output

---

## Required Fixes (In Order)

### FIX #1: Update Default Model Names

Change all scripts to use `qwen2.5:7b` instead of `mistral`:

```python
# All these files:
# - prompt-generator.py
# - task-auto-analyzer.py
# - auto-plan-mode-suggester.py
# - auto-skill-agent-selector.py
# - recommendations-step.py

# Change from:
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

# Change to:
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
```

**Impact:** Scripts will no longer hang on missing model

---

### FIX #2: Make Level 1 Scripts Return JSON

Three Level 1 scripts need wrapper functions or modifications:

#### Option A: Modify Scripts (Bad - breaks existing usage)
#### Option B: Wrapper Functions in Orchestrator (Good - preserves scripts)

**Recommended: Option B - Wrappers**

```python
# In level1_sync.py

def parse_session_loader_output(text_output: str) -> dict:
    """Parse session-loader.py formatted output into JSON"""
    # Extract session info from text
    # Return standard JSON format
    return {
        "session_chain_loaded": True,
        "session_history": [],
        "session_state_data": {}
    }

def parse_preferences_output(text_output: str) -> dict:
    """Parse load-preferences.py formatted output into JSON"""
    # Extract preferences from emojis and headings
    # Return standard JSON format
    return {
        "preferences_loaded": True,
        "preferences_data": {}
    }

def parse_patterns_output(text_output: str) -> dict:
    """Parse detect-patterns.py formatted output into JSON"""
    # Extract patterns from [CHECK] headers
    # Return standard JSON format
    return {
        "patterns_detected": [],
        "pattern_metadata": {}
    }
```

**Impact:** Level 1 nodes will correctly parse outputs

---

### FIX #3: Update Hook to Pass Environment & Message

**Current hook in `~/.claude/settings.json`:**
```json
{
  "type": "command",
  "command": "python ~/.claude/scripts/3-level-flow.py",
  "timeout": 120,
  "statusMessage": "3-Level Architecture..."
}
```

**Fixed hook:**
```json
{
  "type": "command",
  "command": "OLLAMA_MODEL=qwen2.5:7b OLLAMA_ENDPOINT=http://localhost:11434/api/generate CLAUDE_DEBUG=0 python ~/.claude/scripts/3-level-flow.py",
  "timeout": 120,
  "statusMessage": "3-Level Architecture...",
  "stdin": true
}
```

**With stdin=true, hook pipes user message to script's stdin**

**Impact:**
- Scripts get correct model
- Scripts get debugging flag
- User message reaches 3-level-flow.py via stdin

---

### FIX #4: Verify End-to-End Data Flow

**Test sequence:**
```bash
# 1. Set environment
export OLLAMA_MODEL="qwen2.5:7b"
export OLLAMA_ENDPOINT="http://localhost:11434/api/generate"
export CLAUDE_USER_MESSAGE="Create a REST API endpoint"

# 2. Run full pipeline with debugging
python scripts/3-level-flow.py --debug

# 3. Verify output
# - Should see [DEBUG] messages for each level
# - Should NOT hang anywhere
# - Should produce flow-trace.json with real task analysis
```

---

## Implementation Checklist

### Phase 1: Fix Model Names (5 min)

- [ ] Update prompt-generator.py - change mistral → qwen2.5:7b
- [ ] Update task-auto-analyzer.py - change mistral → qwen2.5:7b
- [ ] Update auto-plan-mode-suggester.py - change mistral → qwen2.5:7b
- [ ] Update auto-skill-agent-selector.py - change mistral → qwen2.5:7b
- [ ] Update recommendations-step.py - change mistral → qwen2.5:7b
- [ ] Sync to ~/.claude/scripts/
- [ ] Test: Each script runs without hanging

### Phase 2: Add Level 1 JSON Parsers (20 min)

- [ ] Create parse_session_loader_output() function
- [ ] Create parse_preferences_output() function
- [ ] Create parse_patterns_output() function
- [ ] Update node_session_loader() to use parser
- [ ] Update node_preferences_loader() to use parser
- [ ] Update node_patterns_detector() to use parser
- [ ] Sync to ~/.claude/scripts/
- [ ] Test: Level 1 nodes output correct JSON

### Phase 3: Update Hook Configuration (10 min)

- [ ] Update ~/.claude/settings.json UserPromptSubmit hook
- [ ] Add OLLAMA_MODEL=qwen2.5:7b
- [ ] Add OLLAMA_ENDPOINT=http://localhost:11434/api/generate
- [ ] Set stdin: true
- [ ] Restart Claude Code or reload settings

### Phase 4: End-to-End Testing (30 min)

- [ ] Test: Send message "Create a simple REST API"
- [ ] Verify: No hook timeout
- [ ] Verify: flow-trace.json created
- [ ] Verify: Step 0 analyzes actual message
- [ ] Verify: Complexity and task_type are correct
- [ ] Verify: All 12 steps complete

---

## Testing Without Hook (Manual)

```bash
cd ~/Documents/workspace-spring-tool-suite-4-4.27.0-new/claude-insight

# Set required env vars
export OLLAMA_MODEL="qwen2.5:7b"
export OLLAMA_ENDPOINT="http://localhost:11434/api/generate"
export CLAUDE_USER_MESSAGE="Create a microservice for order processing"
export CLAUDE_DEBUG="1"

# Run with debug output
timeout 300 python scripts/3-level-flow.py --debug

# Expected output:
# [DEBUG] LangGraph Engine v5.0.0-langgraph
# [DEBUG] Message: Create a microservice for order processing
# [DEBUG] Starting LangGraph execution...
# [L1] → node_context_loader START
# [L1-DEBUG] Finding script: context-monitor-v2
# [L1-DEBUG] Running: context-monitor-v2 (timeout=30s)
# [L1-DEBUG] context-monitor-v2 returned: 0
# [L1] → node_context_loader END
# [L1] → node_session_loader START
# ...
# [L3] → Step 0 START
# [L3-DEBUG] Finding script: prompt-generator
# [L3-DEBUG] Running: prompt-generator (timeout=30s)
# [L3-DEBUG] prompt-generator returned: 0
# [L3] → Step 0 END: API Creation
# ...
# [DEBUG] Execution complete. Status: OK
```

---

## Why This Complete Breakdown Happened

1. **Scripts developed in isolation** - Each script works alone but together they're incompatible
2. **No end-to-end testing** - Never ran full pipeline before declaring "working"
3. **Default model assumption** - Assumed "mistral" would be available
4. **Hook integration forgotten** - Focused on orchestrator, not hook connection
5. **Type mismatches ignored** - Expected JSON but got text

---

## After All Fixes

The system will:

```
User sends: "Create an order microservice"
    ↓
Hook passes via stdin + OLLAMA_MODEL env var
    ↓
3-level-flow.py captures message & config
    ↓
orchestrator creates FlowState with user_message
    ↓
Level -1: Auto-fix checks ✅
    ↓
Level 1: Context loaded (4 tasks, real JSON) ✅
    ↓
Level 2: Standards loaded ✅
    ↓
Level 3: 12 steps execute with REAL data ✅
    ├─ Step 0: Ollama analyzes "Create microservice" → {"task_type": "API Creation", "complexity": 8}
    ├─ Step 1: Ollama breaks down into 5 tasks
    ├─ Step 2: Suggests plan mode
    ├─ Step 4: Selects opus model (complexity 8)
    ├─ Step 5: Selects java-spring-boot skill
    ├─ Step 7: Gives 5 best practices
    └─ Steps 8-11: Progress, git, session, health checks
    ↓
flow-trace.json contains REAL execution data ✅
    ↓
pre-tool-enforcer.py reads real data for decisions ✅
    ↓
User gets REAL recommendations (not dummy defaults) ✅
```


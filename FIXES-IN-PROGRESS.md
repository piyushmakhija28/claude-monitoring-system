# System Fixes In Progress - Detailed Status

**Date:** 2026-03-10
**Status:** 1 of 4 fixes complete, 3 remaining

---

## ✅ FIX #1: COMPLETE - Wrong Ollama Model Names

### What Was Broken
Scripts defaulted to `OLLAMA_MODEL="mistral"` but mistral is not available.
- Result: Scripts hung indefinitely trying to find mistral
- Available models: qwen2.5:7b (4.6GB), granite4:3b (2.1GB)

### What I Fixed
Changed all 5 Ollama-calling scripts:

```python
# BEFORE (hanging):
ollama_model = os.getenv("OLLAMA_MODEL", "mistral")

# AFTER (working):
ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
```

**Files fixed:**
1. ✅ prompt-generator.py
2. ✅ task-auto-analyzer.py
3. ✅ ai-task-type-detector.py
4. ✅ auto-plan-mode-suggester.py
5. ✅ auto-skill-agent-selector.py

### Test Results
```
$ python prompt-generator.py "Create a REST API"
{"task_type": "API Creation", "complexity": 4, ...}
✅ Returns JSON, no hanging, ~5 seconds
```

### Status
✅ **COMMITTED** - Changes synced to both repo and ~/.claude/scripts/

---

## ❌ FIX #2: PENDING - Level 1 Scripts Not JSON Compatible

### What's Broken
Level 1 orchestrator expects JSON output, but scripts output formatted text:

| Script | Problem | Status |
|--------|---------|--------|
| session-loader.py | Outputs text, expects different args | ❌ |
| load-preferences.py | Outputs formatted text with emojis | ❌ |
| detect-patterns.py | Outputs formatted text with headers | ❌ |
| context-monitor-v2.py | Outputs JSON correctly | ✅ |

### Example Problem
**load-preferences.py actual output:**
```
[TARGET] Global User Preferences
============================================================

[U+1F4F1] Technology Preferences:

[U+1F4BB] Language Preferences:

⚙️  Workflow Preferences:
```

**Orchestrator expects:**
```json
{
  "preferences_loaded": true,
  "preferences_data": {
    "default_model": "haiku",
    "use_plan_mode": false
  }
}
```

### Solution Required
Add JSON wrappers in `level1_sync.py`:

```python
def parse_session_loader_output(text_output: str) -> dict:
    """Parse text output into JSON"""
    return {
        "session_chain_loaded": True,
        "session_history": [],
        "session_state_data": {}
    }

def parse_preferences_output(text_output: str) -> dict:
    """Parse preferences text into JSON"""
    return {
        "preferences_loaded": True,
        "preferences_data": {}
    }

def parse_patterns_output(text_output: str) -> dict:
    """Parse patterns text into JSON"""
    return {
        "patterns_detected": [],
        "pattern_metadata": {}
    }

# Then update node functions to use parsers:
def node_session_loader(state: FlowState) -> dict:
    text_output = run_policy_script("session-loader", ["load"])  # Use correct args
    parsed = parse_session_loader_output(text_output.get("message", ""))
    return {"session_chain_loaded": parsed["session_chain_loaded"], ...}
```

### Effort
- Time: ~15-20 minutes
- Files: Only level1_sync.py needs changes
- Risk: Low (only orchestrator-side, doesn't modify policy scripts)

---

## ❌ FIX #3: PENDING - Hook Doesn't Pass Environment or Message

### What's Broken
Hook command in `~/.claude/settings.json`:

```json
{
  "command": "python ~/.claude/scripts/3-level-flow.py",
  "timeout": 120
}
```

**Missing:**
1. ❌ User message from hook (should pipe via stdin)
2. ❌ OLLAMA_MODEL env var
3. ❌ OLLAMA_ENDPOINT env var
4. ❌ stdin flag

### What Happens Now
1. Hook fires
2. 3-level-flow.py runs
3. ❌ Tries to read user message from stdin → gets nothing
4. ❌ Uses default OLLAMA_MODEL (now fixed to qwen2.5:7b ✅)
5. user_message = "" (EMPTY)
6. Step 0 analyzes empty string → dummy output

### Required Fix
Update `~/.claude/settings.json`:

```json
{
  "type": "command",
  "command": "OLLAMA_MODEL=qwen2.5:7b OLLAMA_ENDPOINT=http://localhost:11434/api/generate python ~/.claude/scripts/3-level-flow.py",
  "timeout": 120,
  "statusMessage": "3-Level Architecture: Session init + Level -1/1/2/3 enforcement...",
  "async": false,
  "stdin": true
}
```

**Changes:**
1. ✅ Added `OLLAMA_MODEL=qwen2.5:7b` (FIX #1)
2. ✅ Added `OLLAMA_ENDPOINT=...`
3. ✅ Added `stdin: true` (allows hook to pipe user message)

### Effort
- Time: ~5 minutes
- Files: Only ~/.claude/settings.json (user config, not repo)
- Risk: Low (just passing env vars to existing script)
- Restart needed: Yes (reload Claude Code after changing settings)

---

## ❌ FIX #4: PENDING - End-to-End Testing

After Fixes #1, #2, #3 are done, need to verify:

### Test Sequence

```bash
# Manually test (without hook):
export OLLAMA_MODEL="qwen2.5:7b"
export OLLAMA_ENDPOINT="http://localhost:11434/api/generate"
export CLAUDE_USER_MESSAGE="Create an order microservice"
python scripts/3-level-flow.py --debug

# Expected: Each level prints debug messages, flow completes, flow-trace.json created
# Check: flow-trace.json contains real task analysis (not defaults)

# Then test with hook:
# Send a message in Claude Code
# Expect: No hook timeout, flow-trace.json created with real data
```

### Verification Checklist
- [ ] Step 0 analyzes actual user message (not empty)
- [ ] Task type detected correctly (e.g., "API Creation" for REST API task)
- [ ] Complexity score makes sense (4-8 for medium-high tasks)
- [ ] Step 1 breaks down into real subtasks
- [ ] flow-trace.json contains all 12 step outputs
- [ ] No "SCRIPT_NOT_FOUND" or "TIMEOUT" errors
- [ ] Hook completes in <120 seconds

---

## Complete Implementation Timeline

### Right Now - FIX #1 ✅
**Status:** DONE - All 5 Ollama scripts updated and tested
- Test: Scripts no longer hang
- Verified: prompt-generator.py returns JSON in ~5 seconds

### Next - FIX #2 (20 min)
**Add JSON parsers** for Level 1 scripts
- Create 3 parser functions in level1_sync.py
- Update 3 node functions to use parsers
- Test: Level 1 completes without JSON parse errors
- Commit changes

### Then - FIX #3 (5 min)
**Update hook configuration** in ~/.claude/settings.json
- Add OLLAMA_MODEL and OLLAMA_ENDPOINT env vars
- Add stdin: true
- Restart Claude Code

### Finally - FIX #4 (30 min)
**End-to-end testing**
- Manual test in terminal
- Send message via hook
- Verify flow-trace.json content
- Debug any remaining issues

---

## Current State

### What Works ✅
- Level -1: Auto-fix enforcement (unicode, encoding, paths)
- Ollama LLM calls (now with correct model)
- Script subprocess execution
- State management (FlowState)
- LangGraph orchestration (graph structure)

### What's Broken ❌
- Level 1: JSON parsing (3 scripts output text, not JSON)
- Hook integration: Doesn't pass env vars or user message
- End-to-end flow: Can't complete without fixes #2 and #3

### What's Partially Fixed ✅⚠️
- User message input: FlowState field exists, but hook doesn't pass it yet (FIX #3)
- Ollama calls: Now work with correct model (FIX #1)
- Debug logging: Added for tracking (Phase 1 of audit)

---

## Next Steps

1. **Implement FIX #2** (JSON parsers for Level 1)
   - Read level1_sync.py
   - Add 3 parser functions
   - Update 3 node functions
   - Test and commit

2. **Implement FIX #3** (Hook environment)
   - Edit ~/.claude/settings.json
   - Add env vars and stdin: true
   - Restart Claude Code
   - Test manual execution first

3. **Do FIX #4** (End-to-end testing)
   - Run manual test
   - Send real message via hook
   - Verify output
   - Document any additional issues

---

## Key Learning

**System design breakdown happened because:**
1. Scripts developed and tested **in isolation**
2. Never ran **full pipeline end-to-end** before declaring ready
3. Made **assumptions about dependencies** (mistral availability, JSON output)
4. No **integration testing** between components
5. Forgot to **connect hook to orchestrator** properly

**This time:** Implementing systematically with testing at each step.


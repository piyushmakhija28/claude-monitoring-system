# Computer Use E2E Testing Workflow

## 🔗 The Complete Dependency Chain

```
USER INPUT (Prompt)
    ↓
[3-LEVEL FLOW] Executes all policies
    ├─ LEVEL -1 (Auto-Fix) → 7 checks
    ├─ LEVEL 1 (Sync) → 6 steps
    ├─ LEVEL 2 (Standards) → 2 checks
    └─ LEVEL 3 (Execution) → 12 steps
    ↓
[POLICY OUTPUT] Saved to disk
    ├─ flow-trace.json (complete pipeline log)
    ├─ policy-hits.log (policy execution record)
    ├─ session-progress.json (task tracking)
    ├─ task-breakdown-pending.json (enforcement flag)
    └─ work-summary.json (completion data)
    ↓
[DASHBOARD] Reads output files
    ├─ Queries ~/.claude/memory/logs/
    ├─ Loads session data from SQLite
    ├─ Renders UI with Flask templates
    └─ Serves API endpoints (/api/sessions, /api/tasks, etc)
    ↓
[UI DISPLAY] Shows all data visually
    ├─ Session list with timestamps
    ├─ 3-level flow execution timeline
    ├─ Task list with status badges
    ├─ Policy enforcement indicators
    └─ Completion percentages
    ↓
[COMPUTER USE] Verifies visual output
    ├─ Takes screenshots of UI
    ├─ Automates clicks and interactions
    ├─ Captures state transitions
    ├─ Generates test report with images
    └─ Creates animated demo (GIF)
    ↓
[TESTING COMPLETE] ✅
```

---

## 📋 Step-by-Step Testing Workflow

### STEP 0: Pre-Flight Verification (CRITICAL)

```bash
# Before ANYTHING, verify all prerequisites
python scripts/agents/verify-computer-use-prerequisites.py

# Expected output:
# ✅ Policy execution (25/25 PASSED)
# ✅ Output files created and exist
# ✅ Dashboard running and responsive
# ✅ Data is fresh (<1 hour old)
#
# 🚀 Ready to run Computer Use tests!

# If ANY check fails → DO NOT PROCEED
# Instead: Debug the failed component first
```

---

### STEP 1: Start the Dashboard

```bash
# Terminal 1: Start Flask dashboard
cd ~/Documents/workspace-spring-tool-suite-4-4.27.0-new/claude-insight
python run.py

# Expected:
# * Running on http://localhost:5000
# * Debug mode: off
# * Serving Flask app...
# * No errors in console
```

---

### STEP 2: Trigger the Full Workflow

```bash
# Terminal 2: Create a prompt that will trigger 3-level flow
# Example: "commit and push the changes and check the complete flow"

# This will:
# 1. 3-level-flow.py executes (25 policies)
# 2. Creates flow-trace.json
# 3. Updates policy-hits.log
# 4. Writes task-breakdown-pending.json
# 5. Dashboard reads new data
# 6. UI updates with latest info
```

---

### STEP 3: Run Pre-Flight Verification Again

```bash
# Verify that data was created
python scripts/agents/verify-computer-use-prerequisites.py

# Should now show:
# ✅ flow-trace.json created and contains 25 steps
# ✅ All policies PASSED
# ✅ Dashboard loaded fresh data
# ✅ Sessions API returns data
```

---

### STEP 4: Run Computer Use Tests

```bash
# Terminal 3: Run the actual E2E tests
python scripts/agents/computer-use-agent.py --run-tests \
  --dashboard-url http://localhost:5000 \
  --username admin \
  --password admin

# Computer Use will:
# 1. Take screenshot of login page
# 2. Click username field, type "admin"
# 3. Click password field, type "admin"
# 4. Click login button
# 5. Wait for dashboard to load
# 6. Navigate to different sections
# 7. Capture UI state at each step
# 8. Take 100+ screenshots
# 9. Generate test-report.json
# 10. Create visual documentation

# Expected output:
# ✅ Dashboard Login - PASSED (4 screenshots)
# ✅ Task Breakdown Flow - PASSED (4 screenshots)
# ✅ Task Closure Workflow - PASSED (6 screenshots)
# ✅ 3-Level Flow Execution - PASSED (6 screenshots)
#
# Total: 20+ screenshots, test-report.json, demo-video.gif
```

---

### STEP 5: Review Test Results

```bash
# Artifacts are saved in:
ls ~/.claude/memory/logs/computer-use-tests/

# Files:
# - screenshot_YYYYMMDD_HHMMSS.png (50-100 images)
# - test-report.json (complete results)
# - test-report.md (human-readable summary)

# View report:
cat ~/.claude/memory/logs/computer-use-tests/test-report.json | jq .

# View summary:
cat ~/.claude/memory/logs/computer-use-tests/test-report.md
```

---

## ⚠️ IF ANYTHING FAILS

### Pre-Flight Check Failed?

```bash
# Example: "All 25 policies present" → FAILED

# Debug:
python scripts/3-level-flow.py --summary --verbose

# Look for:
# - Which policy failed
# - Error messages
# - Missing output files

# Fix the root cause, then re-run pre-flight
```

### Dashboard Not Loading Data?

```bash
# Check dashboard logs:
tail -50 /tmp/claude_insight.log

# Verify database:
sqlite3 instance/claude_insight.db ".tables"

# Check API:
curl http://localhost:5000/api/sessions | jq .

# If no data: Dashboard might not be reading latest files
# Check: ~/.claude/memory/logs/ directory permissions
```

### Computer Use Test Failed?

```bash
# Check screenshots:
ls -la ~/.claude/memory/logs/computer-use-tests/screenshot_*.png

# If no screenshots:
# - Dashboard might not be responsive
# - Computer Use tool might not have permissions
# - Firefox/browser might be required

# Check test report:
cat ~/.claude/memory/logs/computer-use-tests/test-report.json | jq '.results[0].error'
```

---

## ✅ Success Criteria

**ALL of these must be true:**

1. ✅ Pre-flight verification passes (all 5 checks)
2. ✅ Dashboard loads and displays data
3. ✅ Computer Use tests complete (4 scenarios)
4. ✅ 50+ screenshots captured
5. ✅ All UI state transitions correct
6. ✅ test-report.json shows all PASSED
7. ✅ No errors in screenshots or logs

---

## 📊 Complete Testing Chain Checklist

```
User Input (Prompt)                    [Status]
    ↓
3-Level Flow Executes 25 Policies      [ Run: python scripts/3-level-flow.py --summary ]
    ↓
Output Files Created                   [ Check: verify-computer-use-prerequisites.py ]
    ├─ flow-trace.json                 [ ✅ ]
    ├─ policy-hits.log                 [ ✅ ]
    ├─ session-progress.json           [ ✅ ]
    └─ task-breakdown flags            [ ✅ ]
    ↓
Dashboard Loads Data                   [ Check: curl http://localhost:5000/api/sessions ]
    ├─ Sessions endpoint               [ ✅ ]
    ├─ Flow history endpoint           [ ✅ ]
    ├─ Tasks endpoint                  [ ✅ ]
    └─ Policies endpoint               [ ✅ ]
    ↓
Flask UI Renders Correctly             [ Check: Browser at http://localhost:5000 ]
    ├─ All sections visible            [ ✅ ]
    ├─ Data current (fresh)            [ ✅ ]
    ├─ No console errors               [ ✅ ]
    └─ Interactive elements work       [ ✅ ]
    ↓
Computer Use Tests Run                 [ Run: python scripts/agents/computer-use-agent.py --run-tests ]
    ├─ Dashboard Login                 [ ✅ PASSED ]
    ├─ Task Breakdown Flow             [ ✅ PASSED ]
    ├─ Task Closure Workflow           [ ✅ PASSED ]
    └─ 3-Level Flow Execution          [ ✅ PASSED ]
    ↓
Test Report Generated                  [ Check: ~/.claude/memory/logs/computer-use-tests/ ]
    ├─ 100+ Screenshots                [ ✅ ]
    ├─ test-report.json               [ ✅ ]
    ├─ test-report.md                 [ ✅ ]
    └─ demo-video.gif                 [ ✅ ]
    ↓
TESTING COMPLETE ✅
```

---

## 🔑 Key Rules

1. **DO NOT skip pre-flight checks** - They exist because testing fails without them
2. **Dashboard must be running** - Computer Use can't interact with non-existent UI
3. **Data must be fresh** - If tests see old data, results will be wrong
4. **All 25 policies must PASS** - If any fail, Computer Use can't verify UI
5. **Files must exist** - Dashboard reads from disk, so files must be saved there

---

## Summary

**The chain is:**
```
Policy Execution → Output Files → Dashboard Reads → UI Renders → Computer Use Tests
      ↓                ↓              ↓                  ↓              ↓
    CRITICAL      CRITICAL        CRITICAL          CRITICAL       CANNOT START

If ANY link breaks, the entire chain fails!
```

So verify EVERYTHING before running Computer Use tests! 🔗

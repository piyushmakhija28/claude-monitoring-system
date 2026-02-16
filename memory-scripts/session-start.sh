#!/bin/bash
################################################################################
# SESSION START SCRIPT - WITH BLOCKING ENFORCEMENT
#
# CRITICAL: This script MUST be run at the start of EVERY conversation.
# It initializes the blocking policy enforcer and validates all daemons.
#
# Version: 2.0.0 (Blocking Enforcement)
# Date: 2026-02-16
################################################################################

echo ""
echo "================================================================================"
echo "🚨 SESSION START - INITIALIZING BLOCKING POLICY ENFORCEMENT"
echo "================================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

MEMORY_PATH="$HOME/.claude/memory"

# ============================================================================
# STEP 1: Initialize Blocking Enforcer
# ============================================================================
echo "${BLUE}[1/5] Initializing Blocking Policy Enforcer...${NC}"

python3 "$MEMORY_PATH/blocking-policy-enforcer.py" --mark-session-started
if [ $? -eq 0 ]; then
    echo "${GREEN}✅ Blocking enforcer initialized${NC}"
    echo "${GREEN}   Session marked as started${NC}"
else
    echo "${RED}❌ Failed to initialize blocking enforcer${NC}"
    exit 1
fi

# ============================================================================
# STEP 2: Start Auto-Recommendation Daemon (9th Daemon)
# ============================================================================
echo ""
echo "${BLUE}[2/5] Starting Auto-Recommendation Daemon (9th daemon)...${NC}"

# Check if already running
PID_FILE="$MEMORY_PATH/.pids/auto-recommendation-daemon.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "${GREEN}✅ Daemon already running (PID: $PID)${NC}"
    else
        echo "${YELLOW}⚠️  Stale PID file found, starting daemon...${NC}"
        rm -f "$PID_FILE"
        # Start daemon (example - adjust to your actual daemon)
        # nohup python3 "$MEMORY_PATH/auto-recommendation-daemon.py" start > /dev/null 2>&1 &
        echo "${YELLOW}⚠️  Daemon script not found (auto-recommendation-daemon.py)${NC}"
    fi
else
    echo "${YELLOW}⚠️  Daemon not running, would start here${NC}"
    # nohup python3 "$MEMORY_PATH/auto-recommendation-daemon.py" start > /dev/null 2>&1 &
fi

# ============================================================================
# STEP 3: Check All 9 Daemon PIDs and Status
# ============================================================================
echo ""
echo "${BLUE}[3/5] Checking all 9 daemon statuses...${NC}"

DAEMONS=(
    "context-daemon"
    "session-auto-save-daemon"
    "preference-auto-tracker"
    "skill-auto-suggester"
    "commit-daemon"
    "session-pruning-daemon"
    "pattern-detection-daemon"
    "failure-prevention-daemon"
    "auto-recommendation-daemon"
)

RUNNING=0
STOPPED=0

for daemon in "${DAEMONS[@]}"; do
    PID_FILE="$MEMORY_PATH/.pids/${daemon}.pid"
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "${GREEN}   ✅ ${daemon}: Running (PID: $PID)${NC}"
            ((RUNNING++))
        else
            echo "${RED}   ❌ ${daemon}: Stopped (stale PID)${NC}"
            ((STOPPED++))
        fi
    else
        echo "${RED}   ❌ ${daemon}: Not running${NC}"
        ((STOPPED++))
    fi
done

echo ""
echo "${GREEN}   Running: $RUNNING / 9${NC}"
echo "${RED}   Stopped: $STOPPED / 9${NC}"

# ============================================================================
# STEP 4: Show Latest Recommendations
# ============================================================================
echo ""
echo "${BLUE}[4/5] Loading latest recommendations...${NC}"

RECOMMENDATIONS_FILE="$MEMORY_PATH/.last-automation-check.json"
if [ -f "$RECOMMENDATIONS_FILE" ]; then
    echo "${GREEN}✅ Recommendations found:${NC}"

    # Extract recommendations using Python
    python3 - <<EOF
import json
try:
    with open('$RECOMMENDATIONS_FILE', 'r') as f:
        data = json.load(f)

    print("   Model: ${GREEN}" + data.get('recommended_model', 'N/A') + "${NC}")
    print("   Skills: ${GREEN}" + ', '.join(data.get('recommended_skills', [])) + "${NC}")
    print("   Agents: ${GREEN}" + ', '.join(data.get('recommended_agents', [])) + "${NC}")
except:
    print("   ${YELLOW}Could not parse recommendations${NC}")
EOF
else
    echo "${YELLOW}⚠️  No recommendations file found${NC}"
    echo "   Run: python ~/.claude/memory/session-start-check.py"
fi

# ============================================================================
# STEP 5: Show Context Status
# ============================================================================
echo ""
echo "${BLUE}[5/5] Checking context status...${NC}"

# Check context (if context monitor exists)
if [ -f "$MEMORY_PATH/context-monitor-v2.py" ]; then
    python3 "$MEMORY_PATH/context-monitor-v2.py" --current-status 2>/dev/null || {
        echo "${YELLOW}⚠️  Context monitor not available${NC}"
    }

    # Mark context as checked in blocking enforcer
    python3 "$MEMORY_PATH/blocking-policy-enforcer.py" --mark-context-checked
else
    echo "${YELLOW}⚠️  Context monitor not found${NC}"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
echo "================================================================================"
echo "${GREEN}✅ SESSION INITIALIZATION COMPLETE${NC}"
echo "================================================================================"
echo ""
echo "${BLUE}📋 Next Steps:${NC}"
echo "   1. ${GREEN}✅ Session started${NC} - Blocking enforcer active"
echo "   2. ${YELLOW}⏳ Load standards${NC} - Run: python ~/.claude/memory/standards-loader.py --load-all"
echo "   3. ${YELLOW}⏳ For each request:${NC}"
echo "      - Generate prompt (Step 0)"
echo "      - Create tasks (Step 1)"
echo "      - Decide plan mode (Step 2)"
echo "      - Select model (Step 4)"
echo "      - Check skills/agents (Step 5)"
echo ""
echo "${RED}🚨 WARNING: All steps are BLOCKING - work cannot proceed if skipped!${NC}"
echo ""
echo "================================================================================"
echo ""

# Show enforcer status
echo "${BLUE}📊 Blocking Enforcer Status:${NC}"
python3 "$MEMORY_PATH/blocking-policy-enforcer.py" --status

exit 0

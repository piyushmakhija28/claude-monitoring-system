# Claude Code Plan Detection System

**Version:** 1.0.0
**Status:** 🟢 Active
**Auto-Run:** Session Start

---

## 🎯 Purpose

Automatically detects and displays which Claude Code subscription plan is active for the user.

---

## 📋 Detected Plans

| Plan | Icon | Features |
|------|------|----------|
| **Free** | 🆓 | Basic features, limited usage |
| **Pro** | ⭐ | Full features, extended context, background tasks |
| **Team** | 👥 | Pro + team collaboration, shared workspaces |
| **Enterprise** | 🏢 | All features, SLA, custom deployment |

---

## 🔍 Detection Methods

The system detects plans by analyzing:

1. **Config Files**
   - `~/.claude/config.json`
   - Feature flags
   - Plan indicators

2. **Available Features**
   - Background task support
   - Team collaboration tools
   - Enterprise deployment options

3. **Context Limits**
   - Token limits
   - Request quotas
   - API restrictions

4. **Cache System**
   - 24-hour cache validity
   - Auto-refresh when stale

---

## 🚀 Usage

### Automatic (Session Start)

Plan is automatically detected and shown when you start a Claude Code session.

### Manual Detection

```bash
# Full display
bash ~/.claude/memory/scripts/plan-detector.sh

# Summary only
bash ~/.claude/memory/scripts/plan-detector.sh --summary

# JSON output
bash ~/.claude/memory/scripts/plan-detector.sh --json
```

### Python API

```python
from plan_detector import PlanDetector

detector = PlanDetector()
plan_info = detector.detect_plan()
detector.display_plan_info(plan_info)
```

---

## 📊 Output Format

### Full Display

```
================================================================================
📋 CLAUDE CODE SUBSCRIPTION PLAN
================================================================================

🎯 Active Plan: ⭐ Pro Plan
📅 Detected: 2026-02-16
✅ Status: ACTIVE

📦 Features:
   ✓ Full features
   ✓ Priority support
   ✓ Extended context
   ✓ Background tasks

⚙️ Limits:
   • Max Context: 200K tokens
   • Max Requests: Unlimited

================================================================================
```

### Summary (for Session Start)

```
⭐ Pro Plan | Limits: 200K tokens
```

---

## 🔄 Integration Points

### 1. Session Start Script

Auto-integrated into `session-start.sh`:

```bash
# Show active plan
echo "📋 Checking Claude Code plan..."
bash ~/.claude/memory/scripts/plan-detector.sh --summary
```

### 2. Dashboard

Shown in `dashboard.sh` health check:

```bash
PLAN_INFO=$(bash ~/.claude/memory/scripts/plan-detector.sh --summary)
echo "Active Plan: $PLAN_INFO"
```

### 3. Context Monitor

Used to adjust context thresholds based on plan:

```python
plan_info = detector.detect_plan()
if plan_info['type'] == 'free':
    max_context = 100000  # 100K for free
elif plan_info['type'] in ['pro', 'team', 'enterprise']:
    max_context = 200000  # 200K for paid plans
```

---

## 💾 Cache System

**Location:** `~/.claude/memory/.plan-cache.json`

**Structure:**
```json
{
  "type": "pro",
  "name": "⭐ Pro Plan",
  "features": ["..."],
  "limits": {"..."},
  "detected_at": "2026-02-16T10:30:00",
  "status": "active"
}
```

**Validity:** 24 hours
**Auto-Refresh:** When cache expires or on manual request

---

## 🎯 Plan-Specific Optimizations

The system can automatically adjust behavior based on detected plan:

| Plan | Context Limit | Optimization Strategy |
|------|---------------|----------------------|
| Free | 100K tokens | Aggressive caching, strict limits |
| Pro | 200K tokens | Balanced approach |
| Team | 200K tokens | Collaboration-optimized |
| Enterprise | Custom | Full features unlocked |

---

## 🔧 Configuration

### Enable/Disable

```bash
# Disable plan detection
echo '{"plan_detection": {"enabled": false}}' > ~/.claude/memory/config/plan-detector.json

# Enable plan detection
echo '{"plan_detection": {"enabled": true}}' > ~/.claude/memory/config/plan-detector.json
```

### Custom Cache Duration

```python
# In plan-detector.py
def _is_cache_valid(self, cached_plan, max_age_hours=24):  # Change 24 to desired hours
```

---

## 🐛 Troubleshooting

### Plan Not Detected

```bash
# Clear cache and re-detect
rm ~/.claude/memory/.plan-cache.json
bash ~/.claude/memory/scripts/plan-detector.sh
```

### Wrong Plan Shown

1. Check `~/.claude/config.json` for feature flags
2. Clear cache: `rm ~/.claude/memory/.plan-cache.json`
3. Re-run detection: `bash ~/.claude/memory/scripts/plan-detector.sh`

### Python Not Found

```bash
# Install Python 3
# Windows: Download from python.org
# Linux/Mac: sudo apt install python3 or brew install python3
```

---

## 📈 Future Enhancements

- [ ] Real-time plan upgrade detection
- [ ] Usage statistics based on plan
- [ ] Automatic feature unlocking
- [ ] Plan expiration warnings
- [ ] Multi-user plan management

---

## 🔗 Related Systems

- **Context Monitor:** Uses plan info for context limits
- **Session Start:** Shows plan on startup
- **Dashboard:** Displays plan in health check
- **Auto-Recommendation:** Adjusts based on plan features

---

**Created:** 2026-02-16
**Author:** Claude Sonnet 4.5
**Maintainer:** Memory System

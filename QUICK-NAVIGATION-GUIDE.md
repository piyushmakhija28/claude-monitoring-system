# Quick Navigation Guide

**Claude Memory System v2.0 - Reorganized Structure**

---

## 📁 Where to Find Things

### 🔍 Need to Find a File? Use This Guide

#### Looking for Documentation?
**Go to:** `docs/`

- **Getting Started?** → `docs/guides/QUICKSTART.md`
- **Need Help?** → `docs/guides/TROUBLESHOOTING-V2.md`
- **Learning the System?** → `docs/guides/HOW-IT-WORKS.md`
- **Spring Boot/Java Info?** → `docs/architecture/`
- **Coding Standards?** → `docs/standards/`
- **Performance Tips?** → `docs/optimization/`
- **API Reference?** → `docs/reference/API-REFERENCE.md`

#### Looking for a Script?
**Go to:** `scripts/`

| What You Need | Where to Look |
|---------------|---------------|
| Start/stop daemons | `scripts/daemons/` |
| System monitoring | `scripts/monitors/` |
| Auto-commit, auto-save | `scripts/automation/` |
| Preference tracking | `scripts/trackers/` |
| Daemon manager | `scripts/management/daemon-manager.py` |
| Session management | `scripts/management/session-state.py` |
| Health checks | `scripts/maintenance/daily-health-check.sh` |
| Failure prevention | `scripts/failure-learning/` |
| Utilities/dashboard | `scripts/utils/dashboard.sh` |

#### Looking for Policies?
**Go to:** `policies/`

- All `.md` policy files are here
- Core skills, model selection, failure prevention, etc.

#### Looking for Config Files?
**Go to:** `config/`

- All `.json` configuration files are here
- Preferences, patterns, failure knowledge base, etc.

#### Looking for Historical Info?
**Go to:** `archive/`

- **Phase completions?** → `archive/completion-summaries/`
- **Migration docs?** → `archive/migration/`

---

## 🚀 Common Tasks - Quick Commands

### System Management

```bash
# Start daemons
bash scripts/management/startup-hook.sh

# Check daemon status
python scripts/management/daemon-manager.py --status-all

# View dashboard
bash scripts/utils/dashboard.sh

# Session start check
bash scripts/management/session-start.sh
```

### Monitoring

```bash
# Check context usage
python scripts/monitors/context-monitor-v2.py --current-status

# Monitor model selection
python scripts/monitors/model-selection-monitor.py

# View logs
python scripts/monitors/daemon-logger.py
```

### Maintenance

```bash
# Daily health check
bash scripts/maintenance/daily-health-check.sh

# Weekly health check
bash scripts/maintenance/weekly-health-check.sh

# Verify system
bash scripts/maintenance/verify-system.sh

# Run all tests
python scripts/maintenance/test-all-phases.py
```

### Automation

```bash
# Trigger auto-commit
python scripts/automation/trigger-auto-commit.py

# Auto-save session
python scripts/automation/auto-save-session.py

# Detect skills
python scripts/automation/skill-detector.py
```

---

## 📂 Directory Structure at a Glance

```
claude-memory-system/
├── 📄 README.md                    # Start here
├── 📄 MASTER-README.md             # Complete reference
├── 📄 REORGANIZATION-REPORT.md     # This reorganization
│
├── 📁 docs/                        # ALL documentation
│   ├── guides/                     # How-to guides, quickstarts
│   ├── architecture/               # System architecture
│   ├── standards/                  # Coding standards
│   ├── optimization/               # Performance optimization
│   └── reference/                  # API & system reference
│
├── 📁 policies/                    # Policy documents
│
├── 📁 scripts/                     # ALL executable scripts
│   ├── daemons/                    # Background services
│   ├── monitors/                   # Monitoring tools
│   ├── automation/                 # Automated tasks
│   ├── trackers/                   # Tracking systems
│   ├── management/                 # System management
│   ├── maintenance/                # Maintenance tasks
│   ├── failure-learning/           # Failure prevention
│   └── utils/                      # Utilities
│
├── 📁 config/                      # Configuration files
│
└── 📁 archive/                     # Historical documents
    ├── completion-summaries/       # Phase completions
    └── migration/                  # Migration docs
```

---

## 🔧 Most Commonly Used Files

### Top 10 Files You'll Access Regularly

1. **`README.md`** - Project overview
2. **`docs/guides/QUICKSTART.md`** - Getting started
3. **`scripts/management/daemon-manager.py`** - Manage daemons
4. **`scripts/utils/dashboard.sh`** - System dashboard
5. **`scripts/monitors/context-monitor-v2.py`** - Context monitoring
6. **`scripts/management/session-state.py`** - Session management
7. **`config/consultation-preferences.json`** - User preferences
8. **`config/failure-kb.json`** - Failure knowledge base
9. **`policies/core-skills-mandate.md`** - Core skills policy
10. **`docs/guides/TROUBLESHOOTING-V2.md`** - Troubleshooting

---

## 🎯 Quick File Finder

### By File Type

```bash
# Find all Python scripts
find scripts/ -name "*.py"

# Find all shell scripts
find scripts/ -name "*.sh"

# Find all documentation
find docs/ -name "*.md"

# Find all policies
find policies/ -name "*.md"

# Find all configs
find config/ -name "*.json"
```

### By Purpose

```bash
# Find daemon-related files
find scripts/daemons/ -type f

# Find monitoring scripts
find scripts/monitors/ -type f

# Find automation scripts
find scripts/automation/ -type f

# Find maintenance scripts
find scripts/maintenance/ -type f
```

---

## 📝 File Naming Conventions

### Understand File Names at a Glance

| Pattern | Meaning | Example |
|---------|---------|---------|
| `*-daemon.py` | Background service | `context-daemon.py` |
| `*-monitor*.py` | Monitoring tool | `context-monitor-v2.py` |
| `*-tracker.py` | Tracking system | `consultation-tracker.py` |
| `auto-*.py` | Automation script | `auto-commit.py` |
| `*-manager.py` | Management tool | `daemon-manager.py` |
| `test-*.py` | Test script | `test-all-phases.py` |
| `verify-*.sh` | Verification script | `verify-system.sh` |
| `*-policy.md` | Policy document | `git-auto-commit-policy.md` |
| `*-standards.md` | Standards doc | `api-design-standards.md` |
| `*-QUICKSTART.md` | Quick start guide | `MEMORY-SYSTEM-QUICKSTART.md` |

---

## 🆘 Emergency Commands

If something breaks after reorganization:

```bash
# 1. Check daemon status
python scripts/management/daemon-manager.py --status-all

# 2. View recent logs
tail -f logs/policy-hits.log

# 3. Restart daemons
bash scripts/management/startup-hook.sh

# 4. Verify system
bash scripts/maintenance/verify-system.sh

# 5. Check health
bash scripts/maintenance/daily-health-check.sh
```

---

## 📚 Learn More

- **Full Documentation:** `MASTER-README.md`
- **Reorganization Details:** `REORGANIZATION-REPORT.md`
- **System Architecture:** `docs/reference/SYSTEM-V2-OVERVIEW.md`
- **Getting Started:** `docs/guides/QUICKSTART.md`
- **Troubleshooting:** `docs/guides/TROUBLESHOOTING-V2.md`

---

**Version:** 2.0
**Last Updated:** 2026-02-15
**Status:** ✅ Active

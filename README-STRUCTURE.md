# Claude Insight - Clean Structure

## What is Claude Insight?

**Claude Insight** is a monitoring dashboard for the Claude Memory System v2.8.0.

## Directory Structure

```
claude-insight/
├── README.md                       Main documentation
├── CLAUDE.md                       Setup & configuration
├── src/                            Dashboard backend (Python/Flask)
├── static/                         Dashboard frontend (JS/CSS)  
├── templates/                      Dashboard HTML templates
├── docs/                           Core memory system documentation
├── scripts/                        Core memory system scripts
├── policies/                       Core policies
│   ├── 01-sync-system/            Session & context management
│   ├── 02-standards-system/       Coding standards
│   └── 03-execution-system/       Execution policies
├── agents/                         Agent references (see claude-global-library)
├── skills/                         Skill references (see claude-global-library)
├── data/                           Runtime data
├── logs/                           Runtime logs
├── tests/                          Test files
└── config/                         Configuration files
```

## Companion Repository

**Actual skills and agents are maintained separately:**

📦 **Claude Global Library**
https://github.com/piyushmakhija28/claude-global-library

## Purpose

- **Monitoring Dashboard:** Real-time memory system metrics
- **Core System:** Session management, context optimization
- **Policy Enforcement:** Auto-fix, standards, execution flow

## Not Included

❌ Skills/Agents source code → See claude-global-library
❌ Project-specific code → Each project has own repos
❌ User configurations → In ~/.claude/ directory

# Contextual Recommendations Policy (Level 3, Step 3.8)

**Version:** 3.0.0
**Status:** Active
**Last Updated:** 2026-03-05

---

## Overview

Contextual Recommendations Policy provides intelligent, task-aware suggestions to optimize Claude's execution. It analyzes task complexity, detected technologies, and session context to recommend appropriate skills, agents, best practices, and optimizations.

**Location:** `policies/03-execution-system/07-recommendations/`
**Implementation:** `scripts/architecture/03-execution-system/07-recommendations/check-recommendations.py`

---

## Responsibilities

### 1. **Skill & Agent Recommendations**
- Suggest skills based on detected technology
- Recommend agents for task complexity levels
- Propose supplementary skills for multi-tech projects
- Alert when orchestrator-agent should coordinate

### 2. **Best Practices Recommendations**
- Suggest coding patterns for detected tech
- Recommend performance optimizations
- Propose security best practices
- Advise on testing strategies

### 3. **Optimization Recommendations**
- Suggest tool usage optimizations
- Recommend context-saving techniques
- Propose parallelization opportunities
- Advise on file structure improvements

### 4. **Technology-Specific Guidance**
- Provide framework-specific tips (Flask, Django, FastAPI)
- Offer architecture suggestions (microservices, monolithic)
- Recommend database design patterns
- Suggest deployment strategies

### 5. **Complexity-Based Recommendations**
- Simple tasks: Focus on speed & directness
- Medium tasks: Balance quality & speed
- Complex tasks: Emphasize architecture & planning
- Very complex: Recommend orchestrator-agent coordination

---

## Recommendation Categories

### **Category 1: Skill Recommendations**
```
Trigger: Tech detected in task
Output:
  - Primary skill for current file type
  - Supplementary skills for other techs in task
  - Confidence score (0-100%)
  - Reasoning (why this skill)

Example:
  Tech: spring-boot detected
  Skill: java-spring-boot-microservices (100%)
  Supplementary: [rdbms-core, docker] (from tech_stack)
  Reason: Spring Boot is core, plus PostgreSQL + Docker in task
```

### **Category 2: Agent Recommendations**
```
Trigger: Multi-domain task detected
Output:
  - Primary agent (orchestrator if 2+ domains)
  - Domain agents (supplementary)
  - Coordination strategy
  - Why orchestrator

Example:
  Domains: [backend, frontend, devops]
  Primary: orchestrator-agent (coordinates 3 domains)
  Agents: [java-spring-boot-microservices, angular-engineer, devops-engineer]
  Reason: 3 distinct domains require coordination
```

### **Category 3: Pattern Recommendations**
```
Trigger: Task type detected
Output:
  - Common patterns for this task type
  - Anti-patterns to avoid
  - Recommended file structure
  - Typical tools/libraries

Example:
  Task: REST API with JWT auth
  Patterns:
    ✓ Use service layer for business logic
    ✓ Validate all external input
    ✓ Return consistent error formats
  Anti-patterns:
    ✗ Logic in controller/route layer
    ✗ Direct database access in handlers
```

### **Category 4: Performance Recommendations**
```
Trigger: Complexity > 15
Output:
  - Caching opportunities
  - Query optimization tips
  - Parallel processing suggestions
  - Context window management

Example:
  - Use database indexes on frequently queried fields
  - Implement pagination for large result sets
  - Cache authentication tokens
  - Batch database operations
```

### **Category 5: Testing Recommendations**
```
Trigger: Task involves data persistence
Output:
  - Unit test suggestions
  - Integration test ideas
  - Mock strategies
  - Coverage targets

Example:
  - Test service layer with mocked database
  - Test API endpoints with integration tests
  - Mock external API calls
  - Target 80%+ code coverage
```

---

## Execution Flow

```
Task Detected
    ↓
Step 3.8: Recommendations Policy
    │
    ├─ Skill Detector
    │  ├─ Analyze tech_stack
    │  ├─ Match to skills
    │  └─ Generate recommendations
    │
    ├─ Agent Suggester
    │  ├─ Check domain count
    │  ├─ Recommend orchestration
    │  └─ List supplementary agents
    │
    ├─ Pattern Matcher
    │  ├─ Analyze task_type
    │  ├─ Match code patterns
    │  └─ Suggest best practices
    │
    └─ Performance Advisor
       ├─ Analyze complexity
       ├─ Suggest optimizations
       └─ Recommend tools
    ↓
Output: Recommendation Hints
    └─ Printed to stdout (non-blocking)
```

---

## Helper Scripts

| Script | Purpose |
|--------|---------|
| `check-recommendations.py` | Main recommendation engine |
| `skill-auto-suggester.py` | Auto-generate skill recommendations |
| `skill-detector.py` | Detect skills from task context |

---

## Recommendation Triggers

### **Trigger 1: Technology Detected**
```
When: Tech detected in user message
What: Skill recommendations
Where: checkpoint + per-file hints
Example: "Spring Boot API" → java-spring-boot-microservices
```

### **Trigger 2: Multi-Domain Task**
```
When: 2+ domains detected
What: Orchestrator-agent recommendation
Where: Checkpoint display
Example: "Backend + Frontend + Docker" → orchestrator-agent
```

### **Trigger 3: High Complexity**
```
When: Complexity >= 15
What: Plan mode + detailed recommendations
Where: Checkpoint + session info
Example: "Implement complete system" → Use plan mode
```

### **Trigger 4: Specific File Types**
```
When: Reading/writing specific file type
What: File-specific best practices
Where: Skill context hints
Example: ".py file" → Python patterns, Flask patterns
```

### **Trigger 5: Task Type Classification**
```
When: Task type determined (API, UI, DB, DevOps)
What: Task-type-specific recommendations
Where: Checkpoint, file hints
Example: "API task" → REST patterns, testing tips
```

---

## Recommendation Format

### **To Checkpoint (Session Start):**
```
╔═══════════════════════════════════════════════════════╗
║  RECOMMENDATIONS                                      ║
├───────────────────────────────────────────────────────┤
║  Primary Skill: java-spring-boot-microservices       ║
║  Secondary Skills: rdbms-core, docker                ║
║  Pattern Guidance: Use service layer pattern         ║
║  Performance Tips: Implement database indexing       ║
╚═══════════════════════════════════════════════════════╝
```

### **To File Hints (Per-Tool):**
```
[RECOMMENDATIONS] UserController.java
  - Use Spring Bean Injection for services
  - Validate request DTOs before processing
  - Return consistent error responses
  - Add @Transactional where needed
  - Unit test service layer thoroughly
```

### **To Progress Tracking (Per-Step):**
```json
{
  "step": "Step 3.8 - Recommendations",
  "recommendations": [
    {
      "category": "Skill",
      "priority": "HIGH",
      "text": "Use java-spring-boot-microservices pattern"
    },
    {
      "category": "Performance",
      "priority": "MEDIUM",
      "text": "Implement connection pooling for database"
    },
    {
      "category": "Testing",
      "priority": "MEDIUM",
      "text": "Test service layer with mocked database"
    }
  ]
}
```

---

## Recommendation Levels

### **LEVEL 1: CRITICAL (Always Show)**
- Must-do security practices
- Required error handling patterns
- Mandatory validation points
- Essential architecture patterns

### **LEVEL 2: IMPORTANT (Show by Default)**
- Recommended optimization techniques
- Suggested code patterns
- Proposed testing strategies
- Advisable best practices

### **LEVEL 3: NICE-TO-HAVE (Show on Request)**
- Performance tips
- Code style suggestions
- Alternative approaches
- Enhancement ideas

---

## Integration with Other Policies

### **Receives From:**
- **Task Breakdown (3.1):** Task type, complexity, entities
- **Model Selection (3.4):** Model selected (impacts depth)
- **Skill Selection (3.5):** Tech stack, skill selected
- **Tool Optimization (3.6):** Suggests complementary optimizations

### **Provides To:**
- **Checkpoint Display:** Shows in session summary
- **File-Level Hints:** Added to SKILL-CONTEXT hints
- **Progress Tracking:** Recommendations logged
- **Session Summary:** Included in final report

---

## Configuration

```python
# Recommendation Thresholds
SHOW_SKILL_RECOMMENDATIONS = True
SHOW_PATTERN_RECOMMENDATIONS = True
SHOW_PERFORMANCE_RECOMMENDATIONS = True
SHOW_TESTING_RECOMMENDATIONS = True

# Confidence Thresholds
MIN_SKILL_CONFIDENCE = 70      # Only show if 70%+ confident
MIN_PATTERN_CONFIDENCE = 60    # Patterns: 60%+ confident
MIN_OPTIMIZATION_CONFIDENCE = 50  # Performance: 50%+ confident

# Complexity-Based
COMPLEX_THRESHOLD = 15  # Complex tasks get more recommendations
SIMPLE_THRESHOLD = 5    # Simple tasks get basic recommendations

# Frequency
MAX_RECOMMENDATIONS_PER_FILE = 5
MAX_RECOMMENDATIONS_PER_SESSION = 30
SHOW_EVERY_N_TOOLS = 1  # Show recommendations for every tool
```

---

## Success Criteria

- ✅ Skill recommendations match detected tech (95%+ accuracy)
- ✅ Orchestrator recommended when 2+ domains present
- ✅ Recommendations improve code quality
- ✅ Non-blocking (always allow tool execution)
- ✅ Helpful without being overwhelming
- ✅ Logged for analysis and improvement
- ✅ Respect user preferences for verbosity
- ✅ Never recommend conflicting patterns

---

## Example Recommendations by Tech Stack

### **Spring Boot + PostgreSQL + Docker**
```
Skills: java-spring-boot-microservices, rdbms-core, docker
Patterns:
  - Use JPA/Hibernate for database access
  - Implement @Transactional for transactions
  - Use Docker multi-stage builds
  - Implement connection pooling

Testing:
  - Unit test services with mocked repositories
  - Integration test with TestContainers for DB
  - Test Docker image builds and runs
```

### **Angular + TypeScript + FastAPI**
```
Skills: angular-engineer, python-backend-engineer
Patterns:
  - Use Angular dependency injection
  - Implement RxJS observables for async
  - Use FastAPI Pydantic models for validation
  - Implement async/await in Python handlers

Testing:
  - Unit test Angular components
  - E2E test with Cypress
  - Test FastAPI endpoints with pytest
```

### **Python + PostgreSQL + Docker + Kubernetes**
```
Agent: orchestrator-agent (coordinates 3 domains)
Skills: python-backend-engineer, rdbms-core, docker, kubernetes
Patterns:
  - Use Flask/Django blueprints for modular code
  - Implement SQLAlchemy for ORM
  - Use Docker best practices (layers, caching)
  - Implement Kubernetes health checks

Performance:
  - Implement connection pooling
  - Cache frequently accessed data (Redis)
  - Optimize database queries with indexes
```

---

## Feedback Loop

Recommendations are logged and analyzed to:
- Track recommendation accuracy
- Identify commonly followed suggestions
- Detect patterns in task complexity
- Improve recommendation algorithms
- Adapt to user preferences

---

## Related Policies

- **Task Breakdown (3.1):** Provides task context
- **Skill Selection (3.5):** Provides tech stack info
- **Tool Optimization (3.6):** Provides optimization context
- **Progress Tracking (3.9):** Logs recommendation usage
- **Testing Policy:** Testing recommendations

---

**Policy Status:** ✅ ACTIVE
**Last Verified:** 2026-03-05
**Next Review:** 2026-04-05

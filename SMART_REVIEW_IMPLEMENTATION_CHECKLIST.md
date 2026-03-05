# Smart Code Review - Implementation Checklist

**Feature:** Session-Aware + Skill-Aware PR Review Before Auto-Merge
**Status:** Ready for Implementation (Design Complete)
**Effort:** 2-3 days
**Complexity:** HIGH

---

## Phase 1: Core Review Engine (Priority 1)

### Task 1.1: Create `github-smart-pr-reviewer.py`
**File Location:** `scripts/architecture/03-execution-system/09-git-commit/github-smart-pr-reviewer.py`

**Classes to Implement:**
- [ ] `SmartPRReviewer` (main class)
  - [ ] `__init__(session_id, pr_number)`
  - [ ] `execute_smart_review()` - Main entry point
  - [ ] `load_session_context()` - Load summary + issues + flow-trace
  - [ ] `get_changed_files()` - Get git diff
  - [ ] `review_file(file_path)` - Review single file
  - [ ] `determine_skill(file_path)` - File → Skill mapping
  - [ ] `_review_against_skill()` - Apply skill patterns
  - [ ] `post_review_comment()` - Post findings on PR
  - [ ] `get_review_status()` - Determine auto-merge safety
  - [ ] Helper methods:
    - [ ] `_load_json(filename)`
    - [ ] `_fetch_github_issues()`
    - [ ] `_run_git_diff()`
    - [ ] `_read_file(file_path)`

**Expected Output:**
```python
class SmartPRReviewer:
    def execute_smart_review(self):
        """Returns: {'status': 'all_passed'|'warnings'|'critical_issues', 'findings': {...}}"""
        pass
```

**Lines of Code:** ~800-1000

---

### Task 1.2: Create `skill-review-patterns.py`
**File Location:** `scripts/architecture/03-execution-system/09-git-commit/skill-review-patterns.py`

**Data Structure:**
```python
SKILL_PATTERNS = {
    'java-spring-boot-microservices': {
        'name': 'Spring Boot Microservices',
        'file_types': ['.java', 'pom.xml', 'application.yml'],
        'required_patterns': [
            {'pattern': '@SpringBootApplication', 'files': ['*.java'], 'severity': 'critical'},
            {'pattern': '@RestController', 'files': ['*Controller.java'], 'severity': 'critical'},
            # ... 10+ patterns
        ],
        'optional_patterns': [
            {'pattern': '@Cacheable', 'reason': 'Performance optimization'},
            # ... 5+ patterns
        ],
        'anti_patterns': [
            {'pattern': 'connection.createStatement()', 'reason': 'Use ORM instead'},
            # ... 3+ patterns
        ],
        'checks': [
            'has_service_layer',
            'uses_dependency_injection',
            'has_error_handling',
            'follows_naming_conventions'
        ]
    },
    'angular-engineer': {
        'name': 'Angular Framework',
        'file_types': ['.ts', '.html', '.scss'],
        'required_patterns': [
            {'pattern': '@Component', 'files': ['*.component.ts'], 'severity': 'critical'},
            # ... patterns
        ],
        # ...
    },
    # ... 20+ more skills
}
```

**Patterns to Define (20+ skills):**
- [ ] java-spring-boot-microservices
- [ ] angular-engineer
- [ ] python-backend-engineer
- [ ] python-system-scripting
- [ ] ui-ux-designer
- [ ] css-core
- [ ] docker
- [ ] kubernetes
- [ ] rdbms-core
- [ ] nosql-core
- [ ] java-design-patterns-core
- [ ] spring-boot-design-patterns-core
- [ ] devops-engineer
- [ ] devops-automation-engineer
- [ ] qa-testing-agent
- [ ] swiftui-designer
- [ ] swift-backend-engineer
- [ ] android-backend-engineer
- [ ] android-ui-designer
- [ ] jenkins-pipeline
- [ ] dynamic-seo-agent
- [ ] static-seo-agent

**Lines of Code:** ~1500-2000

---

## Phase 2: Integration with GitHub Workflow

### Task 2.1: Update `github-branch-pr-policy.py`
**File:** `scripts/architecture/03-execution-system/github-branch-pr-policy.py`

**Changes Required:**
- [ ] Import `SmartPRReviewer` from `github-smart-pr-reviewer.py`
- [ ] Update merge workflow in `enforce()` function
  - [ ] Before: `create_pr() → post_review() → merge_pr()`
  - [ ] After: `create_pr() → smart_review() → post_findings() → merge_pr()`
- [ ] Add function: `smart_code_review(pr_number)`
  - [ ] Create reviewer instance
  - [ ] Execute smart review
  - [ ] Return status
- [ ] Add function: `should_auto_merge(review_status)`
  - [ ] Check if all_passed or warnings
  - [ ] Return True/False
- [ ] Update `enforce()` to call smart review
  - [ ] Before auto-merge, call `smart_code_review()`
  - [ ] Check `should_auto_merge()`
  - [ ] Only merge if True
- [ ] Add logging for review process
- [ ] Add error handling for review failures

**Key Changes:**
```python
# Old code:
pr_result = create_pr(...)
post_review_comment(pr_result['pr_number'])
merge_result = auto_merge_pr(pr_result['pr_number'])

# New code:
pr_result = create_pr(...)
review_status = smart_code_review(pr_result['pr_number'])
if should_auto_merge(review_status):
    merge_result = auto_merge_pr(pr_result['pr_number'])
else:
    post_needs_fix_comment(pr_result['pr_number'], review_status)
```

---

### Task 2.2: Update `stop-notifier.py`
**File:** `scripts/stop-notifier.py`

**Changes Required:**
- [ ] Update call to `github_pr_workflow.py`
- [ ] Pass session_id to PR workflow
- [ ] Handle review status in response
- [ ] Log review results to session summary

**Note:** Stop-notifier calls github_pr_workflow, which will now include smart review

---

## Phase 3: Session Context Loading

### Task 3.1: Verify Session Summary Structure
**File:** `~/.claude/memory/logs/sessions/{SESSION_ID}/session-summary.json`

**Required Fields in Session Summary:**
- [ ] `session_id`
- [ ] `task_description`
- [ ] `tech_stack` (array of techs)
- [ ] `skills_used` (array of skills)
- [ ] `agents_used` (array of agents)
- [ ] `files_modified` (array of file paths)
- [ ] `github_issues` (array of issue numbers)

**Verification:**
- [ ] Read actual session-summary.json file
- [ ] Confirm all fields present
- [ ] If missing, update session-summary-generator.py

---

### Task 3.2: Verify Flow-Trace Structure
**File:** `~/.claude/memory/logs/sessions/{SESSION_ID}/flow-trace.json`

**Required Fields in Flow-Trace:**
- [ ] `session_id`
- [ ] `skill` (primary skill used)
- [ ] `agent` (primary agent used)
- [ ] `tech_stack` (array of technologies)
- [ ] `supplementary_skills` (array of skills)

**Verification:**
- [ ] Read actual flow-trace.json file
- [ ] Confirm all fields present
- [ ] If missing, update flow-trace creation

---

## Phase 4: File-to-Skill Mapping

### Task 4.1: Build `FILE_TO_SKILL_MAP`
**In:** `skill-review-patterns.py`

**File Extensions to Map:**
- [ ] `.java` → java-spring-boot-microservices
- [ ] `.ts` → angular-engineer (with context)
- [ ] `.tsx` → ui-ux-designer (React)
- [ ] `.html` → ui-ux-designer
- [ ] `.scss` / `.css` → css-core
- [ ] `.py` → python-backend-engineer (with context: flask/django/fastapi)
- [ ] `.sql` → rdbms-core
- [ ] `Dockerfile` → docker
- [ ] `.yaml` → docker/kubernetes (determine by content)
- [ ] `pom.xml` → java-spring-boot-microservices
- [ ] `package.json` → angular-engineer (or ui-ux-designer)
- [ ] `*Test.java` → java-spring-boot-microservices
- [ ] `*.test.ts` → angular-engineer
- [ ] `*.spec.ts` → angular-engineer
- [ ] `Jenkinsfile` → jenkins-pipeline
- [ ] `k8s-*.yaml` → kubernetes
- [ ] `docker-compose.yml` → docker

**Context Keywords for Each Tech:**
- [ ] Spring Boot: `@SpringBootApplication`, `@RestController`, `@Service`, `spring`
- [ ] Angular: `@Component`, `@NgModule`, `@Injectable`, `rxjs`, `observable`
- [ ] React: `useState`, `useEffect`, `jsx`, `tsx`
- [ ] Python: `def`, `async def`, `@app.route`, `@app.get`
- [ ] Flask: `@app.route`, `Flask(__name__)`
- [ ] Django: `from django`, `models.Model`, `views`
- [ ] FastAPI: `@app.get`, `@app.post`, `Pydantic`

---

## Phase 5: Review Comment Template

### Task 5.1: Implement Review Comment Generator
**In:** `github-smart-pr-reviewer.py`

**Function:** `_build_review_comment(findings)`

**Template:**
```markdown
## 🔍 Smart Code Review (Session-Aware Context)

### 📋 Review Context
- Session: {session_id}
- Task: {task_description}
- Tech Stack: {tech_stack}
- Skills: {skills_used}

### 📁 Files Reviewed: {count}
[For each file]:
- {filename} - {skill} - {status}
  - {findings}

### 📊 Summary
- Critical Issues: {count}
- Warnings: {count}
- Compliance: {percent}%

### Status
[APPROVED for auto-merge] OR [NEEDS FIX]
```

---

## Phase 6: Testing

### Task 6.1: Unit Tests
**File:** `tests/test_smart_pr_reviewer.py`

Tests to Write:
- [ ] Test `determine_skill()` for .java files
- [ ] Test `determine_skill()` for .ts files
- [ ] Test `determine_skill()` for .py files
- [ ] Test `_review_against_skill()` with Spring Boot patterns
- [ ] Test `_review_against_skill()` with Angular patterns
- [ ] Test `post_review_comment()` format
- [ ] Test `get_review_status()` all_passed
- [ ] Test `get_review_status()` warnings
- [ ] Test `get_review_status()` critical_issues
- [ ] Test loading session context
- [ ] Test loading GitHub issues
- [ ] Test loading flow-trace

**Lines of Code:** ~500-700

---

### Task 6.2: Integration Tests
**File:** `tests/test_smart_review_integration.py`

Tests to Write:
- [ ] End-to-end smart review of real Java file
- [ ] End-to-end smart review of real TypeScript file
- [ ] End-to-end smart review of multiple files
- [ ] Verify PR comment posted correctly
- [ ] Verify auto-merge decision logic

---

### Task 6.3: Manual Testing
- [ ] Create test PR with Spring Boot changes
- [ ] Verify smart review runs
- [ ] Verify findings are correct
- [ ] Verify auto-merge happens (or not)
- [ ] Check PR comment content
- [ ] Verify multiple files are handled correctly

---

## Phase 7: Documentation Updates

### Task 7.1: Update Policy Documentation
**File:** `policies/03-execution-system/github-branch-pr-policy.md`

Changes:
- [ ] Add "Step 3: Smart Code Review" section
- [ ] Document review process
- [ ] Show example review comment
- [ ] Explain skill-aware patterns
- [ ] Document review status codes
- [ ] Show decision tree for auto-merge

---

### Task 7.2: Update README
**File:** `README.md`

Changes:
- [ ] Update feature list with smart review
- [ ] Add section explaining smart review
- [ ] Add example review comment
- [ ] Document skill-aware context

---

## Implementation Order (Recommended)

1. **Day 1:**
   - Task 1.1: Create SmartPRReviewer class (skeleton)
   - Task 1.2: Create skill-review-patterns.py (start with 5 skills)
   - Task 3.1-3.2: Verify session context structure

2. **Day 2:**
   - Complete Task 1.1: SmartPRReviewer methods
   - Complete Task 1.2: All 20+ skills
   - Task 4.1: FILE_TO_SKILL_MAP
   - Task 5.1: Review comment template

3. **Day 3:**
   - Task 2.1: Update github-branch-pr-policy.py
   - Task 2.2: Update stop-notifier.py
   - Task 6: Testing
   - Task 7: Documentation

---

## Success Criteria

- [ ] Smart review executes before auto-merge
- [ ] Review correctly identifies skill for each file
- [ ] Review applies skill patterns correctly
- [ ] Review comment posted on PR with findings
- [ ] Auto-merge only happens if status OK
- [ ] Critical issues block merge
- [ ] Warnings allow merge with note
- [ ] All 20+ skills have patterns defined
- [ ] 40+ unit tests passing
- [ ] 10+ integration tests passing
- [ ] Manual testing successful on real PRs
- [ ] Documentation updated
- [ ] Code reviewed and merged

---

## Notes

- **Skill Patterns:** Need to be comprehensive but not overly strict
- **Error Handling:** Review failures should not block merge (log and continue)
- **Performance:** Review should complete in < 30 seconds
- **GitHub API:** Use `gh` CLI for comments (already available)
- **Session Loading:** Use same pattern as flow-trace loading
- **File Reading:** Use safe file reading with encoding handling

---

**Status:** ✅ READY TO IMPLEMENT

All planning complete. Ready for development! 🚀


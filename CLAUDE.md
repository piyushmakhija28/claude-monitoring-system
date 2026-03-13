#  - Claude-Specific Context

**Project:** 
**Version:** 4.23.3
**Type:** Django / FastAPI / Flask
**Last Updated:** 2026-03-13

---

## Project Overview

 is a Django, FastAPI, Flask project providing core functionality.

### Quick Info

| Property | Value |
|----------|-------|
| **Languages** | JavaScript, Python |
| **Frameworks** | Django, FastAPI, Flask |
| **Status** | Active Development |
| **Primary Location** | src/ |

---

## Architecture & Structure

### Directory Layout

```
/
├── src/ → Source code
├── tests/ → Unit and integration tests
├── docs/ → Documentation
├── scripts/ → Utility scripts
├── config/ → Configuration files
├── static/ → Static files
└── templates/ → HTML/View templates
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Core | Main logic | (To be detailed) |

---

## Development Guidelines

### Code Style

- **Language:** JavaScript
- **Format:** Follow PEP 8 / standard conventions
- **Linter:** Use project linters
- **Testing:** All new code requires tests

### Running the Project

```bash
python -m flask run
```

### Testing

```bash
pytest
```

---

## Important Patterns & Conventions

### Code Organization

- Services for business logic
- Models for data structures
- Controllers/Routes for request handling
- Utils for helper functions
- Tests parallel project structure

### Naming Conventions

- Files: snake_case.py
- Classes: PascalCase
- Functions/Methods: snake_case
- Constants: UPPER_SNAKE_CASE

### Common Tasks

#### Adding a New Feature

1. Create issue on GitHub
2. Create feature branch: `git checkout -b feature/issue-XXX-feature-name`
3. Implement feature with tests
4. Update relevant documentation
5. Submit pull request
6. Get approval and merge

---

## Dependencies

- # Claude Insight v4.4.4 - Complete Requirements
- # All production and development dependencies in one file
- # ============================================================================
- # CORE FLASK & WEB FRAMEWORK
- # ============================================================================
- ... and 4 more

---

## Configuration

See environment variables in `.env.example`:
- Database connection settings
- API keys
- Service endpoints
- Debug modes

---

## Troubleshooting

### Common Issues

**Issue:** Module not found
- **Solution:** Ensure virtual environment is activated and dependencies installed

**Issue:** Tests failing
- **Solution:** Run with verbose flag: `pytest -v`

---

## Support

- **GitHub Issues:** Report bugs and request features
- **Documentation:** See README.md and SRS.md
- **Discussion:** GitHub Discussions for general questions

---

**Last Updated:** 2026-03-13
**Next Review:** 2026-03-13

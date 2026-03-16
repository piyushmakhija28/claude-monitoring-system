"""Tests for Skill Manager MCP Server (src/mcp/skill_manager_mcp_server.py)."""

import json
import sys
import importlib.util
import pytest
from pathlib import Path
from unittest.mock import patch

_MCP_DIR = Path(__file__).parent.parent / "src" / "mcp"


def _load_module(name, file_path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_sk_mod = _load_module(
    "skill_manager_mcp_server",
    _MCP_DIR / "skill_manager_mcp_server.py",
)

skill_load_all = _sk_mod.skill_load_all
skill_load = _sk_mod.skill_load
skill_search = _sk_mod.skill_search
skill_validate = _sk_mod.skill_validate
skill_rank = _sk_mod.skill_rank
skill_detect_conflicts = _sk_mod.skill_detect_conflicts
agent_load_all = _sk_mod.agent_load_all
agent_load = _sk_mod.agent_load
_extract_metadata = _sk_mod._extract_metadata
SKILLS_DIR = _sk_mod.SKILLS_DIR
AGENTS_DIR = _sk_mod.AGENTS_DIR


def _parse(result: str) -> dict:
    return json.loads(result)


# =============================================================================
# Helpers
# =============================================================================

_SIMPLE_SKILL_MD = """\
# My Skill

- **Capabilities**: rest_api, jwt, orm
- **Description**: Example skill for testing

This skill covers REST API, JWT auth, and ORM usage.
"""

_EXCLUSIVE_SKILL_MD = """\
# Exclusive Skill

exclusive: true
- **Capabilities**: special_capability
"""

_DOMAIN_A_SKILL_MD = """\
# Domain A

exclusive_domain: auth-layer
- **Capabilities**: login, logout
"""

_DOMAIN_B_SKILL_MD = """\
# Domain B

exclusive_domain: auth-layer
- **Capabilities**: oauth, saml
"""


def _write_skill(skills_dir: Path, name: str, content: str) -> Path:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


def _write_agent(agents_dir: Path, name: str, content: str) -> Path:
    agent_dir = agents_dir / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    agent_file = agent_dir / "agent.md"
    agent_file.write_text(content, encoding="utf-8")
    return agent_file


# =============================================================================
# TOOL 1: skill_load_all
# =============================================================================

class TestSkillLoadAll:
    """Tests for skill_load_all tool."""

    def test_empty_skills_dir_returns_empty_list(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load_all())
        assert result["success"] is True
        assert result["skills"] == []
        assert result["count"] == 0

    def test_missing_skills_dir_returns_empty_list(self, tmp_path):
        missing_dir = tmp_path / "no_such_skills"
        with patch.object(_sk_mod, "SKILLS_DIR", missing_dir):
            result = _parse(skill_load_all())
        assert result["success"] is True
        assert result["skills"] == []
        assert result["count"] == 0

    def test_single_skill_loaded(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load_all())
        assert result["success"] is True
        assert result["count"] == 1
        skill = result["skills"][0]
        assert skill["name"] == "my-skill"
        assert "path" in skill
        assert "size_bytes" in skill

    def test_multiple_skills_all_loaded(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "skill-a", _SIMPLE_SKILL_MD)
        _write_skill(skills_dir, "skill-b", "# Skill B\n- **Capabilities**: testing\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load_all())
        assert result["success"] is True
        assert result["count"] == 2

    def test_capabilities_extracted(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load_all())
        assert result["success"] is True
        skill = result["skills"][0]
        caps = skill.get("capabilities", [])
        assert isinstance(caps, list)

    def test_skill_without_capabilities_still_loads(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "plain-skill", "# Plain Skill\n\nNo capabilities here.\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load_all())
        assert result["success"] is True
        assert result["count"] == 1


# =============================================================================
# TOOL 2: skill_load
# =============================================================================

class TestSkillLoad:
    """Tests for skill_load tool."""

    def test_skill_found_returns_content(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load("my-skill"))
        assert result["success"] is True
        assert result["name"] == "my-skill"
        assert "content" in result
        assert "path" in result
        assert "size_bytes" in result

    def test_skill_not_found_returns_error(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load("nonexistent-skill"))
        assert result["success"] is False
        assert "error" in result
        assert "nonexistent-skill" in result["error"]

    def test_skill_not_found_includes_available_list(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "skill-a", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load("ghost-skill"))
        assert result["success"] is False
        assert "available" in result
        assert isinstance(result["available"], list)

    def test_skill_content_matches_written_file(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load("my-skill"))
        assert result["success"] is True
        assert "Capabilities" in result["content"]

    def test_metadata_extracted_on_load(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_load("my-skill"))
        assert result["success"] is True
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)


# =============================================================================
# TOOL 3: skill_search
# =============================================================================

class TestSkillSearch:
    """Tests for skill_search tool."""

    def test_empty_skills_dir_returns_empty_results(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_search(query="python"))
        assert result["success"] is True
        assert result["results"] == []
        assert result["count"] == 0

    def test_query_matches_skill_name(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "python-flask", "# Flask skill\n")
        _write_skill(skills_dir, "java-spring", "# Spring skill\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_search(query="python"))
        assert result["success"] is True
        names = [r["name"] for r in result["results"]]
        assert "python-flask" in names
        assert "java-spring" not in names

    def test_query_matches_skill_content(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "generic-skill", "This skill uses JWT authentication.")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_search(query="jwt"))
        assert result["success"] is True
        assert result["count"] == 1

    def test_tag_filter_by_keyword_in_name(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "python-auth", "# Auth skill\n")
        _write_skill(skills_dir, "java-spring", "# Spring skill\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_search(tags="python"))
        assert result["success"] is True
        names = [r["name"] for r in result["results"]]
        assert "python-auth" in names

    def test_project_type_filter(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "java-skill", "# Java skill for java projects\n")
        _write_skill(skills_dir, "python-skill", "# Python skill\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_search(project_type="java"))
        assert result["success"] is True
        names = [r["name"] for r in result["results"]]
        assert "java-skill" in names

    def test_name_match_scores_higher_than_content_match(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "flask-core", "# Flask skill\nFlask framework support.")
        _write_skill(skills_dir, "generic-skill", "# Generic skill\nSupports flask indirectly.")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_search(query="flask"))
        assert result["success"] is True
        assert result["count"] >= 1
        # Name-match skill should rank higher
        if len(result["results"]) >= 2:
            assert result["results"][0]["name"] == "flask-core"

    def test_search_with_no_query_returns_all(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "skill-a", "# Skill A\n")
        _write_skill(skills_dir, "skill-b", "# Skill B\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_search())
        assert result["success"] is True
        assert result["count"] == 2

    def test_results_capped_at_twenty(self, tmp_path):
        skills_dir = tmp_path / "skills"
        for i in range(25):
            _write_skill(skills_dir, f"skill-{i:02d}", "# Skill\ncontent here")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_search())
        assert result["success"] is True
        assert len(result["results"]) <= 20


# =============================================================================
# TOOL 4: skill_validate
# =============================================================================

class TestSkillValidate:
    """Tests for skill_validate tool."""

    def test_valid_when_all_capabilities_present(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_validate("my-skill", "rest_api,jwt"))
        assert result["success"] is True
        assert result["valid"] is True
        assert result["missing"] == []

    def test_invalid_when_capability_missing(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_validate("my-skill", "rest_api,graphql"))
        assert result["success"] is True
        assert result["valid"] is False
        assert "graphql" in result["missing"]

    def test_no_requirements_always_valid(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_validate("my-skill", ""))
        assert result["success"] is True
        assert result["valid"] is True

    def test_skill_not_found_returns_error(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_validate("ghost-skill", "rest_api"))
        assert result["success"] is False
        assert "error" in result

    def test_partial_capability_match_invalid(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_validate("my-skill", "rest_api,kafka,redis"))
        assert result["success"] is True
        assert result["valid"] is False
        assert "kafka" in result["missing"]
        assert "redis" in result["missing"]

    def test_response_includes_skill_capabilities(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_validate("my-skill", "rest_api"))
        assert result["success"] is True
        assert "skill_capabilities" in result
        assert isinstance(result["skill_capabilities"], list)


# =============================================================================
# TOOL 5: skill_rank
# =============================================================================

class TestSkillRank:
    """Tests for skill_rank tool."""

    def test_empty_skills_dir_returns_empty_ranked(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_rank(project_type="python"))
        assert result["success"] is True
        assert result["ranked"] == []
        assert result["count"] == 0

    def test_project_type_match_in_name_scores_high(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "python-core", "# Python skill\n")
        _write_skill(skills_dir, "java-core", "# Java skill\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_rank(project_type="python"))
        assert result["success"] is True
        assert result["count"] >= 1
        top = result["ranked"][0]
        assert "python" in top["name"]
        assert top["score"] >= 3

    def test_project_type_in_content_scores_lower_than_name(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "python-core", "# Python core skill\n")
        _write_skill(
            skills_dir, "generic-skill",
            "# Generic\nThis skill also works with python projects.\n"
        )
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_rank(project_type="python"))
        assert result["success"] is True
        name_scores = {r["name"]: r["score"] for r in result["ranked"]}
        if "python-core" in name_scores and "generic-skill" in name_scores:
            assert name_scores["python-core"] >= name_scores["generic-skill"]

    def test_capability_coverage_adds_to_score(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "full-skill", _SIMPLE_SKILL_MD)
        _write_skill(skills_dir, "partial-skill", "# Partial\n- **Capabilities**: rest_api\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_rank(required_capabilities="rest_api,jwt,orm"))
        assert result["success"] is True
        scores = {r["name"]: r["score"] for r in result["ranked"]}
        if "full-skill" in scores and "partial-skill" in scores:
            assert scores["full-skill"] >= scores["partial-skill"]

    def test_zero_score_skills_excluded_from_results(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "irrelevant", "# Irrelevant skill\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_rank(project_type="java", task_type="Implementation"))
        assert result["success"] is True
        for r in result["ranked"]:
            assert r["score"] > 0

    def test_ranked_results_capped_at_ten(self, tmp_path):
        skills_dir = tmp_path / "skills"
        for i in range(15):
            _write_skill(
                skills_dir, f"python-skill-{i:02d}",
                "# Python skill\n- **Capabilities**: testing\n"
            )
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_rank(project_type="python"))
        assert result["success"] is True
        assert len(result["ranked"]) <= 10

    def test_criteria_reflected_in_response(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_rank(
                task_type="Bug Fix",
                project_type="python",
                complexity=7,
            ))
        assert result["success"] is True
        criteria = result["criteria"]
        assert criteria["task_type"] == "Bug Fix"
        assert criteria["project_type"] == "python"
        assert criteria["complexity"] == 7


# =============================================================================
# TOOL 6: skill_detect_conflicts
# =============================================================================

class TestSkillDetectConflicts:
    """Tests for skill_detect_conflicts tool."""

    def test_no_conflicts_between_compatible_skills(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "skill-a", "# Skill A\n- **Capabilities**: rest_api\n")
        _write_skill(skills_dir, "skill-b", "# Skill B\n- **Capabilities**: testing\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_detect_conflicts("skill-a,skill-b"))
        assert result["success"] is True
        assert result["compatible"] is True
        assert result["has_conflicts"] is False
        assert result["conflicts"] == []

    def test_exclusive_flag_causes_conflict(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "exclusive-skill", _EXCLUSIVE_SKILL_MD)
        _write_skill(skills_dir, "other-skill", "# Other skill\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_detect_conflicts("exclusive-skill,other-skill"))
        assert result["success"] is True
        assert result["has_conflicts"] is True
        assert len(result["conflicts"]) == 1

    def test_exclusive_domain_conflict(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "auth-a", _DOMAIN_A_SKILL_MD)
        _write_skill(skills_dir, "auth-b", _DOMAIN_B_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_detect_conflicts("auth-a,auth-b"))
        assert result["success"] is True
        assert result["has_conflicts"] is True
        conflict = result["conflicts"][0]
        assert "auth-layer" in conflict["reason"]

    def test_single_skill_no_conflict(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "solo-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_detect_conflicts("solo-skill"))
        assert result["success"] is True
        assert result["compatible"] is True

    def test_missing_skill_skipped_gracefully(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "real-skill", _SIMPLE_SKILL_MD)
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            # ghost-skill does not exist, should be ignored
            result = _parse(skill_detect_conflicts("real-skill,ghost-skill"))
        assert result["success"] is True

    def test_skills_checked_list_in_response(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "skill-a", _SIMPLE_SKILL_MD)
        _write_skill(skills_dir, "skill-b", "# Skill B\n")
        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir):
            result = _parse(skill_detect_conflicts("skill-a,skill-b"))
        assert result["success"] is True
        assert "skills_checked" in result
        assert "skill-a" in result["skills_checked"]
        assert "skill-b" in result["skills_checked"]


# =============================================================================
# TOOL 7: agent_load_all
# =============================================================================

class TestAgentLoadAll:
    """Tests for agent_load_all tool."""

    def test_missing_agents_dir_returns_empty(self, tmp_path):
        missing_dir = tmp_path / "no_agents"
        with patch.object(_sk_mod, "AGENTS_DIR", missing_dir):
            result = _parse(agent_load_all())
        assert result["success"] is True
        assert result["agents"] == []
        assert result["count"] == 0

    def test_empty_agents_dir_returns_empty(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load_all())
        assert result["success"] is True
        assert result["agents"] == []
        assert result["count"] == 0

    def test_single_agent_loaded(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "my-agent", "# My Agent\n\nDoes great things.\n")
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load_all())
        assert result["success"] is True
        assert result["count"] == 1
        agent = result["agents"][0]
        assert agent["name"] == "my-agent"
        assert "path" in agent
        assert "size_bytes" in agent

    def test_multiple_agents_loaded(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "agent-a", "# Agent A\n")
        _write_agent(agents_dir, "agent-b", "# Agent B\n")
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load_all())
        assert result["success"] is True
        assert result["count"] == 2

    def test_dir_without_agent_md_skipped(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # Directory exists but has no agent.md
        (agents_dir / "empty-agent").mkdir()
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load_all())
        assert result["success"] is True
        assert result["count"] == 0

    def test_count_matches_agents_list_length(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "agent-1", "# A1\n")
        _write_agent(agents_dir, "agent-2", "# A2\n")
        _write_agent(agents_dir, "agent-3", "# A3\n")
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load_all())
        assert result["success"] is True
        assert result["count"] == len(result["agents"])


# =============================================================================
# TOOL 8: agent_load
# =============================================================================

class TestAgentLoad:
    """Tests for agent_load tool."""

    def test_agent_found_returns_content(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "my-agent", "# My Agent\n\nRole: testing.\n")
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load("my-agent"))
        assert result["success"] is True
        assert result["name"] == "my-agent"
        assert "content" in result
        assert "path" in result
        assert "size_bytes" in result

    def test_agent_not_found_returns_error(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load("ghost-agent"))
        assert result["success"] is False
        assert "error" in result
        assert "ghost-agent" in result["error"]

    def test_agent_not_found_includes_available_list(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "real-agent", "# Real Agent\n")
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load("ghost-agent"))
        assert result["success"] is False
        assert "available" in result
        assert isinstance(result["available"], list)

    def test_agent_content_matches_written_file(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agent_content = "# My Agent\n\nRole: orchestration agent.\n"
        _write_agent(agents_dir, "my-agent", agent_content)
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load("my-agent"))
        assert result["success"] is True
        assert "orchestration" in result["content"]

    def test_agent_metadata_extracted(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "my-agent", "# My Agent\n\nDoes things.\n")
        with patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            result = _parse(agent_load("my-agent"))
        assert result["success"] is True
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)


# =============================================================================
# Internal helper: _extract_metadata
# =============================================================================

class TestExtractMetadata:
    """Tests for _extract_metadata helper."""

    def test_extracts_capabilities_from_content(self):
        content = "- **Capabilities**: rest_api, jwt, orm\n"
        meta = _extract_metadata(content)
        assert "capabilities" in meta
        assert "rest_api" in meta["capabilities"]

    def test_extracts_yaml_frontmatter(self):
        content = "---\nexclusive: true\nexclusive_domain: auth\n---\n# Skill\n"
        meta = _extract_metadata(content)
        assert meta.get("exclusive") in (True, "true")
        assert meta.get("exclusive_domain") == "auth"

    def test_empty_content_returns_empty_dict(self):
        meta = _extract_metadata("")
        assert meta == {}

    def test_no_frontmatter_no_capabilities(self):
        content = "# Just a heading\n\nProse text only.\n"
        meta = _extract_metadata(content)
        assert "capabilities" not in meta

    def test_triggers_extracted(self):
        content = "TRIGGER when: task contains 'implement'\n"
        meta = _extract_metadata(content)
        assert "triggers" in meta
        assert len(meta["triggers"]) == 1


# =============================================================================
# JSON response consistency
# =============================================================================

class TestJsonResponseFormat:
    """Verify all tools return valid JSON with success key."""

    def test_all_tools_return_valid_json(self, tmp_path):
        skills_dir = tmp_path / "skills"
        agents_dir = tmp_path / "agents"
        _write_skill(skills_dir, "test-skill", _SIMPLE_SKILL_MD)
        _write_agent(agents_dir, "test-agent", "# Test Agent\n")

        with patch.object(_sk_mod, "SKILLS_DIR", skills_dir), \
             patch.object(_sk_mod, "AGENTS_DIR", agents_dir):
            tools = [
                skill_load_all,
                lambda: skill_load("test-skill"),
                lambda: skill_search(query="test"),
                lambda: skill_validate("test-skill", "rest_api"),
                lambda: skill_rank(project_type="python"),
                lambda: skill_detect_conflicts("test-skill"),
                agent_load_all,
                lambda: agent_load("test-agent"),
            ]
            for fn in tools:
                raw = fn()
                parsed = json.loads(raw)
                assert isinstance(parsed, dict), f"Expected dict, got {type(parsed)}"
                assert "success" in parsed, f"Missing 'success' key in: {parsed}"

#!/usr/bin/env python3
"""
Core Skills Loader - Step 3.5 Pre-Flight Context Provider

Load skill/agent definitions from LOCAL disk for LLM context.

CRITICAL: LLM needs FULL skill definitions to make decisions!

Problem: LLM doesn't know available skills → makes bad choices
Solution: Load ALL skill definitions from local disk → provide as context to LLM

Flow:
1. THIS SCRIPT reads skill definitions from ~/.claude/skills/
2. Provides full skill.md content to LLM
3. LLM reads skill definitions → makes informed decision
4. LLM invokes /skill with chosen skill name
5. Skill already available locally → SUCCESS

Version: 2.0.0 (LOCAL-FIRST)
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

MEMORY_BASE = Path.home() / '.claude' / 'memory'
SKILLS_LOCAL = MEMORY_BASE / 'skills'  # Local skill definitions
AGENTS_LOCAL = MEMORY_BASE / 'agents'  # Local agent definitions


class CoreSkillsLoader:
    """Load core skills from LOCAL disk for LLM context."""

    def __init__(self):
        """Initialize loader pointing to local skill definitions."""
        self.skills_local = SKILLS_LOCAL
        self.agents_local = AGENTS_LOCAL

    def list_available_skills(self):
        """List all available skills from local directory."""
        if not self.skills_local.exists():
            return []

        try:
            # Look for skill.md files in skill directories
            skills = []
            for skill_dir in self.skills_local.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / 'skill.md'
                    if skill_file.exists():
                        skills.append(skill_dir.name)
            return sorted(skills)
        except Exception:
            return []

    def list_available_agents(self):
        """List all available agents from local directory."""
        if not self.agents_local.exists():
            return []

        try:
            # Look for agent.md files in agent directories
            agents = []
            for agent_dir in self.agents_local.iterdir():
                if agent_dir.is_dir():
                    agent_file = agent_dir / 'agent.md'
                    if agent_file.exists():
                        agents.append(agent_dir.name)
            return sorted(agents)
        except Exception:
            return []

    def load_skill(self, skill_name):
        """
        Load skill definition from LOCAL disk.

        LLM needs the full skill.md content to make informed decisions.

        Args:
            skill_name: Skill directory name (e.g., 'docker', 'java-spring-boot')

        Returns:
            dict: {'name', 'status', 'loaded', 'path', 'content', 'size_bytes'}
        """
        skill_dir = self.skills_local / skill_name
        skill_file = skill_dir / 'skill.md'

        if not skill_file.exists():
            return {
                'name': skill_name,
                'status': 'not_found',
                'loaded': False,
                'error': f'Skill "{skill_name}" not found in {self.skills_local}',
                'available_skills': self.list_available_skills()
            }

        try:
            content = skill_file.read_text(encoding='utf-8')
            return {
                'name': skill_name,
                'status': 'loaded',
                'loaded': True,
                'path': str(skill_file),
                'content': content,  # Full definition for LLM
                'size_bytes': len(content),
                'source': 'local'
            }
        except Exception as e:
            return {
                'name': skill_name,
                'status': 'failed',
                'loaded': False,
                'error': f'Could not read skill: {str(e)}'
            }

    def load_agent(self, agent_name):
        """
        Load agent definition from LOCAL disk.

        LLM needs the full agent.md content to make informed decisions.

        Args:
            agent_name: Agent directory name (e.g., 'orchestrator-agent')

        Returns:
            dict: {'name', 'status', 'loaded', 'path', 'content', 'size_bytes'}
        """
        agent_dir = self.agents_local / agent_name
        agent_file = agent_dir / 'agent.md'

        if not agent_file.exists():
            return {
                'name': agent_name,
                'status': 'not_found',
                'loaded': False,
                'error': f'Agent "{agent_name}" not found in {self.agents_local}',
                'available_agents': self.list_available_agents()
            }

        try:
            content = agent_file.read_text(encoding='utf-8')
            return {
                'name': agent_name,
                'status': 'loaded',
                'loaded': True,
                'path': str(agent_file),
                'content': content,  # Full definition for LLM
                'size_bytes': len(content),
                'source': 'local'
            }
        except Exception as e:
            return {
                'name': agent_name,
                'status': 'failed',
                'loaded': False,
                'error': f'Could not read agent: {str(e)}'
            }

if __name__ == '__main__':
    """
    CLI Usage: Load skill or agent definitions for LLM context

    python core-skills-loader.py skill_name   # Load specific skill
    python core-skills-loader.py agent_name   # Load specific agent
    python core-skills-loader.py --list      # List all available
    """
    loader = CoreSkillsLoader()

    if len(sys.argv) < 2 or sys.argv[1] == '--list':
        # List all available skills and agents
        output = {
            'step': 'LEVEL_3_SKILL_LOADER',
            'available_skills': loader.list_available_skills(),
            'available_agents': loader.list_available_agents(),
            'skills_dir': str(SKILLS_LOCAL),
            'agents_dir': str(AGENTS_LOCAL),
            'status': 'OK'
        }
    else:
        name = sys.argv[1]

        # Try loading as skill first, then as agent
        skill_result = loader.load_skill(name)
        if skill_result.get('loaded'):
            output = {
                'step': 'LEVEL_3_SKILL_LOADER',
                'skill_loaded': skill_result,
                'available_skills': loader.list_available_skills(),
                'status': 'OK'
            }
        else:
            agent_result = loader.load_agent(name)
            output = {
                'step': 'LEVEL_3_SKILL_LOADER',
                'agent_loaded': agent_result,
                'available_agents': loader.list_available_agents(),
                'status': 'OK' if agent_result.get('loaded') else 'SKILL_OR_AGENT_NOT_FOUND'
            }

    print(json.dumps(output, indent=2))

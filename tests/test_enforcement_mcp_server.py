#!/usr/bin/env python3
"""
Unit Tests for EnforcementMCPServer

Tests all functionality of the MCP server for policy enforcement including:
- Enforcement status retrieval
- Step enforcement
- Tool call logging
- Compliance verification
- MCP configuration
- Tool call handling
- Resource retrieval
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from mcp.enforcement_server import EnforcementMCPServer, create_mcp_server_config


class TestEnforcementMCPServer(unittest.TestCase):
    """Test suite for EnforcementMCPServer"""

    def setUp(self):
        """Set up test fixtures before each test"""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp_dir) / '.claude' / 'memory'
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Patch home directory
        self.patcher = patch('pathlib.Path.home')
        self.mock_home = self.patcher.start()
        self.mock_home.return_value = Path(self.temp_dir)

        # Create server instance
        self.server = EnforcementMCPServer()

    def tearDown(self):
        """Clean up after each test"""
        self.patcher.stop()
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def create_enforcer_state(self, **kwargs):
        """Helper to create enforcer state file"""
        state = {
            'session_started': False,
            'standards_loaded': False,
            'prompt_generated': False,
            'tasks_created': False,
            'plan_mode_decided': False,
            'model_selected': False,
            'skills_agents_checked': False,
            'context_checked': False
        }
        state.update(kwargs)

        state_file = self.memory_dir / '.blocking-enforcer-state.json'
        with open(state_file, 'w') as f:
            json.dump(state, f)

        return state

    def test_initialization(self):
        """Test server initialization"""
        self.assertIsNotNone(self.server.logger)
        self.assertTrue(self.server.memory_path.exists())

    def test_get_enforcement_status_no_state_file(self):
        """Test getting enforcement status when state file doesn't exist"""
        result = self.server.get_enforcement_status()

        self.assertTrue(result['success'])
        self.assertIsInstance(result['state'], dict)
        self.assertIn('timestamp', result)

    def test_get_enforcement_status_with_state_file(self):
        """Test getting enforcement status when state file exists"""
        expected_state = self.create_enforcer_state(
            session_started=True,
            prompt_generated=True
        )

        result = self.server.get_enforcement_status()

        self.assertTrue(result['success'])
        self.assertTrue(result['state']['session_started'])
        self.assertTrue(result['state']['prompt_generated'])
        self.assertFalse(result['state']['tasks_created'])

    def test_get_enforcement_status_corrupted_file(self):
        """Test getting enforcement status with corrupted state file"""
        state_file = self.memory_dir / '.blocking-enforcer-state.json'
        with open(state_file, 'w') as f:
            f.write("{ invalid json")

        result = self.server.get_enforcement_status()

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_enforce_step_valid_step(self):
        """Test enforcing a valid step"""
        # Create the script directory structure
        execution_dir = self.memory_dir / '03-execution-system' / '00-prompt-generation'
        execution_dir.mkdir(parents=True, exist_ok=True)

        script_file = execution_dir / 'prompt-generator.py'
        script_file.write_text("# Test script")

        result = self.server.enforce_step(0, 'Prompt Generation')

        self.assertTrue(result['success'])
        self.assertEqual(result['step'], 0)
        self.assertEqual(result['name'], 'Prompt Generation')
        self.assertIn('message', result)

    def test_enforce_step_invalid_step(self):
        """Test enforcing an invalid step number"""
        result = self.server.enforce_step(99, 'Invalid Step')

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_enforce_step_missing_script(self):
        """Test enforcing a step when script doesn't exist"""
        result = self.server.enforce_step(0, 'Prompt Generation')

        self.assertFalse(result['success'])
        self.assertIn('Script not found', result['error'])

    def test_log_tool_call_basic(self):
        """Test logging a basic tool call"""
        result = self.server.log_tool_call(
            'Read',
            'Read file',
            None,
            'SUCCESS'
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['tool'], 'Read')
        self.assertEqual(result['operation'], 'Read file')
        self.assertTrue(result['logged'])
        self.assertIn('timestamp', result)

    def test_log_tool_call_with_parameters(self):
        """Test logging a tool call with parameters"""
        params = {
            'file': 'test.py',
            'offset': 0,
            'limit': 100
        }

        result = self.server.log_tool_call(
            'Read',
            'Read with optimization',
            params,
            'OPTIMIZED'
        )

        self.assertTrue(result['success'])
        self.assertTrue(result['logged'])

    def test_verify_policy_compliance_all_complete(self):
        """Test compliance verification when all steps complete"""
        self.create_enforcer_state(
            session_started=True,
            context_checked=True,
            standards_loaded=True,
            prompt_generated=True,
            tasks_created=True,
            plan_mode_decided=True,
            model_selected=True,
            skills_agents_checked=True
        )

        result = self.server.verify_policy_compliance()

        self.assertTrue(result['compliant'])
        self.assertEqual(result['completed_steps'], 8)
        self.assertEqual(result['total_steps'], 8)
        self.assertEqual(len(result['missing_steps']), 0)

    def test_verify_policy_compliance_partial(self):
        """Test compliance verification with partial completion"""
        self.create_enforcer_state(
            session_started=True,
            context_checked=True,
            standards_loaded=True
        )

        result = self.server.verify_policy_compliance()

        self.assertFalse(result['compliant'])
        self.assertEqual(result['completed_steps'], 3)
        self.assertEqual(result['total_steps'], 8)
        self.assertGreater(len(result['missing_steps']), 0)

    def test_verify_policy_compliance_none_complete(self):
        """Test compliance verification when nothing is complete"""
        self.create_enforcer_state()

        result = self.server.verify_policy_compliance()

        self.assertFalse(result['compliant'])
        self.assertEqual(result['completed_steps'], 0)
        self.assertEqual(result['total_steps'], 8)
        self.assertEqual(len(result['missing_steps']), 8)

    def test_get_mcp_config_structure(self):
        """Test MCP configuration structure"""
        config = self.server.get_mcp_config()

        self.assertEqual(config['name'], 'enforcement-server')
        self.assertEqual(config['version'], '1.0.0')
        self.assertIn('tools', config)
        self.assertIn('resources', config)
        self.assertIsInstance(config['tools'], list)
        self.assertIsInstance(config['resources'], list)

    def test_get_mcp_config_tools(self):
        """Test MCP configuration tools"""
        config = self.server.get_mcp_config()
        tools = config['tools']

        tool_names = [tool['name'] for tool in tools]

        self.assertIn('check_enforcement_status', tool_names)
        self.assertIn('enforce_policy_step', tool_names)
        self.assertIn('log_tool_usage', tool_names)
        self.assertIn('verify_compliance', tool_names)

        # Verify tool structure
        for tool in tools:
            self.assertIn('name', tool)
            self.assertIn('description', tool)
            self.assertIn('input_schema', tool)

    def test_get_mcp_config_resources(self):
        """Test MCP configuration resources"""
        config = self.server.get_mcp_config()
        resources = config['resources']

        resource_uris = [resource['uri'] for resource in resources]

        self.assertIn('enforcement://status', resource_uris)
        self.assertIn('enforcement://compliance', resource_uris)

        # Verify resource structure
        for resource in resources:
            self.assertIn('uri', resource)
            self.assertIn('name', resource)
            self.assertIn('description', resource)

    def test_handle_tool_call_check_status(self):
        """Test handling check_enforcement_status tool call"""
        self.create_enforcer_state(session_started=True)

        result = self.server.handle_tool_call('check_enforcement_status', {})

        self.assertTrue(result['success'])
        self.assertIn('state', result)
        self.assertTrue(result['state']['session_started'])

    def test_handle_tool_call_enforce_step(self):
        """Test handling enforce_policy_step tool call"""
        # Create script
        execution_dir = self.memory_dir / '03-execution-system' / '00-prompt-generation'
        execution_dir.mkdir(parents=True, exist_ok=True)
        (execution_dir / 'prompt-generator.py').write_text("# Test")

        args = {
            'step_number': 0,
            'step_name': 'Prompt Generation'
        }

        result = self.server.handle_tool_call('enforce_policy_step', args)

        self.assertTrue(result['success'])
        self.assertEqual(result['step'], 0)

    def test_handle_tool_call_log_tool_usage(self):
        """Test handling log_tool_usage tool call"""
        args = {
            'tool_name': 'Read',
            'operation': 'Read file',
            'parameters': {'file': 'test.py'},
            'result': 'SUCCESS'
        }

        result = self.server.handle_tool_call('log_tool_usage', args)

        self.assertTrue(result['success'])
        self.assertEqual(result['tool'], 'Read')
        self.assertTrue(result['logged'])

    def test_handle_tool_call_verify_compliance(self):
        """Test handling verify_compliance tool call"""
        self.create_enforcer_state()

        result = self.server.handle_tool_call('verify_compliance', {})

        self.assertIn('compliant', result)
        self.assertIn('completed_steps', result)
        self.assertIn('missing_steps', result)

    def test_handle_tool_call_unknown_tool(self):
        """Test handling unknown tool call"""
        result = self.server.handle_tool_call('unknown_tool', {})

        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('Unknown tool', result['error'])

    def test_get_resource_status(self):
        """Test getting enforcement://status resource"""
        self.create_enforcer_state(session_started=True)

        result = self.server.get_resource('enforcement://status')

        self.assertTrue(result['success'])
        self.assertIn('state', result)

    def test_get_resource_compliance(self):
        """Test getting enforcement://compliance resource"""
        self.create_enforcer_state()

        result = self.server.get_resource('enforcement://compliance')

        self.assertIn('compliant', result)
        self.assertIn('missing_steps', result)

    def test_get_resource_unknown(self):
        """Test getting unknown resource"""
        result = self.server.get_resource('enforcement://unknown')

        self.assertFalse(result['success'])
        self.assertIn('error', result)


class TestMCPServerConfigCreation(unittest.TestCase):
    """Test MCP server configuration file creation"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch('pathlib.Path.home')
        self.mock_home = self.patcher.start()
        self.mock_home.return_value = Path(self.temp_dir)

    def tearDown(self):
        """Clean up"""
        self.patcher.stop()
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_create_mcp_server_config_new_file(self):
        """Test creating MCP config file when it doesn't exist"""
        config_file = create_mcp_server_config()

        self.assertTrue(config_file.exists())

        with open(config_file, 'r') as f:
            config = json.load(f)

        self.assertIn('servers', config)
        self.assertIn('enforcement', config['servers'])

    def test_create_mcp_server_config_existing_file(self):
        """Test creating MCP config when file already exists"""
        claude_dir = Path(self.temp_dir) / '.claude'
        claude_dir.mkdir(parents=True, exist_ok=True)

        config_file = claude_dir / 'mcp-servers.json'
        existing_config = {
            'servers': {
                'existing-server': {
                    'command': 'python',
                    'args': ['test.py']
                }
            }
        }

        with open(config_file, 'w') as f:
            json.dump(existing_config, f)

        new_config_file = create_mcp_server_config()

        with open(new_config_file, 'r') as f:
            config = json.load(f)

        # Should preserve existing server
        self.assertIn('existing-server', config['servers'])
        # Should add enforcement server
        self.assertIn('enforcement', config['servers'])

    def test_create_mcp_server_config_structure(self):
        """Test structure of created MCP config"""
        config_file = create_mcp_server_config()

        with open(config_file, 'r') as f:
            config = json.load(f)

        enforcement = config['servers']['enforcement']

        self.assertEqual(enforcement['command'], 'python')
        self.assertIsInstance(enforcement['args'], list)
        self.assertIn('description', enforcement)
        self.assertTrue(enforcement['enabled'])


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestEnforcementMCPServer))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPServerConfigCreation))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

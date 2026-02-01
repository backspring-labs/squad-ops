"""
Unit tests for PRDProcessor capability
Tests prd.process capability functionality
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.capabilities.prd_processor import PRDProcessor


class TestPRDProcessor:
    """Test PRDProcessor capability"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_success(self):
        """Test successful PRD processing"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.current_ecid = None
        mock_agent.warmboot_state = {}
        mock_agent.create_execution_cycle = AsyncMock()
        mock_agent.log_task_delegation = AsyncMock()
        mock_agent.send_message = AsyncMock()
        mock_agent.record_memory = AsyncMock()
        
        mock_capability_loader = MagicMock()
        mock_agent.capability_loader = mock_capability_loader
        
        async def execute_side_effect(capability, agent_instance, *args, **kwargs):
            if capability == 'prd.read':
                return {"prd_content": "# Test PRD", "file_path": "/test/prd.md", "parsed_sections": {}}
            elif capability == 'prd.analyze':
                return {'core_features': ['Feature 1'], 'technical_requirements': [], 'success_criteria': [], 'analysis_summary': 'Test'}
            elif capability == 'task.create':
                return {
                    'tasks': [
                        {'task_id': 'task-001', 'task_type': 'development', 'description': 'Test task', 'requirements': {'action': 'archive'}}
                    ],
                    'app_name': 'TestApp',
                    'app_version': '0.1.0.001',
                    'task_count': 1
                }
            elif capability == 'task.determine_target':
                return {'target_agent': 'dev-agent', 'target_role': 'dev', 'reasoning': 'Test'}
            return {}
        
        mock_capability_loader.execute = AsyncMock(side_effect=execute_side_effect)
        
        processor = PRDProcessor(mock_agent)
        
        task = {
            'prd_path': '/test/prd.md',
            'cycle_id': 'test-ecid-001'
        }
        
        result = await processor.process(task=task)
        
        assert result['status'] == 'success'
        assert 'prd_analysis' in result
        assert 'tasks_delegated' in result
        assert len(result['tasks_delegated']) == 1
        
        # Verify capability loader was called
        assert mock_capability_loader.execute.call_count >= 3
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_with_manifest_injection(self):
        """Test PRD processing with manifest injection for build tasks"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.current_ecid = None
        mock_agent.warmboot_state = {'manifest': {'version': '1.0.0', 'components': []}}
        mock_agent.create_execution_cycle = AsyncMock()
        mock_agent.log_task_delegation = AsyncMock()
        mock_agent.send_message = AsyncMock()
        mock_agent.record_memory = AsyncMock()
        
        mock_capability_loader = MagicMock()
        mock_agent.capability_loader = mock_capability_loader
        
        async def execute_side_effect(capability, agent_instance, *args, **kwargs):
            if capability == 'prd.read':
                return {"prd_content": "# Test PRD", "file_path": "/test/prd.md", "parsed_sections": {}}
            elif capability == 'prd.analyze':
                return {'core_features': ['Feature 1'], 'technical_requirements': [], 'success_criteria': [], 'analysis_summary': 'Test'}
            elif capability == 'task.create':
                return {
                    'tasks': [
                        {
                            'task_id': 'task-001',
                            'task_type': 'development',
                            'description': 'Build task',
                            'requirements': {'action': 'build'}  # No manifest initially
                        }
                    ],
                    'app_name': 'TestApp',
                    'app_version': '0.1.0.001',
                    'task_count': 1
                }
            elif capability == 'task.determine_target':
                return {'target_agent': 'dev-agent', 'target_role': 'dev', 'reasoning': 'Test'}
            return {}
        
        mock_capability_loader.execute = AsyncMock(side_effect=execute_side_effect)
        
        processor = PRDProcessor(mock_agent)
        
        task = {
            'prd_path': '/test/prd.md',
            'cycle_id': 'test-ecid-001'
        }
        
        result = await processor.process(task=task)
        
        assert result['status'] == 'success'
        # Verify manifest was injected (check via send_message call)
        send_call_args = mock_agent.send_message.call_args
        assert send_call_args is not None
        delegated_task = send_call_args[1]['payload']
        assert delegated_task['requirements']['manifest'] == {'version': '1.0.0', 'components': []}
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_missing_path(self):
        """Test PRD processing with missing PRD path"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.capability_loader = MagicMock()
        
        processor = PRDProcessor(mock_agent)
        
        result = await processor.process(task={})
        
        assert result['status'] == 'error'
        assert 'PRD path not provided' in result['message']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_read_failure(self):
        """Test PRD processing when PRD read fails"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.current_ecid = None
        mock_agent.create_execution_cycle = AsyncMock()
        
        mock_capability_loader = MagicMock()
        mock_agent.capability_loader = mock_capability_loader
        
        async def execute_side_effect(capability, agent_instance, *args, **kwargs):
            if capability == 'prd.read':
                return {"prd_content": "", "file_path": "/test/prd.md", "parsed_sections": {}}
            return {}
        
        mock_capability_loader.execute = AsyncMock(side_effect=execute_side_effect)
        
        processor = PRDProcessor(mock_agent)
        
        task = {
            'prd_path': '/test/prd.md',
            'cycle_id': 'test-ecid-001'
        }
        
        result = await processor.process(task=task)
        
        assert result['status'] == 'error'
        assert 'Failed to read PRD' in result['message']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_build_task_without_manifest_skipped(self):
        """Test that build tasks without manifest are skipped"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.current_ecid = None
        mock_agent.warmboot_state = {}  # No manifest
        mock_agent.create_execution_cycle = AsyncMock()
        
        mock_capability_loader = MagicMock()
        mock_agent.capability_loader = mock_capability_loader
        
        async def execute_side_effect(capability, agent_instance, *args, **kwargs):
            if capability == 'prd.read':
                return {"prd_content": "# Test PRD", "file_path": "/test/prd.md", "parsed_sections": {}}
            elif capability == 'prd.analyze':
                return {'core_features': ['Feature 1'], 'technical_requirements': [], 'success_criteria': [], 'analysis_summary': 'Test'}
            elif capability == 'task.create':
                return {
                    'tasks': [
                        {
                            'task_id': 'task-001',
                            'task_type': 'development',
                            'description': 'Build task',
                            'requirements': {'action': 'build'}  # No manifest
                        }
                    ],
                    'app_name': 'TestApp',
                    'app_version': '0.1.0.001',
                    'task_count': 1
                }
            return {}
        
        mock_capability_loader.execute = AsyncMock(side_effect=execute_side_effect)
        
        processor = PRDProcessor(mock_agent)
        
        task = {
            'prd_path': '/test/prd.md',
            'cycle_id': 'test-ecid-001'
        }
        
        result = await processor.process(task=task)
        
        assert result['status'] == 'success'
        # Build task should be skipped, so no tasks delegated
        assert len(result['tasks_delegated']) == 0


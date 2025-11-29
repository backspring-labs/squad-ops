#!/usr/bin/env python3
"""
Unit tests for TaskDelegator capability
Tests task delegation and target determination
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.task_delegator import TaskDelegator


class TestTaskDelegator:
    """Test TaskDelegator capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.instances_file = "agents/instances/instances.yaml"
        agent.task_api_url = "http://localhost:8001"
        return agent
    
    @pytest.fixture
    def delegator(self, mock_agent):
        """Create TaskDelegator instance"""
        return TaskDelegator(mock_agent)
    
    @pytest.mark.unit
    def test_delegator_initialization(self, mock_agent):
        """Test TaskDelegator initialization"""
        delegator = TaskDelegator(mock_agent)
        assert delegator.agent == mock_agent
        assert delegator.name == "test-agent"
        assert delegator.instances_file == "agents/instances/instances.yaml"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_target_development(self, delegator):
        """Test determining target for development task"""
        with patch.object(delegator, '_load_role_to_agent_mapping', return_value={'dev': 'dev-agent'}):
            result = await delegator.determine_target('development')
            
            assert result['target_agent'] == 'dev-agent'
            assert result['target_role'] == 'dev'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_target_testing(self, delegator):
        """Test determining target for testing task"""
        with patch.object(delegator, '_load_role_to_agent_mapping', return_value={'qa': 'qa-agent'}):
            result = await delegator.determine_target('testing')
            
            assert result['target_agent'] == 'qa-agent'
            assert result['target_role'] == 'qa'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_target_governance_error(self, delegator):
        """Test determining target for governance task (should raise error)"""
        with pytest.raises(ValueError, match="Governance tasks should not be delegated"):
            await delegator.determine_target('governance')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_target_warmboot_wrapup(self, delegator, mock_agent):
        """Test determining target for warmboot_wrapup task"""
        mock_agent.capability_loader = MagicMock()
        mock_agent.capability_loader.get_agent_for_capability = MagicMock(return_value='lead-agent')
        
        result = await delegator.determine_target('warmboot_wrapup')
        
        assert result['target_agent'] == 'lead-agent'
        assert result['target_role'] is None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_target_warmboot_wrapup_fallback(self, delegator, mock_agent):
        """Test determining target for warmboot_wrapup with fallback"""
        mock_agent.capability_loader = None
        
        with patch.object(delegator, '_load_role_to_agent_mapping', return_value={'lead': 'max'}):
            result = await delegator.determine_target('warmboot_wrapup')
            
            assert result['target_agent'] == 'max'
            assert result['target_role'] == 'lead'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_target_unknown_type(self, delegator):
        """Test determining target for unknown task type"""
        with patch.object(delegator, '_load_role_to_agent_mapping', return_value={}):
            result = await delegator.determine_target('unknown_type')
            
            # Should return None or default
            assert result is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delegate_success(self, delegator):
        """Test successful task delegation"""
        task_data = {
            'task_id': 'task-001',
            'description': 'Test task',
            'priority': 'HIGH'
        }
        
        with patch.object(delegator, 'determine_target', new_callable=AsyncMock, return_value={'target_agent': 'dev-agent'}), \
             patch.object(delegator.agent, 'send_message', new_callable=AsyncMock) as mock_send:
            
            task_dict = {'task_id': 'task-001', 'task_type': 'development', **task_data}
            result = await delegator.delegate(task_dict)
            
            assert result['delegation_status'] == 'success'
            mock_send.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delegate_api_error(self, delegator):
        """Test delegation when API returns error"""
        task_data = {'task_id': 'task-001'}
        
        with patch.object(delegator, 'determine_target', new_callable=AsyncMock, return_value={'target_agent': 'dev-agent'}), \
             patch.object(delegator.agent, 'send_message', new_callable=AsyncMock, side_effect=Exception("Send failed")):
            
            task_dict = {'task_id': 'task-001', 'task_type': 'development', **task_data}
            result = await delegator.delegate(task_dict)
            
            assert result['delegation_status'] == 'failed'
            assert 'error' in result
    
    @pytest.mark.unit
    def test_load_role_to_agent_mapping(self, delegator, tmp_path):
        """Test loading role to agent mapping"""
        instances_file = tmp_path / "instances.yaml"
        instances_file.parent.mkdir(parents=True, exist_ok=True)
        
        instances_data = {
            'instances': [
                {'id': 'dev-agent', 'role': 'dev', 'enabled': True},
                {'id': 'qa-agent', 'role': 'qa', 'enabled': True}
            ]
        }
        
        import yaml
        with open(instances_file, 'w') as f:
            yaml.dump(instances_data, f)
        
        delegator.instances_file = str(instances_file)
        mapping = delegator._load_role_to_agent_mapping()
        
        assert mapping['dev'] == 'dev-agent'
        assert mapping['qa'] == 'qa-agent'
    
    @pytest.mark.unit
    def test_load_role_to_agent_mapping_not_found(self, delegator):
        """Test loading mapping when file doesn't exist"""
        delegator.instances_file = '/nonexistent/file.yaml'
        
        mapping = delegator._load_role_to_agent_mapping()
        
        # Should return empty dict or default mapping
        assert isinstance(mapping, dict)


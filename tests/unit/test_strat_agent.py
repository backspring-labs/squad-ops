"""
Unit tests for StratAgent
Tests generic capability routing and refactored agent
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.roles.strat.agent import StratAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse


class TestStratAgent:
    """Test StratAgent"""
    
    def setup_method(self):
        """Reset PathResolver before each test"""
        from agents.utils.path_resolver import PathResolver
        PathResolver.reset()
    
    @pytest.mark.unit
    def test_init(self):
        """Test agent initialization"""
        agent = StratAgent(identity="nat")
        
        assert agent.name == "nat"
        assert agent.agent_type == "strategy"
        assert agent.reasoning_style == "abductive"
        assert hasattr(agent, 'validator')
        # Should not have dummy instance variables
        assert not hasattr(agent, 'priority_queue')
        assert not hasattr(agent, 'opportunity_cache')
        assert not hasattr(agent, 'hypothesis_space')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_generic_routing(self):
        """Test generic capability routing"""
        agent = StratAgent(identity="nat")
        
        # Mock capability loader
        mock_loader = MagicMock()
        mock_loader.prepare_capability_args = MagicMock(return_value=({'requirement': 'test'},))
        mock_loader.execute = AsyncMock(return_value={'prd_content': 'test', 'prd_path': '/test.md'})
        agent.capability_loader = mock_loader
        
        # Mock validator
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(True, None))
        agent.validator.validate_result_keys = MagicMock(return_value=(True, None))
        agent._validate_constraints = MagicMock(return_value=(True, None))
        
        request = AgentRequest(
            action="product.draft_prd_from_prompt",
            payload={'requirement': 'test', 'objective': 'test', 'app_name': 'TestApp'},
            metadata={'pid': 'PID-TEST-001', 'ecid': 'ECID-TEST-001'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "ok"
        assert mock_loader.execute.called
        assert mock_loader.prepare_capability_args.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_unknown_capability(self):
        """Test handling unknown capability"""
        agent = StratAgent(identity="nat")
        
        mock_loader = MagicMock()
        mock_loader.prepare_capability_args = MagicMock(side_effect=ValueError("Capability not found"))
        agent.capability_loader = mock_loader
        
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(True, None))
        agent._validate_constraints = MagicMock(return_value=(True, None))
        
        request = AgentRequest(
            action="unknown.capability",
            payload={},
            metadata={'pid': 'PID-TEST-002', 'ecid': 'ECID-TEST-002'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "error"
        assert response.error.code == "UNKNOWN_CAPABILITY"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_generic_routing(self):
        """Test generic task routing"""
        agent = StratAgent(identity="nat")
        
        mock_loader = MagicMock()
        mock_loader.get_capability_for_task = MagicMock(return_value="product.draft_prd_from_prompt")
        mock_loader.prepare_capability_args = MagicMock(return_value=({'requirement': 'test'},))
        mock_loader.execute = AsyncMock(return_value={'prd_content': 'test', 'prd_path': '/test.md'})
        agent.capability_loader = mock_loader
        
        agent.update_task_status = AsyncMock()
        
        task = {
            'task_id': 'task-001',
            'type': 'product',
            'requirement': 'test',
            'objective': 'test',
            'app_name': 'TestApp'
        }
        
        result = await agent.process_task(task)
        
        assert 'prd_content' in result or 'status' in result
        assert mock_loader.get_capability_for_task.called
        assert mock_loader.execute.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_no_capability_mapping(self):
        """Test handling task with no capability mapping"""
        agent = StratAgent(identity="nat")
        
        mock_loader = MagicMock()
        mock_loader.get_capability_for_task = MagicMock(return_value=None)
        agent.capability_loader = mock_loader
        
        task = {
            'task_id': 'task-001',
            'type': 'unknown_type'
        }
        
        result = await agent.process_task(task)
        
        assert result['status'] == 'error'
        assert 'No capability mapping' in result['error']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_message_generic(self):
        """Test generic message handling"""
        agent = StratAgent(identity="nat")
        
        message = MagicMock()
        message.message_type = "test_message"
        message.sender = "test-sender"
        
        # Should just log, no business logic
        await agent.handle_message(message)
        
        # No exceptions should be raised
        assert True


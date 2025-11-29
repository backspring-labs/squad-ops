"""
Unit tests for QAAgent
Tests generic capability routing and refactored agent
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.roles.qa.agent import QAAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse


class TestQAAgent:
    """Test QAAgent"""
    
    def setup_method(self):
        """Reset PathResolver before each test"""
        from agents.utils.path_resolver import PathResolver
        PathResolver.reset()
    
    @pytest.mark.unit
    def test_init(self):
        """Test agent initialization"""
        agent = QAAgent(identity="eve")
        
        assert agent.name == "eve"
        assert agent.agent_type == "quality_assurance"
        assert agent.reasoning_style == "counterfactual"
        assert hasattr(agent, 'validator')
        # Should not have placeholder instance variables
        assert not hasattr(agent, 'state_machine')
        assert not hasattr(agent, 'test_suites')
        assert not hasattr(agent, 'security_protocols')
        assert not hasattr(agent, 'regression_tests')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_test_design(self):
        """Test generic capability routing for test_design"""
        agent = QAAgent(identity="eve")
        
        # Mock capability loader
        mock_loader = MagicMock()
        mock_loader.prepare_capability_args = MagicMock(return_value=({'requirements': 'test requirements'},))
        mock_loader.execute = AsyncMock(return_value={
            'test_plan_uri': '/test-plan.md',
            'test_cases': [],
            'coverage_analysis': {},
            'test_scenarios': []
        })
        agent.capability_loader = mock_loader
        
        # Mock validator
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(True, None))
        agent.validator.validate_result_keys = MagicMock(return_value=(True, None))
        agent._validate_constraints = MagicMock(return_value=(True, None))
        
        request = AgentRequest(
            action="qa.test_design",
            payload={'requirements': 'test requirements'},
            metadata={'pid': 'PID-TEST-001', 'ecid': 'ECID-TEST-001'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "ok"
        assert mock_loader.execute.called
        assert mock_loader.prepare_capability_args.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_test_dev(self):
        """Test generic capability routing for test_dev"""
        agent = QAAgent(identity="eve")
        
        mock_loader = MagicMock()
        mock_loader.prepare_capability_args = MagicMock(return_value=({'test_plan_uri': '/test-plan.md'},))
        mock_loader.execute = AsyncMock(return_value={
            'test_files_uri': ['/test.py'],
            'test_code': {},
            'fixtures_uri': '/conftest.py',
            'test_framework': 'pytest'
        })
        agent.capability_loader = mock_loader
        
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(True, None))
        agent.validator.validate_result_keys = MagicMock(return_value=(True, None))
        agent._validate_constraints = MagicMock(return_value=(True, None))
        
        request = AgentRequest(
            action="qa.test_dev",
            payload={'test_plan_uri': '/test-plan.md'},
            metadata={'pid': 'PID-TEST-002', 'ecid': 'ECID-TEST-002'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "ok"
        assert mock_loader.execute.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_test_execution(self):
        """Test generic capability routing for test_execution"""
        agent = QAAgent(identity="eve")
        
        mock_loader = MagicMock()
        mock_loader.prepare_capability_args = MagicMock(return_value=({'test_files_uri': ['/test.py']},))
        mock_loader.execute = AsyncMock(return_value={
            'passed': 5,
            'failed': 0,
            'report_uri': '/report.json',
            'coverage_percentage': 85.0,
            'execution_log': 'Tests passed'
        })
        agent.capability_loader = mock_loader
        
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(True, None))
        agent.validator.validate_result_keys = MagicMock(return_value=(True, None))
        agent._validate_constraints = MagicMock(return_value=(True, None))
        
        request = AgentRequest(
            action="qa.test_execution",
            payload={'test_files_uri': ['/test.py']},
            metadata={'pid': 'PID-TEST-003', 'ecid': 'ECID-TEST-003'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "ok"
        assert mock_loader.execute.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_unknown_capability(self):
        """Test handling unknown capability"""
        agent = QAAgent(identity="eve")
        
        mock_loader = MagicMock()
        mock_loader.prepare_capability_args = MagicMock(side_effect=ValueError("Capability not found"))
        agent.capability_loader = mock_loader
        
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(True, None))
        agent._validate_constraints = MagicMock(return_value=(True, None))
        
        request = AgentRequest(
            action="unknown.capability",
            payload={},
            metadata={'pid': 'PID-TEST-004', 'ecid': 'ECID-TEST-004'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "error"
        assert response.error.code == "UNKNOWN_CAPABILITY"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_validation_error(self):
        """Test validation error handling"""
        agent = QAAgent(identity="eve")
        
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(False, "Invalid request"))
        
        request = AgentRequest(
            action="qa.test_design",
            payload={},
            metadata={'pid': 'PID-TEST-005', 'ecid': 'ECID-TEST-005'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "error"
        assert response.error.code == "VALIDATION_ERROR"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_generic_routing(self):
        """Test generic task routing"""
        agent = QAAgent(identity="eve")
        
        mock_loader = MagicMock()
        mock_loader.get_capability_for_task = MagicMock(return_value="qa.test_design")
        mock_loader.prepare_capability_args = MagicMock(return_value=({'requirements': 'test'},))
        mock_loader.execute = AsyncMock(return_value={
            'test_plan_uri': '/test-plan.md',
            'test_cases': [],
            'coverage_analysis': {},
            'test_scenarios': []
        })
        agent.capability_loader = mock_loader
        
        agent.update_task_status = AsyncMock()
        
        task = {
            'task_id': 'test-task-001',
            'type': 'test_design',
            'requirements': 'test requirements'
        }
        
        result = await agent.process_task(task)
        
        assert result is not None
        assert 'test_plan_uri' in result
        assert mock_loader.execute.called



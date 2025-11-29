"""
Unit tests for DataAgent
Tests generic capability routing and refactored agent
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.roles.data.agent import DataAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse


class TestDataAgent:
    """Test DataAgent"""
    
    def setup_method(self):
        """Reset PathResolver before each test"""
        from agents.utils.path_resolver import PathResolver
        PathResolver.reset()
    
    @pytest.mark.unit
    def test_init(self):
        """Test agent initialization"""
        agent = DataAgent(identity="data-agent")
        
        assert agent.name == "data-agent"
        assert agent.agent_type == "data_analyst"
        assert agent.reasoning_style == "inductive"
        assert hasattr(agent, 'validator')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_collect_cycle_snapshot(self):
        """Test generic capability routing for collect_cycle_snapshot"""
        agent = DataAgent(identity="data-agent")
        
        # Mock capability loader
        mock_loader = MagicMock()
        mock_loader.prepare_capability_args = MagicMock(return_value=('ECID-WB-001',))
        mock_loader.execute = AsyncMock(return_value={
            'snapshot_path': '/warm-boot/runs/run-001/cycle-snapshot-ECID-WB-001.json',
            'ecid': 'ECID-WB-001',
            'task_count': 10,
            'agent_count': 3
        })
        agent.capability_loader = mock_loader
        
        # Mock validator
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(True, None))
        agent.validator.validate_result_keys = MagicMock(return_value=(True, None))
        agent._validate_constraints = MagicMock(return_value=(True, None))
        
        request = AgentRequest(
            action="data.collect_cycle_snapshot",
            payload={'ecid': 'ECID-WB-001'},
            metadata={'pid': 'PID-TEST-001', 'ecid': 'ECID-WB-001'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "ok"
        assert mock_loader.execute.called
        assert mock_loader.prepare_capability_args.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_profile_cycle_metrics(self):
        """Test generic capability routing for profile_cycle_metrics"""
        agent = DataAgent(identity="data-agent")
        
        mock_loader = MagicMock()
        mock_loader.prepare_capability_args = MagicMock(return_value=('ECID-WB-001',))
        mock_loader.execute = AsyncMock(return_value={
            'metrics_json_path': '/warm-boot/runs/run-001/cycle-metrics-ECID-WB-001.json',
            'metrics_md_path': '/warm-boot/runs/run-001/cycle-metrics-ECID-WB-001.md',
            'ecid': 'ECID-WB-001',
            'metrics_summary': {'total_tasks': 10, 'success_rate': 0.9}
        })
        agent.capability_loader = mock_loader
        
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(True, None))
        agent.validator.validate_result_keys = MagicMock(return_value=(True, None))
        agent._validate_constraints = MagicMock(return_value=(True, None))
        
        request = AgentRequest(
            action="data.profile_cycle_metrics",
            payload={'ecid': 'ECID-WB-001'},
            metadata={'pid': 'PID-TEST-002', 'ecid': 'ECID-WB-001'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "ok"
        assert mock_loader.execute.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_compose_cycle_summary(self):
        """Test generic capability routing for compose_cycle_summary"""
        agent = DataAgent(identity="data-agent")
        
        mock_loader = MagicMock()
        mock_loader.prepare_capability_args = MagicMock(return_value=('ECID-WB-001',))
        mock_loader.execute = AsyncMock(return_value={
            'summary_path': '/warm-boot/runs/run-001/cycle-summary-ECID-WB-001.json',
            'ecid': 'ECID-WB-001',
            'health': 'green',
            'agent_summary': {'max': {'task_count': 5, 'failures': 0, 'success_rate': 1.0}}
        })
        agent.capability_loader = mock_loader
        
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(True, None))
        agent.validator.validate_result_keys = MagicMock(return_value=(True, None))
        agent._validate_constraints = MagicMock(return_value=(True, None))
        
        request = AgentRequest(
            action="data.compose_cycle_summary",
            payload={'ecid': 'ECID-WB-001'},
            metadata={'pid': 'PID-TEST-003', 'ecid': 'ECID-WB-001'}
        )
        
        response = await agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "ok"
        assert mock_loader.execute.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_unknown_capability(self):
        """Test handling unknown capability"""
        agent = DataAgent(identity="data-agent")
        
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
        agent = DataAgent(identity="data-agent")
        
        agent.validator = MagicMock()
        agent.validator.validate_request = MagicMock(return_value=(False, "Invalid request"))
        
        request = AgentRequest(
            action="data.collect_cycle_snapshot",
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
        agent = DataAgent(identity="data-agent")
        
        mock_loader = MagicMock()
        mock_loader.get_capability_for_task = MagicMock(return_value="data.collect_cycle_snapshot")
        mock_loader.prepare_capability_args = MagicMock(return_value=('ECID-WB-001',))
        mock_loader.execute = AsyncMock(return_value={
            'snapshot_path': '/warm-boot/runs/run-001/cycle-snapshot-ECID-WB-001.json',
            'ecid': 'ECID-WB-001',
            'task_count': 10,
            'agent_count': 3
        })
        agent.capability_loader = mock_loader
        
        agent.update_task_status = AsyncMock()
        
        task = {
            'task_id': 'test-task-001',
            'type': 'cycle_analysis',
            'ecid': 'ECID-WB-001'
        }
        
        result = await agent.process_task(task)
        
        assert result is not None
        assert 'snapshot_path' in result
        assert mock_loader.execute.called






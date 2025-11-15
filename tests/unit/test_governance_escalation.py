#!/usr/bin/env python3
"""Unit tests for GovernanceEscalation capability"""

import pytest
from unittest.mock import Mock, AsyncMock
from agents.capabilities.governance_escalation import GovernanceEscalation


@pytest.fixture
def mock_agent():
    """Create a mock agent instance"""
    agent = Mock()
    agent.name = "test-agent"
    agent.escalate_task = AsyncMock()
    return agent


@pytest.fixture
def capability(mock_agent):
    """Create a GovernanceEscalation capability instance"""
    return GovernanceEscalation(mock_agent)


@pytest.mark.asyncio
async def test_escalate_task(capability, mock_agent):
    """Test task escalation"""
    request = {
        'task_id': 'test-task-123',
        'task': {'complexity': 0.9}
    }
    result = await capability.escalate(request)
    
    assert result['escalated'] is True
    assert result['resolution'] == 'escalated_to_premium'
    assert result['escalation_time'] == 1.0
    mock_agent.escalate_task.assert_called_once_with('test-task-123', request['task'])


@pytest.mark.asyncio
async def test_escalate_with_task_in_request(capability, mock_agent):
    """Test escalation when task is in request payload"""
    request = {
        'task_id': 'test-task-456',
        'complexity': 0.9
    }
    result = await capability.escalate(request)
    
    assert result['escalated'] is True
    mock_agent.escalate_task.assert_called_once_with('test-task-456', request)


@pytest.mark.asyncio
async def test_escalate_error_handling(capability, mock_agent):
    """Test error handling in escalation"""
    mock_agent.escalate_task.side_effect = Exception("Escalation failed")
    
    request = {'task_id': 'test-task-789'}
    result = await capability.escalate(request)
    
    assert result['escalated'] is False
    assert result['resolution'] == 'error'
    assert 'error' in result



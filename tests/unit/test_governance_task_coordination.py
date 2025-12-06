#!/usr/bin/env python3
"""Unit tests for GovernanceTaskCoordination capability"""

from unittest.mock import AsyncMock, Mock

import pytest

from agents.capabilities.governance_task_coordination import GovernanceTaskCoordination


@pytest.fixture
def mock_agent():
    """Create a mock agent instance"""
    agent = Mock()
    agent.name = "test-agent"
    agent.send_message = AsyncMock()
    agent.capability_loader = Mock()
    agent.capability_loader.execute = AsyncMock(return_value={'target_agent': 'dev-agent'})
    return agent


@pytest.fixture
def capability(mock_agent):
    """Create a GovernanceTaskCoordination capability instance"""
    return GovernanceTaskCoordination(mock_agent)


@pytest.mark.asyncio
async def test_coordinate_task_delegation(capability, mock_agent):
    """Test task coordination and delegation"""
    request = {
        'type': 'build',
        'payload': {'task_id': 'test-task-123'}
    }
    metadata = {'cycle_id': 'test-ecid'}
    
    result = await capability.coordinate(request, metadata)
    
    assert result['tasks_created'] == 1
    assert result['tasks_delegated'] == 1
    assert 'dev-agent' in result['coordination_log']
    mock_agent.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_coordinate_without_metadata(capability, mock_agent):
    """Test coordination without metadata"""
    request = {'type': 'deploy'}
    
    result = await capability.coordinate(request)
    
    assert result['tasks_created'] == 1
    assert result['tasks_delegated'] == 1


@pytest.mark.asyncio
async def test_coordinate_delegation_target_failure(capability, mock_agent):
    """Test coordination when delegation target determination fails"""
    mock_agent.capability_loader.execute.side_effect = Exception("Target determination failed")
    
    request = {'type': 'build'}
    result = await capability.coordinate(request)
    
    assert result['tasks_created'] == 1
    assert result['tasks_delegated'] == 1
    # Should fallback to 'dev-agent'
    mock_agent.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_coordinate_no_capability_loader(capability, mock_agent):
    """Test coordination without capability loader"""
    capability.capability_loader = None
    
    request = {'type': 'build'}
    result = await capability.coordinate(request)
    
    assert result['tasks_created'] == 1
    assert result['tasks_delegated'] == 1
    # Should fallback to 'dev-agent'
    mock_agent.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_coordinate_error_handling(capability, mock_agent):
    """Test error handling in coordination"""
    mock_agent.send_message.side_effect = Exception("Send failed")
    
    request = {'type': 'build'}
    result = await capability.coordinate(request)
    
    assert result['tasks_created'] == 0
    assert result['tasks_delegated'] == 0
    assert 'error' in result



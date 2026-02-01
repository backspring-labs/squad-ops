#!/usr/bin/env python3
"""Unit tests for WarmBootValidator capability"""

from unittest.mock import AsyncMock, Mock

import pytest

from agents.capabilities.warmboot_validator import WarmBootValidator


@pytest.fixture
def mock_agent():
    """Create a mock agent instance"""
    agent = Mock()
    agent.name = "test-agent"
    agent.process_task = AsyncMock(return_value={
        'status': 'completed',
        'diffs': [],
        'wrap_up_uri': '/warm-boot/runs/test-ecid/wrap-up.md',
        'metrics': {'duration': 10.5}
    })
    return agent


@pytest.fixture
def capability(mock_agent):
    """Create a WarmBootValidator capability instance"""
    return WarmBootValidator(mock_agent)


@pytest.mark.asyncio
async def test_validate_successful_warmboot(capability, mock_agent):
    """Test successful WarmBoot validation"""
    request = {
        'application': 'test-app',
        'request_type': 'warmboot',
        'agents': ['max', 'neo']
    }
    metadata = {
        'cycle_id': 'test-ecid',
        'pid': 'test-pid'
    }
    
    result = await capability.validate(request, metadata)
    
    assert result['match'] is True
    assert result['diffs'] == []
    assert 'wrap_up_uri' in result
    assert 'metrics' in result
    mock_agent.process_task.assert_called_once()


@pytest.mark.asyncio
async def test_validate_failed_warmboot(capability, mock_agent):
    """Test failed WarmBoot validation"""
    mock_agent.process_task.return_value = {
        'status': 'failed',
        'diffs': ['error1', 'error2'],
        'metrics': {}
    }
    
    request = {'application': 'test-app'}
    metadata = {'cycle_id': 'test-ecid'}
    
    result = await capability.validate(request, metadata)
    
    assert result['match'] is False
    assert len(result['diffs']) == 2


@pytest.mark.asyncio
async def test_validate_without_metadata(capability, mock_agent):
    """Test validation without metadata"""
    request = {'application': 'test-app'}
    
    result = await capability.validate(request)
    
    assert 'match' in result
    # Should use default ecid 'unknown'
    mock_agent.process_task.assert_called_once()


@pytest.mark.asyncio
async def test_validate_error_handling(capability, mock_agent):
    """Test error handling in validation"""
    mock_agent.process_task.side_effect = Exception("Validation failed")
    
    request = {'application': 'test-app'}
    metadata = {'cycle_id': 'test-ecid'}
    
    result = await capability.validate(request, metadata)
    
    assert result['match'] is False
    assert 'error' in result



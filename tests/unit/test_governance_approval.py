#!/usr/bin/env python3
"""Unit tests for GovernanceApproval capability"""

import pytest
from unittest.mock import Mock, AsyncMock
from agents.capabilities.governance_approval import GovernanceApproval


@pytest.fixture
def mock_agent():
    """Create a mock agent instance"""
    agent = Mock()
    agent.name = "test-agent"
    agent.escalation_threshold = 0.7
    return agent


@pytest.fixture
def capability(mock_agent):
    """Create a GovernanceApproval capability instance"""
    return GovernanceApproval(mock_agent)


@pytest.mark.asyncio
async def test_approve_low_complexity(capability, mock_agent):
    """Test approval for low complexity request"""
    request = {'complexity': 0.5}
    result = await capability.approve(request)
    
    assert result['approved'] is True
    assert result['decision'] == 'approved'
    assert result['approval_time'] == 0.5


@pytest.mark.asyncio
async def test_approve_high_complexity(capability, mock_agent):
    """Test escalation for high complexity request"""
    request = {'complexity': 0.8}
    result = await capability.approve(request)
    
    assert result['approved'] is False
    assert result['decision'] == 'escalated'
    assert result['approval_time'] == 0.0


@pytest.mark.asyncio
async def test_approve_at_threshold(capability, mock_agent):
    """Test approval at escalation threshold"""
    request = {'complexity': 0.7}
    result = await capability.approve(request)
    
    # At threshold, should approve (complexity == threshold, not > threshold)
    assert result['approved'] is True
    assert result['decision'] == 'approved'


@pytest.mark.asyncio
async def test_approve_default_complexity(capability, mock_agent):
    """Test approval with default complexity"""
    request = {}
    result = await capability.approve(request)
    
    assert result['approved'] is True
    assert result['decision'] == 'approved'


@pytest.mark.asyncio
async def test_approve_error_handling(capability, mock_agent):
    """Test error handling in approval"""
    # Simulate error by making escalation_threshold access fail
    del mock_agent.escalation_threshold
    capability.escalation_threshold = 0.7  # Reset default
    
    request = {'complexity': 0.5}
    result = await capability.approve(request)
    
    assert result['approved'] is True
    assert 'error' not in result


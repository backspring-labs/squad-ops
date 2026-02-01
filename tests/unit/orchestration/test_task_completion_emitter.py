#!/usr/bin/env python3
"""Unit tests for TaskCompletionEmitter capability"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest

from agents.capabilities.task_completion_emitter import TaskCompletionEmitter


@pytest.fixture
def mock_agent():
    """Create a mock agent instance"""
    agent = Mock()
    agent.name = "test-agent"
    agent.send_message = AsyncMock()
    agent.communication_log = []
    agent.task_start_times = {}
    return agent


@pytest.fixture
def capability(mock_agent):
    """Create a TaskCompletionEmitter capability instance"""
    return TaskCompletionEmitter(mock_agent)


@pytest.mark.asyncio
async def test_emit_build_task_completion(capability, mock_agent):
    """Test emitting build task completion event"""
    task_id = 'test-task-123'
    ecid = 'test-ecid'
    result = {
        'action': 'build',
        'status': 'completed',
        'created_files': ['file1.py', 'file2.py'],
        'tests_passed': 5,
        'tests_failed': 0
    }
    
    with patch('os.path.exists', return_value=True):
        with patch('builtins.open', mock_open(read_data=b'test content')):
            with patch('hashlib.sha256') as mock_hash:
                mock_hash.return_value.hexdigest.return_value = 'abc123'
                mock_hash.return_value.update = Mock()
                
                emit_result = await capability.emit(task_id, ecid, result)
    
    assert emit_result['event_sent'] is True
    assert emit_result['task_id'] == task_id
    assert emit_result['cycle_id'] == ecid
    mock_agent.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_emit_with_task_duration(capability, mock_agent):
    """Test emitting with task duration calculation"""
    task_id = 'test-task-456'
    ecid = 'test-ecid'
    
    # Set start time
    start_time = datetime.utcnow()
    capability.task_start_times[task_id] = start_time
    
    result = {
        'action': 'deploy',
        'status': 'completed',
        'created_files': []
    }
    
    emit_result = await capability.emit(task_id, ecid, result)
    
    assert emit_result['event_sent'] is True
    assert task_id not in capability.task_start_times  # Should be cleaned up
    mock_agent.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_emit_archive_task(capability, mock_agent):
    """Test emitting archive task completion"""
    task_id = 'test-task-789'
    ecid = 'test-ecid'
    result = {
        'action': 'archive',
        'status': 'completed'
    }
    
    emit_result = await capability.emit(task_id, ecid, result)
    
    assert emit_result['event_sent'] is True
    # Verify message payload contains correct tasks_completed
    call_args = mock_agent.send_message.call_args
    assert call_args[1]['payload']['tasks_completed'] == ['archive']


@pytest.mark.asyncio
async def test_emit_error_handling(capability, mock_agent):
    """Test error handling in emit"""
    mock_agent.send_message.side_effect = Exception("Send failed")
    
    task_id = 'test-task-error'
    ecid = 'test-ecid'
    result = {'action': 'build', 'status': 'completed'}
    
    emit_result = await capability.emit(task_id, ecid, result)
    
    assert emit_result['event_sent'] is False
    assert 'error' in emit_result



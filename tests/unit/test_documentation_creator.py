#!/usr/bin/env python3
"""Unit tests for DocumentationCreator capability"""

from unittest.mock import AsyncMock, Mock

import pytest

from agents.capabilities.documentation_creator import DocumentationCreator


@pytest.fixture
def mock_agent():
    """Create a mock agent instance"""
    agent = Mock()
    agent.name = "test-agent"
    agent.write_file = AsyncMock()
    return agent


@pytest.fixture
def capability(mock_agent):
    """Create a DocumentationCreator capability instance"""
    return DocumentationCreator(mock_agent)


@pytest.mark.asyncio
async def test_create_documentation(capability, mock_agent):
    """Test creating documentation"""
    task_id = 'test-task-123'
    result = {
        'status': 'completed',
        'action': 'build',
        'app_name': 'test-app',
        'version': '1.0.0',
        'created_files': ['file1.py'],
        'image': 'test-image',
        'container_name': 'test-container'
    }
    
    doc_result = await capability.create(task_id, result)
    
    assert doc_result['documentation_uri'] is not None
    assert doc_result['format'] == 'markdown'
    assert 'test-task-123' in doc_result['documentation_uri']
    assert doc_result['content'] is not None
    assert 'test-app' in doc_result['content']
    mock_agent.write_file.assert_called()


@pytest.mark.asyncio
async def test_create_documentation_minimal_result(capability, mock_agent):
    """Test creating documentation with minimal result"""
    task_id = 'test-task-456'
    result = {'status': 'completed'}
    
    doc_result = await capability.create(task_id, result)
    
    assert doc_result['documentation_uri'] is not None
    assert doc_result['format'] == 'markdown'
    assert doc_result['content'] is not None


@pytest.mark.asyncio
async def test_create_documentation_error_handling(capability, mock_agent):
    """Test error handling in documentation creation"""
    mock_agent.write_file.side_effect = Exception("Write failed")
    
    task_id = 'test-task-error'
    result = {'status': 'completed'}
    
    doc_result = await capability.create(task_id, result)
    
    assert doc_result['documentation_uri'] is None
    assert 'error' in doc_result



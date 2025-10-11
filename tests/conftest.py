#!/usr/bin/env python3
"""
Pytest configuration and fixtures for SquadOps test harness
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, '/app')  # Match agent imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

# Test configuration
TEST_CONFIG = {
    'database_url': 'postgresql://test:test@localhost:5432/squadops_test',
    'redis_url': 'redis://localhost:6379/1',
    'rabbitmq_url': 'amqp://test:test@localhost:5672/',
    'ollama_url': 'http://localhost:11434',
    'log_level': 'DEBUG'
}

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_database():
    """Mock database pool matching asyncpg.Pool"""
    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()
    
    # Mock connection context manager
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetch_one = AsyncMock(return_value={'id': 1, 'status': 'test'})
    mock_conn.fetch_all = AsyncMock(return_value=[{'id': 1, 'status': 'test'}])
    
    # Create a proper async context manager
    class MockConnectionContext:
        def __init__(self, conn):
            self.conn = conn
        
        async def __aenter__(self):
            return self.conn
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    # Make acquire return the context manager
    mock_pool.acquire = MagicMock(return_value=MockConnectionContext(mock_conn))
    
    return mock_pool

@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing"""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    return mock_redis

@pytest.fixture
def mock_rabbitmq():
    """Mock RabbitMQ connection for testing"""
    mock_rmq = AsyncMock()
    mock_rmq.publish.return_value = True
    mock_rmq.consume.return_value = []
    return mock_rmq

@pytest.fixture
def mock_ollama():
    """Mock Ollama LLM for testing"""
    mock_ollama = AsyncMock()
    mock_ollama.generate.return_value = {
        'response': 'Mock LLM response',
        'model': 'test-model',
        'created_at': '2025-01-01T00:00:00Z'
    }
    return mock_ollama

@pytest.fixture
def sample_task():
    """Sample task for testing"""
    return {
        'task_id': 'test-task-001',
        'type': 'development',
        'description': 'Test task for unit testing',
        'requirements': {
            'action': 'test',
            'application': 'test-app',
            'version': '0.1.4.001'
        },
        'complexity': 0.5,
        'priority': 'MEDIUM',
        'ecid': 'test-ecid-001'
    }

@pytest.fixture
def sample_prd():
    """Sample PRD for testing"""
    return """
# Test Application PRD

## Overview
Test application for SquadOps testing

## Core Features
- Feature 1: Basic functionality
- Feature 2: Advanced features
- Feature 3: Integration capabilities

## Technical Requirements
- Web application
- REST API
- Database integration
- Container deployment

## Success Criteria
- Application runs successfully
- All features work as expected
- Performance meets requirements
"""

@pytest.fixture
def sample_agent_message():
    """Sample agent message for testing"""
    return {
        'sender': 'max',
        'recipient': 'neo', 
        'message_type': 'TASK_ASSIGNMENT',
        'payload': {'task_id': 'test-task-001', 'description': 'Test task'},
        'context': {'priority': 'MEDIUM'},
        'timestamp': '2025-01-01T00:00:00Z',
        'message_id': 'msg-001'
    }

@pytest.fixture
def mock_agent_config():
    """Mock agent configuration"""
    return {
        'max': {
            'id': 'max',
            'display_name': 'Max',
            'role': 'lead',
            'model': 'llama3.1:8b',
            'enabled': True,
            'description': 'Task Lead - Governance and coordination'
        },
        'neo': {
            'id': 'neo',
            'display_name': 'Neo',
            'role': 'dev',
            'model': 'qwen2.5:7b',
            'enabled': True,
            'description': 'Developer - Deductive reasoning'
        }
    }

@pytest.fixture
def mock_deployment_config():
    """Mock deployment configuration"""
    return {
        'docker': {
            'registry': 'localhost:5000',
            'tag_prefix': 'squadops',
            'build_context': '/app'
        },
        'services': {
            'web': {
                'port': 8080,
                'health_check': '/health'
            },
            'api': {
                'port': 8000,
                'health_check': '/api/health'
            }
        }
    }

# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "regression: mark test as regression test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location"""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "regression" in str(item.fspath):
            item.add_marker(pytest.mark.regression)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        
        # Mark slow tests
        if "slow" in item.name or "performance" in item.name:
            item.add_marker(pytest.mark.slow)

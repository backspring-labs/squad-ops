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
        'sender': 'lead-agent',
        'recipient': 'dev-agent', 
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
        'lead-agent': {
            'id': 'lead-agent',
            'display_name': 'LeadAgent',
            'role': 'lead',
            'model': 'llama3.1:8b',
            'enabled': True,
            'description': 'Task Lead - Governance and coordination'
        },
        'dev-agent': {
            'id': 'dev-agent',
            'display_name': 'DevAgent',
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

@pytest.fixture
def sample_task_spec():
    """Sample task requirements dict for JSON workflow testing (TaskSpec removed)"""
    return {
        "app_name": "TestApp",
        "version": "1.0.0",
        "run_id": "TEST-001",
        "prd_analysis": "Test application for JSON workflow testing",
        "features": ["Feature 1", "Feature 2"],
        "constraints": {"framework": "vanilla_js"},
        "success_criteria": ["Application loads", "No errors"]
    }

@pytest.fixture
def sample_build_manifest():
    """Sample build manifest dict for JSON workflow testing (BuildManifest removed)"""
    return {
        "architecture": {
            "type": "spa_web_app",
            "framework": "vanilla_js",
            "description": "Test application"
        },
        "files": [
            {
                "path": "index.html",
                "purpose": "Main page",
                "dependencies": []
            },
            {
                "path": "app.js",
                "purpose": "JavaScript logic",
                "dependencies": ["index.html"]
            }
        ],
        "deployment": {
            "container": "nginx:alpine",
            "port": 80,
            "environment": "production"
        }
    }

@pytest.fixture
def app_builder():
    """Real AppBuilder for integration tests"""
    from agents.tools.app_builder import AppBuilder
    from agents.llm.providers.ollama import OllamaClient
    
    # Create real Ollama client with local URL
    llm_client = OllamaClient(url='http://localhost:11434')
    app_builder = AppBuilder(llm_client)
    
    return app_builder

@pytest.fixture
def mock_app_builder():
    """Mock AppBuilder for testing"""
    from agents.tools.app_builder import AppBuilder
    mock_llm_client = MagicMock()
    app_builder = AppBuilder(mock_llm_client)
    
    # Mock the LLM call methods
    app_builder._call_ollama_json = MagicMock()
    app_builder.generate_manifest_json = MagicMock()
    app_builder.generate_files_json = MagicMock()
    app_builder.build_from_task_spec = MagicMock()
    
    return app_builder

@pytest.fixture
def mock_dev_agent():
    """Mock DevAgent for testing"""
    from agents.roles.dev.agent import DevAgent
    agent = DevAgent("test-dev-agent")
    
    # Mock components
    agent.app_builder = MagicMock()
    agent.file_manager = MagicMock()
    agent.docker_manager = MagicMock()
    
    return agent

@pytest.fixture
def mock_lead_agent():
    """Mock LeadAgent for testing"""
    from agents.roles.lead.agent import LeadAgent
    agent = LeadAgent("test-lead-agent")
    
    # Mock messaging components
    agent.send_message = MagicMock()
    agent.update_task_status = MagicMock()
    
    return agent

@pytest.fixture
def mock_unified_config():
    """Mock unified configuration for testing"""
    mock_config = MagicMock()
    
    # Mock infrastructure URLs
    mock_config.get_rabbitmq_url.return_value = 'amqp://test:test@localhost:5672/'
    mock_config.get_postgres_url.return_value = 'postgresql://test:test@localhost:5432/squadops'
    mock_config.get_redis_url.return_value = 'redis://localhost:6379'
    mock_config.get_task_api_url.return_value = 'http://task-api:8001'
    
    # Mock agent config
    mock_config.get_agent_id.return_value = 'test-agent'
    mock_config.get_agent_role.return_value = 'test'
    mock_config.get_agent_display_name.return_value = 'Test Agent'
    
    # Mock LLM config
    mock_config.get_llm_config.return_value = {
        'url': 'http://localhost:11434',
        'model': 'test-model',
        'use_local': True,
        'timeout': 60
    }
    mock_config.get_ollama_url.return_value = 'http://localhost:11434'
    mock_config.get_agent_model.return_value = 'test-model'
    mock_config.get_use_local_llm.return_value = True
    
    return mock_config

@pytest.fixture
def mock_task_api():
    """Mock Task API HTTP responses for testing"""
    from unittest.mock import AsyncMock
    
    class MockResponse:
        def __init__(self, status=200, json_data=None, text_data=""):
            self.status = status
            self._json_data = json_data or {}
            self._text_data = text_data
        
        async def json(self):
            return self._json_data
        
        async def text(self):
            return self._text_data
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            return None
    
    class MockSession:
        def __init__(self):
            self.post_responses = {}
            self.get_responses = {}
        
        def set_post_response(self, url_pattern, status=200, json_data=None):
            """Set response for POST requests matching pattern"""
            self.post_responses[url_pattern] = MockResponse(status, json_data)
        
        def set_get_response(self, url_pattern, status=200, json_data=None):
            """Set response for GET requests matching pattern"""
            self.get_responses[url_pattern] = MockResponse(status, json_data)
        
        async def post(self, url, **kwargs):
            """Mock POST request"""
            for pattern, response in self.post_responses.items():
                if pattern in url:
                    return response
            return MockResponse(200, {"status": "ok"})
        
        async def get(self, url, **kwargs):
            """Mock GET request"""
            for pattern, response in self.get_responses.items():
                if pattern in url:
                    return response
            return MockResponse(200, {"status": "ok"})
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            return None
    
    return MockSession()

@pytest.fixture
def mock_ollama_json_response():
    """Mock Ollama JSON response for testing"""
    return {
        "architecture": {
            "type": "spa_web_app",
            "framework": "vanilla_js",
            "description": "Test application"
        },
        "files": [
            {
                "path": "index.html",
                "purpose": "Main HTML page",
                "dependencies": []
            },
            {
                "path": "app.js",
                "purpose": "JavaScript application logic",
                "dependencies": ["index.html"]
            }
        ],
        "deployment": {
            "container": "nginx:alpine",
            "port": 80,
            "environment": "production"
        }
    }

@pytest.fixture
def mock_files_json_response():
    """Mock files JSON response for testing"""
    return {
        "files": [
            {
                "path": "index.html",
                "content": "<!DOCTYPE html>\n<html>\n<head><title>Test App</title></head>\n<body><h1>Hello World</h1></body>\n</html>"
            },
            {
                "path": "app.js",
                "content": "console.log('Hello from Test App');"
            },
            {
                "path": "styles.css",
                "content": "body { font-family: Arial, sans-serif; }"
            },
            {
                "path": "nginx.conf",
                "content": "server {\n    listen 80;\n    location / {\n        root /usr/share/nginx/html;\n        index index.html;\n    }\n}"
            },
            {
                "path": "Dockerfile",
                "content": "FROM nginx:alpine\nCOPY . /usr/share/nginx/html/\nEXPOSE 80"
            }
        ]
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
    config.addinivalue_line(
        "markers", "smoke: mark test as smoke test"
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
        
        # Mark smoke tests
        if "smoke" in str(item.fspath):
            item.add_marker(pytest.mark.smoke)
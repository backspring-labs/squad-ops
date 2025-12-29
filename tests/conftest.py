#!/usr/bin/env python3
"""
Pytest configuration and fixtures for SquadOps test harness
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, '/app')  # Match agent imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

# IMPORTANT: Patch BaseAgent methods ONLY for unit tests, NOT integration tests
# Integration tests MUST use real services (see tests/integration/README.md)
# Check if we're running integration tests by examining command line arguments and paths
# This check happens at import time, before BaseAgent is imported

def _detect_integration_tests():
    """Detect if integration tests are being run"""
    # Check sys.argv for integration test paths
    for arg in sys.argv:
        # Check for integration directory in paths
        if 'integration' in arg and ('test' in arg.lower() or arg.endswith('.py') or '/' in arg or '\\' in arg):
            return True
        # Check for -m integration marker
        if arg == '-m' and 'integration' in ' '.join(sys.argv):
            return True
    return False

_is_integration_test = _detect_integration_tests()

# Only apply patches if NOT running integration tests
_base_agent_patch1 = None
_base_agent_patch2 = None

if not _is_integration_test:
    try:
        from agents.capabilities.loader import AgentConfig
        
        # Mock LLM client initialization for unit tests only
        _mock_llm_client = MagicMock()
        
        # Create mock function for _initialize_llm_client that returns the mock client
        def _mock_initialize_llm_client(self):
            """Mock _initialize_llm_client to return mock LLM client"""
            return _mock_llm_client
        
        # Mock capability config loading to set minimal config instead of loading from files
        def _mock_load_capability_config(self):
            """Mock _load_capability_config to set minimal config"""
            self.capability_config = AgentConfig(
                agent_id=getattr(self, 'name', 'test-agent'),
                role=getattr(self, 'agent_type', 'test'),
                spec_version='1.0.0',
                implements=[],
                constraints={},
                defaults={'model': 'ollama:test-model'}  # Provide model to prevent LLM init errors
            )
            self.capability_loader = MagicMock()
            self.implemented_capabilities = []
        
        # Apply patches on the import path to ensure they work even if BaseAgent is already imported
        # This patches the methods before any test modules import BaseAgent
        _base_agent_patch1 = patch('agents.base_agent.BaseAgent._initialize_llm_client', _mock_initialize_llm_client)
        _base_agent_patch2 = patch('agents.base_agent.BaseAgent._load_capability_config', _mock_load_capability_config)
        _base_agent_patch1.start()
        _base_agent_patch2.start()
    except ImportError:
        # If modules can't be imported, patches will remain None
        pass

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
    from agents.llm.providers.ollama import OllamaClient
    from agents.tools.app_builder import AppBuilder
    
    # Create real Ollama client with local URL and a real model
    # Use llama3.1:8b as default (should be available for integration tests)
    # Tests should check ollama_available fixture before using this
    llm_client = OllamaClient(url='http://localhost:11434', model='llama3.1:8b')
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
    from unittest.mock import AsyncMock

    from agents.roles.lead.agent import LeadAgent
    agent = LeadAgent("test-lead-agent")
    
    # Mock messaging components
    agent.send_message = MagicMock()
    agent.update_task_status = MagicMock()
    
    # CRITICAL: Mock capability_loader.execute as AsyncMock
    if not hasattr(agent, 'capability_loader') or agent.capability_loader is None:
        agent.capability_loader = MagicMock()
    agent.capability_loader.execute = AsyncMock()
    
    return agent

@pytest.fixture
def mock_unified_config():
    """Mock unified configuration for testing (SIP-051: AppConfig-based)"""
    from infra.config.schema import AppConfig, DBConfig, CommsConfig, RabbitMQConfig, RedisConfig, AgentConfig, LLMConfig
    
    # Create a proper AppConfig mock
    mock_config = MagicMock(spec=AppConfig)
    
    # Mock DB config
    mock_config.db = MagicMock(spec=DBConfig)
    mock_config.db.url = 'postgresql://test:test@localhost:5432/squadops'
    mock_config.db.pool_size = 5
    
    # Mock Comms config
    mock_config.comms = MagicMock(spec=CommsConfig)
    mock_config.comms.rabbitmq = MagicMock(spec=RabbitMQConfig)
    mock_config.comms.rabbitmq.url = 'amqp://test:test@localhost:5672/'
    mock_config.comms.redis = MagicMock(spec=RedisConfig)
    mock_config.comms.redis.url = 'redis://localhost:6379'
    
    # Mock Runtime API URL
    mock_config.runtime_api_url = 'http://runtime-api:8001'
    
    # Mock Agent config
    mock_config.agent = MagicMock(spec=AgentConfig)
    mock_config.agent.id = 'test-agent'
    mock_config.agent.role = 'test'
    mock_config.agent.display_name = 'Test Agent'
    
    # Mock LLM config
    mock_config.llm = MagicMock(spec=LLMConfig)
    mock_config.llm.url = 'http://localhost:11434'
    mock_config.llm.model = 'test-model'
    mock_config.llm.use_local = True
    mock_config.llm.timeout = 60
    
    # Mock Telemetry config
    from infra.config.schema import TelemetryConfig
    from pathlib import Path
    mock_config.telemetry = MagicMock(spec=TelemetryConfig)
    mock_config.telemetry.backend = 'null'
    mock_config.telemetry.otlp_endpoint = None
    mock_config.telemetry.prometheus_port = 8888
    
    # Mock Observability config (including health_check)
    from infra.config.schema import ObservabilityConfig, ServiceConfig
    mock_config.observability = MagicMock(spec=ObservabilityConfig)
    mock_config.observability.health_check = MagicMock(spec=ServiceConfig)
    mock_config.observability.health_check.url = 'http://health-check:8000'
    
    # Mock CycleData config
    from infra.config.schema import CycleDataConfig
    mock_config.cycle_data = MagicMock(spec=CycleDataConfig)
    mock_config.cycle_data.root = Path('/tmp/test-cycle-data')
    
    return mock_config

@pytest.fixture
def mock_task_api():
    """Mock Task API HTTP responses for testing"""
    
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

@pytest.fixture(autouse=True)
def reset_path_resolver():
    """Reset PathResolver cache before each test to ensure isolation"""
    from agents.utils.path_resolver import PathResolver
    PathResolver.reset()
    yield
    PathResolver.reset()  # Also reset after test

# ACI v0.8 Test Fixtures
@pytest.fixture
def sample_task_envelope():
    """Sample TaskEnvelope with all required fields"""
    from agents.tasks.models import TaskEnvelope
    return TaskEnvelope(
        task_id="task-001",
        agent_id="agent-001",
        cycle_id="CYCLE-001",
        pulse_id="pulse-001",
        project_id="project-001",
        task_type="code_generate",
        inputs={"action": "build"},
        correlation_id="corr-CYCLE-001",
        causation_id="cause-root",
        trace_id="trace-placeholder-task-001",
        span_id="span-placeholder-task-001",
    )

@pytest.fixture
def sample_task_envelope_minimal():
    """Minimal TaskEnvelope with required fields only"""
    from agents.tasks.models import TaskEnvelope
    return TaskEnvelope(
        task_id="task-002",
        agent_id="agent-002",
        cycle_id="CYCLE-002",
        pulse_id="pulse-002",
        project_id="project-002",
        task_type="test_execute",
        inputs={},  # Empty but present
        correlation_id="corr-CYCLE-002",
        causation_id="cause-root",
        trace_id="trace-placeholder-task-002",
        span_id="span-placeholder-task-002",
    )

@pytest.fixture
def legacy_task_dict():
    """Legacy task dict format (should be rejected)"""
    return {
        "task_id": "task-003",
        "type": "development",
        "description": "Legacy task",
        "cycle_id": "CYCLE-003",
        # Missing: agent_id, pulse_id, project_id, task_type, inputs, lineage fields
    }

def pytest_configure(config):
    """Configure pytest with custom markers and verify patch application"""
    global _base_agent_patch1, _base_agent_patch2
    
    # Add custom markers
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
    
    # Verify patch application: if integration tests are detected but patches were applied, stop them
    # This is a safety net in case the import-time detection missed something
    test_paths = config.getoption('file_or_dir', default=[])
    has_integration = False
    
    # Check test paths for 'integration' directory
    if test_paths:
        for path in test_paths:
            path_str = str(path)
            if 'integration' in path_str:
                has_integration = True
                break
    
    # Check marker expression for integration marker
    marker_expr = config.getoption('-m', default=None)
    if marker_expr and 'integration' in marker_expr:
        has_integration = True
    
    # If integration tests detected but patches were applied, stop them
    if has_integration and _base_agent_patch1 is not None:
        _base_agent_patch1.stop()
        _base_agent_patch2.stop()
        _base_agent_patch1 = None
        _base_agent_patch2 = None

def pytest_unconfigure(config):
    """Clean up patches after all tests complete"""
    # Stop patches if they were created
    if '_base_agent_patch1' in globals() and _base_agent_patch1:
        _base_agent_patch1.stop()
    if '_base_agent_patch2' in globals() and _base_agent_patch2:
        _base_agent_patch2.stop()

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
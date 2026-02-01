#!/usr/bin/env python3
"""
Unit test configuration and fixtures for SquadOps.

This file contains fixtures specific to unit tests that mock external dependencies.
Integration tests use real services via tests/integration/conftest.py.

Part of SIP-0.8.9 Phase 3: conftest.py split.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Legacy BaseAgent Patching (Unit Tests Only)
# =============================================================================
# IMPORTANT: These patches mock LLM and config loading for unit tests
# Integration tests MUST NOT use these patches

_base_agent_patch1 = None
_base_agent_patch2 = None

try:
    from agents.capabilities.loader import AgentConfig

    # Mock LLM client initialization for unit tests only
    _mock_llm_client = MagicMock()

    def _mock_initialize_llm_client(self):
        """Mock _initialize_llm_client to return mock LLM client"""
        return _mock_llm_client

    def _mock_load_capability_config(self):
        """Mock _load_capability_config to set minimal config"""
        self.capability_config = AgentConfig(
            agent_id=getattr(self, "name", "test-agent"),
            role=getattr(self, "agent_type", "test"),
            spec_version="1.0.0",
            implements=[],
            constraints={},
            defaults={"model": "ollama:test-model"},
        )
        self.capability_loader = MagicMock()
        self.implemented_capabilities = []

    _base_agent_patch1 = patch(
        "agents.base_agent.BaseAgent._initialize_llm_client", _mock_initialize_llm_client
    )
    _base_agent_patch2 = patch(
        "agents.base_agent.BaseAgent._load_capability_config", _mock_load_capability_config
    )
    _base_agent_patch1.start()
    _base_agent_patch2.start()
except ImportError:
    # Legacy modules not available (expected after migration)
    pass


def pytest_unconfigure(config):
    """Clean up patches after unit tests complete"""
    global _base_agent_patch1, _base_agent_patch2
    if _base_agent_patch1:
        _base_agent_patch1.stop()
    if _base_agent_patch2:
        _base_agent_patch2.stop()


# =============================================================================
# Mock Infrastructure Fixtures
# =============================================================================


@pytest.fixture
def mock_database():
    """Mock database pool matching asyncpg.Pool"""
    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetch_one = AsyncMock(return_value={"id": 1, "status": "test"})
    mock_conn.fetch_all = AsyncMock(return_value=[{"id": 1, "status": "test"}])

    class MockConnectionContext:
        def __init__(self, conn):
            self.conn = conn

        async def __aenter__(self):
            return self.conn

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_pool.acquire = MagicMock(return_value=MockConnectionContext(mock_conn))
    return mock_pool


@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing"""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    return mock


@pytest.fixture
def mock_rabbitmq():
    """Mock RabbitMQ connection for testing"""
    mock = AsyncMock()
    mock.publish.return_value = True
    mock.consume.return_value = []
    return mock


@pytest.fixture
def mock_ollama():
    """Mock Ollama LLM for testing"""
    mock = AsyncMock()
    mock.generate.return_value = {
        "response": "Mock LLM response",
        "model": "test-model",
        "created_at": "2025-01-01T00:00:00Z",
    }
    return mock


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_task():
    """Sample task for testing"""
    return {
        "task_id": "test-task-001",
        "type": "development",
        "description": "Test task for unit testing",
        "requirements": {"action": "test", "application": "test-app", "version": "0.1.4.001"},
        "complexity": 0.5,
        "priority": "MEDIUM",
        "ecid": "test-ecid-001",
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
        "sender": "lead-agent",
        "recipient": "dev-agent",
        "message_type": "TASK_ASSIGNMENT",
        "payload": {"task_id": "test-task-001", "description": "Test task"},
        "context": {"priority": "MEDIUM"},
        "timestamp": "2025-01-01T00:00:00Z",
        "message_id": "msg-001",
    }


@pytest.fixture
def mock_agent_config():
    """Mock agent configuration"""
    return {
        "lead-agent": {
            "id": "lead-agent",
            "display_name": "LeadAgent",
            "role": "lead",
            "model": "llama3.1:8b",
            "enabled": True,
            "description": "Task Lead - Governance and coordination",
        },
        "dev-agent": {
            "id": "dev-agent",
            "display_name": "DevAgent",
            "role": "dev",
            "model": "qwen2.5:7b",
            "enabled": True,
            "description": "Developer - Deductive reasoning",
        },
    }


@pytest.fixture
def mock_deployment_config():
    """Mock deployment configuration"""
    return {
        "docker": {"registry": "localhost:5000", "tag_prefix": "squadops", "build_context": "/app"},
        "services": {
            "web": {"port": 8080, "health_check": "/health"},
            "api": {"port": 8000, "health_check": "/api/health"},
        },
    }


@pytest.fixture
def sample_task_spec():
    """Sample task requirements dict for JSON workflow testing"""
    return {
        "app_name": "TestApp",
        "version": "1.0.0",
        "run_id": "TEST-001",
        "prd_analysis": "Test application for JSON workflow testing",
        "features": ["Feature 1", "Feature 2"],
        "constraints": {"framework": "vanilla_js"},
        "success_criteria": ["Application loads", "No errors"],
    }


@pytest.fixture
def sample_build_manifest():
    """Sample build manifest dict for JSON workflow testing"""
    return {
        "architecture": {
            "type": "spa_web_app",
            "framework": "vanilla_js",
            "description": "Test application",
        },
        "files": [
            {"path": "index.html", "purpose": "Main page", "dependencies": []},
            {"path": "app.js", "purpose": "JavaScript logic", "dependencies": ["index.html"]},
        ],
        "deployment": {"container": "nginx:alpine", "port": 80, "environment": "production"},
    }


# =============================================================================
# Mock Agent Fixtures (Legacy)
# =============================================================================


@pytest.fixture
def mock_app_builder():
    """Mock AppBuilder for testing"""
    try:
        from agents.tools.app_builder import AppBuilder

        mock_llm_client = MagicMock()
        app_builder = AppBuilder(mock_llm_client)

        app_builder._call_ollama_json = MagicMock()
        app_builder.generate_manifest_json = MagicMock()
        app_builder.generate_files_json = MagicMock()
        app_builder.build_from_task_spec = MagicMock()

        return app_builder
    except ImportError:
        return MagicMock()


@pytest.fixture
def mock_dev_agent():
    """Mock DevAgent for testing"""
    try:
        from agents.roles.dev.agent import DevAgent

        agent = DevAgent("test-dev-agent")
        agent.app_builder = MagicMock()
        agent.file_manager = MagicMock()
        agent.docker_manager = MagicMock()
        return agent
    except ImportError:
        return MagicMock()


@pytest.fixture
def mock_lead_agent():
    """Mock LeadAgent for testing"""
    try:
        from agents.roles.lead.agent import LeadAgent

        agent = LeadAgent("test-lead-agent")
        agent.send_message = MagicMock()
        agent.update_task_status = MagicMock()

        if not hasattr(agent, "capability_loader") or agent.capability_loader is None:
            agent.capability_loader = MagicMock()
        agent.capability_loader.execute = AsyncMock()

        return agent
    except ImportError:
        return MagicMock()


@pytest.fixture
def mock_unified_config():
    """Mock unified configuration for testing (SIP-051: AppConfig-based)"""
    try:
        from pathlib import Path

        from infra.config.schema import (
            AgentConfig,
            AppConfig,
            CommsConfig,
            CycleDataConfig,
            DBConfig,
            LLMConfig,
            ObservabilityConfig,
            RabbitMQConfig,
            RedisConfig,
            ServiceConfig,
            TelemetryConfig,
        )

        mock_config = MagicMock(spec=AppConfig)

        # DB config
        mock_config.db = MagicMock(spec=DBConfig)
        mock_config.db.url = "postgresql://test:test@localhost:5432/squadops"
        mock_config.db.pool_size = 5

        # Comms config
        mock_config.comms = MagicMock(spec=CommsConfig)
        mock_config.comms.rabbitmq = MagicMock(spec=RabbitMQConfig)
        mock_config.comms.rabbitmq.url = "amqp://test:test@localhost:5672/"
        mock_config.comms.redis = MagicMock(spec=RedisConfig)
        mock_config.comms.redis.url = "redis://localhost:6379"

        mock_config.runtime_api_url = "http://runtime-api:8001"

        # Agent config
        mock_config.agent = MagicMock(spec=AgentConfig)
        mock_config.agent.id = "test-agent"
        mock_config.agent.role = "test"
        mock_config.agent.display_name = "Test Agent"

        # LLM config
        mock_config.llm = MagicMock(spec=LLMConfig)
        mock_config.llm.url = "http://localhost:11434"
        mock_config.llm.model = "test-model"
        mock_config.llm.use_local = True
        mock_config.llm.timeout = 60

        # Telemetry config
        mock_config.telemetry = MagicMock(spec=TelemetryConfig)
        mock_config.telemetry.backend = "null"
        mock_config.telemetry.otlp_endpoint = None
        mock_config.telemetry.prometheus_port = 8888

        # Observability config
        mock_config.observability = MagicMock(spec=ObservabilityConfig)
        mock_config.observability.health_check = MagicMock(spec=ServiceConfig)
        mock_config.observability.health_check.url = "http://health-check:8000"

        # CycleData config
        mock_config.cycle_data = MagicMock(spec=CycleDataConfig)
        mock_config.cycle_data.root = Path("/tmp/test-cycle-data")

        return mock_config
    except ImportError:
        return MagicMock()


# =============================================================================
# Mock HTTP API Fixtures
# =============================================================================


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
            self.post_responses[url_pattern] = MockResponse(status, json_data)

        def set_get_response(self, url_pattern, status=200, json_data=None):
            self.get_responses[url_pattern] = MockResponse(status, json_data)

        async def post(self, url, **kwargs):
            for pattern, response in self.post_responses.items():
                if pattern in url:
                    return response
            return MockResponse(200, {"status": "ok"})

        async def get(self, url, **kwargs):
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
            "description": "Test application",
        },
        "files": [
            {"path": "index.html", "purpose": "Main HTML page", "dependencies": []},
            {"path": "app.js", "purpose": "JavaScript application logic", "dependencies": ["index.html"]},
        ],
        "deployment": {"container": "nginx:alpine", "port": 80, "environment": "production"},
    }


@pytest.fixture
def mock_files_json_response():
    """Mock files JSON response for testing"""
    return {
        "files": [
            {
                "path": "index.html",
                "content": "<!DOCTYPE html>\n<html>\n<head><title>Test App</title></head>\n<body><h1>Hello World</h1></body>\n</html>",
            },
            {"path": "app.js", "content": "console.log('Hello from Test App');"},
            {"path": "styles.css", "content": "body { font-family: Arial, sans-serif; }"},
            {
                "path": "nginx.conf",
                "content": "server {\n    listen 80;\n    location / {\n        root /usr/share/nginx/html;\n        index index.html;\n    }\n}",
            },
            {"path": "Dockerfile", "content": "FROM nginx:alpine\nCOPY . /usr/share/nginx/html/\nEXPOSE 80"},
        ]
    }


# =============================================================================
# Legacy Path Reset Fixture
# =============================================================================


@pytest.fixture(autouse=True)
def reset_path_resolver():
    """Reset PathResolver cache before each test to ensure isolation"""
    try:
        from agents.utils.path_resolver import PathResolver

        PathResolver.reset()
        yield
        PathResolver.reset()
    except ImportError:
        yield


# =============================================================================
# ACI v0.8 TaskEnvelope Fixtures (Legacy)
# =============================================================================


@pytest.fixture
def sample_task_envelope():
    """Sample TaskEnvelope with all required fields"""
    try:
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
    except ImportError:
        # Use new architecture
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task-001",
            task_type="code_generate",
            source_agent="agent-001",
            inputs={"action": "build"},
        )


@pytest.fixture
def sample_task_envelope_minimal():
    """Minimal TaskEnvelope with required fields only"""
    try:
        from agents.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task-002",
            agent_id="agent-002",
            cycle_id="CYCLE-002",
            pulse_id="pulse-002",
            project_id="project-002",
            task_type="test_execute",
            inputs={},
            correlation_id="corr-CYCLE-002",
            causation_id="cause-root",
            trace_id="trace-placeholder-task-002",
            span_id="span-placeholder-task-002",
        )
    except ImportError:
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task-002",
            task_type="test_execute",
            source_agent="agent-002",
            inputs={},
        )


@pytest.fixture
def legacy_task_dict():
    """Legacy task dict format (should be rejected)"""
    return {
        "task_id": "task-003",
        "type": "development",
        "description": "Legacy task",
        "cycle_id": "CYCLE-003",
    }

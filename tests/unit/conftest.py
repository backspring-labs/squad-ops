#!/usr/bin/env python3
"""
Unit test configuration and fixtures for SquadOps.

This file contains fixtures specific to unit tests that mock external dependencies.
Integration tests use real services via tests/integration/conftest.py.

Part of SIP-0.8.9: Modernized to use only new architecture imports.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.tasks.models import TaskEnvelope

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
# Mock Ports Fixtures (New Architecture)
# =============================================================================


@pytest.fixture
def mock_ports():
    """Create mock ports bundle for BaseAgent testing."""
    return {
        "llm": MagicMock(),
        "memory": MagicMock(),
        "prompt_service": MagicMock(),
        "queue": MagicMock(),
        "metrics": MagicMock(),
        "events": MagicMock(),
        "filesystem": MagicMock(),
        "llm_observability": MagicMock(),
    }


@pytest.fixture
def mock_llm_observability():
    """Mock LLMObservabilityPort for testing (SIP-0061)."""
    mock = MagicMock()
    mock.health = AsyncMock(return_value={"status": "ok", "backend": "mock", "details": {}})
    return mock


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_task():
    """Sample task dict for testing"""
    return {
        "task_id": "test-task-001",
        "type": "development",
        "description": "Test task for unit testing",
        "requirements": {"action": "test", "application": "test-app", "version": "0.1.4.001"},
        "complexity": 0.5,
        "priority": "MEDIUM",
    }


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


# =============================================================================
# TaskEnvelope Fixtures (New Architecture)
# =============================================================================


@pytest.fixture
def sample_task_envelope():
    """Sample TaskEnvelope with all required fields (new architecture)"""
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


# =============================================================================
# Mock HTTP API Fixtures
# =============================================================================


@pytest.fixture
def mock_http_session():
    """Mock HTTP session for API testing"""

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

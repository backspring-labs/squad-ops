"""
Unit test configuration and fixtures for SquadOps.

This file contains fixtures specific to unit tests that mock external dependencies.
Integration tests use real services via tests/integration/conftest.py.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


# =============================================================================
# Mock Infrastructure Fixtures
# =============================================================================


@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing"""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
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

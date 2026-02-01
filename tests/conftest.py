#!/usr/bin/env python3
"""
Root pytest configuration for SquadOps test suite.

This file contains ONLY shared configuration:
- Session-scoped fixtures (event_loop)
- pytest hooks for markers and collection
- TEST_CONFIG constants

Unit-specific fixtures are in tests/unit/conftest.py
Integration-specific fixtures are in tests/integration/conftest.py

Part of SIP-0.8.9 Phase 3: conftest.py split.
"""

import asyncio

import pytest

# =============================================================================
# Shared Test Configuration
# =============================================================================

TEST_CONFIG = {
    "database_url": "postgresql://test:test@localhost:5432/squadops_test",
    "redis_url": "redis://localhost:6379/1",
    "rabbitmq_url": "amqp://test:test@localhost:5672/",
    "ollama_url": "http://localhost:11434",
    "log_level": "DEBUG",
}


# =============================================================================
# Session-Scoped Fixtures (Shared)
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# pytest Hooks
# =============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "regression: mark test as regression test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "smoke: mark test as smoke test")
    config.addinivalue_line("markers", "stack_validation: full stack validation tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        fspath = str(item.fspath)

        if "/unit/" in fspath:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in fspath:
            item.add_marker(pytest.mark.integration)
        elif "/regression/" in fspath:
            item.add_marker(pytest.mark.regression)
        elif "/performance/" in fspath:
            item.add_marker(pytest.mark.performance)
        elif "/smoke/" in fspath:
            item.add_marker(pytest.mark.smoke)

        # Mark slow tests
        if "slow" in item.name or "performance" in item.name:
            item.add_marker(pytest.mark.slow)

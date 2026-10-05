#!/usr/bin/env python3
"""
Root pytest configuration for SquadOps test suite.

This file contains ONLY shared configuration:
- pytest hooks for path-based marker assignment
- the signal guard: no test may signal every process (``pytest_configure``)
- TEST_CONFIG constants

Unit-specific fixtures are in tests/unit/conftest.py
Integration-specific fixtures are in tests/integration/conftest.py

Part of SIP-0.8.9 Phase 3: conftest.py split.
"""

import os

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
# pytest Hooks
# =============================================================================

#: The real ``os.kill``/``os.killpg``, kept while the run's guards stand in for them.
_REAL_SIGNALLERS: dict = {}


def _refusing(name: str, real, lowest: int):
    def guarded(target, sig):
        if type(target) is not int or target < lowest:
            raise RuntimeError(
                f"tests/conftest.py refused os.{name}({target!r}, {sig!r}): that signals every "
                "process this user may signal, or the test run's own group. A mocked "
                "process's pid converts to 1; fake the code's own seam instead."
            )
        return real(target, sig)

    return guarded


def pytest_configure(config):
    """No test may signal every process, or its own process group.

    ``os.kill(-1, sig)`` and ``os.killpg(1, sig)`` reach every process the runner's user may
    signal: on a dev box that is the login session, tmux, the agent driving the run and any
    container under the same uid. A mocked process's ``pid`` converts to 1, so one mocked
    subprocess reaching a group kill is ``kill -9 -1``; #1983's first draft did that twice on
    2026-10-05. ``bounded_run.signal_group`` refuses such a target in the code; this is the layer
    under it, for the next signal site that does not go through the helper.
    """
    for name, lowest in (("kill", 1), ("killpg", 2)):
        real = getattr(os, name)
        _REAL_SIGNALLERS[name] = real
        setattr(os, name, _refusing(name, real, lowest))


def pytest_unconfigure(config):
    for name, real in _REAL_SIGNALLERS.items():
        setattr(os, name, real)
    _REAL_SIGNALLERS.clear()


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

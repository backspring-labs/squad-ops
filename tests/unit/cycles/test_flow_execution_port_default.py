"""Tests for FlowExecutionPort.execute_cycle() default implementation (SIP-0083 §5.1).

Verifies the backward-compatible default that delegates to execute_run().
"""

from __future__ import annotations

import pytest

from squadops.ports.cycles.flow_execution import FlowExecutionPort

pytestmark = [pytest.mark.domain_orchestration]


class ConcreteExecutor(FlowExecutionPort):
    """Minimal concrete executor that tracks execute_run() calls."""

    def __init__(self):
        self.execute_run_calls: list[tuple] = []

    async def execute_run(
        self, cycle_id: str, run_id: str, profile_id: str | None = None
    ) -> None:
        self.execute_run_calls.append((cycle_id, run_id, profile_id))

    async def cancel_run(self, run_id: str) -> None:
        pass


class TestExecuteCycleDefault:
    """Default execute_cycle() delegates to execute_run()."""

    async def test_default_delegates_to_execute_run(self):
        """Default execute_cycle() calls execute_run() with same args."""
        executor = ConcreteExecutor()

        await executor.execute_cycle("cyc_001", "run_001", "profile_1")

        assert executor.execute_run_calls == [("cyc_001", "run_001", "profile_1")]

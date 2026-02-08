"""
In-process flow executor adapter (SIP-0064, T8).

Wraps AgentOrchestrator for task dispatch. v0.9.3 scope:
- sequential: submit tasks one at a time
- fan_out_fan_in: submit all, await all
- fan_out_soft_gates: sequential with pause points

Simple dispatch loop, not a workflow engine.
"""

from __future__ import annotations

import logging

from squadops.cycles.models import Cycle, Run, SquadProfile
from squadops.ports.cycles.flow_execution import FlowExecutionPort

logger = logging.getLogger(__name__)


class InProcessFlowExecutor(FlowExecutionPort):
    """In-process flow executor that interprets TaskFlowPolicy.

    For v0.9.3 this is a stub that logs intent. Full orchestrator integration
    will be wired when AgentOrchestrator is updated to accept Cycle/Run context.
    """

    def __init__(self, **kwargs) -> None:
        self._active_runs: set[str] = set()

    async def execute_run(
        self, cycle: Cycle, run: Run, profile: SquadProfile
    ) -> None:
        logger.info(
            "Flow executor: starting run %s for cycle %s (mode=%s)",
            run.run_id,
            cycle.cycle_id,
            cycle.task_flow_policy.mode,
        )
        self._active_runs.add(run.run_id)

    async def cancel_run(self, run_id: str) -> None:
        logger.info("Flow executor: cancelling run %s", run_id)
        self._active_runs.discard(run_id)

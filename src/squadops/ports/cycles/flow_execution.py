"""
FlowExecutionPort — abstract interface for task flow execution (SIP-0064 §7.1).
"""

from abc import ABC, abstractmethod

from squadops.cycles.models import Cycle, Run, SquadProfile


class FlowExecutionPort(ABC):
    """Port for interpreting TaskFlowPolicy and dispatching tasks."""

    @abstractmethod
    async def execute_run(
        self, cycle: Cycle, run: Run, profile: SquadProfile
    ) -> None:
        """Execute a run according to the cycle's TaskFlowPolicy.

        Dispatches tasks, updates Run status via CycleRegistryPort.
        For fan_out_soft_gates: pauses at gate points and awaits decisions.
        """

    @abstractmethod
    async def cancel_run(self, run_id: str) -> None:
        """Cancel an in-progress run execution."""

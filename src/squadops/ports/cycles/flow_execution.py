"""
FlowExecutionPort — abstract interface for task flow execution (SIP-0064 §7.1, SIP-0066 §5.3).
"""

from abc import ABC, abstractmethod


class FlowExecutionPort(ABC):
    """Port for interpreting TaskFlowPolicy and dispatching tasks.

    SIP-0066 breaking change: execute_run takes IDs (not domain objects)
    so the executor can load authoritative state from the registry.
    """

    @abstractmethod
    async def execute_run(self, cycle_id: str, run_id: str, profile_id: str | None = None) -> None:
        """Execute a run by loading authoritative state from registry.

        Dispatches tasks, updates Run status via CycleRegistryPort.
        For fan_out_soft_gates: pauses at gate points and awaits decisions.
        """

    @abstractmethod
    async def cancel_run(self, run_id: str) -> None:
        """Cancel an in-progress run execution."""

    async def execute_cycle(
        self, cycle_id: str, first_run_id: str, profile_id: str | None = None
    ) -> None:
        """Execute a full cycle by iterating over workload_sequence.

        Default implementation delegates to execute_run() for backward
        compatibility with executors that do not support multi-workload
        orchestration. execute_cycle() accepts the already-created first Run
        so cycle creation semantics remain unchanged and the executor can
        begin orchestration from the initial persisted Run.
        """
        await self.execute_run(cycle_id, first_run_id, profile_id)

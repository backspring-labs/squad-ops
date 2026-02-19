"""
CycleRegistryPort — abstract interface for cycle and run persistence (SIP-0064 §7.1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.cycles.models import (
    Cycle,
    CycleStatus,
    GateDecision,
    Run,
    RunStatus,
)
from squadops.cycles.pulse_models import PulseVerificationRecord


class CycleRegistryPort(ABC):
    """Port for cycle and run CRUD, state transitions, and gate decisions."""

    # --- Cycle CRUD ---

    @abstractmethod
    async def create_cycle(self, cycle: Cycle) -> Cycle:
        """Persist a new Cycle and return it."""

    @abstractmethod
    async def get_cycle(self, cycle_id: str) -> Cycle:
        """Return a cycle by ID.

        Raises:
            CycleNotFoundError: If the cycle_id is not found.
        """

    @abstractmethod
    async def list_cycles(
        self,
        project_id: str,
        *,
        status: CycleStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Cycle]:
        """List cycles for a project, optionally filtered by status."""

    @abstractmethod
    async def cancel_cycle(self, cycle_id: str) -> None:
        """Mark a cycle as cancelled (no further runs permitted).

        Raises:
            CycleNotFoundError: If the cycle_id is not found.
        """

    # --- Run CRUD ---

    @abstractmethod
    async def create_run(self, run: Run) -> Run:
        """Persist a new Run and return it."""

    @abstractmethod
    async def get_run(self, run_id: str) -> Run:
        """Return a run by ID.

        Raises:
            RunNotFoundError: If the run_id is not found.
        """

    @abstractmethod
    async def list_runs(
        self, cycle_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[Run]:
        """List runs for a cycle, with pagination."""

    @abstractmethod
    async def update_run_status(self, run_id: str, status: RunStatus) -> Run:
        """Transition a run to a new status.

        Raises:
            RunNotFoundError: If the run_id is not found.
            IllegalStateTransitionError: If the transition is not legal.
        """

    @abstractmethod
    async def cancel_run(self, run_id: str) -> None:
        """Cancel a run.

        Raises:
            RunNotFoundError: If the run_id is not found.
            IllegalStateTransitionError: If the run is in a terminal state.
        """

    @abstractmethod
    async def append_artifact_refs(self, run_id: str, artifact_ids: tuple[str, ...]) -> Run:
        """Append artifact references to a run record.

        De-duplicates: IDs already present on the run are not re-added.

        Raises:
            RunNotFoundError: If the run_id is not found.
        """

    @abstractmethod
    async def record_gate_decision(self, run_id: str, decision: GateDecision) -> Run:
        """Record a gate decision on a run (T11).

        Validation:
        - gate_name must exist in the Cycle's TaskFlowPolicy.gates
        - Run must not be in a terminal state (RunTerminalError)
        - Conflicting decision raises GateAlreadyDecidedError
        - Same decision is idempotent (no-op, return current Run)

        Raises:
            RunNotFoundError: If the run_id is not found.
            ValidationError: If gate_name is not in the policy.
            RunTerminalError: If the run is in a terminal state.
            GateAlreadyDecidedError: If a conflicting decision exists.
        """

    # --- Pulse Verification (SIP-0070) ---

    @abstractmethod
    async def record_pulse_verification(
        self, run_id: str, record: PulseVerificationRecord
    ) -> Run:
        """Persist a pulse verification record for a run.

        Each record is per-suite: contains suite_id + suite_outcome.
        The composite key (run_id, boundary_id, cadence_interval_id,
        suite_id, repair_attempt) uniquely identifies each record.

        Raises:
            RunNotFoundError: If the run_id is not found.
            RunTerminalError: If the run is in a terminal state.
        """

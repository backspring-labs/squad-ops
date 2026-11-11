"""Remote execution port (SIP-0117 R3.3, R4.4).

``RemoteExecutionPort`` is one operation: run a provider's operation for a request and return
its result. Everything about how the operation reaches the provider (a worker that connects
outward, its claim, lease and fence) is behind this port. The handler of
``qa.run_remote_operation`` is its only caller.

``WorkerRegistryStorePort`` is where the runtime keeps the workers, the operations queued for
them and each attempt (R5.4). The rules over those rows are the domain's.

The worker has two ports of its own (R5.5). ``WorkerApiPort`` is the runtime as the worker
calls it, and ``OperationRunnerPort`` is the tool on the worker's machine.

An implementation returns a ``RemoteOperationResult`` for every request it accepts. When the
operation can't run it says so, as ``not_executed`` with the reason; it doesn't raise for
that, and it never returns a pass for an operation that didn't run. It raises for a defect of
the deploy, which is no reading of the operation at all: a runtime that refuses the caller, or
an answer it can't read (R5.6).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING

from squadops.remote_execution.models import RemoteOperationRequest, RemoteOperationResult
from squadops.remote_execution.workers import (
    Attempt,
    Claim,
    Enrolment,
    Fence,
    LeaseReading,
    QueuedOperation,
    RecordedRefusal,
    ResultReading,
    ServedOperation,
    WorkerRegistration,
    WorkerSession,
)

if TYPE_CHECKING:
    from squadops.runtime.models import RuntimeStatus


class RemoteExecutionPort(ABC):
    @abstractmethod
    async def run_operation(self, request: RemoteOperationRequest) -> RemoteOperationResult:
        """Run ``request``'s operation and return what the provider reported."""


class WorkerRegistryTransaction(ABC):
    """The rows of the worker registry, inside one exclusive transaction.

    Rows only: every rule about them is ``squadops.remote_execution.leasing``'s, applied by
    ``squadops.remote_execution.registry.WorkerRegistry``. An implementation stores what it is
    given and returns what it stored.
    """

    @abstractmethod
    async def session(self, session_id: str) -> WorkerSession | None:
        """The session with this id, ended or not."""

    @abstractmethod
    async def live_sessions(self) -> list[WorkerSession]:
        """Every session that has not ended, oldest registration first."""

    @abstractmethod
    async def save_session(self, session: WorkerSession) -> None:
        """Insert the session, or replace the one with its id."""

    @abstractmethod
    async def operation(self, operation_id: str) -> QueuedOperation | None: ...

    @abstractmethod
    async def claimed_operations(self) -> list[QueuedOperation]:
        """Every operation a worker holds."""

    @abstractmethod
    async def queued_operations(self, served: Sequence[ServedOperation]) -> list[QueuedOperation]:
        """The queued operations among ``served``, oldest first."""

    @abstractmethod
    async def save_operation(self, operation: QueuedOperation) -> None:
        """Insert the operation, or replace the one with its id."""

    @abstractmethod
    async def attempt(self, operation_id: str, attempt: int) -> Attempt | None: ...

    @abstractmethod
    async def attempts_of(self, worker_id: str) -> list[Attempt]:
        """The worker's attempts across its sessions, most recent claim first."""

    @abstractmethod
    async def save_attempt(self, attempt: Attempt) -> None:
        """Insert the attempt, or replace the one with its operation and number."""

    @abstractmethod
    async def record_refusal(self, refusal: RecordedRefusal) -> None:
        """Append a refused result. Never replaced or removed."""

    @abstractmethod
    async def refusals(self, operation_id: str) -> list[RecordedRefusal]:
        """The results refused for this operation, in the order they arrived."""


class WorkerRegistryStorePort(ABC):
    """Where the worker registry's rows are kept (SIP-0117 R3.3, R5.4).

    ``exclusive()`` is the one way in: a transaction no other caller's runs beside, whose
    writes all happen or none do. A claim and a late result are decided against the same rows,
    so they are never read in one transaction and written in another.
    """

    @abstractmethod
    def exclusive(self) -> AbstractAsyncContextManager[WorkerRegistryTransaction]:
        """One exclusive transaction. Leaving it by an exception keeps none of its writes."""


class WorkerApiPort(ABC):
    """The runtime's ``/api/v1/workers``, as a worker calls it (SIP-0117 R3.3, R5.5).

    Every call raises ``RuntimeUnreachable`` when it gets no answer, ``WorkerRefused`` when the
    runtime will not serve this worker, and ``RuntimeAnswerUnreadable`` when the answer isn't
    the document expected. None of them is turned into an empty answer.
    """

    @abstractmethod
    async def register(self, registration: WorkerRegistration) -> Enrolment:
        """Register a session for the worker."""

    @abstractmethod
    async def heartbeat(self, session_id: str, runtime_status: RuntimeStatus) -> None:
        """Report the worker's health while it holds no claim. Raises ``UnknownSession`` when
        the runtime has no live session with this id."""

    @abstractmethod
    async def renew(
        self, session_id: str, runtime_status: RuntimeStatus, fence: Fence
    ) -> LeaseReading:
        """Report the worker's health and renew the lease of the claim it holds. Raises
        ``UnknownSession`` as ``heartbeat`` does."""

    @abstractmethod
    async def claim(self, session_id: str) -> Claim | None:
        """Claim the oldest queued operation the session serves, or ``None`` when there is
        none. Raises ``UnknownSession`` as ``heartbeat`` does."""

    @abstractmethod
    async def submit_result(self, fence: Fence, result: RemoteOperationResult) -> ResultReading:
        """Submit the claim's result. A refusal is returned with its reason, never raised."""

    @abstractmethod
    async def close(self) -> None:
        """Release the connection."""


class OperationRunnerPort(ABC):
    """The tool on a worker's machine, running a provider's operations (SIP-0117 R4.2, R5.5).

    ``run`` returns a result for every request. When the operation can't begin it returns
    ``not_executed`` with the reason. It is stopped by cancelling the call, and whatever it
    raises is reported as ``interrupted``, since it had started.
    """

    @abstractmethod
    def serves(self) -> tuple[ServedOperation, ...]:
        """The operations this tool runs, as the worker registers them."""

    @abstractmethod
    async def tool_versions(self) -> Mapping[str, str]:
        """The tool and what it runs with, by name, as the worker registers them."""

    @abstractmethod
    async def health(self) -> RuntimeStatus:
        """Whether the tool can run an operation now, in the canonical health vocabulary."""

    @abstractmethod
    async def run(self, request: RemoteOperationRequest) -> RemoteOperationResult:
        """Run ``request``'s operation and return what it came to."""

    @abstractmethod
    async def reset(self) -> None:
        """Reconcile and reset: leave the tool as a new operation can start from, whatever an
        earlier one left behind. Raises when it can't, and then nothing is run on it."""

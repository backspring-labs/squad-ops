"""Workers, the operations queued for them, and each attempt at one (SIP-0117 R3.3, R5.4).

A worker is a process on another machine that connects outward to the runtime API. It
registers a **session**, claims at most one **operation** under a **lease**, renews the lease
while the operation runs, and submits a result. The runtime believes a result only when the
ids it presents are the current ones: its **fence**.

R3.3 calls the unit of work an assignment. That word is SIP-0089's (an agent's assignment),
so here it is the operation and its attempt (R5.4).

Nothing here decides anything. The rules are ``squadops.remote_execution.leasing``'s, and the
storage is an adapter's behind ``squadops.ports.remote_execution.WorkerRegistryPort``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from squadops.remote_execution.models import RemoteOperationRequest, RemoteOperationResult
from squadops.runtime.models import RuntimeStatus


class OperationState(StrEnum):
    """Where a queued operation is. ``claimed`` is the lease: a worker is busy with it."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    #: It has its result, whichever kind: completed, not executed or interrupted.
    SETTLED = "settled"


class AttemptOutcome(StrEnum):
    """How an attempt ended."""

    #: Its result was accepted.
    ACCEPTED = "accepted"
    #: Its lease ran out, or its worker registered again while holding it.
    EXPIRED = "expired"


class FenceRefusal(StrEnum):
    """Why a fence presented with a heartbeat or a result isn't the current one."""

    UNKNOWN_OPERATION = "unknown_operation"
    #: The operation already has its result, from another attempt.
    ALREADY_SETTLED = "already_settled"
    #: No worker holds the operation: its lease ran out and it waits for a new claim.
    NOT_CLAIMED = "not_claimed"
    STALE_ATTEMPT = "stale_attempt"
    STALE_SESSION = "stale_session"
    STALE_LEASE = "stale_lease"
    #: The ids are the current ones and the lease ran out before this arrived.
    LEASE_EXPIRED = "lease_expired"


@dataclass(frozen=True)
class ServedOperation:
    """One operation of one provider that a worker can run."""

    provider: str
    operation: str


@dataclass(frozen=True)
class WorkerRegistration:
    """What a worker says about itself when it registers (R3.3's first step)."""

    #: The worker's logical identity, the same across its sessions.
    worker_id: str
    platform: str
    tool_versions: Mapping[str, str]
    operations: tuple[ServedOperation, ...]


@dataclass(frozen=True)
class WorkerSession:
    """One registration of a worker. A worker that registers again ends its earlier session."""

    session_id: str
    worker_id: str
    platform: str
    tool_versions: Mapping[str, str]
    operations: tuple[ServedOperation, ...]
    #: What the worker last reported, in the canonical health vocabulary. Whether it is still
    #: being heard from is ``leasing.health``'s to say.
    runtime_status: RuntimeStatus
    registered_at: datetime
    last_heartbeat_at: datetime
    ended_at: datetime | None = None

    def serves(self, provider: str, operation: str) -> bool:
        return ServedOperation(provider, operation) in self.operations


@dataclass(frozen=True)
class Fence:
    """The four ids a heartbeat or a result presents (R3.3). All four are the current ones, or
    it is refused."""

    operation_id: str
    attempt: int
    session_id: str
    lease_id: str


@dataclass(frozen=True)
class QueuedOperation:
    """One operation, from the request for it to its result."""

    operation_id: str
    request: RemoteOperationRequest
    #: Who asked, for the audit: the cycle, run and task ids.
    origin: Mapping[str, str]
    #: How many times it may be claimed. An expiry on the last one settles it as interrupted.
    max_attempts: int
    state: OperationState
    created_at: datetime
    #: The number of the current attempt, or of the last one. 0 before the first claim.
    attempt: int = 0
    lease_id: str | None = None
    session_id: str | None = None
    lease_expires_at: datetime | None = None
    #: Asked to stop. A queued operation settles at once; a claimed one's worker sees this at
    #: its next heartbeat.
    cancel_requested: bool = False
    result: RemoteOperationResult | None = None
    settled_at: datetime | None = None

    @property
    def fence(self) -> Fence | None:
        """The fence of the attempt that holds it, or ``None`` when none does."""
        if self.state is not OperationState.CLAIMED:
            return None
        if self.lease_id is None or self.session_id is None:
            raise ValueError(f"operation {self.operation_id} is claimed and holds no lease")
        return Fence(self.operation_id, self.attempt, self.session_id, self.lease_id)


@dataclass(frozen=True)
class Attempt:
    """One claim of an operation, kept after it ends: the record a late result is read against."""

    operation_id: str
    attempt: int
    session_id: str
    worker_id: str
    lease_id: str
    claimed_at: datetime
    ended_at: datetime | None = None
    outcome: AttemptOutcome | None = None

    @property
    def fence(self) -> Fence:
        return Fence(self.operation_id, self.attempt, self.session_id, self.lease_id)


@dataclass(frozen=True)
class Claim:
    """What a worker is given when it claims: the request, and the fence it runs under."""

    fence: Fence
    request: RemoteOperationRequest
    lease_expires_at: datetime
    #: The worker's last attempt ended without a result, so whatever it left behind is unknown.
    #: It reconciles and resets before it starts this one (R3.3's expiry row).
    reconcile_first: bool = False


@dataclass(frozen=True)
class LeaseReading:
    """What a heartbeat that presented a fence is told about its lease."""

    #: ``None`` when the lease is held, and why it isn't otherwise. A worker told its lease
    #: isn't held stops, resets and claims again.
    refusal: FenceRefusal | None
    expires_at: datetime | None = None
    cancel_requested: bool = False


@dataclass(frozen=True)
class ResultReading:
    """What submitting a result came to."""

    #: ``None`` when the result was accepted, and why it wasn't otherwise.
    refusal: FenceRefusal | None
    #: The same fence submitted the result it had already had accepted. It is answered as
    #: accepted and nothing is stored again.
    replayed: bool = False


@dataclass(frozen=True)
class RecordedRefusal:
    """A result that was refused, kept: a late completion is evidence about a worker."""

    fence: Fence
    refusal: FenceRefusal
    received_at: datetime


@dataclass(frozen=True)
class Enrolment:
    """What a worker is told when it registers: its session, and the cadence to keep."""

    session_id: str
    #: How often to heartbeat, and how long a lease lasts from a claim or a renewal.
    heartbeat: timedelta
    lease: timedelta


class RuntimeUnreachable(Exception):
    """A call to the runtime got no answer: the network, the identity provider or the runtime
    itself is down. The worker tries again."""


class WorkerRefused(Exception):
    """The runtime answered and will not serve this worker: its credentials, its scope, or a
    request the runtime can't read. Trying again changes nothing, so the worker stops."""


class RuntimeAnswerUnreadable(Exception):
    """The runtime's answer isn't the document its caller reads: a key missing or of the
    wrong kind. The two are different versions, so a worker stops and a requester raises."""


class RequestRefused(Exception):
    """The runtime answered and will not take a requester's call: its credentials, its scope,
    or a request the runtime can't read. Trying again changes nothing. It is a defect of the
    deploy, never an operation that didn't run (R5.6)."""


class UnknownSession(LookupError):
    """No live session has this id: it never registered here, or its worker registered again."""


class UnknownOperation(LookupError):
    """No operation has this id."""


@dataclass(frozen=True)
class NoWorker:
    """Why no registered worker can run an operation now, in words for a ``not_executed``."""

    reason: str
    #: The workers that serve the operation and aren't being heard from.
    unreachable: tuple[str, ...] = field(default=())

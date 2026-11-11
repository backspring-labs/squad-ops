"""Request and response bodies of ``/api/v1/workers`` and ``/api/v1/remote-operations``
(SIP-0117 R3.3, R5.4, R5.6).

A request and a result travel as the documents ``squadops.remote_execution.wire`` reads and
writes, so the routes, the store, the worker and the requester share one reading of them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    """A body a worker sends: a key this version doesn't know is refused, never dropped."""

    model_config = ConfigDict(extra="forbid")


class ServedOperationDTO(_Strict):
    provider: str
    operation: str


class WorkerRegistrationRequest(_Strict):
    worker_id: str
    platform: str
    tool_versions: dict[str, str]
    operations: list[ServedOperationDTO]


class WorkerSessionResponse(BaseModel):
    session_id: str
    worker_id: str
    registered_at: datetime
    #: How often to heartbeat and how long a lease lasts, so a worker carries neither number.
    heartbeat_seconds: float
    lease_seconds: float


class FenceDTO(_Strict):
    """The ids of the claim a worker holds. Its session is the one in the path."""

    operation_id: str
    attempt: int
    lease_id: str


class HeartbeatRequest(_Strict):
    runtime_status: str
    #: The claim the worker holds, to renew its lease. Absent when it holds none.
    fence: FenceDTO | None = None


class LeaseDTO(BaseModel):
    #: Whether the lease is still held. When it isn't, ``refusal`` says why, and the worker
    #: stops, resets and claims again.
    held: bool
    refusal: str | None
    expires_at: datetime | None
    cancel_requested: bool


class HeartbeatResponse(BaseModel):
    #: The reading of the fence the heartbeat presented, or ``None`` when it presented none.
    lease: LeaseDTO | None


class ClaimDTO(BaseModel):
    operation_id: str
    attempt: int
    lease_id: str
    lease_expires_at: datetime
    #: The worker's last attempt ended with no result: reconcile and reset before this one.
    reconcile_first: bool
    request: dict[str, Any]


class ClaimResponse(BaseModel):
    #: The operation claimed, or ``None`` when nothing the worker serves is queued or it
    #: already holds a claim.
    claim: ClaimDTO | None


class ResultRequest(_Strict):
    fence: FenceDTO
    result: dict[str, Any]


class ResultResponse(BaseModel):
    accepted: bool
    #: The same claim had already had this result accepted; nothing was stored again.
    replayed: bool


class RemoteOperationCreate(_Strict):
    """A requester's operation to queue (R5.6)."""

    #: The request, as ``wire.request_to_wire`` writes it.
    request: dict[str, Any]
    #: Who asked, for the audit: the agent it ran in. The task and its send are the request's.
    origin: dict[str, str]
    #: How many times a worker may claim it. The requester's to say.
    max_attempts: int = Field(ge=1)


class RemoteOperationResponse(BaseModel):
    """One operation as it stands, for the requester that waits on it."""

    operation_id: str
    #: ``queued``, ``claimed`` or ``settled``.
    state: str
    attempt: int
    max_attempts: int
    cancel_requested: bool
    created_at: datetime
    settled_at: datetime | None
    #: The result as ``wire.result_to_wire`` writes it, once the operation is settled.
    result: dict[str, Any] | None
    #: How long a lease lasts. A claimed operation asked to stop is settled within it: by its
    #: worker, or by its lease running out. So a requester carries no such number itself.
    lease_seconds: float

"""Request and response bodies of ``/api/v1/workers`` (SIP-0117 R3.3, R5.4).

A request and a result travel as the documents ``squadops.remote_execution.wire`` reads and
writes, so the route, the store and the worker share one reading of them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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

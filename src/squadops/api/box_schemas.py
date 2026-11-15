"""``/api/v1/box/lease``'s bodies: the operator's lease on the box, outside every campaign
(SIP-0109 §24dw; #2287)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from squadops.api.campaign_schemas import LeaseResponse
from squadops.campaigns.box import OPERATOR_LEASE_MAX_S, OperatorLeaseEntry


class OperatorLeaseRequest(BaseModel):
    """Take the box: why, under which key, and for how long, at most an hour. Asking again
    while holding it renews it from now."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=200)
    expires_in_s: int = Field(gt=0, le=OPERATOR_LEASE_MAX_S)


class OperatorReleaseRequest(BaseModel):
    """Give the box back, after the last request served on it has finished."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=200)


class OperatorLeaseEntryResponse(BaseModel):
    """One row of the operator lease's log: applied or refused, with what a refusal read."""

    seq: int
    operation: str
    outcome: str
    actor: str
    actor_role: str
    reason: str
    idempotency_key: str
    committed_at: datetime
    expires_in_s: int | None
    refusal: str | None
    reasons: list[str]

    @classmethod
    def of(cls, e: OperatorLeaseEntry) -> OperatorLeaseEntryResponse:
        return cls(
            seq=e.seq,
            operation=e.operation.value,
            outcome=e.outcome.value,
            actor=e.actor,
            actor_role=e.actor_role,
            reason=e.reason,
            idempotency_key=e.idempotency_key,
            committed_at=e.committed_at,
            expires_in_s=e.expires_in_s,
            refusal=e.refusal.value if e.refusal else None,
            reasons=list(e.reasons),
        )


class BoxLeaseResponse(BaseModel):
    """The box's lease, whoever holds it, or ``null`` before any was recorded, and the operator
    lease's latest rows, newest first."""

    lease: LeaseResponse | None
    log: list[OperatorLeaseEntryResponse]


class OperatorLeaseResultResponse(BaseModel):
    """An applied, or replayed, change: its row and the lease it left."""

    entry: OperatorLeaseEntryResponse
    replayed: bool
    lease: LeaseResponse | None

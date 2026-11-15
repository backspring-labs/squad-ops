"""``/api/v1/box/lease``: the operator's lease on the box, outside every campaign (SIP-0109
§24dw; #2287).

§9.3 records one owner of the box at a time. Inside a campaign the supervisor takes it at an
increment gate (``/api/v1/campaigns/{id}/lease``). Between campaigns the operator takes it here,
for its own inference, and every launch and run start waits while it holds it:
- **acquire** only while nobody else holds the box, no run is running or queued, and no campaign
  is live (every one is a draft, paused, escalated or completed); at most an hour, renewed by
  asking again;
- **release** only by the operator holding it. An expired lease holds nothing, and anyone may
  record its return.

Every change is a row of the operator lease's own log, refusals included, and goes to the
security audit. Reading needs ``campaigns:read``; changing it needs ``box:operate``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from squadops.api.box_schemas import (
    BoxLeaseResponse,
    OperatorLeaseEntryResponse,
    OperatorLeaseRequest,
    OperatorLeaseResultResponse,
    OperatorReleaseRequest,
)
from squadops.api.campaign_schemas import LeaseResponse
from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.campaigns.campaigns import actor_from
from squadops.api.runtime.deps import get_audit_port, get_box_reader, get_campaign_registry
from squadops.auth.models import AuditEvent, Identity, Scope
from squadops.campaigns.box import (
    OperatorLeaseChange,
    OperatorLeaseEntry,
    OperatorLeaseOperation,
    OperatorLeaseRefused,
)

router = APIRouter(prefix="/api/v1/box", tags=["box"])

#: The log rows a read returns: the recent handovers, enough to see who has had the box.
LOG_ROWS_SHOWN = 20


@router.get("/lease")
async def get_box_lease(
    request: Request,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_READ)),
) -> BoxLeaseResponse:
    """The box's lease, whoever holds it, and the operator lease's latest rows."""
    registry = get_campaign_registry(request)
    lease = await registry.box_lease()
    log = await registry.operator_lease_log(limit=LOG_ROWS_SHOWN)
    return BoxLeaseResponse(
        lease=LeaseResponse.of(lease, datetime.now(UTC)) if lease is not None else None,
        log=[OperatorLeaseEntryResponse.of(e) for e in log],
    )


@router.post("/lease")
async def acquire_box_lease(
    request: Request,
    body: OperatorLeaseRequest,
    identity: Identity | None = Depends(require_scopes(Scope.BOX_OPERATE)),
) -> OperatorLeaseResultResponse:
    """The operator takes the box. Refused, and recorded, while the supervisor or another
    operator holds it (``box_held``), a run is running or queued (``run_in_flight``), or a
    campaign is live (``campaign_live``)."""
    actor, role = actor_from(identity)
    change = OperatorLeaseChange(
        operation=OperatorLeaseOperation.ACQUIRE,
        actor=actor,
        actor_role=role,
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        expires_in_s=body.expires_in_s,
    )
    runs = await get_box_reader(request).runs_running_or_queued()
    return await _change(request, change, identity, runs)


@router.post("/lease/release")
async def release_box_lease(
    request: Request,
    body: OperatorReleaseRequest,
    identity: Identity | None = Depends(require_scopes(Scope.BOX_OPERATE)),
) -> OperatorLeaseResultResponse:
    """The operator gives the box back. Only the operator holding it may (``not_lease_holder``);
    a lease past its expiry holds nothing, and releasing it records the return."""
    actor, role = actor_from(identity)
    change = OperatorLeaseChange(
        operation=OperatorLeaseOperation.RELEASE,
        actor=actor,
        actor_role=role,
        reason=body.reason,
        idempotency_key=body.idempotency_key,
    )
    return await _change(request, change, identity, ())


async def _change(
    request: Request,
    change: OperatorLeaseChange,
    identity: Identity | None,
    runs: tuple[str, ...],
) -> OperatorLeaseResultResponse:
    registry = get_campaign_registry(request)
    try:
        result = await registry.change_operator_lease(change, runs_in_flight=runs)
    except OperatorLeaseRefused as refused:
        _audit(request, identity, refused.entry)
        raise http_error(
            409,
            "OPERATOR_LEASE_REFUSED",
            f"the box's lease can't {change.operation.value}: {refused.entry.refusal}"
            + (f" ({'; '.join(refused.entry.reasons)})" if refused.entry.reasons else ""),
            {
                "seq": refused.entry.seq,
                "refusal": str(refused.entry.refusal),
                "reasons": list(refused.entry.reasons),
            },
        ) from refused
    if not result.replayed:
        _audit(request, identity, result.entry)
    return OperatorLeaseResultResponse(
        entry=OperatorLeaseEntryResponse.of(result.entry),
        replayed=result.replayed,
        lease=LeaseResponse.of(result.lease, datetime.now(UTC)) if result.lease else None,
    )


def _audit(request: Request, identity: Identity | None, entry: OperatorLeaseEntry) -> None:
    """A change of the operator's lease, to the security audit. Fail-open: the row is the
    record, and it stands whether or not the audit takes it."""
    audit = get_audit_port(request)
    if audit is None:
        return
    try:
        audit.record(
            AuditEvent(
                action=f"box.lease_{entry.operation.value}",
                actor_id=identity.user_id if identity is not None else "anonymous",
                actor_type=identity.identity_type if identity is not None else "unknown",
                resource_type="box",
                resource_id="box",
                result="denied" if entry.refusal else "success",
                denial_reason=str(entry.refusal) if entry.refusal else None,
                metadata=(("seq", str(entry.seq)), ("reason", entry.reason))
                + tuple(("read", r) for r in entry.reasons),
                request_id=request.headers.get("X-Request-ID"),
            )
        )
    except Exception:  # noqa: BLE001 — fail-open, as the port's contract says
        pass

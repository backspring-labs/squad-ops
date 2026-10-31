"""``/api/v1/intervention-ledgers/{campaign_id}``: a campaign's intervention ledger (SIP-0113 §4.3;
#2417).

- **read** (``campaigns:read``): the campaign's interventions, each with its classification, and
  §7 prediction 5's two gaps.
- **classify** and **declare** (``campaigns:supervise``, the supervisor's seat): a control-log row's
  reason and severity, and an action outside the interface.

The ledger never writes a control-log row: the rows are SIP-0109's, and it projects them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from squadops.api.middleware.auth import require_scopes
from squadops.api.outcome_schemas import (
    ClassificationDTO,
    ClassificationRequest,
    DeclaredDTO,
    DeclaredRequest,
    LedgerEntryDTO,
    LedgerResponse,
)
from squadops.api.runtime.deps import get_campaign_registry, get_intervention_ledger
from squadops.auth.models import Identity, Scope
from squadops.campaigns.models import CampaignNotFoundError
from squadops.outcomes.ledger import (
    Classification,
    DeclaredIntervention,
    LedgerInvalid,
    check_classifiable,
    ledger,
)
from squadops.ports.outcomes import InterventionLedgerPort

router = APIRouter(prefix="/api/v1/intervention-ledgers", tags=["outcomes"])


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, "details": None}})


def _actor(identity: Identity | None) -> str:
    return identity.user_id if identity is not None else "system"


def _store(request: Request) -> InterventionLedgerPort:
    store = get_intervention_ledger(request)
    if store is None:
        raise _error(503, "LEDGER_UNAVAILABLE", "the intervention ledger is not configured")
    return store


async def _control_log(request: Request, campaign_id: str):
    registry = get_campaign_registry(request)
    try:
        await registry.get_campaign(campaign_id)
    except CampaignNotFoundError as e:
        raise _error(404, "CAMPAIGN_NOT_FOUND", f"no campaign {campaign_id}") from e
    return await registry.control_log(campaign_id)


def _classification(c: Classification) -> ClassificationDTO:
    return ClassificationDTO(
        entry_id=c.entry_id,
        reason=c.reason,
        severity=c.severity,
        squad_could_resolve=c.squad_could_resolve,
        note=c.note,
        classified_by=c.classified_by,
        classified_at=c.classified_at,
    )


def _declared(d: DeclaredIntervention) -> DeclaredDTO:
    return DeclaredDTO(
        declared_id=d.declared_id,
        reason=d.reason,
        severity=d.severity,
        description=d.description,
        occurred_at=d.occurred_at,
        declared_by=d.declared_by,
        declared_at=d.declared_at,
        squad_could_resolve=d.squad_could_resolve,
    )


@router.get("/{campaign_id}")
async def read_ledger(
    request: Request,
    campaign_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_READ)),
) -> LedgerResponse:
    log = await _control_log(request, campaign_id)
    store = _store(request)
    read = ledger(
        campaign_id,
        log,
        await store.classifications(campaign_id),
        await store.declared(campaign_id),
    )
    return LedgerResponse(
        campaign_id=campaign_id,
        entries=[
            LedgerEntryDTO(
                entry_id=e.entry_id,
                operation=e.operation,
                actor=e.actor,
                at=e.at,
                classification=_classification(e.classification) if e.classification else None,
                declared=_declared(e.declared) if e.declared else None,
            )
            for e in read.entries
        ],
        unclassified=list(read.unclassified),
        orphaned=list(read.orphaned),
        matches_the_control_log=read.matches_the_control_log,
    )


@router.post("/{campaign_id}/classifications", status_code=201)
async def classify(
    request: Request,
    campaign_id: str,
    body: ClassificationRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_SUPERVISE)),
) -> ClassificationDTO:
    log = await _control_log(request, campaign_id)
    try:
        check_classifiable(next((e for e in log if e.entry_id == body.entry_id), None), campaign_id)
    except LedgerInvalid as e:
        raise _error(422, "NOT_AN_INTERVENTION", str(e)) from e
    try:
        classification = Classification(
            entry_id=body.entry_id,
            campaign_id=campaign_id,
            reason=body.reason,
            severity=body.severity,
            classified_by=_actor(identity),
            classified_at=datetime.now(UTC),
            squad_could_resolve=body.squad_could_resolve,
            note=body.note,
        )
    except LedgerInvalid as e:
        raise _error(422, "LEDGER_INVALID", str(e)) from e
    await _store(request).save_classification(classification)
    return _classification(classification)


@router.post("/{campaign_id}/declared", status_code=201)
async def declare(
    request: Request,
    campaign_id: str,
    body: DeclaredRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_SUPERVISE)),
) -> DeclaredDTO:
    await _control_log(request, campaign_id)
    try:
        declared = DeclaredIntervention(
            declared_id=f"dcl_{uuid.uuid4().hex[:12]}",
            campaign_id=campaign_id,
            reason=body.reason,
            severity=body.severity,
            description=body.description,
            occurred_at=body.occurred_at,
            declared_by=_actor(identity),
            declared_at=datetime.now(UTC),
            squad_could_resolve=body.squad_could_resolve,
        )
    except LedgerInvalid as e:
        raise _error(422, "LEDGER_INVALID", str(e)) from e
    await _store(request).save_declared(declared)
    return _declared(declared)

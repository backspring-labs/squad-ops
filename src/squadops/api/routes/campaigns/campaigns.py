"""``/api/v1/campaigns`` — create, read, pause, resume, abort; the control log (SIP-0109 §13).

Each operation is a control-log transition through ``CampaignRegistryPort``, acknowledged only
after its row commits. The scopes are the owner's ruling of 2026-10-02:
- **read** (``campaigns:read``): the campaign and its control log;
- **supervise** (``campaigns:supervise``, the crew's supervisor): pause. Ruling at the increment
  gate and the box lease arrive with step 5;
- **control** (``campaigns:control``, the owner): create, resume, abort.

The actor and role on every row come from the caller's verified token, never from the request
body. Each row is projected to ``AuditPort``, and each applied row to the cycle event bus as
``campaign.transitioned``. Both are best-effort, which is acceptable because the control log, not a
projection, carries completeness (§13).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from squadops.api.campaign_schemas import (
    AcceptedTreeDTO,
    CampaignCreateRequest,
    CampaignObjectiveDTO,
    CampaignPolicyDTO,
    CampaignResponse,
    ControlLogEntryResponse,
    ControlRequest,
    ControlResultResponse,
    ResumeRequest,
)
from squadops.api.middleware.auth import require_scopes
from squadops.auth.models import AuditEvent, Identity, Role, Scope
from squadops.campaigns import lifecycle
from squadops.campaigns.models import (
    Campaign,
    CampaignObjective,
    CampaignOutcome,
    CampaignPolicy,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOperationRefused,
    ControlOutcome,
    TransitionResult,
)
from squadops.cycles.lifecycle import derive_cycle_status
from squadops.cycles.models import CycleStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])

#: The role a control-log row names, first match: the most authoritative the caller holds.
_ROLE_ORDER = (
    Role.ADMIN,
    Role.CAMPAIGN_SUPERVISOR,
    Role.CAMPAIGN_TRIAGE,
    Role.OPERATOR,
    Role.VIEWER,
)
_TERMINAL_CYCLE = frozenset({CycleStatus.COMPLETED, CycleStatus.FAILED, CycleStatus.CANCELLED})


def actor_from(identity: Identity | None) -> tuple[str, str]:
    """Who acted, from the verified token. With auth disabled there is no token, and the row
    says so rather than inventing a name."""
    if identity is None:
        return "anonymous", "unauthenticated"
    held = next((role for role in _ROLE_ORDER if role in identity.roles), "none")
    return identity.user_id, held


def _registry(request: Request):
    from squadops.api.runtime.deps import get_campaign_registry

    return get_campaign_registry(request)


def _project_to_audit(request: Request, entry: ControlLogEntry, identity: Identity | None) -> None:
    """Project a control-log row to the security audit (§13). Fail-open by contract: a failed
    projection is logged and loses no control record."""
    try:
        from squadops.api.runtime.deps import get_audit_port

        audit = get_audit_port(request)
    except Exception:  # noqa: BLE001 — an unwired audit port is a missing projection, not an error
        audit = None
    if audit is None:
        return
    try:
        audit.record(
            AuditEvent(
                action=f"campaign.{entry.operation}",
                actor_id=entry.actor,
                actor_type=(identity.identity_type if identity is not None else "unknown"),
                resource_type="campaign",
                resource_id=entry.campaign_id,
                result="success" if entry.outcome is ControlOutcome.APPLIED else "denied",
                denial_reason=str(entry.refusal) if entry.refusal else None,
                metadata=(
                    ("actor_role", entry.actor_role),
                    ("reason", entry.reason),
                    ("idempotency_key", entry.idempotency_key),
                    ("entry_id", entry.entry_id),
                    ("prior_state", str(entry.prior_state)),
                    ("next_state", str(entry.next_state)),
                ),
                request_id=request.headers.get("X-Request-ID"),
            )
        )
    except Exception:  # noqa: BLE001 — fail-open, as the port's contract says
        logger.warning("campaign audit projection failed: %s", entry.entry_id, exc_info=True)


def _project_to_events(request: Request, result: TransitionResult) -> None:
    """Project an applied control-log row to the cycle event bus (SIP-0077, §13). Best-effort:
    a missed event loses no control record, and the control log is read for the truth."""
    try:
        from squadops.api.runtime.deps import get_cycle_event_bus
        from squadops.events.types import EventType

        entry = result.entry
        get_cycle_event_bus(request).emit(
            EventType.CAMPAIGN_TRANSITIONED,
            entity_type="campaign",
            entity_id=entry.campaign_id,
            context={"campaign_id": entry.campaign_id, "project_id": result.campaign.project_id},
            payload={
                "entry_id": entry.entry_id,
                "operation": str(entry.operation),
                "prior_state": str(entry.prior_state) if entry.prior_state else None,
                "next_state": str(entry.next_state),
                "actor_role": entry.actor_role,
            },
        )
    except Exception:  # noqa: BLE001 — a projection never fails the operation it projects
        logger.warning("campaign event projection failed: %s", result.entry.entry_id, exc_info=True)


def _project(request: Request, result: TransitionResult, identity: Identity | None) -> None:
    if not result.replayed:
        _project_to_audit(request, result.entry, identity)
        _project_to_events(request, result)


async def apply_control(
    request: Request, campaign_id: str, transition: CampaignTransition, identity: Identity | None
) -> TransitionResult:
    try:
        result = await _registry(request).transition(campaign_id, transition)
    except ControlOperationRefused as refused:
        _project_to_audit(request, refused.entry, identity)
        raise
    _project(request, result, identity)
    return result


async def launch_pending(request: Request, result: TransitionResult) -> list[str]:
    """Drain the launch intents (§12b) when this row wrote one, and name the cycle this row's
    intent launched. A replay drains too: its intent may be pending still, if the first attempt
    died before launching. A launch the drain could not make names nothing, and stays pending."""
    if result.intent is None:
        return []
    from squadops.api.runtime.deps import get_campaign_launch

    await get_campaign_launch(request).drain()
    intent = await _registry(request).get_launch_intent(result.intent.launch_id)
    return [intent.cycle_id] if intent.cycle_id else []


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------


@router.post("")
async def create_campaign(
    request: Request,
    body: CampaignCreateRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_CONTROL)),
) -> ControlResultResponse:
    actor, role = actor_from(identity)
    now = datetime.now(UTC)
    try:
        campaign = Campaign(
            campaign_id=body.campaign_id or lifecycle.new_campaign_id(),
            project_id=body.project_id,
            objective=CampaignObjective(
                statement=body.objective.statement,
                allowed_scope=tuple(body.objective.allowed_scope),
                measurement=body.objective.measurement,
            ),
            policy=CampaignPolicy(**body.policy.model_dump()),
            state=CampaignState.DRAFT,
            created_at=now,
            created_by=actor,
            updated_at=now,
        )
        _require_profiles(campaign.policy)
        result = await _registry(request).create_campaign(
            campaign,
            actor=actor,
            actor_role=role,
            reason=body.reason,
            idempotency_key=body.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(
            422, {"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": None}}
        ) from e
    _project(request, result, identity)
    return _result(result)


@router.get("")
async def list_campaigns(
    request: Request,
    project_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_READ)),
) -> list[CampaignResponse]:
    return [_campaign(c) for c in await _registry(request).list_campaigns(project_id)]


@router.get("/{campaign_id}")
async def get_campaign(
    request: Request,
    campaign_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_READ)),
) -> CampaignResponse:
    return _campaign(await _registry(request).get_campaign(campaign_id))


@router.get("/{campaign_id}/control-log")
async def get_control_log(
    request: Request,
    campaign_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_READ)),
) -> list[ControlLogEntryResponse]:
    return [_entry(e) for e in await _registry(request).control_log(campaign_id)]


@router.post("/{campaign_id}/start")
async def start_campaign(
    request: Request,
    campaign_id: str,
    body: ControlRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_CONTROL)),
) -> ControlResultResponse:
    """The owner's start (§17): the draft moves to calibrating, its calibration cycle's launch
    intent written in the same row (§12b), and the cycle is launched by the cycle-create path.
    A campaign that is not a draft refuses the start as stale, and the refusal is recorded."""
    from squadops.campaigns.launch_requests import start_transition

    actor, role = actor_from(identity)
    campaign = await _registry(request).get_campaign(campaign_id)
    try:
        transition = start_transition(
            campaign,
            actor=actor,
            actor_role=role,
            reason=body.reason,
            idempotency_key=body.idempotency_key,
        )
    except FileNotFoundError as e:
        # The policy names a request profile that does not exist: nothing can launch.
        raise HTTPException(status_code=422, detail=str(e)) from e
    result = await apply_control(request, campaign_id, transition, identity)
    return _result(result, launched_cycles=await launch_pending(request, result))


@router.post("/{campaign_id}/pause")
async def pause_campaign(
    request: Request,
    campaign_id: str,
    body: ControlRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_SUPERVISE)),
) -> ControlResultResponse:
    actor, role = actor_from(identity)
    transition = _transition(ControlOperation.PAUSE, CampaignState.PAUSED, body, actor, role)
    return _result(await apply_control(request, campaign_id, transition, identity))


@router.post("/{campaign_id}/resume")
async def resume_campaign(
    request: Request,
    campaign_id: str,
    body: ResumeRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_CONTROL)),
) -> ControlResultResponse:
    """The owner's word (§10, §17).

    - **Paused by a limit:** the action the decision held is executed as recorded, never
      recomputed, and a launch action's intent is written in this row.
    - **Paused by the supervisor:** the campaign returns to the state it was paused from.
    - **Escalated:** the action this ruling names is executed the same way.

    Anything else refuses the resume as stale, and the refusal is recorded.
    """
    from squadops.api.runtime.deps import get_campaign_progress
    from squadops.campaigns.continuation import PendingAction
    from squadops.campaigns.progress import CannotLaunch, held_action

    actor, role = actor_from(identity)
    registry = _registry(request)
    log = await registry.control_log(campaign_id)
    campaign = await registry.get_campaign(campaign_id)
    held = held_action(log) if campaign.state is CampaignState.PAUSED else None
    named = None
    if body.action is not None:
        try:
            named = PendingAction(body.action)
        except ValueError as e:
            raise HTTPException(422, _validation(f"unknown action {body.action!r}")) from e
    if campaign.state is CampaignState.ESCALATED and named is None:
        raise HTTPException(422, _validation("an escalated campaign resumes on a named action"))
    if held is not None and named is not None and named is not held:
        raise HTTPException(
            422, _validation(f"the held action is {held}; a resume executes it as recorded")
        )
    action = held or (named if campaign.state is CampaignState.ESCALATED else None)
    if action is not None:
        try:
            transition = await get_campaign_progress(request).owner_action(
                campaign,
                action,
                held=held is not None,
                actor=actor,
                actor_role=role,
                reason=body.reason,
                idempotency_key=body.idempotency_key,
            )
        except CannotLaunch as e:
            raise HTTPException(422, _validation(str(e))) from e
        result = await apply_control(request, campaign_id, transition, identity)
        return _result(result, launched_cycles=await launch_pending(request, result))
    paused_from = _paused_from(log)
    target = (
        paused_from if campaign.state is CampaignState.PAUSED and paused_from else campaign.state
    )
    transition = _transition(
        ControlOperation.RESUME,
        target,
        body,
        actor,
        role,
        expected_state=CampaignState.PAUSED,
    )
    return _result(await apply_control(request, campaign_id, transition, identity))


def _require_profiles(policy: CampaignPolicy) -> None:
    """Every request profile the policy names must exist: a campaign whose launches could never
    be built is refused at its creation, not discovered at its first launch."""
    from squadops.contracts.cycle_request_profiles import load_profile

    for field in ("calibration_profile", "proposal_profile"):
        try:
            load_profile(getattr(policy, field))
        except FileNotFoundError as e:
            raise ValueError(f"policy.{field}: {e}") from e


def _validation(message: str) -> dict:
    return {"error": {"code": "VALIDATION_ERROR", "message": message, "details": None}}


@router.post("/{campaign_id}/abort")
async def abort_campaign(
    request: Request,
    campaign_id: str,
    body: ControlRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_CONTROL)),
) -> ControlResultResponse:
    """Abort: terminal (§12a). Every cycle the campaign launched that has not ended is
    cancelled by the existing cancel path, and no continuation follows."""
    actor, role = actor_from(identity)
    transition = _transition(
        ControlOperation.ABORT,
        CampaignState.COMPLETED,
        body,
        actor,
        role,
        outcome=CampaignOutcome.ABORTED,
    )
    result = await apply_control(request, campaign_id, transition, identity)
    cancelled = await _cancel_launched_cycles(request, campaign_id)
    return _result(result, cancelled_cycles=cancelled)


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def _transition(
    operation: ControlOperation,
    next_state: CampaignState,
    body: ControlRequest,
    actor: str,
    role: str,
    *,
    expected_state: CampaignState | None = None,
    outcome: CampaignOutcome | None = None,
) -> CampaignTransition:
    stated = CampaignState(body.expected_state) if body.expected_state else None
    try:
        return CampaignTransition(
            operation=operation,
            actor=actor,
            actor_role=role,
            reason=body.reason,
            idempotency_key=body.idempotency_key,
            next_state=next_state,
            outcome=outcome,
            expected_state=stated or expected_state,
        )
    except ValueError as e:
        raise HTTPException(
            422, {"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": None}}
        ) from e


def _paused_from(log: list[ControlLogEntry]) -> CampaignState | None:
    """The state a resume returns the campaign to: the one the latest applied row into
    ``paused`` moved it out of, or ``awaiting_ruling`` when its proposal was submitted to the
    increment gate during the pause (the gate opened while the campaign held, §9.2)."""
    gate_opened = False
    for entry in reversed(log):
        if entry.outcome is not ControlOutcome.APPLIED:
            continue
        if entry.operation is ControlOperation.SUBMIT and entry.prior_state is CampaignState.PAUSED:
            gate_opened = True
        elif (
            entry.next_state is CampaignState.PAUSED
            and entry.prior_state is not CampaignState.PAUSED
        ):
            if gate_opened and entry.prior_state is CampaignState.AT_PROPOSAL:
                return CampaignState.AWAITING_RULING
            return entry.prior_state
    return None


async def _cancel_launched_cycles(request: Request, campaign_id: str) -> list[str]:
    """Cancel, by the existing path, each cycle the campaign launched that has not ended."""
    from squadops.api.routes.cycles.cancellation import cancel_cycle_by_the_existing_path
    from squadops.api.runtime.deps import get_cycle_registry

    cycles = get_cycle_registry(request)
    cancelled: list[str] = []
    for intent in await _registry(request).launch_intents(campaign_id):
        if intent.cycle_id is None:
            continue
        cycle = await cycles.get_cycle(intent.cycle_id)
        status = derive_cycle_status(await cycles.list_runs(cycle.cycle_id), cycle.cancelled)
        if status in _TERMINAL_CYCLE:
            continue
        await cancel_cycle_by_the_existing_path(request, cycle.project_id, cycle.cycle_id)
        cancelled.append(cycle.cycle_id)
    return cancelled


def _campaign(c: Campaign) -> CampaignResponse:
    return CampaignResponse(
        campaign_id=c.campaign_id,
        project_id=c.project_id,
        objective=CampaignObjectiveDTO(
            statement=c.objective.statement,
            allowed_scope=list(c.objective.allowed_scope),
            measurement=c.objective.measurement,
        ),
        policy=CampaignPolicyDTO(
            **{f: getattr(c.policy, f) for f in CampaignPolicyDTO.model_fields}
        ),
        state=str(c.state),
        outcome=str(c.outcome) if c.outcome else None,
        created_at=c.created_at,
        created_by=c.created_by,
        updated_at=c.updated_at,
        accepted=(
            AcceptedTreeDTO(identity=c.accepted.identity, cycle_id=c.accepted.cycle_id)
            if c.accepted
            else None
        ),
    )


def _entry(e: ControlLogEntry) -> ControlLogEntryResponse:
    return ControlLogEntryResponse(
        entry_id=e.entry_id,
        campaign_id=e.campaign_id,
        seq=e.seq,
        operation=str(e.operation),
        actor=e.actor,
        actor_role=e.actor_role,
        reason=e.reason,
        target=e.target,
        idempotency_key=e.idempotency_key,
        binding=dict(e.binding),
        outcome=str(e.outcome),
        refusal=str(e.refusal) if e.refusal else None,
        prior_state=str(e.prior_state) if e.prior_state else None,
        next_state=str(e.next_state),
        committed_at=e.committed_at,
        launch_id=e.launch_id,
    )


def _result(
    result: TransitionResult,
    cancelled_cycles: list[str] | None = None,
    launched_cycles: list[str] | None = None,
):
    return ControlResultResponse(
        campaign=_campaign(result.campaign),
        entry=_entry(result.entry),
        replayed=result.replayed,
        cancelled_cycles=cancelled_cycles or [],
        launched_cycles=launched_cycles or [],
    )

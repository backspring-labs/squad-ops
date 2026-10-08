"""``/api/v1/campaigns`` — create, read, pause, resume, abort; the control log (SIP-0109 §13).

Each operation is a control-log transition through ``CampaignRegistryPort``, acknowledged only
after its row commits. The scopes are the owner's ruling of 2026-10-02:
- **read** (``campaigns:read``): the campaign and its control log;
- **supervise** (``campaigns:supervise``, the crew's supervisor): pause, classify, the box lease,
  and ruling at the increment gate;
- **manage** (``campaigns:manage``, the supervisor and the owner; #1940, SIP-0109 §24az, revising
  that ruling at the owner's request of 2026-10-03): create, start, abort, materialize the package,
  and resume a pause the supervisor made;
- **control** (``campaigns:control``, the owner alone): resume an escalation, a limit's pause or
  the owner's own pause. The resume route reads which one from the row that held the campaign.

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
    ClassificationRequest,
    ControlLogEntryResponse,
    ControlRequest,
    ControlResultResponse,
    EscalationAnswerRequest,
    EscalationResponse,
    LeaseRequest,
    LeaseResponse,
    LeaseResultResponse,
    ResumeRequest,
)
from squadops.api.middleware.auth import holds_scopes, require_scopes
from squadops.auth.models import Identity, Role, Scope
from squadops.campaigns import lifecycle
from squadops.campaigns.escalation import Escalation
from squadops.campaigns.models import (
    Campaign,
    CampaignDefinition,
    CampaignObjective,
    CampaignOutcome,
    CampaignPolicy,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOperationRefused,
    ControlOutcome,
    ResumeReservedToOwner,
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


def _ports(request: Request) -> tuple:
    """The audit port and the event bus, each ``None`` when unwired: a missing projection, not
    an error."""
    from squadops.api.runtime.deps import get_audit_port, get_cycle_event_bus

    try:
        audit = get_audit_port(request)
    except Exception:  # noqa: BLE001
        audit = None
    try:
        events = get_cycle_event_bus(request)
    except Exception:  # noqa: BLE001
        events = None
    return audit, events


def _project_to_audit(request: Request, entry: ControlLogEntry, identity: Identity | None) -> None:
    """A refused row, to the security audit (§13): the route's own projection, with the
    caller's identity type and request id. Fail-open."""
    from squadops.campaigns.projection import project

    audit, _events = _ports(request)
    project(
        audit,
        None,
        entry=entry,
        result=None,
        actor_type=identity.identity_type if identity is not None else "unknown",
        request_id=request.headers.get("X-Request-ID"),
    )


def _project(request: Request, result: TransitionResult, identity: Identity | None) -> None:
    """An applied row, to the audit and the event bus (§13), by the one builder every writer
    uses (``squadops.campaigns.projection``). A replay projects nothing new."""
    from squadops.campaigns.projection import project

    if result.replayed:
        return
    audit, events = _ports(request)
    project(
        audit,
        events,
        entry=result.entry,
        result=result,
        actor_type=identity.identity_type if identity is not None else "unknown",
        request_id=request.headers.get("X-Request-ID"),
    )


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
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_MANAGE)),
) -> ControlResultResponse:
    actor, role = actor_from(identity)
    now = datetime.now(UTC)
    try:
        if body.objective.target_accepted_increments is None:
            # §24ah: a new campaign's measurement has a reader, or row 3 can never stop it in
            # success and it proposes past its objective until a limit stops it.
            raise ValueError(
                "objective.target_accepted_increments is required: the accepted increments "
                "that meet the objective (§10 row 3)"
            )
        campaign = Campaign(
            campaign_id=body.campaign_id or lifecycle.new_campaign_id(),
            project_id=body.project_id,
            objective=CampaignObjective(
                statement=body.objective.statement,
                allowed_scope=tuple(body.objective.allowed_scope),
                measurement=body.objective.measurement,
                target_accepted_increments=body.objective.target_accepted_increments,
            ),
            policy=CampaignPolicy(**body.policy.model_dump()),
            state=CampaignState.DRAFT,
            created_at=now,
            created_by=actor,
            updated_at=now,
        )
        _require_profiles(campaign.policy)
        definition = CampaignDefinition(**body.definition.model_dump()) if body.definition else None
        result = await _registry(request).create_campaign(
            campaign,
            actor=actor,
            actor_role=role,
            reason=body.reason,
            idempotency_key=body.idempotency_key,
            definition=definition,
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
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_MANAGE)),
) -> ControlResultResponse:
    """The start (§17), the owner's or the supervisor's (#1940): the draft moves to calibrating, its calibration cycle's launch
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
    # SIP-0110 §0.7: the campaign pins its memory snapshot at admission, before its calibration
    # launches, so every proposal and cycle of it selects from one snapshot.
    await _pin_memory(request, result.campaign)
    return _result(result, launched_cycles=await launch_pending(request, result))


async def _pin_memory(request: Request, campaign) -> None:
    """A pin that fails is logged and the campaign starts; its seams record recall as failed.
    Repeated (a replayed start, a restart), it returns the first pin."""
    from datetime import UTC, datetime

    from squadops.api.runtime.deps import get_memory_store
    from squadops.memory.pinning import pin_campaign

    store = get_memory_store(request)
    if store is None:
        return
    try:
        await pin_campaign(store, campaign, now=datetime.now(UTC))
    except Exception:
        logger.warning(
            "memory_snapshot_not_pinned campaign=%s", campaign.campaign_id, exc_info=True
        )


@router.post("/{campaign_id}/classifications")
async def classify_proposal(
    request: Request,
    campaign_id: str,
    body: ClassificationRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_SUPERVISE)),
) -> ControlResultResponse:
    """The supervisor's classification of what went wrong with a proposal version (§9.4): a
    record, accepted after the campaign has ended. A version never submitted to the gate cannot
    be classified."""
    from squadops.campaigns.models import ProposalClassification

    try:
        classification = ProposalClassification(body.classification)
    except ValueError as e:
        raise HTTPException(
            422, _validation(f"unknown classification {body.classification!r}")
        ) from e
    log = await _registry(request).control_log(campaign_id)
    submitted = any(
        e.operation == ControlOperation.SUBMIT
        and e.outcome == ControlOutcome.APPLIED
        and (e.binding.get("proposal_id"), e.binding.get("version"))
        == (body.proposal_id, body.version)
        for e in log
    )
    if not submitted:
        raise HTTPException(
            422,
            _validation(f"{body.proposal_id} v{body.version} was never submitted to the gate"),
        )
    actor, role = actor_from(identity)
    transition = CampaignTransition(
        operation=ControlOperation.CLASSIFY,
        actor=actor,
        actor_role=role,
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        next_state=None,
        target=body.proposal_id,
        binding={
            "proposal_id": body.proposal_id,
            "version": body.version,
            "classification": classification.value,
        },
    )
    return _result(await apply_control(request, campaign_id, transition, identity))


@router.get("/{campaign_id}/escalations")
async def list_escalations(
    request: Request,
    campaign_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_READ)),
) -> list[EscalationResponse]:
    """The plan-review tier's escalations (§24bj, §24bk), each in its state, with its late
    answer when one is recorded."""
    from squadops.campaigns.escalation import escalations

    campaign = await _registry(request).get_campaign(campaign_id)
    return [
        _escalation(e)
        for e in escalations(await _registry(request).control_log(campaign_id), campaign.state)
    ]


@router.post("/{campaign_id}/escalations/{escalation_id}/answer")
async def answer_escalation(
    request: Request,
    campaign_id: str,
    escalation_id: str,
    body: EscalationAnswerRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_SUPERVISE)),
) -> ControlResultResponse:
    """A late answer to an expired or cancelled escalation (§24bj's ruling 4, §24bl): a record,
    accepted after the campaign ended. It never reopens the campaign or resumes the parked cycle;
    a later plan gate of the project reads it by the decision's id."""
    from squadops.campaigns.escalation import answer_refusal, answer_transition, escalations

    campaign = await _registry(request).get_campaign(campaign_id)
    found = next(
        (
            e
            for e in escalations(await _registry(request).control_log(campaign_id), campaign.state)
            if e.escalation_id == escalation_id
        ),
        None,
    )
    refusal = answer_refusal(found, body.answer)
    if refusal is not None:
        raise HTTPException(422, _validation(refusal))
    assert found is not None
    actor, role = actor_from(identity)
    transition = answer_transition(
        found, body.answer, actor=actor, actor_role=role, reason=body.reason
    )
    return _result(await apply_control(request, campaign_id, transition, identity))


@router.get("/{campaign_id}/ledger")
async def read_ledger(
    request: Request,
    campaign_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_READ)),
) -> list[dict]:
    """The proposal ledger (§9.4), read from the control log: per proposal version, its
    submission, its ruling, its cycle's outcome and its classification."""
    import dataclasses

    from squadops.campaigns.ledger import ledger

    await _registry(request).get_campaign(campaign_id)
    return [
        dataclasses.asdict(e) for e in ledger(await _registry(request).control_log(campaign_id))
    ]


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
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_MANAGE)),
) -> ControlResultResponse:
    """The owner's word (§10, §17), or the supervisor's on its own pause (#1940, §24az).

    Who may resume is read from the row that held the campaign (``owner_held``): an escalation,
    a limit's pause and the owner's pause need ``campaigns:control``, and a supervisor asking is
    refused 403 before anything is written.

    - **Paused by a limit:** the action the decision held is executed as recorded, never
      recomputed, and a launch action's intent is written in this row.
    - **Paused by the supervisor:** the campaign returns to the state it was paused from.
    - **Escalated:** the action this ruling names is executed the same way.

    Anything else refuses the resume as stale, and the refusal is recorded.
    """
    from squadops.api.runtime.deps import get_campaign_progress
    from squadops.campaigns.continuation import PendingAction
    from squadops.campaigns.progress import CannotLaunch, held_action, owner_held

    actor, role = actor_from(identity)
    registry = _registry(request)
    log = await registry.control_log(campaign_id)
    campaign = await registry.get_campaign(campaign_id)
    held_by_owner = owner_held(campaign, log)
    if held_by_owner is not None and not holds_scopes(request, Scope.CAMPAIGNS_CONTROL):
        raise ResumeReservedToOwner(campaign_id, held_by_owner)
    held = held_action(log) if campaign.state is CampaignState.PAUSED else None
    named = None
    if body.action is not None:
        try:
            named = PendingAction(body.action)
        except ValueError as e:
            raise HTTPException(422, _validation(f"unknown action {body.action!r}")) from e
    from squadops.campaigns.launch_blocking import escalated_by_a_refused_launch

    refused = escalated_by_a_refused_launch(campaign, log)
    if refused is not None:
        refused_from, launch_id = refused
        # #1971: the cycle-create path refused the launch, which is still pending. The owner's
        # word returns the campaign to the state it was written from, and the drain re-attempts
        # it: launched if what refused it is fixed, escalated again if not. An action would write
        # a second launch beside the pending one.
        if named is not None:
            raise HTTPException(
                422,
                _validation(
                    "the refused launch is still pending: resume without an action to retry it "
                    "once what refused it is fixed, or abort the campaign"
                ),
            )
        transition = _transition(
            ControlOperation.RESUME,
            refused_from,
            body,
            actor,
            role,
            expected_state=CampaignState.ESCALATED,
        )
        result = await apply_control(request, campaign_id, transition, identity)
        return _result(result, launched_cycles=await _retry_launch(request, launch_id, result))
    if campaign.state is CampaignState.ESCALATED and named is None:
        from squadops.campaigns.launch_blocking import escalated_by_a_blocked_launch

        if escalated_by_a_blocked_launch(campaign, log):
            # §9.3 (#1802): the launch it escalated over is still pending. The owner's word
            # returns it to launch_blocked, re-attempted at once and counted afresh.
            transition = _transition(
                ControlOperation.RESUME,
                CampaignState.LAUNCH_BLOCKED,
                body,
                actor,
                role,
                expected_state=CampaignState.ESCALATED,
            )
            return _result(await apply_control(request, campaign_id, transition, identity))
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


@router.get("/{campaign_id}/lease")
async def get_lease(
    request: Request,
    campaign_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_READ)),
) -> LeaseResponse | None:
    """The box's lease (§9.3; #1802), or ``null`` before any was recorded. The box is one, so
    every campaign reads the same lease; the campaign must exist."""
    await _registry(request).get_campaign(campaign_id)
    lease = await _registry(request).box_lease()
    return _lease(lease) if lease is not None else None


@router.post("/{campaign_id}/lease")
async def acquire_lease(
    request: Request,
    campaign_id: str,
    body: LeaseRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_SUPERVISE)),
) -> LeaseResultResponse:
    """The supervisor takes the box for this campaign's increment gate (§9.3).

    Refused, and recorded, outside the gate (``gate_not_open``), while any run is in flight on
    the box (``run_in_flight``), or while another supervisor holds it (``box_held``). While it
    holds the box, every cycle launch is refused and every run start waits.
    """
    from squadops.api.runtime.deps import get_box_reader

    campaign = await _registry(request).get_campaign(campaign_id)
    if body.expires_in_s > campaign.policy.lease_expiry_s:
        raise HTTPException(
            422,
            _validation(
                f"expires_in_s {body.expires_in_s} exceeds the policy's lease_expiry_s "
                f"{campaign.policy.lease_expiry_s}"
            ),
        )
    actor, role = actor_from(identity)
    transition = _lease_transition(
        ControlOperation.LEASE_ACQUIRE,
        body,
        actor,
        role,
        {"held_by": actor, "expires_in_s": body.expires_in_s},
    )
    runs = await get_box_reader(request).runs_in_flight()
    return await _change_lease(request, campaign_id, transition, identity, runs)


@router.post("/{campaign_id}/lease/release")
async def release_lease(
    request: Request,
    campaign_id: str,
    body: ControlRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_SUPERVISE)),
) -> LeaseResultResponse:
    """The supervisor gives the box back, its models unloaded (§9.3). Only the holder of a live
    lease may; an expired lease holds nothing, and releasing it records the return."""
    actor, role = actor_from(identity)
    transition = _lease_transition(
        ControlOperation.LEASE_RELEASE, body, actor, role, {"held_by": actor}
    )
    return await _change_lease(request, campaign_id, transition, identity, ())


def _lease_transition(
    operation: ControlOperation, body: ControlRequest, actor: str, role: str, binding: dict
) -> CampaignTransition:
    return CampaignTransition(
        operation=operation,
        actor=actor,
        actor_role=role,
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        next_state=None,
        binding=binding,
    )


async def _change_lease(
    request: Request,
    campaign_id: str,
    transition: CampaignTransition,
    identity: Identity | None,
    runs_in_flight: tuple[str, ...],
) -> LeaseResultResponse:
    registry = _registry(request)
    try:
        result = await registry.change_box_lease(
            campaign_id, transition, runs_in_flight=runs_in_flight
        )
    except ControlOperationRefused as refused:
        _project_to_audit(request, refused.entry, identity)
        raise
    _project(request, result, identity)
    lease = await registry.box_lease()
    return LeaseResultResponse(
        entry=_entry(result.entry), replayed=result.replayed, lease=_lease(lease)
    )


def _lease(lease) -> LeaseResponse:
    from datetime import UTC, datetime

    return LeaseResponse(
        holder=str(lease.holder),
        held_by=lease.held_by,
        campaign_id=lease.campaign_id,
        acquired_at=lease.acquired_at,
        expires_at=lease.expires_at,
        supervisor_holds=lease.supervisor_holds(datetime.now(UTC)),
    )


def _require_profiles(policy: CampaignPolicy) -> None:
    """Every request profile the policy names must exist, and the proposal profile must reach
    the increment ruling: a campaign whose launches could never be built, or whose increments
    could never be ruled, is refused at its creation, not discovered at its first launch."""
    from squadops.campaigns.gate import increment_sequence_refusal
    from squadops.contracts.cycle_request_profiles import load_profile

    profiles = {}
    for field in ("calibration_profile", "proposal_profile"):
        try:
            profiles[field] = load_profile(getattr(policy, field))
        except FileNotFoundError as e:
            raise ValueError(f"policy.{field}: {e}") from e
    # The increments are launched from the proposal profile: one that never reaches the ruling
    # would escalate every increment the campaign proposes.
    refusal = increment_sequence_refusal(profiles["proposal_profile"].defaults)
    if refusal:
        raise ValueError(f"policy.proposal_profile {policy.proposal_profile!r}: {refusal}")


async def _materialize_after_close(request: Request, campaign_id: str) -> None:
    """A closed campaign's package (§14). The close is committed whatever happens here; a
    failure is logged loudly, and ``POST …/package`` materializes it later from the same
    records."""
    try:
        from squadops.api.runtime.deps import get_campaign_progress

        await get_campaign_progress(request).materialize_package(campaign_id)
    except Exception:
        logger.exception("campaign_package_not_materialized", extra={"campaign_id": campaign_id})


async def _retry_launch(request: Request, launch_id: str, result: TransitionResult) -> list[str]:
    """After the owner's resume of a refused launch (#1971): drain, so the pending intent is
    attempted again now, and name its cycle when it launched. When it was refused again it names
    none, and the drain's own row has escalated the campaign anew. A replay drains nothing."""
    from squadops.api.runtime.deps import get_campaign_launch

    if result.replayed:
        return []
    await get_campaign_launch(request).drain()
    intent = await _registry(request).get_launch_intent(launch_id)
    return [intent.cycle_id] if intent.cycle_id else []


def _escalation(e: Escalation) -> EscalationResponse:
    return EscalationResponse(
        escalation_id=e.escalation_id,
        cycle_id=e.cycle_id,
        run_id=e.run_id,
        gate_name=e.gate_name,
        state=str(e.state),
        opened_at=e.opened_at,
        failed=[{"condition": c, "reading": r} for c, r in e.failed],
        questions=list(e.questions),
        decision_ids=list(e.decision_ids),
        closed_by=e.closed_by,
        closed_at=e.closed_at,
        answer=e.answer,
        answered_by=e.answered_by,
        answered_at=e.answered_at,
    )


def _validation(message: str) -> dict:
    return {"error": {"code": "VALIDATION_ERROR", "message": message, "details": None}}


@router.post("/{campaign_id}/abort")
async def abort_campaign(
    request: Request,
    campaign_id: str,
    body: ControlRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_MANAGE)),
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
    if not result.replayed:
        await _materialize_after_close(request, campaign_id)
    return _result(result, cancelled_cycles=cancelled)


@router.post("/{campaign_id}/package")
async def materialize_package(
    request: Request,
    campaign_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_MANAGE)),
) -> dict:
    """Materialize the campaign's evidence package and digest now (§14, #1710): a projection
    of its records, idempotent by identity. A campaign's close materializes it on its own."""
    from squadops.api.runtime.deps import get_campaign_progress

    await _registry(request).get_campaign(campaign_id)  # 404 before anything is written
    pkg_identity, package_id, digest_id = await get_campaign_progress(request).materialize_package(
        campaign_id
    )
    return {
        "identity": pkg_identity,
        "package_artifact_id": package_id,
        "digest_artifact_id": digest_id,
    }


@router.get("/{campaign_id}/package")
async def read_package(
    request: Request,
    campaign_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_READ)),
) -> dict:
    """The latest stored evidence package's identity and its digest (the morning read)."""
    from squadops.api.runtime.deps import get_artifact_vault
    from squadops.campaigns.progress import EVIDENCE_ARTIFACT_TYPE

    campaign = await _registry(request).get_campaign(campaign_id)
    vault = get_artifact_vault(request)
    digests = sorted(
        (
            r
            for r in await vault.list_artifacts(
                project_id=campaign.project_id, artifact_type=EVIDENCE_ARTIFACT_TYPE
            )
            if r.metadata.get("campaign_id") == campaign_id and r.metadata.get("part") == "digest"
        ),
        key=lambda r: str(r.created_at),
    )
    if not digests:
        raise HTTPException(
            404,
            {
                "error": {
                    "code": "PACKAGE_NOT_FOUND",
                    "message": f"campaign {campaign_id} has no evidence package yet",
                    "details": None,
                }
            },
        )
    ref, content = await vault.retrieve(digests[-1].artifact_id)
    return {
        "identity": ref.metadata.get("identity"),
        "digest_artifact_id": ref.artifact_id,
        "digest": content.decode("utf-8"),
    }


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
            target_accepted_increments=c.objective.target_accepted_increments,
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

"""
Run API routes (SIP-0064 §9.4).
"""

import dataclasses
import hashlib
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from squadops.api.cycle_schemas import (
    CheckpointSummaryResponse,
    GateDecisionRequest,
    RunCancelResponse,
    RunResponse,
    RunResumeRequest,
    TaskInstructionDTO,
)
from squadops.api.errors import http_error
from squadops.api.middleware.auth import holds_scopes, require_scopes
from squadops.api.paging import Page, page
from squadops.api.routes.cycles.mapping import compute_workload_progress, run_to_response
from squadops.api.runtime.deps import (
    get_artifact_vault,
    get_cycle_event_bus,
    get_cycle_registry,
    get_flow_executor,
    get_memory_records,
    get_reference_resolvers,
)
from squadops.auth.models import Identity, Scope
from squadops.campaigns.gate import INCREMENT_RULING_GATE, ruling_transition
from squadops.campaigns.models import ProposalBinding
from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.cycles.gate_attribution import compose_decided_by
from squadops.cycles.gate_decisions import record_gate_decision
from squadops.cycles.lifecycle import (
    TERMINAL_STATES,
    compute_config_hash,
    resolve_cycle_status,
)
from squadops.cycles.models import (
    Cycle,
    CycleStatus,
    GateDecision,
    GateDecisionValue,
    IllegalStateTransitionError,
    Run,
    RunStatus,
    RunTerminalError,
    ValidationError,
    validate_waiver_request,
    validate_workload_type,
)
from squadops.events.types import EventType
from squadops.memory.observations import PLAN_REVIEW_GATE
from squadops.memory.pinning import cycle_binding
from squadops.memory.records import RecordRefused, Source, SourceKind, TaskTarget
from squadops.memory.reference_binding import bound_for_cycle
from squadops.memory.task_instructions import admitted, requested_references
from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
from squadops.ports.memory.records import RecordConflict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/cycles/{cycle_id}/runs", tags=["runs"])


def _resolve_retry_workload_type(cycle: Cycle, existing_runs: list[Run]) -> str | None:
    """Positional workload resolution for retry-created runs (#433).

    Mirrors the executor's ``_starting_workload_index`` semantics (D14: runs
    map positionally to workloads): the new run's index among the cycle's
    non-cancelled runs selects its ``workload_sequence`` entry — the same
    resolution ``cycles create`` applies at position 0 (#26). Legacy cycles
    (no sequence) keep ``None``. An out-of-bounds position is rejected rather
    than falling back to a ``None``-typed run, which on a multi-workload
    cycle silently produces the legacy plan shape with no artifact seeding.
    To re-attempt a failed workload at the same position, cancel the failed
    run first (or pass ``workload_type`` explicitly).
    """
    workload_sequence = cycle.resolved_config().get("workload_sequence", [])
    if not workload_sequence:
        return None
    non_cancelled = [r for r in existing_runs if r.status != RunStatus.CANCELLED.value]
    position = len(non_cancelled)
    if position >= len(workload_sequence):
        # #880: the overflow IS the natural retry — a failed run still occupies
        # its slot, so a fresh attempt at the SAME position lands one past the
        # end. Resolve to the latest non-cancelled run's own workload_type (the
        # executor maps typed runs to their type's position, so both runs share
        # the slot). The old error's advice was a closed loop: cancelling a
        # terminal run is refused by design, and the run this creates would
        # have sat queued forever regardless.
        latest = max(non_cancelled, key=lambda r: r.run_number, default=None)
        latest_type = getattr(latest, "workload_type", None) if latest else None
        if latest_type:
            return latest_type
        raise ValidationError(
            f"Cannot resolve workload_type for retry: the new run would occupy "
            f"position {position} but workload_sequence has {len(workload_sequence)} "
            f"entries, and the latest run carries no workload_type to re-attempt. "
            f"Pass workload_type explicitly — or use `runs resume` to re-run the "
            f"failed run in place from its checkpoint."
        )
    return workload_sequence[position]["type"]


@router.post("", status_code=201, dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def create_run(
    request: Request,
    project_id: str,
    cycle_id: str,
    background_tasks: BackgroundTasks,
    workload_type: str | None = None,
) -> RunResponse:
    """Create a new Run (retry) for an existing Cycle and enqueue its execution.

    Mirrors ``cycles create`` / ``resume_run``: the new run is dispatched
    server-side (not just recorded), so a retry actually re-runs (#133).
    """

    validated_wt = validate_workload_type(workload_type)
    registry = get_cycle_registry(request)
    cycle = await registry.get_cycle(cycle_id)
    existing_runs = await registry.list_runs(cycle_id)
    run_number = len(existing_runs) + 1

    if validated_wt is None:
        validated_wt = _resolve_retry_workload_type(cycle, existing_runs)

    config_hash = compute_config_hash(cycle.applied_defaults, cycle.execution_overrides)

    run = Run(
        run_id=f"run_{uuid.uuid4().hex[:12]}",
        cycle_id=cycle_id,
        run_number=run_number,
        status="queued",
        initiated_by="retry",
        resolved_config_hash=config_hash,
        workload_type=validated_wt,
    )
    created = await registry.create_run(run)

    # SIP-0077: run.created

    get_cycle_event_bus(request).emit(
        EventType.RUN_CREATED,
        entity_type="run",
        entity_id=created.run_id,
        context={
            "cycle_id": cycle_id,
            "run_id": created.run_id,
            "project_id": project_id,
        },
        payload={
            "run_number": created.run_number,
            "initiated_by": created.initiated_by,
            "workload_type": created.workload_type,
        },
    )

    # Enqueue execution so the retry run actually proceeds (#133) — creating
    # the run record alone never ran it (only cycle-create/resume dispatched).
    # Mirrors resume_run; execute_cycle re-runs the §2.5 duty guard, so a
    # still-active hard-duty window simply re-defers.

    background_tasks.add_task(
        get_flow_executor(request).execute_cycle,
        cycle_id,
        created.run_id,
        cycle.squad_profile_id,
    )

    return run_to_response(created)


@router.get("", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_runs(
    request: Request,
    project_id: str,
    cycle_id: str,
    workload_type: str | None = None,
    page: Page = Depends(page),
) -> list[RunResponse]:
    """A page of the cycle's runs, in run order (#1976)."""

    registry = get_cycle_registry(request)
    runs = await registry.list_runs(
        cycle_id, workload_type=workload_type, limit=page.limit, offset=page.offset
    )
    return [run_to_response(r) for r in runs]


@router.get("/{run_id}", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_run(request: Request, project_id: str, cycle_id: str, run_id: str) -> RunResponse:

    registry = get_cycle_registry(request)
    run = await registry.get_run(run_id)
    return run_to_response(run)


@router.post("/{run_id}/cancel", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def cancel_run(
    request: Request, project_id: str, cycle_id: str, run_id: str
) -> RunCancelResponse:

    registry = get_cycle_registry(request)
    # The run state machine gained a COMPLETED -> CANCELLED edge so the executor can
    # supersede a framing run whose plan was auto-rejected (#522). That edge is for
    # the orchestrator, not for operators: cancelling a run that already finished is
    # not a cancel, it is a rewrite of what happened. Refuse it here so this surface
    # behaves exactly as it did before that edge existed.
    existing = await registry.get_run(run_id)
    if RunStatus(existing.status) in TERMINAL_STATES:
        raise IllegalStateTransitionError(
            f"Cannot transition Run from '{existing.status}' to 'cancelled'"
        )
    # Cancellation bypasses the executor's finalize path, so everything
    # finalize would have torn down has to be torn down here: the Prefect
    # flow run (#77), the focus leases the run holds (#529), and the cycle's
    # open activity rows (#561).
    # deferred (cycle): api.routes.cycles.cancellation loads this module
    from squadops.api.routes.cycles.cancellation import cancel_run_by_the_existing_path

    return await cancel_run_by_the_existing_path(request, project_id, cycle_id, run_id)


async def _gate_scopes(request: Request, gate_name: str) -> Identity | None:
    """The increment gate is the campaign supervisor's (``campaigns:supervise``); every other
    gate is a cycle write. One route, so a campaign's ruling goes through the existing gate path
    (SIP-0109 §9.2) and an operator's cycle writes never reach it.

    #2837: the plan gate is a cycle write, or the campaign supervisor's on a cycle a campaign
    launched, as the runbook says the supervisor answers plan gates. Which cycle it is is read in
    the route (``_supervisor_answers_a_campaign_plan_gate``), since the scope check can't see it."""
    if gate_name == INCREMENT_RULING_GATE:
        return await require_scopes(Scope.CAMPAIGNS_SUPERVISE)(request)
    if gate_name == PLAN_REVIEW_GATE and not holds_scopes(request, Scope.CYCLES_WRITE):
        return await require_scopes(Scope.CAMPAIGNS_SUPERVISE)(request)
    return await require_scopes(Scope.CYCLES_WRITE)(request)


async def _supervisor_answers_a_campaign_plan_gate(
    request: Request, registry, cycle_id: str
) -> None:
    """#2837: a caller ruling the plan gate on ``campaigns:supervise`` alone may do so only on a
    cycle a campaign launched. An operator's own cycle stays a cycle write."""
    if holds_scopes(request, Scope.CYCLES_WRITE):
        return
    cycle = await registry.get_cycle(cycle_id)
    if getattr(cycle, "campaign_id", None) is None:
        raise http_error(
            403,
            "FORBIDDEN",
            "the plan gate of a cycle no campaign launched is a cycle write (cycles:write)",
        )


#: The decisions a ruling's task instructions may go with: an approval launches the work they direct.
_INSTRUCTING = frozenset({"approved", "approved_with_refinements"})


async def _ruling_instructions(
    request: Request, cycle: Cycle, run_id: str, body: GateDecisionRequest, actor: str
) -> tuple:
    """The approval's task instructions as records of the ruled cycle (SIP-0110 Appendix A §3.5;
    #2178), checked before the ruling's row is written. Their source is the gate's decision, so
    they are the cycle's admitted inputs, never interventions. Their ids come from the cycle, the
    ruling's retry key and what each says, so a repeated ruling replays its row, and one repeating
    the key with other instructions conflicts with it rather than keeping the first silently."""
    if not body.task_instructions:
        return ()
    if body.decision not in _INSTRUCTING:
        raise ValidationError("a ruling's task instructions go with an approval")
    if get_memory_records(request) is None:
        raise ValidationError("no store holds task instructions")
    store = get_memory_records(request)
    ids = [
        _ruling_record_id(cycle.cycle_id, body.idempotency_key or "", n, given)
        for n, given in enumerate(body.task_instructions)
    ]
    # One already stored was stored by this ruling's applied attempt, which a repeat replays as it
    # stands: its framing may have dispatched since, and its reference is bound already (T16).
    stored = {rid: await store.get(rid) for rid in ids}
    fresh = [(rid, given) for rid, given in zip(ids, body.task_instructions, strict=True)
             if stored[rid] is None]  # fmt: skip
    # deferred (cycle): api.routes.memory.interventions loads api.routes.campaigns, which loads this
    from squadops.api.routes.memory.interventions import refuse_dispatched

    requested = [given.model_dump() for _, given in fresh]
    try:
        for item in requested:
            await refuse_dispatched(
                request, cycle, TaskTarget(cycle.cycle_id, tuple(item.get("task_types") or ()))
            )
        # T16: bound with the ruled cycle, after the refusals that read no reference.
        bound = await bound_for_cycle(
            requested_references(requested), get_reference_resolvers(request), cycle_binding(cycle)
        )
        built = admitted(
            requested,
            project_id=cycle.project_id,
            cycle_id=cycle.cycle_id,
            actor=actor,
            now=datetime.now(UTC),
            instructable=lambda t: authoring_seam_of(t) is not None,
            source=Source(
                SourceKind.GATE_DECISION,
                {"cycle_id": cycle.cycle_id, "run_id": run_id, "gate": INCREMENT_RULING_GATE},
            ),
            bound=bound,
        )
    except RecordRefused as e:
        raise ValidationError(str(e)) from e
    made = {
        rid: dataclasses.replace(r, record_id=rid) for (rid, _), r in zip(fresh, built, strict=True)
    }
    return tuple(stored[rid] or made[rid] for rid in ids)


def _ruling_record_id(cycle_id: str, key: str, n: int, given: TaskInstructionDTO) -> str:
    # The cycle too: a retry key is unique within a campaign, and a record id in the whole store.
    content = given.model_dump_json()
    return "mrec_" + hashlib.sha256(f"{cycle_id}|{key}|{n}|{content}".encode()).hexdigest()[:16]


async def _store_ruling_instructions(request: Request, records: tuple) -> None:
    """Store an applied ruling's instructions before its cycle's framing dispatches. One an
    earlier attempt of the same ruling stored is kept as it was."""
    store = get_memory_records(request)
    for record in records:
        try:
            await store.create(record)
        except RecordConflict:
            continue  # the ruling was repeated: its first attempt stored this one


async def _rule_increment(
    request: Request,
    registry,
    cycle_id: str,
    run_id: str,
    body: GateDecisionRequest,
    identity: Identity | None,
) -> bool:
    """SIP-0109 §9.2: the ruling's control-log row first, checked in its own transaction
    against the proposal at the gate and the accepted tree; the gate decision follows it.

    A stale, conflicting or illegal ruling is refused there and recorded (409), and decides
    nothing. Returns whether the gate decision is still to be recorded: a repeated ruling
    replays its row, and records the decision only if the first attempt never did.
    """
    # deferred (cycle): api.routes.campaigns.campaigns loads this module
    from squadops.api.routes.campaigns.campaigns import actor_from, apply_control

    reason = (body.notes or "").strip()
    missing = [
        name
        for name, value in (
            ("binding", body.binding),
            ("idempotency_key", body.idempotency_key),
            ("notes (the ruling's reason)", reason),
        )
        if not value
    ]
    if missing:
        raise ValidationError(f"the {INCREMENT_RULING_GATE} gate requires {', '.join(missing)}")
    if body.waived_checks or body.waiver_reason:
        raise ValidationError(f"the {INCREMENT_RULING_GATE} gate takes no waiver")
    cycle = await registry.get_cycle(cycle_id)
    if not cycle.campaign_id:
        raise ValidationError(f"cycle {cycle_id} belongs to no campaign")
    actor, role = actor_from(identity)
    # deferred (cycle): as _ruling_instructions' own import
    from squadops.api.routes.memory.interventions import dispatch_turn, turn_of

    # #2545: the ruling's task instructions are checked against the cycle's dispatches and stored
    # in the unit's dispatch turn, so none of its dispatches composes between the two.
    async with dispatch_turn(request, turn_of(cycle) if body.task_instructions else None):
        instructions = await _ruling_instructions(request, cycle, run_id, body, actor)
        try:
            transition = ruling_transition(
                GateDecisionValue(body.decision),
                ProposalBinding(**body.binding.model_dump()),
                run_id=run_id,
                actor=actor,
                actor_role=role,
                reason=reason,
                idempotency_key=body.idempotency_key,
                classification=body.classification,
                classification_rationale=body.classification_rationale,
                instruction_ids=tuple(r.record_id for r in instructions),
            )
        except ValueError as e:  # §24bi: a return names what went wrong, or it is refused
            raise ValidationError(str(e)) from e
        await apply_control(request, cycle.campaign_id, transition, identity)
        await _store_ruling_instructions(request, instructions)
    run = await registry.get_run(run_id)
    return not any(d.gate_name == INCREMENT_RULING_GATE for d in run.gate_decisions)


@router.post("/{run_id}/gates/{gate_name}")
async def gate_decision(
    project_id: str,
    cycle_id: str,
    run_id: str,
    gate_name: str,
    body: GateDecisionRequest,
    request: Request,
    identity: Identity | None = Depends(_gate_scopes),
) -> RunResponse:

    registry = get_cycle_registry(request)
    if gate_name == PLAN_REVIEW_GATE:
        await _supervisor_answers_a_campaign_plan_gate(request, registry, cycle_id)

    if gate_name == INCREMENT_RULING_GATE:
        if not await _rule_increment(request, registry, cycle_id, run_id, body, identity):
            return run_to_response(await registry.get_run(run_id))
    elif (
        any(
            value is not None
            for value in (
                body.binding,
                body.idempotency_key,
                body.classification,
                body.classification_rationale,
            )
        )
        or body.task_instructions
    ):
        raise ValidationError(
            "binding, idempotency_key, classification and task_instructions belong to the "
            f"{INCREMENT_RULING_GATE} gate only"
        )

    # SIP-0096 §6.5 (#682): accept-with-waiver is explicit, reasoned, and
    # validated against the run's own unverified disclosure — a waiver
    # records above the evidence and can never touch a check that ran.
    if body.waived_checks or body.waiver_reason:
        summary = await registry.get_run_verification_summary(run_id)
        unverified_ids = {u.check_id for u in summary.unverified} if summary is not None else None
        waiver_error = validate_waiver_request(
            body.decision, body.waived_checks, body.waiver_reason, unverified_ids
        )
        if waiver_error is not None:
            raise ValidationError(waiver_error)

    # #812: was a hardcoded "system" with a TODO beside it, so every human approval
    # carried the word that means "no human was involved" — the same namespace the
    # machine paths use. The identity was available the whole time.
    decision = GateDecision(
        gate_name=gate_name,
        decision=body.decision,
        decided_by=compose_decided_by(
            getattr(request.state, "identity", None), body.decided_by_kind
        ),
        decided_at=datetime.now(UTC),
        notes=body.notes,
        waived_checks=tuple(body.waived_checks),
        waiver_reason=body.waiver_reason,
    )
    # #1986: one recorder for every decider: the row, the promotion an approval implies
    # (SIP-0086), and one `gate.decided` shape (SIP-0077 §7.3).

    updated = await record_gate_decision(
        registry,
        _artifact_vault_or_none(request, run_id),
        get_cycle_event_bus(request),
        project_id=project_id,
        cycle_id=cycle_id,
        run_id=run_id,
        decision=decision,
    )

    return run_to_response(updated)


@router.post("/{run_id}/resume", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def resume_run(
    request: Request,
    project_id: str,
    cycle_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    body: RunResumeRequest | None = None,
) -> RunResponse:
    """Resume a paused or failed run (SIP-0079).

    Resumes from the latest checkpoint when one exists; a run PAUSED before any
    task ran (e.g. a SIP-0089 §2.5 duty deferral, #222) is re-attempted from the
    start. Re-execution is enqueued so the run actually proceeds — flipping status
    alone does not re-run the executor.
    """

    registry = get_cycle_registry(request)

    # 1. Fetch run — validates existence
    run = await registry.get_run(run_id)

    # 2. Status must be paused or failed
    if run.status not in (RunStatus.PAUSED.value, RunStatus.FAILED.value):
        raise RunTerminalError(
            f"Cannot resume run in status {run.status!r} — must be paused or failed"
        )

    # 3. Resume source: a checkpoint (resume mid-plan), or — for a run PAUSED
    #    before any task ran (e.g. a §2.5 duty deferral, #222) — a re-attempt
    #    from the start. A checkpoint-less FAILED run still can't be resumed
    #    (no progress and no deliberate pause → create a fresh run).
    latest_cp = await registry.get_latest_checkpoint(run_id)
    if latest_cp is None and run.status != RunStatus.PAUSED.value:
        raise ValidationError("Cannot resume run without a checkpoint")

    # 4. Parent cycle must not be terminal
    cycle = await registry.get_cycle(cycle_id)  # validates cycle exists
    runs = await registry.list_runs(cycle_id)
    ws = cycle.resolved_config().get("workload_sequence", [])
    progress = compute_workload_progress(ws, runs)
    workload_statuses = [e.status for e in progress] if progress else None
    cycle_status = resolve_cycle_status(runs, False, workload_statuses=workload_statuses)
    if cycle_status in (CycleStatus.COMPLETED, CycleStatus.CANCELLED):
        raise RunTerminalError(f"Cannot resume run — parent cycle is {cycle_status.value}")

    # 5. Transition to running
    updated = await registry.update_run_status(run_id, RunStatus.RUNNING)

    # SIP-0077: run.resumed

    resume_reason = body.resume_reason if body else None
    get_cycle_event_bus(request).emit(
        EventType.RUN_RESUMED,
        entity_type="run",
        entity_id=run_id,
        context={
            "cycle_id": cycle_id,
            "run_id": run_id,
            "project_id": project_id,
        },
        payload={
            "resume_reason": resume_reason,
            "checkpoint_index": latest_cp.checkpoint_index if latest_cp else None,
        },
    )

    # Re-attempt execution. Flipping status to RUNNING alone does not re-run
    # the executor — only cycle-create enqueues it. execute_run self-detects
    # the resume source: it resumes from the latest checkpoint if one exists,
    # else restarts the plan from the beginning, and re-runs the §2.5 duty
    # guard (a still-active hard-duty window simply re-defers).

    background_tasks.add_task(
        get_flow_executor(request).execute_cycle,
        cycle_id,
        run_id,
        cycle.squad_profile_id,
    )

    return run_to_response(updated)


@router.get("/{run_id}/checkpoints", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_checkpoints(
    request: Request, project_id: str, cycle_id: str, run_id: str
) -> list[CheckpointSummaryResponse]:
    """List checkpoints for a run (SIP-0079)."""

    registry = get_cycle_registry(request)
    checkpoints = await registry.list_checkpoints(run_id)
    return [
        CheckpointSummaryResponse(
            checkpoint_index=cp.checkpoint_index,
            completed_task_count=len(cp.completed_task_ids),
            artifact_ref_count=len(cp.artifact_refs),
            created_at=cp.created_at,
        )
        for cp in checkpoints
    ]


def _artifact_vault_or_none(request: Request, run_id: str) -> ArtifactVaultPort | None:
    """The vault an approval promotes into, or ``None`` when none is wired.

    A missing vault never fails the decision: it is recorded, and promotion is skipped
    with a warning (``gate_promotion.promote_run_artifacts``).
    """

    try:
        return get_artifact_vault(request)
    except Exception:
        logger.warning("artifact_vault unavailable; skipping promotion for run %s", run_id)
        return None

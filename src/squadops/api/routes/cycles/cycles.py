"""
Cycle API routes (SIP-0064 §9.3).
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends

from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.cycles.dtos import (
    CycleCreateRequest,
    CycleCreateResponse,
    PreflightWarningDTO,
)
from squadops.api.routes.cycles.errors import handle_cycle_error
from squadops.api.routes.cycles.mapping import cycle_to_response
from squadops.auth.models import Scope
from squadops.cycles.check_tooling import resolve_provisioned_tooling
from squadops.cycles.cycle_outcome import resolve_cycle_outcome
from squadops.cycles.lifecycle import TERMINAL_STATES, compute_config_hash
from squadops.cycles.models import (
    Cycle,
    CycleError,
    CycleStatus,
    Gate,
    PreflightRejectedError,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
    resolve_config,
)
from squadops.cycles.preflight import (
    Finding,
    PreflightDecision,
    bind_mode_authoring_decision,
    combine,
    model_availability_decision,
    required_check_tooling_decision,
    required_roles_decision,
    stack_dev_capability_decision,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/cycles", tags=["cycles"])


async def _pulled_model_names() -> list[str] | None:
    """Best-effort list of the LLM backend's pulled-model names, or ``None``.

    ``None`` (backend not configured / provider declares no listing / unreachable) makes
    the model-availability preflight *warn and allow* rather than block — never block on
    missing evidence (SIP-0095 §6.2). Only a reachable backend yields a verifiable list.

    Asks the port what it can do (``LLMCapability.MODEL_LISTING``) rather than which
    adapter class it is — SIP-0106 §3.2's site 2; the ``isinstance(OllamaAdapter)`` it
    replaces made every non-Ollama provider silently unverifiable (#1157).
    """
    from squadops.api.runtime.deps import get_llm_port
    from squadops.ports.llm.provider import LLMCapability

    try:
        port = get_llm_port()
        if not port.supports(LLMCapability.MODEL_LISTING):
            return None
        raw = await port.list_available_models()
    except Exception as exc:  # not configured or backend unreachable
        logger.info("preflight_model_list_unverifiable", extra={"error": str(exc)})
        return None
    return [m.name for m in raw if m.name]


async def _sandbox_preflight_decision() -> PreflightDecision:
    """SIP-0102 102.2c: reconcile the configured sandbox environment before
    dispatch. Dormant provider ⇒ empty decision (no IO); malformed sandbox
    config ⇒ block (verifiable misconfiguration); unreachable service ⇒ the
    pure decision warns and allows (never block on missing evidence)."""
    import httpx

    from squadops.sandbox.environment import get_environment_contract
    from squadops.sandbox.main import sandbox_config_from_env
    from squadops.sandbox.preflight import sandbox_environment_decision

    try:
        cfg = sandbox_config_from_env()
    except ValueError as exc:
        return PreflightDecision(
            blocking=(
                Finding(
                    code="sandbox_config_invalid",
                    severity="block",
                    message=f"sandbox configuration is invalid: {exc}",
                ),
            )
        )
    if cfg.provider != "docker":
        return PreflightDecision()
    try:
        expected: str | None = get_environment_contract(cfg.environment).contract_id()
    except ValueError:
        expected = None
    report = None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{cfg.service_url.rstrip('/')}/health")
        if response.status_code == 200:
            report = response.json().get("environment")
    except Exception as exc:  # unreachable/timeout/bad payload ⇒ unverifiable
        logger.info("preflight_sandbox_unverifiable", extra={"error": str(exc)})
    return sandbox_environment_decision(
        provider=cfg.provider, expected_contract_id=expected, report=report
    )


async def _run_create_preflight(profile: SquadProfile, config: dict) -> tuple[Finding, ...]:
    """SIP-0095 create-time preflight: fail fast BEFORE persist/dispatch.

    Blocks (HTTP 422) when the squad can't satisfy the requested workloads' required
    roles or names a model definitively not pulled; an unreachable backend warns and
    allows. Returns the non-blocking warnings so the route can surface them on the
    response (Phase 4); raises on a blocking finding.

    ``config`` is the EFFECTIVE config (the #426 single merge, #724): dispatch
    honors ``execution_overrides``, so preflight must validate the same merged
    view — evaluating ``applied_defaults`` alone would approve a shape dispatch
    never runs (or reject one it would).
    """
    decision = combine(
        required_roles_decision(profile, config),
        # #762: bind mode with no plan_authoring_contributors is unwinnable by
        # construction — the sole-author path never receives the criteria index,
        # so every framing attempt is rejected. Fail in seconds, not per re-roll.
        bind_mode_authoring_decision(config),
        # #832: build_profile and dev_capability both name the stack. Disagreement expands
        # one stack's skeleton while prompting the dev agent for another's files — every
        # emission outside the fill slots, surfacing as "the plan claims nothing" a full
        # framing workload later.
        stack_dev_capability_decision(config),
        model_availability_decision(profile, await _pulled_model_names()),
        # SIP-0096 §6.5: a required check whose tooling is knowably absent is a
        # create-time reject, never a mid-run blocked_unverified surprise.
        required_check_tooling_decision(
            config.get("required_checks") or (),
            resolve_provisioned_tooling(),
        ),
        # SIP-0102 102.2c: a skewed/unprovisioned sandbox environment is a
        # create-time reject, never a mid-run environment stall (roll-4).
        await _sandbox_preflight_decision(),
    )
    if decision.rejected:
        raise PreflightRejectedError(decision.summary())
    for w in decision.warnings:
        logger.warning(
            "cycle_create_preflight_warning", extra={"code": w.code, "detail": w.message}
        )
    return decision.warnings


async def _seed_derived_contract(body: CycleCreateRequest, project_id: str) -> str | None:
    """Derive a verification contract from a seeded manifest (#779, M0b).

    Fires only when the cycle supplies an interface manifest but **no**
    ``contract_ref`` — the manifest says what the app's interface is, and the contract
    is the checklist derived from it.

    Bind mode is keyed on ``contract_ref``, so a cycle that seeds only a manifest runs
    UNBOUND today — the operator asked for contract verification by seeding the
    manifest and would silently get none. The contract is mechanically derivable from
    that manifest (#777 pins the equality as exact), so derive it here, store it, and
    let the rest of the pipeline see an ordinary ``contract_ref``.

    Never overrides a supplied ref: an operator who passes one is pinning a SPECIFIC
    contract — possibly deliberately unlike what today's deriver emits, as when
    replaying an older run — and replay compatibility keys on ``contract_ref``.

    Returns the new artifact id, or None when nothing was derived. An unusable
    manifest raises :class:`PreflightRejectedError`: falling through to author mode
    would hand back a green carrying none of the criteria that were asked for.
    """
    from squadops.api.runtime.deps import get_artifact_vault
    from squadops.cycles.contract_derivation import (
        ContractDerivationError,
        derive_and_store_contract,
        load_seeded_manifest_content,
    )

    overrides = body.execution_overrides or {}
    if overrides.get("contract_ref"):
        return None
    if not overrides.get("plan_artifact_refs"):
        # Nothing seeded to derive from. Checked before reaching for the vault so a
        # cycle that never had a manifest does not depend on vault wiring at all.
        return None

    vault = get_artifact_vault()
    manifest_content = await load_seeded_manifest_content(
        vault, overrides.get("plan_artifact_refs")
    )
    if manifest_content is None:
        return None

    try:
        return await derive_and_store_contract(vault, project_id, manifest_content)
    except ContractDerivationError as exc:
        raise PreflightRejectedError(
            f"a manifest is seeded in plan_artifact_refs but no verification contract "
            f"could be derived from it, so the cycle would run unbound: {exc}"
        ) from exc


async def _validate_replay_declaration(
    registry, body: CycleCreateRequest, applied_defaults: dict
) -> None:
    """SIP-0101 Slice 3.1/3.5 — create-time replay validation + interim gate.

    Rejects (as a preflight rejection, the create path's 422 shape) unless the
    declaration is well-formed, the source run and boundary checkpoint exist,
    and source/target agree on every ``REPLAY_COMPATIBILITY_ELEMENTS`` entry —
    strict equality, more conservative than §3.5's eventual per-boundary sets,
    so Slice 4 relaxes an existing guard rather than adding a missing one. The
    refusal names the failing element. Maintainer-only surface (the declaration
    rides ``execution_overrides``); no-op for normal cycles.
    """
    from squadops.cycles.models import RunNotFoundError
    from squadops.cycles.replay import (
        check_replay_compatibility,
        parse_replay_declaration,
    )

    try:
        replay_req = parse_replay_declaration(body.execution_overrides or {})
    except ValueError as e:
        raise PreflightRejectedError(f"replay_declaration_invalid: {e}") from e
    if replay_req is None:
        return

    try:
        source_run = await registry.get_run(replay_req.source_run_id)
    except RunNotFoundError as e:
        raise PreflightRejectedError(
            f"replay_source_missing: run {replay_req.source_run_id} not found"
        ) from e
    source_cycle = await registry.get_cycle(source_run.cycle_id)

    checkpoints = await registry.list_checkpoints(replay_req.source_run_id)
    if replay_req.boundary_index not in {c.checkpoint_index for c in checkpoints}:
        raise PreflightRejectedError(
            f"replay_boundary_missing: run {replay_req.source_run_id} has no "
            f"checkpoint at boundary {replay_req.boundary_index} (pruned, or never "
            "written — only Slice-2+ runs retain their phase boundaries)"
        )

    # Target resolved config mirrors Cycle.resolved_config() for the cycle
    # about to be built (#426 seam — never applied_defaults alone). #724: the
    # hoisted single merge definition, not an inline duplicate of it.
    target_resolved = resolve_config(applied_defaults, body.execution_overrides or {})
    source_resolved = source_cycle.resolved_config()
    errors = check_replay_compatibility(
        {
            "prd_ref": source_cycle.prd_ref,
            "build_profile": source_resolved.get("build_profile"),
            "contract_ref": source_resolved.get("contract_ref"),
        },
        {
            "prd_ref": body.prd_ref,
            "build_profile": target_resolved.get("build_profile"),
            "contract_ref": target_resolved.get("contract_ref"),
        },
    )
    if errors:
        raise PreflightRejectedError("; ".join(errors))


@router.post("", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def create_cycle(
    project_id: str, body: CycleCreateRequest, background_tasks: BackgroundTasks
):
    """Create a Cycle + first Run (T17: atomic).

    SIP-0066: After persisting, enqueues execute_run as a background task.
    """
    from squadops.api.runtime.deps import (
        get_cycle_registry,
        get_flow_executor,
        get_project_registry,
        get_squad_profile_port,
    )

    try:
        # Verify project exists
        project_registry = get_project_registry()
        await project_registry.get_project(project_id)

        # Resolve squad profile snapshot
        profile_port = get_squad_profile_port()
        profile, snapshot_hash = await profile_port.resolve_snapshot(body.squad_profile_id)

        # Build domain objects
        cycle_id = f"cyc_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        # Convert DTO policy to domain
        gates = tuple(
            Gate(
                name=g.name,
                description=g.description,
                after_task_types=tuple(g.after_task_types),
            )
            for g in body.task_flow_policy.gates
        )
        policy = TaskFlowPolicy(mode=body.task_flow_policy.mode, gates=gates)

        # SIP-0065 D2: use client-supplied applied_defaults (CRP defaults from CLI)
        applied_defaults = body.applied_defaults
        # #724: the effective config the runtime will read (#426 single merge) —
        # preflight and position-0 workload resolution must see what dispatch sees.
        effective_config = resolve_config(applied_defaults, body.execution_overrides or {})

        # SIP-0095: create-time preflight — fail fast (422) before persist/dispatch.
        preflight_warnings = await _run_create_preflight(profile, effective_config)

        # SIP-0101 Slice 3: replay declaration validated + interim compatibility
        # gate, same fail-fast point (moves into the SIP-0095 preflight in Slice 4).
        await _validate_replay_declaration(get_cycle_registry(), body, applied_defaults)

        # #779 (M0b): a seeded manifest with no contract_ref would run UNBOUND. Derive
        # the contract it implies and pin it as an artifact, so bind mode engages
        # exactly as it does for an operator who ingested one by hand. After this the
        # effective config must be recomputed — the new ref is part of it.
        derived_ref = await _seed_derived_contract(body, project_id)
        if derived_ref is not None:
            body.execution_overrides = {
                **(body.execution_overrides or {}),
                "contract_ref": derived_ref,
            }
            effective_config = resolve_config(applied_defaults, body.execution_overrides)
            logger.info(
                "cycle_create_derived_contract",
                extra={"project_id": project_id, "contract_ref": derived_ref},
            )

        config_hash = compute_config_hash(applied_defaults, body.execution_overrides)

        cycle = Cycle(
            cycle_id=cycle_id,
            project_id=project_id,
            created_at=now,
            created_by="system",
            prd_ref=body.prd_ref,
            squad_profile_id=body.squad_profile_id,
            squad_profile_snapshot_ref=snapshot_hash,
            task_flow_policy=policy,
            build_strategy=body.build_strategy,
            applied_defaults=applied_defaults,
            execution_overrides=body.execution_overrides,
            expected_artifact_types=tuple(body.expected_artifact_types),
            experiment_context=body.experiment_context,
            request_profile=body.request_profile,
            notes=body.notes,
        )

        # Resolve workload_type from workload_sequence (fixes #26; #724: the
        # effective sequence, so an overridden sequence types run 1 correctly)
        ws = effective_config.get("workload_sequence", [])
        workload_type = ws[0]["type"] if ws else None

        run = Run(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            cycle_id=cycle_id,
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash=config_hash,
            workload_type=workload_type,
        )

        # Persist atomically (T17)
        cycle_registry = get_cycle_registry()
        await cycle_registry.create_cycle(cycle)
        await cycle_registry.create_run(run)

        # SIP-0077: cycle.created
        from squadops.api.runtime.deps import get_cycle_event_bus
        from squadops.events.types import EventType

        get_cycle_event_bus().emit(
            EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id=cycle.cycle_id,
            context={"cycle_id": cycle.cycle_id, "project_id": project_id},
            payload={
                "project_id": project_id,
                "created_by": cycle.created_by,
                "squad_profile_id": cycle.squad_profile_id,
                "prd_ref": cycle.prd_ref,
            },
        )

        # SIP-0083: Enqueue cycle execution (wraps execute_run for multi-workload)
        flow_executor = get_flow_executor()
        background_tasks.add_task(
            flow_executor.execute_cycle,
            cycle.cycle_id,
            run.run_id,
            body.squad_profile_id,
        )

        return CycleCreateResponse(
            cycle_id=cycle.cycle_id,
            project_id=project_id,
            run_id=run.run_id,
            run_number=run.run_number,
            status=run.status,
            prd_ref=cycle.prd_ref,
            squad_profile_id=cycle.squad_profile_id,
            squad_profile_snapshot_ref=snapshot_hash,
            task_flow_policy=body.task_flow_policy,
            resolved_config_hash=config_hash,
            warnings=[
                PreflightWarningDTO(code=w.code, message=w.message) for w in preflight_warnings
            ],
        )
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_cycles(project_id: str, status: CycleStatus | None = None):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        cycles = await registry.list_cycles(project_id, status=status)
        results = []
        for c in cycles:
            runs = await registry.list_runs(c.cycle_id)
            results.append(cycle_to_response(c, runs))
        return results
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/{cycle_id}", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_cycle(project_id: str, cycle_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        cycle = await registry.get_cycle(cycle_id)
        runs = await registry.list_runs(cycle_id)
        # SIP-0096 §10: derive the verification roll-up on read (detail GET only —
        # kept out of the list path to avoid a per-cycle query), the same
        # derive-on-read pattern as the cycle status above.
        outcome = await resolve_cycle_outcome(registry, cycle_id)
        return cycle_to_response(cycle, runs, cycle_outcome=outcome)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/{cycle_id}/cancel", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def cancel_cycle(project_id: str, cycle_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        await registry.cancel_cycle(cycle_id)

        # SIP-0077: cycle.cancelled
        from squadops.api.runtime.deps import get_cycle_event_bus
        from squadops.events.types import EventType

        get_cycle_event_bus().emit(
            EventType.CYCLE_CANCELLED,
            entity_type="cycle",
            entity_id=cycle_id,
            context={"cycle_id": cycle_id, "project_id": project_id},
            payload={"project_id": project_id},
        )

        # #77: stop the orphaned Prefect flow run(s) for this cycle's runs so
        # workers don't keep executing a logically-cancelled cycle.
        from squadops.api.routes.cycles.cancellation import (
            abort_cancelled_cycle_activities,
            cancel_orphaned_flow_runs,
            release_cancelled_run_leases,
        )

        runs = await registry.list_runs(cycle_id)
        run_ids = [run.run_id for run in runs]
        cancelled = await cancel_orphaned_flow_runs(project_id, cycle_id, run_ids)

        # #529: `cancel_cycle` writes only the cycle's `cancelled` flag, so an
        # in-flight run stays `running` forever — a stale status, and one that
        # makes the run look live to the startup lease reaper. Transition them
        # here, per-run isolated so one failure never blocks the rest.
        for run in runs:
            if RunStatus(run.status) in TERMINAL_STATES:
                continue
            try:
                await registry.cancel_run(run.run_id)
            except Exception:
                logger.warning(
                    "cancel_cycle: run %s could not be cancelled", run.run_id, exc_info=True
                )

        # #529: release the focus leases those runs hold. Swept across every run,
        # not just the in-flight ones — a lease stranded under an already-terminal
        # run is exactly #373's case and blocks recruitment just as hard.
        leases_released = await release_cancelled_run_leases(cycle_id, run_ids)

        # #561: and end the cycle's open activity rows. One left active trips the
        # one-active-per-agent index on every later dispatch, silently ending
        # that agent's activity tracking.
        activities_ended = await abort_cancelled_cycle_activities(cycle_id)

        return {
            "status": "cancelled",
            "cycle_id": cycle_id,
            "prefect_flow_runs_cancelled": cancelled,
            "focus_leases_released": leases_released,
            "activities_ended": activities_ended,
        }
    except CycleError as e:
        raise handle_cycle_error(e) from e

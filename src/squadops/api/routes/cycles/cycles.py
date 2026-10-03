"""
Cycle API routes (SIP-0064 §9.3).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from squadops import __version__ as SQUADOPS_VERSION
from squadops._version import resolve_git_sha
from squadops.api.cycle_schemas import (
    CycleAssessmentResponse,
    CycleCreateRequest,
    CycleCreateResponse,
    PreflightWarningDTO,
    ProposalRatingRequest,
    ProposalRatingResponse,
)
from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.cycles.mapping import assessment_to_response, cycle_to_response
from squadops.auth.models import Identity, Scope
from squadops.cycles.check_tooling import resolve_provisioned_tooling
from squadops.cycles.cycle_outcome import resolve_cycle_outcome
from squadops.cycles.lifecycle import compute_config_hash
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    CycleStatus,
    Gate,
    PreflightRejectedError,
    Run,
    SquadProfile,
    TaskFlowPolicy,
    ValidationError,
    resolve_config,
)
from squadops.cycles.preflight import (
    Finding,
    PreflightDecision,
    bind_mode_authoring_decision,
    combine,
    fault_injection_decision,
    model_availability_decision,
    model_registration_decision,
    required_check_tooling_decision,
    required_roles_decision,
    stack_development_profile_decision,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/cycles", tags=["cycles"])


async def _pulled_model_names(port: Any | None) -> list[str] | None:
    """Best-effort list of the LLM backend's pulled-model names, or ``None``.

    ``None`` (backend not configured / provider declares no listing / unreachable) makes
    the model-availability preflight *warn and allow* rather than block — never block on
    missing evidence (SIP-0095 §6.2). Only a reachable backend yields a verifiable list.

    Asks the port what it can do (``LLMCapability.MODEL_LISTING``) rather than which
    adapter class it is — SIP-0106 §3.2's site 2; the ``isinstance(OllamaAdapter)`` it
    replaces made every non-Ollama provider silently unverifiable (#1157).
    """
    from squadops.ports.llm.provider import LLMCapability

    if port is None:
        logger.info("preflight_model_list_unverifiable", extra={"error": "no LLM port"})
        return None
    try:
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


async def _run_create_preflight(
    llm_port: Any | None, profile: SquadProfile, config: dict
) -> tuple[Finding, ...]:
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
        # #832: build_profile and development_profile both name the stack. Disagreement expands
        # one stack's skeleton while prompting the dev agent for another's files — every
        # emission outside the fill slots, surfacing as "the plan claims nothing" a full
        # framing workload later.
        stack_development_profile_decision(config),
        model_availability_decision(profile, await _pulled_model_names(llm_port)),
        # #1145: pulled is not the same as registered. A model the backend serves but
        # MODEL_SPECS does not know runs with the overflow guard disabled and a
        # different completion budget than a registered model on the same capability —
        # silently, until it shows up as an odd result in a measurement window.
        model_registration_decision(profile),
        # SIP-0096 §6.5: a required check whose tooling is knowably absent is a
        # create-time reject, never a mid-run blocked_unverified surprise.
        required_check_tooling_decision(
            config.get("required_checks") or (),
            resolve_provisioned_tooling(),
        ),
        # SIP-0102 102.2c: a skewed/unprovisioned sandbox environment is a
        # create-time reject, never a mid-run environment stall (roll-4).
        await _sandbox_preflight_decision(),
        # #1251: a fault declaration that could never fire would produce a green
        # diagnostic — a cycle reading as evidence the loop handled a fault that never
        # happened. A usable one warns, so the create log says the cycle is a diagnostic.
        fault_injection_decision(config),
    )
    if decision.rejected:
        raise PreflightRejectedError(decision.summary())
    for w in decision.warnings:
        logger.warning(
            "cycle_create_preflight_warning", extra={"code": w.code, "detail": w.message}
        )
    return decision.warnings


async def _seed_derived_contract(
    vault: Any | None, body: CycleCreateRequest, project_id: str
) -> str | None:
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

    if vault is None:
        raise RuntimeError("ArtifactVaultPort not configured: a seeded manifest cannot be read")
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


async def _current_deploy_id(registry) -> str | None:
    """The latest deploy record's id (#1720), or None when no deploy has been recorded."""
    latest = await registry.latest()
    return latest.deploy_id if latest else None


@dataclass(frozen=True)
class CreationPorts:
    """The ports creating a cycle reads: gathered from the request's app by the create route,
    and from the composition root by a campaign's launch (SIP-0109 §12b), so both create a cycle
    by one path. The LLM port and the vault are optional, as they are to the route: the model
    preflight warns without a listing, and the vault is read only when a manifest is seeded."""

    project_registry: Any
    squad_profile: Any
    cycle_registry: Any
    deploy_registry: Any
    llm: Any | None = None
    artifact_vault: Any | None = None

    @classmethod
    def of_request(cls, request: Request) -> "CreationPorts":
        from squadops.api.runtime.deps import (
            get_artifact_vault,
            get_cycle_registry,
            get_deploy_registry,
            get_llm_port,
            get_project_registry,
            get_squad_profile_port,
        )

        def optional(getter):
            try:
                return getter(request)
            except Exception:  # noqa: BLE001 — unwired is what the reader handles
                return None

        return cls(
            project_registry=get_project_registry(request),
            squad_profile=get_squad_profile_port(request),
            cycle_registry=get_cycle_registry(request),
            deploy_registry=get_deploy_registry(request),
            llm=optional(get_llm_port),
            artifact_vault=optional(get_artifact_vault),
        )


@dataclass(frozen=True)
class PreparedCycle:
    """A cycle and its first run, built and preflighted, not yet persisted."""

    cycle: Cycle
    run: Run
    warnings: tuple[Finding, ...]


def first_run(cycle: Cycle, *, initiated_by: str) -> Run:
    """A cycle's first run: its workload type is the effective sequence's first (#26, #724)."""
    ws = cycle.resolved_config().get("workload_sequence", [])
    return Run(
        run_id=f"run_{uuid.uuid4().hex[:12]}",
        cycle_id=cycle.cycle_id,
        run_number=1,
        status="queued",
        initiated_by=initiated_by,
        resolved_config_hash=compute_config_hash(cycle.applied_defaults, cycle.execution_overrides),
        workload_type=ws[0]["type"] if ws else None,
    )


async def prepare_cycle(
    ports: CreationPorts,
    project_id: str,
    body: CycleCreateRequest,
    *,
    created_by: str = "system",
    initiated_by: str = "api",
    campaign_id: str | None = None,
    kind: str | None = None,
) -> PreparedCycle:
    """Build and preflight a cycle and its first run from a create request: the route's body,
    or a campaign launch's (SIP-0109 §12b), which also names the campaign and the cycle's kind.
    Raises before anything is persisted when the project is unknown or a preflight blocks."""
    await ports.project_registry.get_project(project_id)

    # Resolve squad profile snapshot
    profile, snapshot_hash = await ports.squad_profile.resolve_snapshot(body.squad_profile_id)

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
    preflight_warnings = await _run_create_preflight(ports.llm, profile, effective_config)

    # SIP-0101 Slice 3: replay declaration validated + interim compatibility
    # gate, same fail-fast point (moves into the SIP-0095 preflight in Slice 4).
    await _validate_replay_declaration(ports.cycle_registry, body, applied_defaults)

    # #779 (M0b): a seeded manifest with no contract_ref would run UNBOUND. Derive
    # the contract it implies and pin it as an artifact, so bind mode engages
    # exactly as it does for an operator who ingested one by hand. After this the
    # effective config must be recomputed — the new ref is part of it.
    derived_ref = await _seed_derived_contract(ports.artifact_vault, body, project_id)
    if derived_ref is not None:
        body.execution_overrides = {
            **(body.execution_overrides or {}),
            "contract_ref": derived_ref,
        }
        logger.info(
            "cycle_create_derived_contract",
            extra={"project_id": project_id, "contract_ref": derived_ref},
        )

    cycle = Cycle(
        cycle_id=cycle_id,
        project_id=project_id,
        created_at=now,
        created_by=created_by,
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
        # #80: which code created the cycle — read here, at creation, so the record
        # carries the deploy that actually served the request.
        framework_version=SQUADOPS_VERSION,
        framework_git_sha=resolve_git_sha(),
        # #1720: and which deploy — every service's image and the models' weights, recorded by
        # the deploy step. None when no deploy has been recorded: unknown, never a guess.
        deploy_id=await _current_deploy_id(ports.deploy_registry),
        notes=body.notes,
        campaign_id=campaign_id,
        kind=kind,
    )
    return PreparedCycle(cycle, first_run(cycle, initiated_by=initiated_by), preflight_warnings)


@router.post("", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def create_cycle(
    request: Request, project_id: str, body: CycleCreateRequest, background_tasks: BackgroundTasks
):
    """Create a Cycle + first Run (T17: atomic).

    SIP-0066: After persisting, enqueues execute_run as a background task.
    """
    from squadops.api.runtime.deps import get_flow_executor

    ports = CreationPorts.of_request(request)
    prepared = await prepare_cycle(ports, project_id, body)
    cycle, run, preflight_warnings = prepared.cycle, prepared.run, prepared.warnings
    snapshot_hash = cycle.squad_profile_snapshot_ref
    config_hash = run.resolved_config_hash

    # Persist atomically (T17)
    await ports.cycle_registry.create_cycle(cycle)
    await ports.cycle_registry.create_run(run)

    # SIP-0077: cycle.created
    from squadops.api.runtime.deps import get_cycle_event_bus
    from squadops.events.types import EventType

    get_cycle_event_bus(request).emit(
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
    flow_executor = get_flow_executor(request)
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
        warnings=[PreflightWarningDTO(code=w.code, message=w.message) for w in preflight_warnings],
    )


@router.get("", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_cycles(request: Request, project_id: str, status: CycleStatus | None = None):
    from squadops.api.runtime.deps import get_cycle_registry

    registry = get_cycle_registry(request)
    cycles = await registry.list_cycles(project_id, status=status)
    results = []
    for c in cycles:
        runs = await registry.list_runs(c.cycle_id)
        results.append(cycle_to_response(c, runs))
    return results


@router.get("/{cycle_id}", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_cycle(request: Request, project_id: str, cycle_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    registry = get_cycle_registry(request)
    cycle = await registry.get_cycle(cycle_id)
    runs = await registry.list_runs(cycle_id)
    # SIP-0096 §10: derive the verification roll-up on read (detail GET only —
    # kept out of the list path to avoid a per-cycle query), the same
    # derive-on-read pattern as the cycle status above.
    outcome = await resolve_cycle_outcome(registry, cycle_id)
    return cycle_to_response(cycle, runs, cycle_outcome=outcome)


@router.get("/{cycle_id}/assessment", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_cycle_assessment(
    request: Request, project_id: str, cycle_id: str
) -> CycleAssessmentResponse:
    """The cycle's assessment, computed on read (SIP-0108 §4.1 (a)).

    The 1.8.0 cut could only recompute this by hand: the stores carried the assessment's
    inputs and nothing printed it, so the evidence gate's word "carries" was read as
    "recomputable". This is the reader that makes it "shows".

    Derive-on-read, the same pattern as the detail GET's verification roll-up: the projection
    is pure and does no I/O of its own (an architecture test holds that). Assembling the
    evidence is an adapter concern, so the composition root owns it (#154) and this route
    asks the root. Read-only — nothing here writes, and no agent is in the path.
    """
    from squadops.api.runtime.deps import assess_cycle_from_stores

    return assessment_to_response(await assess_cycle_from_stores(request, cycle_id))


@router.post("/{cycle_id}/proposal-rating")
async def rate_proposal(
    request: Request,
    project_id: str,
    cycle_id: str,
    body: ProposalRatingRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CAMPAIGNS_SUPERVISE)),
) -> ProposalRatingResponse:
    """The supervisor's rating of a proposal nothing builds (SIP-0109 §11a; §24af).

    The reference scenario's proposal runs on ``campaign-proposal``: the proposal workload with
    no gate, so there is nothing to rule. The rating is stored beside the change request it is
    bound to. A campaign's proposals are ruled at the increment gate (§9.2), never rated here.
    """
    import hashlib

    from squadops.api.routes.campaigns.campaigns import actor_from
    from squadops.api.runtime.deps import get_artifact_vault, get_cycle_registry
    from squadops.campaigns.change_request import load_stored_change_request
    from squadops.campaigns.proposal_rating import (
        PROPOSAL_RATING_ARTIFACT_TYPE,
        PROPOSAL_RATING_FILENAME,
        rating_document,
        rating_from_request,
    )
    from squadops.capabilities.handlers.planning.proposal import CHANGE_REQUEST_ARTIFACT_TYPE

    cycle = await get_cycle_registry(request).get_cycle(cycle_id)
    if cycle.campaign_id:
        raise ValidationError(
            f"cycle {cycle_id} belongs to campaign {cycle.campaign_id}: its proposals are ruled "
            f"at the increment gate, not rated"
        )
    vault = get_artifact_vault(request)
    stored = sorted(
        (
            r
            for r in await vault.list_artifacts(cycle_id=cycle_id)
            if r.artifact_type == CHANGE_REQUEST_ARTIFACT_TYPE
        ),
        key=lambda r: str(r.created_at),
    )
    if not stored:
        raise ValidationError(f"cycle {cycle_id} stored no change request to rate")
    ref, content = await vault.retrieve(stored[-1].artifact_id)
    change_request = load_stored_change_request(content.decode("utf-8"))
    now = datetime.now(UTC)
    try:
        rating = rating_from_request(
            body.model_dump(),
            change_request=change_request,
            rated_by=actor_from(identity)[0],
            rated_at=now,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    document = rating_document(rating).encode("utf-8")
    artifact_id = f"art_{uuid.uuid4().hex[:12]}"
    await vault.store(
        ArtifactRef(
            artifact_id=artifact_id,
            project_id=project_id,
            artifact_type=PROPOSAL_RATING_ARTIFACT_TYPE,
            filename=PROPOSAL_RATING_FILENAME,
            content_hash=hashlib.sha256(document).hexdigest(),
            size_bytes=len(document),
            media_type="text/yaml",
            created_at=now,
            cycle_id=cycle_id,
            run_id=ref.run_id,
            metadata={
                "proposal_id": rating.proposal_id,
                "version": rating.version,
                "change_request_hash": rating.content_hash,
            },
        ),
        document,
    )
    return ProposalRatingResponse(
        artifact_id=artifact_id,
        proposal_id=rating.proposal_id,
        version=rating.version,
        verdict=rating.verdict.value,
    )


@router.post("/{cycle_id}/cancel", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def cancel_cycle(request: Request, project_id: str, cycle_id: str):
    from squadops.api.routes.cycles.cancellation import cancel_cycle_by_the_existing_path

    return await cancel_cycle_by_the_existing_path(request, project_id, cycle_id)

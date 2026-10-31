"""
Cycle API routes (SIP-0064 §9.3).
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from squadops import __version__ as SQUADOPS_VERSION
from squadops._version import resolve_git_sha
from squadops.api.cycle_schemas import (
    CycleAssessmentResponse,
    CycleCancelResponse,
    CycleCreateRequest,
    CycleCreateResponse,
    CycleResponse,
    PreflightWarningDTO,
    ProposalRatingRequest,
    ProposalRatingResponse,
    SourcePreconditionDTO,
)
from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.paging import Page, page
from squadops.api.routes.cycles.mapping import assessment_to_response, cycle_to_response
from squadops.api.runtime.deps import (
    assess_cycle_from_stores,
    get_artifact_vault,
    get_audit_port,
    get_box_reader,
    get_cycle_event_bus,
    get_cycle_registry,
    get_deploy_registry,
    get_flow_executor,
    get_llm_port,
    get_memory_records,
    get_memory_store,
    get_project_registry,
    get_reference_resolvers,
    get_squad_profile_port,
)
from squadops.auth.models import AuditEvent, Identity, Scope
from squadops.campaigns.change_request import load_stored_change_request
from squadops.campaigns.models import CycleKind
from squadops.campaigns.proposal_rating import (
    PROPOSAL_RATING_ARTIFACT_TYPE,
    PROPOSAL_RATING_FILENAME,
    rating_document,
    rating_from_request,
)
from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.capabilities.handlers.planning.proposal import CHANGE_REQUEST_ARTIFACT_TYPE
from squadops.cycles.check_tooling import resolve_provisioned_tooling
from squadops.cycles.contract_derivation import (
    ContractDerivationError,
    derive_and_store_contract,
    load_seeded_manifest_content,
)
from squadops.cycles.cycle_outcome import resolve_cycle_outcome
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.lifecycle import compute_config_hash
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    CycleStatus,
    DerivedProfileNotFoundError,
    Gate,
    InheritedBaselineNotFoundError,
    PreflightRejectedError,
    Project,
    ProjectNotReadyError,
    ProjectStateConflictError,
    Run,
    RunNotFoundError,
    SquadProfile,
    StaleSourcePreconditionError,
    TaskFlowPolicy,
    ValidationError,
    resolve_config,
)
from squadops.cycles.preflight import (
    Finding,
    PreflightDecision,
    bind_mode_authoring_decision,
    builder_build_profile_decision,
    combine,
    fault_injection_decision,
    memory_declaration_decision,
    model_availability_decision,
    model_registration_decision,
    required_check_tooling_decision,
    required_roles_decision,
    source_backed_stack_decision,
    stack_development_profile_decision,
)
from squadops.cycles.replay import check_replay_compatibility, parse_replay_declaration
from squadops.cycles.vault_reads import retrieve_or_absent
from squadops.events.types import EventType
from squadops.memory.pinning import cycle_binding, pin_standalone_cycle
from squadops.memory.records import RecordRefused, Source, SourceKind
from squadops.memory.reference_binding import bound_for_cycle
from squadops.memory.task_instructions import admitted, requested_references
from squadops.ports.llm.provider import LLMCapability
from squadops.projects.source_context import (
    CAMPAIGN_BRANCH,
    PROJECT_BASELINE,
    ProjectSourceContext,
)
from squadops.projects.sync import unreconciled
from squadops.projects.verification import ACCEPTED as VERIFICATION_ACCEPTED
from squadops.projects.verification import SOURCE_VERIFICATION_TYPE
from squadops.sandbox.environment import get_environment_contract
from squadops.sandbox.main import sandbox_config_from_env
from squadops.sandbox.preflight import sandbox_environment_decision
from squadops.stacks.development_profiles import blueprint_development_profile

if TYPE_CHECKING:
    from squadops.campaigns.campaign_branch import CampaignHead
    from squadops.projects.derived_profile import DerivedProfile

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
    llm_port: Any | None,
    profile: SquadProfile,
    config: dict,
    *,
    campaign_cycle: bool,
    source_backed: bool = False,
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
        # #2437: a builder squad with a build step and no build_profile fails the moment
        # implementation starts (#392), after the whole framing workload. Fail in seconds.
        builder_build_profile_decision(profile, config, source_backed=source_backed),
        # SIP-0112 E.4.3: an external product's cycle starts from its tree, never a stack's.
        source_backed_stack_decision(config, source_backed=source_backed),
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
        # SIP-0110 §0.7: a memory declaration is `disabled` or `enabled`, never guessed.
        memory_declaration_decision(config, campaign_cycle=campaign_cycle),
    )
    if decision.rejected:
        raise PreflightRejectedError(decision.summary())
    for w in decision.warnings:
        logger.warning(
            "cycle_create_preflight_warning", extra={"code": w.code, "detail": w.message}
        )
    return decision.warnings


async def _seed_derived_contract(
    vault: Any | None, body: CycleCreateRequest, project_id: str, *, source_backed: bool
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

    A source-backed cycle that seeds a manifest is refused before anything is derived or
    stored (SIP-0112 H.4 point 3): the contract would bind a stack's checks beside the
    product's files, the ``contract_ref`` that E.4.3's guard refuses by name.
    """

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
    if source_backed:
        raise PreflightRejectedError(
            "source_backed_seeded_manifest: this cycle develops an external product from its own "
            "tree at the pinned commit, and plan_artifact_refs seeds an interface manifest, from "
            "which a stack's verification contract would be derived and bound beside the "
            "product's files. Seed no manifest for a cycle of an external Project: its own "
            "declared checks verify it"
        )

    try:
        return await derive_and_store_contract(vault, project_id, manifest_content)
    except ContractDerivationError as exc:
        raise PreflightRejectedError(
            f"a manifest is seeded in plan_artifact_refs but no verification contract "
            f"could be derived from it, so the cycle would run unbound: {exc}"
        ) from exc


def _pin_blueprint_conventions(
    body: CycleCreateRequest, profile: "DerivedProfile | None"
) -> str | None:
    """Pin the development profile of the blueprint a product was made from (SIP-0112 H.13).

    A product's cycle runs under the default profile unless something names another, and that is
    ``python_cli``, so a frontend change on a FastAPI and React product was given a Python
    package's prompts and a Python-only source filter. The derived profile at the pin names the
    blueprint the product follows (contract 8's ``blueprint``), and that blueprint's development
    profile is pinned in ``execution_overrides``, as ``_seed_derived_contract`` pins its
    ``contract_ref``: one value on the cycle record, read by every task, retry and repair through
    ``effective_development_profile``. It seeds nothing (``seeds_skeleton``).

    Each task is then shown the blueprint's conventions for a product, never its test placement,
    which the product's runners give (``source_repository_section``). Nothing is pinned:
    - for no profile at the pin, or no blueprint, or one whose profile says nothing for a product
      (``blueprint_development_profile``): the default stands, as in 2.4;
    - where the request already names a ``development_profile``: the operator's choice stands, as
      a supplied ``contract_ref`` does;
    - for a cycle with no implementation plan. Only the plan's tasks are shown the product, with
      its runners, so a plan-less task under the blueprint's profile would be given the profile's
      prose for the skeleton, and its test placement with it.

    Returns the profile pinned, or ``None``."""
    if profile is None:
        return None
    name = blueprint_development_profile(profile.blueprint_stack)
    if not name:
        return None
    overrides = body.execution_overrides or {}
    config = resolve_config(body.applied_defaults, overrides)
    if config.get("development_profile"):
        return None
    if not (config.get("implementation_plan") or config.get("typed_acceptance")):
        return None
    body.execution_overrides = {**overrides, "development_profile": name}
    return name


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
    #: Where a cycle's admitted task instructions are stored (#2178): by the route, and by a
    #: campaign's launch, which creates its cycles through this same path.
    memory_records: Any | None = None
    #: What binds a task instruction's ``@current`` references with its cycle, by family (T16).
    reference_resolvers: Any | None = None
    #: Where a campaign cycle's own bindings of its campaign's pinned instructions are recorded
    #: when the campaign launches it (SIP-0110 §5ad). Read by a launch only.
    memory_store: Any | None = None

    @classmethod
    def of_request(cls, request: Request) -> "CreationPorts":

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
            memory_records=get_memory_records(request),
            reference_resolvers=get_reference_resolvers(request),
            memory_store=optional(get_memory_store),
        )


@dataclass(frozen=True)
class PreparedCycle:
    """A cycle and its first run, built and preflighted, not yet persisted."""

    cycle: Cycle
    run: Run
    warnings: tuple[Finding, ...]
    #: The task instructions the request gave (#2178), as records of this cycle, confirmed by
    #: whoever instructed it: stored by the caller before the first run is enqueued.
    instructions: tuple[Any, ...] = ()


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


def pin_source_context(
    project: Project,
    precondition: SourcePreconditionDTO | None,
    head: "CampaignHead | None" = None,
) -> ProjectSourceContext | None:
    """SIP-0112 contract 1 (FR-04, FR-09, §D.3): an external Project's source, resolved from the
    registry's record and pinned before dispatch. A sample application has none. A stated
    precondition the Project has moved past is refused; an absent one pins the current source,
    which is persisted all the same.

    ``head`` is a repository-backed Campaign increment's ``CampaignHead`` (H.4, SIP-0109 §24cd
    point 1): its tree is pinned there, and the Project's baseline stays recorded beside it."""
    if project.source is None:
        if precondition is not None or head is not None:
            raise ValidationError(
                f"Project {project.project_id} is a sample application: it has no external "
                "source to state a precondition for, or campaign branch to pin"
            )
        return None
    commit = project.development_baseline_commit
    revision = project.development_configuration_revision
    if commit is None or revision is None:
        raise ProjectStateConflictError(
            f"Project {project.project_id} needs its source validated and a Development "
            "Configuration recorded before a Cycle develops it (E.4.2)"
        )
    if precondition is not None and (
        precondition.development_baseline_commit != commit
        or precondition.development_configuration_revision not in (None, revision)
    ):
        raise StaleSourcePreconditionError(
            f"Project {project.project_id} is at baseline {commit}, Development Configuration "
            f"revision {revision}; the request expected "
            f"{precondition.development_baseline_commit}, revision "
            f"{precondition.development_configuration_revision or 'any'}"
        )
    return ProjectSourceContext(
        project_id=project.project_id,
        record_version=project.record_version,
        development_configuration_revision=revision,
        repo_uri=project.source.repo_uri,
        development_baseline_commit=commit,
        integrated_upstream_commit=project.integrated_upstream_commit,
        pinned_commit=head.commit if head is not None else commit,
        pinned_from=CAMPAIGN_BRANCH if head is not None else PROJECT_BASELINE,
        previous_verification_ref=head.previous_verification_ref if head is not None else None,
    )


async def require_campaign_head(
    vault: Any | None,
    context: ProjectSourceContext,
    head: "CampaignHead | None",
    *,
    kind: str | None,
) -> None:
    """H.4, SIP-0109 §24cd point 1: a repository-backed Campaign's cycle is pinned at its campaign
    branch's head, never at the Project's baseline by default, and its regression baseline is the
    accepted verification that made that head. The calibration is the record of the Project's
    inherited baseline (§24bv point 1), so the first head is the Project's baseline commit, with
    no verification before it."""
    if head is None:
        raise ProjectStateConflictError(
            f"Project {context.project_id}'s Campaign {kind or 'cycle'} is pinned at its campaign "
            "branch's head, and its launch names none (SIP-0109 §24cd point 1): it is refused, "
            "never pinned at the Project's baseline"
        )
    ref = head.previous_verification_ref
    if ref is None:
        if head.commit != context.development_baseline_commit:
            raise ProjectStateConflictError(
                f"the campaign branch's head {head.commit} names no verification, and only the "
                f"calibration record's commit {context.development_baseline_commit} has none"
            )
        return
    if vault is None:
        raise RuntimeError("ArtifactVaultPort not configured: an increment's head can't be read")
    got = await retrieve_or_absent(vault, ref)
    document = None
    if got is not None and getattr(got[0], "artifact_type", None) == SOURCE_VERIFICATION_TYPE:
        try:
            document = json.loads(got[1])
        except ValueError:
            document = None
    if (
        not isinstance(document, dict)
        or document.get("verdict") != VERIFICATION_ACCEPTED
        or document.get("candidate_tree_identity") != head.tree_identity
    ):
        raise ProjectStateConflictError(
            f"the campaign branch's head {head.commit} names verification {ref}, which isn't an "
            "accepted source verification of that tree, so the increment has no regression "
            "baseline to be compared with (SIP-0109 §24bv point 3)"
        )


async def require_reconciled_upstream(registry: Any, context: ProjectSourceContext) -> None:
    """FR-21 (#2608): once a sync has read upstream past the pinned baseline, with drift in evidence
    a unit relies on, a Cycle on the older evidence is refused until the Project is reconciled:
    validated, configured and its baseline captured at the new commit. Source drift alone holds
    nothing: the pinned evidence still describes the tree the Cycle develops."""
    finding = unreconciled(
        await registry.source_syncs(context.project_id), context.development_baseline_commit
    )
    if finding is not None:
        raise StaleSourcePreconditionError(
            f"Project {context.project_id}'s upstream is at {finding['upstream_commit']}, past its "
            f"baseline {context.development_baseline_commit}, with "
            f"{', '.join(finding['drift']['relevant'])} changed (projects sync): reconcile it at "
            "the new commit first (squadops projects validate, configure, baseline --capture)"
        )


async def require_inherited_baseline(registry: Any, context: ProjectSourceContext) -> None:
    """FR-20, FR-09: a source-backed run is judged against the product's inherited baseline at
    the commit and Development Configuration revision it pins, so a Cycle without that
    baseline is refused before dispatch, not once its work is done."""
    try:
        baseline = await registry.get_inherited_baseline(context.project_id)
    except InheritedBaselineNotFoundError:
        baseline = None
    pinned = (context.development_baseline_commit, context.development_configuration_revision)
    if baseline is None or (baseline.commit, baseline.development_configuration_revision) != pinned:
        held = (
            "none"
            if baseline is None
            else f"{baseline.commit}, revision {baseline.development_configuration_revision}"
        )
        raise ProjectStateConflictError(
            f"Project {context.project_id}'s inherited baseline is {held}; this Cycle pins "
            f"{pinned[0]}, revision {pinned[1]}: capture the baseline there first "
            "(squadops projects baseline)"
        )


async def derived_profile_at_pin(
    registry: Any, context: ProjectSourceContext
) -> "DerivedProfile | None":
    """The derived profile at the Project's pin (contract 8), or ``None`` for a baseline captured
    before profiles were. An increment pinned at its campaign branch's head reads it at the
    Project's pin all the same, as SIP-0109 §24cd point 3 rules."""
    try:
        return await registry.get_derived_profile(
            context.project_id,
            at=(context.development_baseline_commit, context.development_configuration_revision),
        )
    except DerivedProfileNotFoundError:
        return None


async def require_no_blocking_gap(
    profile: "DerivedProfile | None",
    vault: Any | None,
    context: ProjectSourceContext,
    body: CycleCreateRequest,
) -> tuple[Finding, ...]:
    """SIP-0112 H.4 (H.6, H.8): a source-backed Cycle whose work meets a blocking gap of the
    derived profile at its pin is refused before anything is persisted, naming the gap.

    Its work's paths are known here only from an operator's plan. A framing-authored plan meets
    the same rule at the plan gate (``validate_blocking_gaps``). A pin whose baseline has no
    profile runs as it did in 2.4, and the absence is returned as a warning."""
    if profile is None:
        return (
            Finding(
                code="derived_profile_absent",
                severity="warning",
                message=(
                    f"Project {context.project_id}'s baseline at its pin has no derived profile, "
                    "so no gap is checked: capture the baseline again (squadops projects "
                    "baseline --capture)"
                ),
            ),
        )
    plan = await _operator_plan(vault, body)
    if plan is not None:
        errors = plan.validate_blocking_gaps(profile)
    else:
        errors = [
            f"blocking_gap: {g.id}{f' ({g.subject})' if g.subject else ''} stops all work: "
            f"{g.reason}. Close it first: {g.closes_by}."
            for g in profile.blocking_work(None)
        ]
    if errors:
        raise ProjectStateConflictError(
            f"Project {context.project_id}'s derived profile names a blocking gap this Cycle's "
            "work meets: " + "; ".join(errors)
        )
    return ()


async def _operator_plan(vault: Any | None, body: CycleCreateRequest) -> ImplementationPlan | None:
    """The implementation plan an operator seeded in ``plan_artifact_refs``, or ``None``. One
    that can't be read is left to the dispatch-time net, which diagnoses it in full."""
    refs = (body.execution_overrides or {}).get("plan_artifact_refs") or []
    if vault is None or not refs:
        return None
    for ref_id in refs:
        got = await retrieve_or_absent(vault, ref_id)
        if got is None:
            continue
        ref, content = got
        if ref.filename == "implementation_plan.yaml" or (
            getattr(ref, "artifact_type", None) == "control_implementation_plan"
        ):
            try:
                return ImplementationPlan.from_yaml(content.decode(errors="replace"))
            except Exception:  # noqa: BLE001 - an unreadable plan is the dispatch net's to name
                return None
    return None


async def prepare_cycle(
    ports: CreationPorts,
    project_id: str,
    body: CycleCreateRequest,
    *,
    created_by: str = "system",
    initiated_by: str = "api",
    campaign_id: str | None = None,
    kind: str | None = None,
    increment_id: str | None = None,
    instructed_by: str | None = None,
    campaign_head: "CampaignHead | None" = None,
) -> PreparedCycle:
    """Build and preflight a cycle and its first run from a create request: the route's body,
    or a campaign launch's (SIP-0109 §12b), which also names the campaign and the cycle's kind.
    Raises before anything is persisted when the project is unknown, its lifecycle accepts no
    Cycle (SIP-0112 contract 1: registering, archived or failed) or a preflight blocks."""
    project = await ports.project_registry.get_project(project_id)
    if not project.lifecycle_status.accepts_cycles:
        raise ProjectNotReadyError(
            f"Project {project_id} is {project.lifecycle_status.value}: a Cycle needs it READY"
        )
    source_context = pin_source_context(project, body.source_precondition, campaign_head)
    gap_warnings: tuple[Finding, ...] = ()
    if source_context is not None and campaign_id is not None and kind != CycleKind.CALIBRATION:
        await require_campaign_head(ports.artifact_vault, source_context, campaign_head, kind=kind)
    if source_context is not None:
        await require_reconciled_upstream(ports.project_registry, source_context)
        await require_inherited_baseline(ports.project_registry, source_context)
        derived = await derived_profile_at_pin(ports.project_registry, source_context)
        gap_warnings = await require_no_blocking_gap(
            derived, ports.artifact_vault, source_context, body
        )
        # SIP-0112 H.13: before the effective config is read, so preflight sees what dispatch runs.
        pinned = _pin_blueprint_conventions(body, derived)
        if pinned is not None:
            logger.info(
                "cycle_create_blueprint_conventions",
                extra={"project_id": project_id, "development_profile": pinned},
            )

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
    preflight_warnings = gap_warnings + await _run_create_preflight(
        ports.llm,
        profile,
        effective_config,
        campaign_cycle=campaign_id is not None,
        source_backed=source_context is not None,
    )

    # SIP-0101 Slice 3: replay declaration validated + interim compatibility
    # gate, same fail-fast point (moves into the SIP-0095 preflight in Slice 4).
    await _validate_replay_declaration(ports.cycle_registry, body, applied_defaults)

    # #779 (M0b): a seeded manifest with no contract_ref would run UNBOUND. Derive
    # the contract it implies and pin it as an artifact, so bind mode engages
    # exactly as it does for an operator who ingested one by hand. After this the
    # effective config must be recomputed — the new ref is part of it.
    derived_ref = await _seed_derived_contract(
        ports.artifact_vault, body, project_id, source_backed=source_context is not None
    )
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
        increment_id=increment_id,
        source_context=source_context,
    )
    return PreparedCycle(
        cycle,
        first_run(cycle, initiated_by=initiated_by),
        preflight_warnings,
        await _admitted_instructions(
            cycle, body, actor=instructed_by or created_by, resolvers=ports.reference_resolvers
        ),
    )


@router.post("", status_code=201)
async def create_cycle(
    request: Request,
    project_id: str,
    body: CycleCreateRequest,
    background_tasks: BackgroundTasks,
    identity: Identity | None = Depends(require_scopes(Scope.CYCLES_WRITE)),
) -> CycleCreateResponse:
    """Create a Cycle + first Run (T17: atomic).

    SIP-0066: After persisting, enqueues execute_run as a background task.

    SIP-0109 §9.3 (#1802): the box is read first. While the supervisor holds it, or an engine
    holds a model the active deploy did not declare, the launch is refused with a 409 that
    names the refusal and its reasons, and the refusal is a security-audit event. A campaign's
    own launches are refused by its launcher instead, as a ``launch_blocked`` row.
    """

    verdict = await get_box_reader(request).verdict()
    if not verdict.allowed:
        _audit_launch_refused(request, identity, project_id, verdict)
        raise HTTPException(
            409,
            {
                "error": {
                    "code": "BOX_REFUSED",
                    "message": f"the box refuses a launch ({verdict.refusal}): "
                    + "; ".join(verdict.reasons),
                    "details": {"refusal": str(verdict.refusal), "reasons": list(verdict.reasons)},
                }
            },
        )

    ports = CreationPorts.of_request(request)
    prepared = await prepare_cycle(
        ports, project_id, body, instructed_by=identity.user_id if identity is not None else None
    )
    cycle, run, preflight_warnings = prepared.cycle, prepared.run, prepared.warnings
    snapshot_hash = cycle.squad_profile_snapshot_ref
    config_hash = run.resolved_config_hash
    # #2178: the cycle's task instructions, checked by prepare_cycle before anything is stored.
    instructions, records = prepared.instructions, ports.memory_records
    if instructions and records is None:
        raise http_error(503, "MEMORY_RECORDS_UNAVAILABLE", "no store holds task instructions")

    # Persist atomically (T17)
    await ports.cycle_registry.create_cycle(cycle)
    await ports.cycle_registry.create_run(run)
    await _pin_memory(request, cycle)
    # Before the run is enqueued, so its provisioning reads them.
    if records is not None:
        for record in instructions:
            await records.create(record)

    # SIP-0077: cycle.created

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
        source_context=(
            cycle.source_context.to_document() if cycle.source_context is not None else None
        ),
    )


async def _admitted_instructions(cycle, body, *, actor: str, resolvers) -> tuple:
    """The task instructions a cycle is created with (SIP-0110 Appendix A §3.5; #2178), as
    records, their ``@current`` references bound with the cycle (T16), or the refusal (422) for one
    the rules refuse or that won't bind. Nothing is stored: whoever stores the cycle stores them,
    the route or a campaign's launch, before its first run is enqueued."""
    if not body.task_instructions:
        return ()
    requested = [i.model_dump() for i in body.task_instructions]
    try:
        bound = await bound_for_cycle(
            requested_references(requested), resolvers or {}, cycle_binding(cycle)
        )
        return tuple(
            admitted(
                requested,
                project_id=cycle.project_id,
                cycle_id=cycle.cycle_id,
                actor=actor,
                now=datetime.now(UTC),
                instructable=lambda t: authoring_seam_of(t) is not None,
                source=Source(SourceKind.CYCLE_REQUEST, {"cycle_id": cycle.cycle_id}),
                bound=bound,
            )
        )
    except RecordRefused as e:
        raise ValidationError(str(e)) from e


async def _pin_memory(request: Request, cycle) -> None:
    """SIP-0110 §0.7: a standalone cycle pins its memory snapshot when it is created. Beside the
    launch: a pin that fails is logged, the cycle runs, and its seams record recall as failed."""
    from datetime import UTC, datetime

    store = get_memory_store(request)
    if store is None:
        return
    try:
        await pin_standalone_cycle(
            store,
            cycle,
            now=datetime.now(UTC),
            records=get_memory_records(request),
            resolvers=get_reference_resolvers(request),
        )
    except Exception:
        logger.warning("memory_snapshot_not_pinned cycle=%s", cycle.cycle_id, exc_info=True)


def _audit_launch_refused(
    request: Request, identity: Identity | None, project_id: str, verdict
) -> None:
    """A launch the box refused, to the security audit (§9.3). Fail-open: the refusal stands
    whether or not it is recorded."""

    audit = get_audit_port(request)
    if audit is None:
        return
    audit.record(
        AuditEvent(
            action="cycle.launch_refused",
            actor_id=identity.user_id if identity is not None else "anonymous",
            actor_type=identity.identity_type if identity is not None else "unknown",
            resource_type="project",
            resource_id=project_id,
            result="denied",
            denial_reason=str(verdict.refusal),
            metadata=tuple(("reason", r) for r in verdict.reasons),
            request_id=request.headers.get("X-Request-ID"),
        )
    )


@router.get("", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_cycles(
    request: Request,
    project_id: str,
    status: CycleStatus | None = None,
    page: Page = Depends(page),
) -> list[CycleResponse]:
    """A page of the project's cycles, newest first; ``status`` filters before the page
    (#1891). A full page means there may be more: ask again from ``offset + limit``."""

    registry = get_cycle_registry(request)
    cycles = await registry.list_cycles(
        project_id, status=status, limit=page.limit, offset=page.offset
    )
    # The page's runs in one read (#1976): one query per cycle made a page of 500 cost 501.
    runs = await registry.list_runs_for_cycles([c.cycle_id for c in cycles])
    return [cycle_to_response(c, runs[c.cycle_id]) for c in cycles]


@router.get("/{cycle_id}", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_cycle(request: Request, project_id: str, cycle_id: str) -> CycleResponse:

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

    # deferred (cycle): api.routes.campaigns.campaigns loads this module
    from squadops.api.routes.campaigns.campaigns import actor_from

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
async def cancel_cycle(request: Request, project_id: str, cycle_id: str) -> CycleCancelResponse:
    # deferred (cycle): api.routes.cycles.cancellation loads this module
    from squadops.api.routes.cycles.cancellation import cancel_cycle_by_the_existing_path

    return await cancel_cycle_by_the_existing_path(request, project_id, cycle_id)

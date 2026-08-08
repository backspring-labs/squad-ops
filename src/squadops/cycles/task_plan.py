"""Static task plan generator for cycle execution pipeline.

Produces a deterministic task sequence for the standard squad roles
using pinned task_type values from SIP-0066 §5.4, with optional
build steps from SIP-Enhanced-Agent-Build-Capabilities and builder-aware
routing from SIP-0071.

Workload-type branching (SIP-0078): when ``run.workload_type`` is set,
the generator selects task steps based on workload type instead of
the legacy ``plan_tasks``/``build_tasks`` flags.

Part of SIP-0066 Phase 4 + build capabilities extension + SIP-0071 + SIP-0078.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from squadops.capabilities.context_assembly import get_context_contract
from squadops.capabilities.handlers.build_profiles import (
    ROUTING_BUILDER_PRESENT,
    ROUTING_FALLBACK_NO_BUILDER,
)
from squadops.capabilities.scaffold import (
    InterfaceManifest,
    frozen_surface_index_lines,
    harness_entry_modules,
    is_qa_test_path_for_stack,
    testid_surface_instructions,
)
from squadops.cycles.acceptance_check_spec import (
    CHECK_CONTRACT_ASSERTIONS,
    CHECK_FILL_SLOT_SIGNATURE,
    is_check_applicable,
)
from squadops.cycles.agent_config import resolve_agent_config
from squadops.cycles.failure_evidence import FailureLocus
from squadops.cycles.implementation_plan import (
    ImplementationPlan,
    TypedCheck,
    resolve_contract_refs,
)
from squadops.cycles.manifest_authoring import (
    AUTHOR_MANIFEST_CAPABILITY,
    AUTHOR_MANIFEST_ROLE,
    authors_interface_manifest,
)
from squadops.cycles.models import (
    REQUIRED_PLAN_ROLES,
    VALID_PLAN_AUTHORING_CONTRIBUTORS,
    WORKLOAD_REQUIRED_ROLES,
    Cycle,
    CycleError,
    Run,
    SquadProfile,
    WorkloadType,
)
from squadops.cycles.proposed_role_tasks import role_to_id
from squadops.tasks.models import TaskEnvelope

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from squadops.cycles.verification_contract import VerificationContract

# Pinned task_type → role mapping (SIP-0066 §5.4)
CYCLE_TASK_STEPS: list[tuple[str, str]] = [
    ("strategy.analyze_prd", "strat"),
    ("development.design", "dev"),
    ("qa.validate", "qa"),
    ("data.report", "data"),
    ("governance.review", "lead"),
]

# Build task steps (SIP-Enhanced-Agent-Build-Capabilities)
BUILD_TASK_STEPS: list[tuple[str, str]] = [
    ("development.develop", "dev"),
    ("qa.test", "qa"),
]

# Builder-aware build steps (SIP-0071)
BUILDER_ASSEMBLY_TASK_STEPS: list[tuple[str, str]] = [
    ("development.develop", "dev"),
    ("builder.assemble", "builder"),
    ("qa.test", "qa"),
]

# Framing task steps — pre-SIP-0093 backbone. The four upstream framing
# tasks (data → strategy → dev → qa) are stable. The post-framing tail
# changes after SIP-0093 PR 93.3 cutover: brief → proposers → merger →
# review_plan. The full sequence is built by ``build_planning_steps``
# below, which threads in the proposer steps per ``plan_authoring_contributors``.
PLANNING_TASK_STEPS: list[tuple[str, str]] = [
    ("data.research_context", "data"),
    ("strategy.frame_objective", "strat"),
    ("development.design_plan", "dev"),
    ("qa.define_test_strategy", "qa"),
    ("governance.prepare_plan_authoring_brief", "lead"),
    ("governance.merge_plan", "lead"),
    ("governance.review_plan", "lead"),
]


# Per SIP-0093 §5.3: role → (task_type, role_id) mapping for the proposer
# steps the framing sequence inserts between brief and merger when that
# role is in ``plan_authoring_contributors``. The role-id column is derived
# from ``proposed_role_tasks.role_to_id`` so it can't drift from the merger's
# dependency-key normalization (issue #189).
_PLAN_AUTHORING_PROPOSER_STEPS: dict[str, tuple[str, str]] = {
    "development": ("development.propose_plan_tasks", role_to_id("development")),
    "qa": ("qa.propose_plan_tasks", role_to_id("qa")),
    "strategy": ("strategy.propose_plan_guidance", role_to_id("strategy")),
}


# Rev 1 contributor vocabulary. ``build`` is reserved for Rev 2 (SIP-0093
# §5.12 — builder-role proposer). Reject early so a typo or premature
# config doesn't silently drop a proposer.
def build_planning_steps(
    plan_authoring_contributors: list[str] | None,
    authors_manifest: bool = False,
) -> list[tuple[str, str]]:
    """Return the framing task sequence per SIP-0093 PR 93.3 cutover.

    The sequence is:
    1. Framing tail (data → strategy → dev → qa) — always.
    2. ``development.author_manifest`` — authored mode only (SIP-0103 §3.1).
    3. ``governance.prepare_plan_authoring_brief`` — always.
    4. Proposer steps for each role in ``plan_authoring_contributors``,
       in canonical order (development, qa, strategy). Sequential per
       Rev 1 (parallel fan-out deferred — see plan-doc amendment).
    5. ``governance.merge_plan`` — always.
    6. ``governance.review_plan`` (sign-off only) — always.

    Empty contributors list → no proposer steps; the merger runs in
    sole-author mode (``no_contributors_configured``).

    ``authors_manifest`` inserts the authoring stage after dev's technical
    design and BEFORE qa's test strategy (#791): dev is best-informed there,
    and qa then writes its strategy against the interface it will be held to
    — §5a's "QA reviews for verifiability" obtained without adding a second
    judgment gate over proofs M3 already makes mechanically.

    Raises:
        CycleError: if any contributor in the list isn't in
            ``VALID_PLAN_AUTHORING_CONTRIBUTORS``. Rejecting at sequence-
            build time fails the cycle early rather than running a partial
            pipeline that drops the misconfigured proposer.
    """
    contributors = list(plan_authoring_contributors or [])
    unknown = set(contributors) - VALID_PLAN_AUTHORING_CONTRIBUTORS
    if unknown:
        raise CycleError(
            "plan_authoring_contributors contains unsupported roles: "
            f"{sorted(unknown)}. Rev 1 supports "
            f"{sorted(VALID_PLAN_AUTHORING_CONTRIBUTORS)}."
        )

    steps: list[tuple[str, str]] = [
        ("data.research_context", "data"),
        ("strategy.frame_objective", "strat"),
        ("development.design_plan", "dev"),
    ]
    if authors_manifest:
        steps.append((AUTHOR_MANIFEST_CAPABILITY, AUTHOR_MANIFEST_ROLE))
    steps.extend(
        [
            ("qa.define_test_strategy", "qa"),
            ("governance.prepare_plan_authoring_brief", "lead"),
        ]
    )
    # Canonical order: development first (largest contribution surface),
    # then qa (gap-catching pen), then strategy (overlay).
    for role in ("development", "qa", "strategy"):
        if role in contributors:
            steps.append(_PLAN_AUTHORING_PROPOSER_STEPS[role])
    steps.extend(
        [
            ("governance.merge_plan", "lead"),
            ("governance.review_plan", "lead"),
        ]
    )
    return steps


# Refinement task steps (SIP-0078 §5.10)
REFINEMENT_TASK_STEPS: list[tuple[str, str]] = [
    ("governance.incorporate_feedback", "lead"),
    ("qa.validate_refinement", "qa"),
]

# Implementation task steps (SIP-0079 §7.2): contract + build steps
IMPLEMENTATION_TASK_STEPS: list[tuple[str, str]] = [
    ("governance.define_done", "lead"),
    ("development.develop", "dev"),
    ("qa.test", "qa"),
]

# Correction protocol task steps (SIP-0079 §7.7)
CORRECTION_TASK_STEPS: list[tuple[str, str]] = [
    ("data.analyze_failure", "data"),
    ("governance.correction_decision", "lead"),
]

# Repair task steps (SIP-0079 §7.7).
# Issue #100: development.correction_repair (NOT development.repair) — the
# latter belongs to the SIP-0070 pulse-check chain in pulse_verification.py.
#
# Default sequence used when the failed task type has no specialized repair
# step registered below. Kept as a module constant for direct import in
# tests and for use as the fallback inside `repair_steps_for`.
#
# Issue #556: the `qa.validate_repair` step that used to follow each repair
# was removed — its verdict had no programmatic consumer; repair acceptance
# is decided deterministically by patch verification (#389) and the
# behavioral retest (#456). Any future LLM judgment on repairs belongs
# AFTER the retest, on the governance role, fail-closed (#557).
REPAIR_TASK_STEPS: list[tuple[str, str]] = [
    ("development.correction_repair", "dev"),
]

# Specialized repair sequences keyed by the failed task's task_type. The
# correction loop dispatches the right sequence instead of always running
# the dev-flavored default — without this mapping a failed `builder.assemble`
# task gets repaired by the dev role (which has no useful context for
# packaging output) and the builder role is silently bypassed even though
# the failed work is the builder's.
_REPAIR_STEPS_BY_FAILED_TASK_TYPE: dict[str, list[tuple[str, str]]] = {
    "development.develop": REPAIR_TASK_STEPS,
    "builder.assemble": [
        ("builder.assemble_repair", "builder"),
    ],
}

# #568: repair sequences reachable ONLY when the failure locus is the failed
# task's OWN artifact (missing/unparseable/uncollectable emission) — the owning
# role re-produces its own artifact. Deliberately a separate table from the
# default above: a qa.test entry in the default table would route BEHAVIORAL
# failures (app failed the tests) to qa re-authoring, i.e. "fix the app by
# rewriting tests until green" — a manufactured false green. Locus is computed
# deterministically (failure_evidence.classify_failure_locus); ambiguity falls
# through to the default table.
QA_TEST_REPAIR_STEPS: list[tuple[str, str]] = [
    ("qa.test_repair", "qa"),
]
_REPAIR_STEPS_BY_FAILED_TASK_TYPE_OWN_ARTIFACT: dict[str, list[tuple[str, str]]] = {
    "qa.test": QA_TEST_REPAIR_STEPS,
}

# pf-31 Fix E: every task type that produces repair-CANDIDATE emissions, derived
# from the dispatch tables above (never re-typed — #559). Candidates land in the
# artifact store for the correction loop's accumulation (RC3), but an ACCEPTED
# patch is re-stored under the repaired task's own type by the #389 accept path —
# so candidate-typed artifacts are, by construction, in-flight or rejected, and
# workspace views for fresh dispatches exclude them by this provenance.
REPAIR_TASK_TYPES: frozenset[str] = (
    frozenset(
        task_type for steps in _REPAIR_STEPS_BY_FAILED_TASK_TYPE.values() for task_type, _ in steps
    )
    | frozenset(
        task_type
        for steps in _REPAIR_STEPS_BY_FAILED_TASK_TYPE_OWN_ARTIFACT.values()
        for task_type, _ in steps
    )
    | frozenset(task_type for task_type, _ in REPAIR_TASK_STEPS)
)


def repair_steps_for(
    failed_task_type: str,
    failure_locus: str | None = None,
) -> list[tuple[str, str]]:
    """Return the repair (task_type, role) sequence for a failed task.

    Looked up by the failed task's `task_type`, which is authoritative —
    the LLM-emitted `affected_task_types` field on a PlanDelta is
    free-text and was previously the only routing signal, so a builder
    failure tagged `["QA Handoff"]` would mis-route to the dev repair
    handler. Falls back to `REPAIR_TASK_STEPS` (dev) for any task type
    without a specialized sequence.

    #568: when ``failure_locus`` is ``FailureLocus.OWN_ARTIFACT``, the
    own-artifact table takes precedence — the failed task's own role
    re-produces its own artifact. Any other locus (including ``None`` and
    ``UNKNOWN``) uses the default tables unchanged.
    """
    if failure_locus == FailureLocus.OWN_ARTIFACT:
        specialized = _REPAIR_STEPS_BY_FAILED_TASK_TYPE_OWN_ARTIFACT.get(failed_task_type)
        if specialized is not None:
            return specialized
    return _REPAIR_STEPS_BY_FAILED_TASK_TYPE.get(failed_task_type, REPAIR_TASK_STEPS)


# Wrap-up task steps (SIP-0080 §7.1)
WRAPUP_TASK_STEPS: list[tuple[str, str]] = [
    ("data.gather_evidence", "data"),
    ("qa.assess_outcomes", "qa"),
    ("data.classify_unresolved", "data"),
    ("governance.closeout_decision", "lead"),
    ("governance.publish_handoff", "lead"),
]

# Well-known workload types that have dedicated step selection.
_KNOWN_WORKLOAD_TYPES = {
    WorkloadType.FRAMING,
    WorkloadType.IMPLEMENTATION,
    WorkloadType.REFINEMENT,
    WorkloadType.EVALUATION,
    WorkloadType.WRAPUP,
}

# Task types that are build steps (for routing_reason metadata)
_BUILD_TASK_TYPES = {s[0] for s in BUILD_TASK_STEPS} | {s[0] for s in BUILDER_ASSEMBLY_TASK_STEPS}

# Workload-invariant tail (#439): assembly and verification are workload-owned.
# Plan substitution may replace dev work but must never descope these — a
# dev-only manifest that dropped them completed green with no build subject
# (every required check `subject_missing` → blocked_unverified).
# Canonical execution order of the workload-invariant tail: assembly, then
# verification. Verification must be the last word on the deliverable (#458).
_WORKLOAD_INVARIANT_TAIL_ORDER = ("builder.assemble", "qa.test")
_WORKLOAD_INVARIANT_TASK_TYPES = frozenset(_WORKLOAD_INVARIANT_TAIL_ORDER)

# Builder-role (SIP-0071) capability namespace. A run is a *builder deliverable*
# run — subject to the profile-level ``required_files`` completeness gate
# (#291) — iff its plan contains a ``builder.*`` task. This is deliberately
# narrower than ``_BUILD_TASK_TYPES``: the generic ``development.develop`` /
# ``qa.test`` steps are shared by plain build-only runs that have no build
# profile and emit source, not a packaged deliverable.
BUILDER_TASK_TYPE_PREFIX = "builder."


def plan_has_builder_task(plan: list[TaskEnvelope]) -> bool:
    """True when the plan contains a builder-role assembly task (#291).

    Distinguishes a builder deliverable run (a build profile with
    ``required_files`` applies) from a plain develop+test build run, which
    reuses the ``development.develop`` / ``qa.test`` task types but produces
    no packaged deliverable to check for completeness.
    """
    return any(t.task_type.startswith(BUILDER_TASK_TYPE_PREFIX) for t in plan)


def _has_builder_role(profile: SquadProfile) -> bool:
    """Check if squad profile includes a builder role agent.

    V1: presence-only detection (any(...)). Multi-builder selection
    behavior is out of scope and not specified by this plan.
    """
    return any(a.role == "builder" and a.enabled for a in profile.agents)


def _check_required_roles(
    profile_id: str, required: set[str], available: set[str], label: str = ""
) -> None:
    """Raise CycleError if required roles are missing from profile."""
    missing = required - available
    if missing:
        qualifier = f"{label} " if label else ""
        raise CycleError(
            f"Squad profile '{profile_id}' is missing required {qualifier}roles: "
            f"{', '.join(sorted(missing))}"
        )


def _resolve_workload_steps(
    workload_type: str,
    profile: SquadProfile,
    profile_roles: set[str],
    resolved_config: dict | None = None,
) -> tuple[list, bool]:
    """Select task steps and builder flag based on workload type (SIP-0078)."""
    if workload_type not in _KNOWN_WORKLOAD_TYPES:
        raise CycleError(
            f"Unknown workload_type '{workload_type}'. "
            f"Known types: {', '.join(sorted(_KNOWN_WORKLOAD_TYPES))}"
        )

    builder_used = False

    if workload_type == WorkloadType.FRAMING:
        _check_required_roles(
            profile.profile_id, WORKLOAD_REQUIRED_ROLES[workload_type], profile_roles
        )
        # SIP-0093 PR 93.3: framing sequence is dynamic per
        # plan_authoring_contributors config. Empty/missing contributors
        # → sole-author route through the merger.
        contributors = (resolved_config or {}).get("plan_authoring_contributors")
        steps = build_planning_steps(
            contributors,
            authors_manifest=authors_interface_manifest(resolved_config),
        )
    elif workload_type == WorkloadType.REFINEMENT:
        _check_required_roles(
            profile.profile_id, WORKLOAD_REQUIRED_ROLES[workload_type], profile_roles, "refinement"
        )
        steps = list(REFINEMENT_TASK_STEPS)
    elif workload_type == WorkloadType.IMPLEMENTATION:
        builder_used = _has_builder_role(profile)
        if builder_used:
            steps = list(IMPLEMENTATION_TASK_STEPS[:1]) + list(BUILDER_ASSEMBLY_TASK_STEPS)
        else:
            steps = list(IMPLEMENTATION_TASK_STEPS)
    elif workload_type == WorkloadType.EVALUATION:
        _check_required_roles(
            profile.profile_id, WORKLOAD_REQUIRED_ROLES[workload_type], profile_roles
        )
        steps = list(CYCLE_TASK_STEPS)
    elif workload_type == WorkloadType.WRAPUP:
        _check_required_roles(
            profile.profile_id, WORKLOAD_REQUIRED_ROLES[workload_type], profile_roles, "wrap-up"
        )
        steps = list(WRAPUP_TASK_STEPS)
    else:
        steps = []

    return steps, builder_used


def _resolve_legacy_steps(
    cycle: Cycle, profile: SquadProfile, profile_roles: set[str]
) -> tuple[list, bool]:
    """Select task steps from legacy plan_tasks/build_tasks flags."""
    include_plan = bool(cycle.resolved_config().get("plan_tasks", True))
    include_build = bool(cycle.resolved_config().get("build_tasks"))
    builder_used = include_build and _has_builder_role(profile)

    steps: list = []
    if include_plan:
        steps.extend(CYCLE_TASK_STEPS)
    if include_build:
        if builder_used:
            steps.extend(BUILDER_ASSEMBLY_TASK_STEPS)
        else:
            steps.extend(BUILD_TASK_STEPS)

    if include_plan:
        _check_required_roles(profile.profile_id, REQUIRED_PLAN_ROLES, profile_roles)

    return steps, builder_used


def _applicable_acceptance(plan_task: Any) -> list:
    """The task's authored acceptance criteria, minus checks that can never evaluate.

    pf-47/pf-49: the author dresses non-Python files in Python-AST checks (pytest
    idioms on ``.jsx`` test files) because the vocabulary never told it which checks
    apply where. Such a check skips at every evaluation forever — and a QA task whose
    checks are ALL dead can never land a repair (zero executed blocking checks →
    unverifiable → fail closed): both rolls burned their full correction budgets
    rejecting repairs unheard. Stripped at dispatch, loudly; the vocabulary now
    teaches applicability so authored plans converge, and this is the deterministic
    backstop.
    """
    acceptance: list = []
    for criterion in plan_task.acceptance_criteria:
        if isinstance(criterion, TypedCheck):
            target = str(criterion.params.get("file", ""))
            if target and not is_check_applicable(criterion.check, target):
                logger.warning(
                    "inapplicable_check_stripped task=%s check=%s file=%s — the "
                    "evaluator cannot parse this file type; the check would skip "
                    "at every evaluation (pf-47/pf-49 deadlock class)",
                    plan_task.task_index,
                    criterion.check,
                    target,
                )
                continue
        acceptance.append(criterion)
    return acceptance


def _inject_rejection_context(
    inputs: dict[str, Any], rejection_context: Any, task_type: str
) -> None:
    """#669: thread the prior framing's rejection into plan-authoring inputs.

    A #522 framing re-roll previously granted fresh dice with zero context —
    the validator's teaching message was persisted in gate_decisions and read
    by nobody, so the re-roll was free to re-emit the exact rejected shape
    (fay-10 tripped the same ownership class on all three framings). Data-only
    keys; the authoring handlers render them through a managed appendix asset
    (CLAUDE.md #448). Non-re-roll runs carry no context and get no keys.

    #663 S3: WHO receives the context is the registry's declaration
    (``plan_rejection_context`` — the four authoring types, merger excluded);
    this composer owns only the derivation and injection mechanics.
    """
    if not isinstance(rejection_context, dict):
        return
    if not get_context_contract(task_type).plan_rejection_context:
        return
    reasons = [
        str(r).strip() for r in (rejection_context.get("rejection_reasons") or []) if str(r).strip()
    ]
    if not reasons:
        return
    inputs["rejection_reasons"] = reasons
    plan_yaml = str(rejection_context.get("rejected_plan_yaml") or "")
    if plan_yaml.strip():
        inputs["rejected_plan_yaml"] = plan_yaml


def _inject_contract_inputs(
    inputs: dict,
    contract: VerificationContract | None,
    task_type: str,
    interface_manifest: InterfaceManifest | None = None,
) -> None:
    """Bind-mode envelope inputs derived from the seeded contract (SIP-0098).

    98.3 (§6.3): dev/qa proposers receive the criteria index so they *bind*
    (list ``criteria_refs``) rather than author covered-file criteria; only the
    index data is injected here — the bind instruction prose lives in the
    proposer's managed prompt asset (CLAUDE.md #448). Strategy proposes
    guidance, not build tasks, so it is not indexed.

    98.5 (§6.4): qa.test carries the contract's behavioral probes (serialized
    ``Probe`` dicts — envelope inputs are JSON). The qa handler reconstructs and
    executes them against the built workspace, so probe evidence lands in
    live-cycle runs, not only the CI gate. Probe-less contracts inject no key.
    #688 adds the endpoint→fill-slot ownership map alongside them, so a repair
    born of a failing probe can be aimed at the slot that owns the endpoint.

    Author mode (``contract is None``) injects nothing — contract-less cycles
    stay byte-identical.

    #663 S3: WHO receives each bind-mode input class is the registry's
    declaration (``bind_criteria_index`` / ``bind_behavioral_surface``); this
    composer owns only the contract/manifest derivation mechanics.
    """
    if contract is None:
        return
    task_contract = get_context_contract(task_type)
    if task_contract.bind_criteria_index:
        inputs["contract_criteria_index"] = "\n".join(contract.criteria_index_lines())
        # pf-42: the criteria index covers the fill slots only — four files of
        # seventeen. The rest are frozen, and the proposer was never told they exist,
        # so a check it wanted on one was written against an invented interior
        # (``RunEvent.meeting_location`` for the declared ``location``). Same data-only
        # injection as the index above; the instruction prose is a managed asset (#448).
        frozen_index = frozen_surface_index_lines(interface_manifest)
        if frozen_index:
            inputs["frozen_surface_index"] = "\n".join(frozen_index)
    if task_contract.bind_behavioral_surface:
        if contract.behavioral.probes:
            inputs["contract_probes"] = [p.to_dict() for p in contract.behavioral.probes]
            # #688: the endpoint→fill-slot ownership map, so a correction born of a
            # FAILING probe can aim the repair at the slot that owns the failing
            # endpoint. Threaded with the probes because it is only meaningful
            # alongside them — probe-less contracts inject neither key and stay
            # byte-identical. Data only; no prose (#448).
            endpoint_owners = contract.endpoint_owners()
            if endpoint_owners:
                inputs["contract_endpoint_owners"] = endpoint_owners
        # #629 / pf-54: the contract's pinned statuses (probe expects + the
        # error-code→status map) never reached suite AUTHORING — five authored
        # suite versions asserted 200 where the probe pinned 201, an unwinnable
        # loop no source repair could satisfy. Data-only injection; the
        # "assertions must match" prose is a managed asset (#448).
        behavior_lines = contract.behavior_expectation_lines()
        if behavior_lines:
            inputs["api_behavior_contract"] = behavior_lines
        # #659: the DOM anchor inventory — the api_behavior_contract move
        # applied to the frontend. Suites that query manifest-pinned testids
        # assert a surface dev is told to preserve, instead of inventing
        # roles/text the view never promised (fay-6/fay-12 churn). Data only;
        # the query-only-these prose is a managed asset (#448).
        testid_lines = testid_surface_instructions(interface_manifest)
        if testid_lines:
            inputs["dom_testid_surface"] = testid_lines


def _contract_assertion_criteria(
    task_type: str, plan_task: Any, contract: VerificationContract | None
) -> list[TypedCheck]:
    """#629 (1.5 A6/D2): contract-owned ``contract_assertions_match`` checks for a bound
    qa.test task — one per expected ``.py`` suite file in the stack's QA namespace, params
    carrying the contract's pinned statuses as self-contained data (``METHOD /path STATUS``
    tokens + the suite-wide allowed error statuses), so the evaluator needs no contract
    access. pf-54: five authored suite versions asserted 200 where the probe pinned 201 —
    the authoring injection (layer 1) states the pins; this check enforces them. Empty in
    author mode, non-qa tasks, and probe-less contracts (byte-identical plans there)."""
    if task_type != "qa.test" or contract is None:
        return []
    pinned = contract.pinned_endpoint_statuses()
    if not pinned:
        return []
    endpoints = [
        f"{method} {path} {status}"
        for (method, path), statuses in sorted(pinned.items())
        for status in statuses
    ]
    params: dict[str, Any] = {"endpoints": endpoints}
    error_statuses = contract.allowed_error_statuses()
    if error_statuses:
        params["allowed_error_statuses"] = list(error_statuses)
    stack = contract.skeleton.expander
    return [
        TypedCheck(
            check=CHECK_CONTRACT_ASSERTIONS,
            params={"file": art, **params},
            id=f"contract-assertions:{art}",
        )
        for art in plan_task.expected_artifacts
        if art.endswith(".py") and is_qa_test_path_for_stack(art, stack)
    ]


def _harness_boundary_criteria(
    task_type: str, plan_task: Any, contract: VerificationContract | None
) -> list[TypedCheck]:
    """SIP-0100 1.1: scaffold-owned ``harness_boundary`` checks for a bound qa.test task — one per
    Python test file in the stack's QA namespace, so a suite that re-derives the app boundary
    (pf-25/26: ``from app.main import app``) is rejected mechanically (the harness prompt is only
    guidance; this is the guarantee). Empty in author mode, non-qa tasks, or a stack with no
    declared boundary. Scoped to ``.py`` — ``harness_boundary`` is a Python-AST check; frontend
    ``.jsx`` tests carry their own boundary check (future)."""
    if task_type != "qa.test" or contract is None:
        return []
    stack = contract.skeleton.expander
    entry = list(harness_entry_modules(stack))
    if not entry:
        return []
    return [
        TypedCheck(
            check="harness_boundary",
            params={"file": art, "entry_modules": entry},
            id=f"scaffold-harness:{art}",
        )
        for art in plan_task.expected_artifacts
        if art.endswith(".py") and is_qa_test_path_for_stack(art, stack)
    ]


def _fill_slot_signature_criteria(
    task_type: str,
    plan_task: Any,
    interface_manifest: InterfaceManifest | None,
) -> list[TypedCheck]:
    """#730 D1 / #504: scaffold-owned ``fill_slot_signature`` checks for a dev task
    authoring ``.py`` fill slots — the pf-40 report promoted to blocking. Params carry
    the seed's declared signature surface (handler name, parameter names,
    response_model), derived from the manifest via the same expander the bound record
    uses, so the evaluator needs no scaffold access. Empty for manifest-less cycles,
    non-scaffoldable stacks, non-dev tasks, and tasks that claim no ``.py`` fill slot
    (the ``.jsx`` slots are #668/D3's territory). status_code and the router
    assignment stay restore-owned (SIP-0100), deliberately outside this check."""
    if task_type != "development.develop" or interface_manifest is None:
        return []
    from squadops.capabilities.scaffold import expand, fill_slot_paths, is_scaffoldable_stack
    from squadops.cycles.bound_scaffold_record import _normalize
    from squadops.cycles.fill_slot_integrity import declared_route_signatures

    if not is_scaffoldable_stack(getattr(interface_manifest, "stack", "")):
        return []
    fill = {_normalize(p) for p in fill_slot_paths(interface_manifest)}
    claimed = [
        art
        for art in plan_task.expected_artifacts
        if art.endswith(".py") and _normalize(art) in fill
    ]
    if not claimed:
        return []
    seeds = {_normalize(f["name"]): f["content"] for f in expand(interface_manifest)}
    checks: list[TypedCheck] = []
    for art in claimed:
        routes = declared_route_signatures(seeds.get(_normalize(art), ""))
        if routes:
            checks.append(
                TypedCheck(
                    check=CHECK_FILL_SLOT_SIGNATURE,
                    params={"file": art, "routes": routes},
                    id=f"fill-slot-signature:{art}",
                )
            )
    return checks


def _bind_plan_criteria(plan, contract):
    """#509: same deterministic binding the plan-validation gate applies —
    dispatch and validation must see one plan. Criterion linkage comes from
    the contract, never from the author's transcription."""
    if contract is None:
        return plan
    bound, notes = plan.with_contract_criteria_bound(contract)
    for note in notes:
        logger.info("criteria_auto_bound (dispatch): %s", note)
    return bound


def generate_task_plan(
    cycle: Cycle,
    run: Run,
    profile: SquadProfile,
    plan: ImplementationPlan | None = None,
    contract: VerificationContract | None = None,
    interface_manifest: InterfaceManifest | None = None,
) -> list[TaskEnvelope]:
    """Generate a task plan for a cycle run.

    When ``run.workload_type`` is set, selects task steps based on workload
    type (SIP-0078). Otherwise falls back to legacy ``plan_tasks`` /
    ``build_tasks`` flags from ``applied_defaults``.

    When a ``plan`` is provided (SIP-0086 / SIP-0092), the build-phase segment
    is materialized from the approved implementation plan instead of static
    ``BUILD_TASK_STEPS``. The approved plan is the build-phase contract;
    ``TaskEnvelope`` objects are its deterministic execution materialization.

    Args:
        cycle: The cycle containing experiment config.
        run: The run to generate tasks for.
        profile: The squad profile for agent resolution.
        plan: Optional approved implementation plan (SIP-0086 / SIP-0092).
        contract: Optional seeded verification contract (SIP-0098 98.3). When
            present the cycle is in bind mode: the plan is validated to *bind*
            the contract's criteria by id (net-a, raises), and each task's
            ``criteria_refs`` resolve into TypedChecks. Absent = author mode.

    Returns:
        Ordered list of TaskEnvelopes, one per pipeline step.
    """
    profile_roles = {a.role for a in profile.agents if a.enabled}

    # SIP-0093 PR 93.3: framing workload threads plan_authoring_contributors
    # through resolved_config so the proposer steps are added/skipped per
    # cycle config. Other workload types ignore the extra argument.
    resolved_config = cycle.resolved_config()
    # #669: a framing re-roll forwards the prior rejection on the §6.6 overrides
    # rail. It is authoring CONTEXT, not config — lift it out so resolved_config
    # stays config-shaped on every envelope, then inject it onto the
    # plan-authoring tasks only (below).
    framing_rejection_context = resolved_config.pop("framing_rejection_context", None)

    if run.workload_type is not None:
        steps, builder_used = _resolve_workload_steps(
            run.workload_type, profile, profile_roles, resolved_config
        )
    else:
        steps, builder_used = _resolve_legacy_steps(cycle, profile, profile_roles)

    # SIP-0086: replace static build steps with plan-derived steps.
    # Only applies when the step list actually contains build steps.
    has_build_steps = any(s[0] in _BUILD_TASK_TYPES for s in steps)
    _require_plan_for_instrumented_cycle(plan, has_build_steps, resolved_config)
    if plan is not None and has_build_steps:
        plan = _bind_plan_criteria(plan, contract)
        steps = _replace_build_steps_with_plan(steps, plan, profile, profile_roles, contract)

    # Shared lineage IDs for the entire plan
    correlation_id = uuid4().hex
    trace_id = uuid4().hex

    # Routing reason for build step metadata (D14)
    routing_reason = ROUTING_BUILDER_PRESENT if builder_used else ROUTING_FALLBACK_NO_BUILDER

    # RC-1 (SIP-0079): Deterministic task IDs for implementation runs.
    # RC-2 (SIP-0086): Manifest-derived IDs use -m{index}- namespace.
    use_deterministic_ids = (
        run.workload_type is not None and run.workload_type == WorkloadType.IMPLEMENTATION
    )

    envelopes: list[TaskEnvelope] = []
    prev_task_id: str | None = None

    # #94: resolve each step's agent once and count per-agent (≈ per-role, since
    # the squad maps one agent to one role) so the Prefect label can read
    # "{agent}[{n}/{total}]" — position within that agent's work, not a global
    # index. ``lane_seen`` advances in dispatch order to give the 1-based n.
    step_resolutions = [
        resolve_agent_config(s[1] if isinstance(s, tuple) else s.role, profile) for s in steps
    ]
    lane_totals = Counter(r.agent_id for r in step_resolutions)
    lane_seen: dict[str, int] = {}

    # RC2 (pf-24): the plan's implementation source surface — every
    # development.develop task's expected_artifacts. Threaded onto qa.test envelopes
    # (below) so a no-drift qa.test correction can retarget the source under test
    # (package-scoped in _resolve_repair_target) instead of only re-emitting the
    # test file, which orphaned the buggy source (missing /api prefix in main.py)
    # and exhausted the loop. A static plan fact, computed once.
    implementation_artifacts = [
        artifact
        for s in steps
        if not isinstance(s, tuple) and getattr(s, "task_type", None) == "development.develop"
        for artifact in (getattr(s, "expected_artifacts", None) or [])
    ]

    for step_index, step in enumerate(steps):
        # Steps are either (task_type, role) tuples or PlanTask objects
        if isinstance(step, tuple):
            task_type, role = step
            plan_task = None
        else:
            task_type = step.task_type
            role = step.role
            plan_task = step

        # Determine task ID
        if plan_task is not None:
            # SIP-0086 RC-2: deterministic plan-task namespace
            task_id = f"task-{run.run_id[:12]}-m{plan_task.task_index:03d}-{task_type}"
        elif use_deterministic_ids:
            task_id = f"task-{run.run_id[:12]}-{step_index:03d}-{task_type}"
        else:
            task_id = uuid4().hex

        pulse_id = uuid4().hex
        span_id = uuid4().hex
        causation_id = prev_task_id or correlation_id

        resolved = step_resolutions[step_index]
        agent_id = resolved.agent_id
        agent_model = resolved.model
        agent_overrides = resolved.config_overrides

        metadata: dict = {
            "step_index": step_index,
            "role": role,
        }

        # Add routing_reason only on build step envelopes
        if task_type in _BUILD_TASK_TYPES:
            metadata["routing_reason"] = routing_reason

        inputs: dict = {
            "prd": cycle.prd_ref,
            "resolved_config": resolved_config,
            "config_hash": run.resolved_config_hash,
            "agent_model": agent_model,
            "agent_config_overrides": agent_overrides,
            # SIP-0086: expose active profile roles so planning handlers can
            # constrain plan role choices to what the squad actually has.
            "profile_roles": sorted(profile_roles),
        }

        # #94: per-agent position/total for the Prefect "{agent}[{n}/{total}]" label
        lane_seen[agent_id] = lane_seen.get(agent_id, 0) + 1
        inputs["role_index"] = lane_seen[agent_id]
        inputs["role_total"] = lane_totals[agent_id]

        # SIP-0086: populate subtask fields from plan
        if plan_task is not None:
            inputs["subtask_focus"] = plan_task.focus
            inputs["subtask_description"] = plan_task.description
            inputs["expected_artifacts"] = plan_task.expected_artifacts
            inputs["subtask_index"] = plan_task.task_index
            # RC2: only qa.test failures need the source-under-test surface — their
            # own artifacts are the test files, so a no-drift correction must reach
            # past them to the dev source. Dev tasks already own their source
            # artifact, so omitting the key keeps their corrections byte-identical.
            if task_type == "qa.test":
                inputs["implementation_artifacts"] = implementation_artifacts
            acceptance = _applicable_acceptance(plan_task)
            # SIP-0098 98.3: in bind mode, resolve the task's criteria_refs into
            # TypedChecks (stamped with contract ids) and merge them in. The plan
            # binds by id, dispatch materializes — evaluation is unchanged. Author
            # mode (no contract / no refs) leaves acceptance_criteria as authored.
            if contract is not None and plan_task.criteria_refs:
                acceptance.extend(resolve_contract_refs(plan_task.criteria_refs, contract))
            # SIP-0100 1.1: bind scaffold-owned harness_boundary checks onto bound qa.test slots.
            acceptance.extend(_harness_boundary_criteria(task_type, plan_task, contract))
            # #629 (A6/D2): bind contract-owned assertion-vs-contract checks onto
            # bound qa.test suite files — layer 1's authoring block is guidance,
            # this is the guarantee.
            acceptance.extend(_contract_assertion_criteria(task_type, plan_task, contract))
            # #730 D1 / #504: scaffold-owned signature enforcement on .py fill
            # slots — the pf-40 report, promoted to blocking.
            acceptance.extend(
                _fill_slot_signature_criteria(task_type, plan_task, interface_manifest)
            )
            inputs["acceptance_criteria"] = acceptance

        _inject_contract_inputs(inputs, contract, task_type, interface_manifest)
        _inject_rejection_context(inputs, framing_rejection_context, task_type)

        envelope = TaskEnvelope(
            task_id=task_id,
            agent_id=agent_id,
            cycle_id=cycle.cycle_id,
            pulse_id=pulse_id,
            project_id=cycle.project_id,
            task_type=task_type,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            span_id=span_id,
            inputs=inputs,
            metadata=metadata,
        )
        envelopes.append(envelope)
        prev_task_id = task_id

    # #392: a builder deliverable needs an explicit build_profile — there is no
    # useful default (a builder must not assemble for an assumed stack, and the
    # #291 completeness gate would otherwise check the wrong profile's required
    # files). Reject at plan generation, the single point where builder-in-play
    # is known with config in hand — before any builder task is dispatched.
    if plan_has_builder_task(envelopes) and not resolved_config.get("build_profile"):
        raise CycleError(
            "build_profile is required when the plan includes a builder task, but none "
            "was configured. Set build_profile in the cycle request profile — there is "
            "no default (a builder must not assemble for an assumed stack)."
        )

    _attach_unbound_contract_criteria(envelopes, plan, contract)

    return envelopes


def _attach_unbound_contract_criteria(
    envelopes: list[TaskEnvelope],
    plan: ImplementationPlan | None,
    contract: VerificationContract | None,
) -> None:
    """Attach every contract criterion no plan task bound to the tail qa.test (#509).

    The bind nets key on exact string matches between LLM-authored plan fields
    (``expected_artifacts``, typed-check ``file`` params) and contract fill paths,
    so a plan that names a covered file differently binds nothing for it and
    sails through — criterion coverage then varies roll to roll with plan
    authoring (criteria_total went 3 → 1 → 1 across identical contracts in the
    night rolls). The contract, not the plan, is the last word on verification:
    the residue resolves into criterion-stamped TypedChecks on the final qa.test
    envelope, where the assembled workspace is complete — so every criterion
    produces an evidence row with its ``criterion_id`` on every roll. Bound
    criteria keep their item-level attachment (better repair locality); this is
    the deterministic floor, not a replacement for binding.
    """
    if contract is None:
        return
    bound: set[str] = set()
    if plan is not None:
        for task in plan.tasks:
            bound.update(task.criteria_refs)
    residue = [rid for rid in contract.criterion_index() if rid not in bound]
    if not residue:
        return
    tail_qa = next((e for e in reversed(envelopes) if e.task_type == "qa.test"), None)
    if tail_qa is None:
        return
    existing = list(tail_qa.inputs.get("acceptance_criteria") or [])
    existing.extend(resolve_contract_refs(residue, contract))
    tail_qa.inputs["acceptance_criteria"] = existing


def _validate_plan_against_contract(plan: ImplementationPlan, contract: VerificationContract):
    """Bind-mode dispatch nets: every contract-gated plan validator, raising
    ``CycleError`` on the first failing category (same backstop contract as the
    contract-free nets in ``_replace_build_steps_with_plan``)."""
    ref_errors = plan.validate_criteria_refs(contract)
    if ref_errors:
        raise CycleError("Plan validation failed (contract binding): " + "; ".join(ref_errors))
    # pf-39: a qa.test task declaring scaffold-/dev-owned files as its expected
    # artifacts is unsatisfiable (write authorization refuses the emission) and
    # misdirects any repair scoped to it. Same referent as write authorization,
    # applied at authoring time.
    ownership_errors = plan.validate_qa_artifact_ownership(contract)
    if ownership_errors:
        raise CycleError(
            "Plan validation failed (qa artifact ownership): " + "; ".join(ownership_errors)
        )
    # #658: the same referent for every other role — frozen files are
    # claimable by nobody (fay-12's dev task on the frozen api.js slipped
    # between the qa net and the typed-criteria frozen rule).
    frozen_ownership_errors = plan.validate_frozen_artifact_ownership(contract)
    if frozen_ownership_errors:
        raise CycleError(
            "Plan validation failed (frozen artifact ownership): "
            + "; ".join(frozen_ownership_errors)
        )
    # #671: an import_present requiring a module the scaffold surface cannot
    # provide (fay-17's app.routes) is unwinnable by construction — the
    # surface is closed, so absence is provable at authoring time.
    module_errors = plan.validate_module_existence(contract)
    if module_errors:
        raise CycleError("Plan validation failed (module existence): " + "; ".join(module_errors))
    # pf-31 Fix A3: warning-only prose-vs-contract conflict lint, surfaced for
    # the gate reviewer (never a rejection — reverted-#552 lesson).
    for warning in plan.lint_prose_contract_conflicts(contract):
        logger.warning("Plan prose/contract conflict: %s", warning)


def _require_plan_for_instrumented_cycle(
    plan: ImplementationPlan | None, has_build_steps: bool, resolved_config: dict
) -> None:
    """#424: refuse the static-step fallback when the plan IS the instrument.

    For a profile with ``typed_acceptance``/``implementation_plan``, a missing
    plan must never degrade to static steps — the run would spend itself with
    its instrumentation contract silently absent, caught only by the SIP-0096
    required-check throttle at the very end (cyc_7d2f505e5e8f). Raising here is
    the dispatch backstop (the #291/#392 precedent, single point with config in
    hand); the workload-gate net records the graceful rejection first.
    """
    if plan is not None or not has_build_steps:
        return
    if not (resolved_config.get("implementation_plan") or resolved_config.get("typed_acceptance")):
        return
    raise CycleError(
        "implementation plan required but absent: this cycle's profile sets "
        "typed_acceptance/implementation_plan, so its instrumentation contract "
        "lives in the authored plan — plan authoring collapsed (or the plan "
        "artifact was not forwarded), and falling back to static task steps "
        "would run the cycle with that contract silently absent."
    )


def _replace_build_steps_with_plan(
    steps: list,
    plan: ImplementationPlan,
    profile: SquadProfile,
    profile_roles: set[str],
    contract: VerificationContract | None = None,
) -> list:
    """Replace static build steps with plan-derived PlanTask objects.

    Preserves planning steps; only the build-phase segment is replaced.
    Validates that all plan roles exist in the profile.
    """
    # Validate plan roles against profile
    errors = plan.validate_against_profile(profile)
    if errors:
        raise CycleError(
            f"Plan validation failed against profile '{profile.profile_id}': " + "; ".join(errors)
        )

    # #464 dispatch-time net: fires for every plan-driven run regardless of
    # gate shape — the gate-time checks only ever add an earlier rejection.
    scope_errors = plan.validate_criteria_scope()
    if scope_errors:
        raise CycleError("Plan validation failed (criteria scope): " + "; ".join(scope_errors))

    # #645 dispatch-time nets (contract-independent, same raising backstop
    # pattern): unexecutable command checks and directory-shaped expected
    # artifacts are both provable at authoring time and unwinnable at runtime.
    command_errors = plan.validate_command_checks()
    if command_errors:
        raise CycleError("Plan validation failed (command checks): " + "; ".join(command_errors))
    shape_errors = plan.validate_expected_artifact_shapes()
    if shape_errors:
        raise CycleError("Plan validation failed (expected artifacts): " + "; ".join(shape_errors))
    # #673: two tasks claiming the same expected artifact alias themselves onto
    # one file's fate — repairs mis-scope and last-wins ordering decides whose
    # emission ships (fay-18's dual-claimed test suite).
    duplicate_errors = plan.validate_unique_expected_artifacts()
    if duplicate_errors:
        raise CycleError(
            "Plan validation failed (duplicate expected artifacts): " + "; ".join(duplicate_errors)
        )

    # SIP-0098 98.3 bind-mode dispatch net: when a contract is seeded, the plan
    # must bind the contract's covered-file criteria by id rather than author
    # them. This is the raising backstop; the gate-time net records the graceful
    # #473 rejection first. Contract absent = author mode = no-op.
    if contract is not None:
        _validate_plan_against_contract(plan, contract)

    # Remove static build steps, keep everything else (planning steps)
    static_build_types = {s[0] for s in BUILD_TASK_STEPS} | {
        s[0] for s in BUILDER_ASSEMBLY_TASK_STEPS
    }
    non_build_steps = [s for s in steps if s[0] not in static_build_types]

    # Re-append the workload-invariant tail (#439): assembly/verification
    # steps survive substitution unless the plan authored its own task of
    # that type (which then stands in).
    #
    # Ordering is workload-owned, not plan-owned (#458): plan-authored
    # invariant tasks keep their titles/criteria but move to the tail in
    # canonical order, after every mutation-producing task — otherwise an
    # assembly (or assembly repair) can postdate all test evidence.
    plan_task_types = {t.task_type for t in plan.tasks}
    plan_body = [t for t in plan.tasks if t.task_type not in _WORKLOAD_INVARIANT_TASK_TYPES]

    invariant_tail: list = []
    for task_type in _WORKLOAD_INVARIANT_TAIL_ORDER:
        if task_type in plan_task_types:
            invariant_tail.extend(t for t in plan.tasks if t.task_type == task_type)
        else:
            invariant_tail.extend(s for s in steps if s[0] == task_type)

    # Append plan tasks (PlanTask objects, not tuples), then the tail
    return non_build_steps + plan_body + invariant_tail

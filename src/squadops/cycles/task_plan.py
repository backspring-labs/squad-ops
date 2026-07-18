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

from collections import Counter
from typing import TYPE_CHECKING
from uuid import uuid4

from squadops.capabilities.handlers.build_profiles import (
    ROUTING_BUILDER_PRESENT,
    ROUTING_FALLBACK_NO_BUILDER,
)
from squadops.cycles.agent_config import resolve_agent_config
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    REQUIRED_PLAN_ROLES,
    WORKLOAD_REQUIRED_ROLES,
    Cycle,
    CycleError,
    Run,
    SquadProfile,
    WorkloadType,
)
from squadops.cycles.proposed_role_tasks import role_to_id
from squadops.tasks.models import TaskEnvelope

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
_VALID_PLAN_AUTHORING_CONTRIBUTORS = frozenset({"development", "qa", "strategy"})


def build_planning_steps(
    plan_authoring_contributors: list[str] | None,
) -> list[tuple[str, str]]:
    """Return the framing task sequence per SIP-0093 PR 93.3 cutover.

    The sequence is:
    1. Framing tail (data → strategy → dev → qa) — always.
    2. ``governance.prepare_plan_authoring_brief`` — always.
    3. Proposer steps for each role in ``plan_authoring_contributors``,
       in canonical order (development, qa, strategy). Sequential per
       Rev 1 (parallel fan-out deferred — see plan-doc amendment).
    4. ``governance.merge_plan`` — always.
    5. ``governance.review_plan`` (sign-off only) — always.

    Empty contributors list → no proposer steps; the merger runs in
    sole-author mode (``no_contributors_configured``).

    Raises:
        CycleError: if any contributor in the list isn't in
            ``_VALID_PLAN_AUTHORING_CONTRIBUTORS``. Rejecting at sequence-
            build time fails the cycle early rather than running a partial
            pipeline that drops the misconfigured proposer.
    """
    contributors = list(plan_authoring_contributors or [])
    unknown = set(contributors) - _VALID_PLAN_AUTHORING_CONTRIBUTORS
    if unknown:
        raise CycleError(
            "plan_authoring_contributors contains unsupported roles: "
            f"{sorted(unknown)}. Rev 1 supports "
            f"{sorted(_VALID_PLAN_AUTHORING_CONTRIBUTORS)}."
        )

    steps: list[tuple[str, str]] = [
        ("data.research_context", "data"),
        ("strategy.frame_objective", "strat"),
        ("development.design_plan", "dev"),
        ("qa.define_test_strategy", "qa"),
        ("governance.prepare_plan_authoring_brief", "lead"),
    ]
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
# pair registered below. Kept as a module constant for direct import in
# tests and for use as the fallback inside `repair_steps_for`.
REPAIR_TASK_STEPS: list[tuple[str, str]] = [
    ("development.correction_repair", "dev"),
    ("qa.validate_repair", "qa"),
]

# Specialized repair sequences keyed by the failed task's task_type. The
# correction loop dispatches the right pair instead of always running the
# dev-flavored default — without this mapping a failed `builder.assemble`
# task gets repaired by the dev role (which has no useful context for
# packaging output) and the builder role is silently bypassed even though
# the failed work is the builder's.
_REPAIR_STEPS_BY_FAILED_TASK_TYPE: dict[str, list[tuple[str, str]]] = {
    "development.develop": REPAIR_TASK_STEPS,
    "builder.assemble": [
        ("builder.assemble_repair", "builder"),
        ("qa.validate_repair", "qa"),
    ],
}


def repair_steps_for(failed_task_type: str) -> list[tuple[str, str]]:
    """Return the repair (task_type, role) sequence for a failed task.

    Looked up by the failed task's `task_type`, which is authoritative —
    the LLM-emitted `affected_task_types` field on a PlanDelta is
    free-text and was previously the only routing signal, so a builder
    failure tagged `["QA Handoff"]` would mis-route to the dev repair
    handler. Falls back to `REPAIR_TASK_STEPS` (dev + qa) for any task
    type without a specialized pair.
    """
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
        steps = build_planning_steps(contributors)
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
    include_plan = bool(cycle.applied_defaults.get("plan_tasks", True))
    include_build = bool(cycle.applied_defaults.get("build_tasks"))
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


def generate_task_plan(
    cycle: Cycle,
    run: Run,
    profile: SquadProfile,
    plan: ImplementationPlan | None = None,
    contract: VerificationContract | None = None,
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
    resolved_config = {**cycle.applied_defaults, **cycle.execution_overrides}

    if run.workload_type is not None:
        steps, builder_used = _resolve_workload_steps(
            run.workload_type, profile, profile_roles, resolved_config
        )
    else:
        steps, builder_used = _resolve_legacy_steps(cycle, profile, profile_roles)

    # SIP-0086: replace static build steps with plan-derived steps.
    # Only applies when the step list actually contains build steps.
    has_build_steps = any(s[0] in _BUILD_TASK_TYPES for s in steps)
    if plan is not None and has_build_steps:
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
            inputs["acceptance_criteria"] = plan_task.acceptance_criteria

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

    return envelopes


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

    # SIP-0098 98.3 bind-mode dispatch net: when a contract is seeded, the plan
    # must bind the contract's covered-file criteria by id rather than author
    # them. This is the raising backstop; the gate-time net records the graceful
    # #473 rejection first. Contract absent = author mode = no-op.
    if contract is not None:
        ref_errors = plan.validate_criteria_refs(contract)
        if ref_errors:
            raise CycleError("Plan validation failed (contract binding): " + "; ".join(ref_errors))

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

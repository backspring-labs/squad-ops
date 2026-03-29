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

from uuid import uuid4

from squadops.capabilities.handlers.build_profiles import (
    ROUTING_BUILDER_PRESENT,
    ROUTING_FALLBACK_NO_BUILDER,
)
from squadops.cycles.models import (
    REQUIRED_PLAN_ROLES,
    REQUIRED_REFINEMENT_ROLES,
    REQUIRED_WRAPUP_ROLES,
    Cycle,
    CycleError,
    Run,
    SquadProfile,
    WorkloadType,
)
from squadops.tasks.models import TaskEnvelope

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

# Planning task steps (SIP-0078 §5.3)
PLANNING_TASK_STEPS: list[tuple[str, str]] = [
    ("data.research_context", "data"),
    ("strategy.frame_objective", "strat"),
    ("development.design_plan", "dev"),
    ("qa.define_test_strategy", "qa"),
    ("governance.assess_readiness", "lead"),
]

# Refinement task steps (SIP-0078 §5.10)
REFINEMENT_TASK_STEPS: list[tuple[str, str]] = [
    ("governance.incorporate_feedback", "lead"),
    ("qa.validate_refinement", "qa"),
]

# Implementation task steps (SIP-0079 §7.2): contract + build steps
IMPLEMENTATION_TASK_STEPS: list[tuple[str, str]] = [
    ("governance.establish_contract", "lead"),
    ("development.develop", "dev"),
    ("qa.test", "qa"),
]

# Correction protocol task steps (SIP-0079 §7.7)
CORRECTION_TASK_STEPS: list[tuple[str, str]] = [
    ("data.analyze_failure", "data"),
    ("governance.correction_decision", "lead"),
]

# Repair task steps (SIP-0079 §7.7)
REPAIR_TASK_STEPS: list[tuple[str, str]] = [
    ("development.repair", "dev"),
    ("qa.validate_repair", "qa"),
]

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
    WorkloadType.PLANNING,
    WorkloadType.IMPLEMENTATION,
    WorkloadType.REFINEMENT,
    WorkloadType.EVALUATION,
    WorkloadType.WRAPUP,
}

# Task types that are build steps (for routing_reason metadata)
_BUILD_TASK_TYPES = {s[0] for s in BUILD_TASK_STEPS} | {s[0] for s in BUILDER_ASSEMBLY_TASK_STEPS}


def _resolve_agent_config(profile: SquadProfile, role: str) -> tuple[str, str | None, dict]:
    """Resolve agent config from profile by role.

    Returns:
        (agent_id, model_or_None, config_overrides)
    """
    for agent in profile.agents:
        if agent.role == role and agent.enabled:
            model = agent.model if agent.model else None
            return agent.agent_id, model, dict(agent.config_overrides or {})
    return role, None, {}


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
    workload_type: str, profile: SquadProfile, profile_roles: set[str]
) -> tuple[list, bool]:
    """Select task steps and builder flag based on workload type (SIP-0078)."""
    if workload_type not in _KNOWN_WORKLOAD_TYPES:
        raise CycleError(
            f"Unknown workload_type '{workload_type}'. "
            f"Known types: {', '.join(sorted(_KNOWN_WORKLOAD_TYPES))}"
        )

    builder_used = False

    if workload_type == WorkloadType.PLANNING:
        _check_required_roles(profile.profile_id, REQUIRED_PLAN_ROLES, profile_roles)
        steps = list(PLANNING_TASK_STEPS)
    elif workload_type == WorkloadType.REFINEMENT:
        _check_required_roles(
            profile.profile_id, REQUIRED_REFINEMENT_ROLES, profile_roles, "refinement"
        )
        steps = list(REFINEMENT_TASK_STEPS)
    elif workload_type == WorkloadType.IMPLEMENTATION:
        builder_used = _has_builder_role(profile)
        if builder_used:
            steps = list(IMPLEMENTATION_TASK_STEPS[:1]) + list(BUILDER_ASSEMBLY_TASK_STEPS)
        else:
            steps = list(IMPLEMENTATION_TASK_STEPS)
    elif workload_type == WorkloadType.EVALUATION:
        _check_required_roles(profile.profile_id, REQUIRED_PLAN_ROLES, profile_roles)
        steps = list(CYCLE_TASK_STEPS)
    elif workload_type == WorkloadType.WRAPUP:
        _check_required_roles(profile.profile_id, REQUIRED_WRAPUP_ROLES, profile_roles, "wrap-up")
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


def generate_task_plan(cycle: Cycle, run: Run, profile: SquadProfile) -> list[TaskEnvelope]:
    """Generate a task plan for a cycle run.

    When ``run.workload_type`` is set, selects task steps based on workload
    type (SIP-0078). Otherwise falls back to legacy ``plan_tasks`` /
    ``build_tasks`` flags from ``applied_defaults``.

    Args:
        cycle: The cycle containing experiment config.
        run: The run to generate tasks for.
        profile: The squad profile for agent resolution.

    Returns:
        Ordered list of TaskEnvelopes, one per pipeline step.
    """
    profile_roles = {a.role for a in profile.agents if a.enabled}

    if run.workload_type is not None:
        steps, builder_used = _resolve_workload_steps(run.workload_type, profile, profile_roles)
    else:
        steps, builder_used = _resolve_legacy_steps(cycle, profile, profile_roles)

    # Shared lineage IDs for the entire plan
    correlation_id = uuid4().hex
    trace_id = uuid4().hex

    # Resolved config = applied_defaults merged with execution_overrides
    resolved_config = {**cycle.applied_defaults, **cycle.execution_overrides}

    # Routing reason for build step metadata (D14)
    routing_reason = ROUTING_BUILDER_PRESENT if builder_used else ROUTING_FALLBACK_NO_BUILDER

    # RC-1: Deterministic task IDs for implementation runs (stable across resume).
    use_deterministic_ids = (
        run.workload_type is not None and run.workload_type == WorkloadType.IMPLEMENTATION
    )

    envelopes: list[TaskEnvelope] = []
    prev_task_id: str | None = None

    for step_index, (task_type, role) in enumerate(steps):
        if use_deterministic_ids:
            task_id = f"task-{run.run_id[:12]}-{step_index:03d}-{task_type}"
        else:
            task_id = uuid4().hex
        pulse_id = uuid4().hex
        span_id = uuid4().hex
        causation_id = prev_task_id or correlation_id

        agent_id, agent_model, agent_overrides = _resolve_agent_config(profile, role)

        metadata: dict = {
            "step_index": step_index,
            "role": role,
        }

        # Add routing_reason only on build step envelopes
        if task_type in _BUILD_TASK_TYPES:
            metadata["routing_reason"] = routing_reason

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
            inputs={
                "prd": cycle.prd_ref,
                "resolved_config": resolved_config,
                "config_hash": run.resolved_config_hash,
                "agent_model": agent_model,
                "agent_config_overrides": agent_overrides,
            },
            metadata=metadata,
        )
        envelopes.append(envelope)
        prev_task_id = task_id

    return envelopes

"""Static task plan generator for cycle execution pipeline.

Produces a deterministic task sequence for the standard squad roles
using pinned task_type values from SIP-0066 §5.4, with optional
build steps from SIP-Enhanced-Agent-Build-Capabilities and builder-aware
routing from SIP-0071.

Part of SIP-0066 Phase 4 + build capabilities extension + SIP-0071.
"""

from __future__ import annotations

from uuid import uuid4

from squadops.capabilities.handlers.build_profiles import (
    ROUTING_BUILDER_PRESENT,
    ROUTING_FALLBACK_NO_BUILDER,
)
from squadops.cycles.models import Cycle, Run, SquadProfile
from squadops.tasks.models import TaskEnvelope

# Pinned task_type → role mapping (SIP-0066 §5.4)
CYCLE_TASK_STEPS: list[tuple[str, str]] = [
    ("strategy.analyze_prd", "strat"),
    ("development.implement", "dev"),
    ("qa.validate", "qa"),
    ("data.report", "data"),
    ("governance.review", "lead"),
]

# Build task steps (SIP-Enhanced-Agent-Build-Capabilities)
BUILD_TASK_STEPS: list[tuple[str, str]] = [
    ("development.build", "dev"),
    ("qa.build_validate", "qa"),
]

# Builder-aware build steps (SIP-0071)
BUILDER_BUILD_TASK_STEPS: list[tuple[str, str]] = [
    ("builder.build", "builder"),
    ("qa.build_validate", "qa"),
]

# Task types that are build steps (for routing_reason metadata)
_BUILD_TASK_TYPES = {s[0] for s in BUILD_TASK_STEPS} | {s[0] for s in BUILDER_BUILD_TASK_STEPS}


def _resolve_agent_id(profile: SquadProfile, role: str) -> str:
    """Resolve agent_id from profile by role, fallback to role name."""
    for agent in profile.agents:
        if agent.role == role and agent.enabled:
            return agent.agent_id
    return role


def _has_builder_role(profile: SquadProfile) -> bool:
    """Check if squad profile includes a builder role agent.

    V1: presence-only detection (any(...)). Multi-builder selection
    behavior is out of scope and not specified by this plan.
    """
    return any(a.role == "builder" and a.enabled for a in profile.agents)


def generate_task_plan(
    cycle: Cycle, run: Run, profile: SquadProfile
) -> list[TaskEnvelope]:
    """Generate a task plan for a cycle run.

    Produces plan steps (5 standard) and/or build steps (2) based on
    ``applied_defaults``:

    - ``plan_tasks`` (default True): include the 5 standard plan steps
    - ``build_tasks`` (default falsy): if non-empty, append build steps
    - When builder role present in profile, routes build to ``builder.build``
      instead of ``development.build`` (SIP-0071 D5)

    Args:
        cycle: The cycle containing experiment config.
        run: The run to generate tasks for.
        profile: The squad profile for agent resolution.

    Returns:
        Ordered list of TaskEnvelopes, one per pipeline step.
    """
    # Determine which step groups to include (D7)
    include_plan = bool(cycle.applied_defaults.get("plan_tasks", True))
    include_build = bool(cycle.applied_defaults.get("build_tasks"))

    # Compute routing decision once before step expansion (D5, D14)
    builder_used = include_build and _has_builder_role(profile)

    steps: list[tuple[str, str]] = []
    if include_plan:
        steps.extend(CYCLE_TASK_STEPS)
    if include_build:
        if builder_used:
            steps.extend(BUILDER_BUILD_TASK_STEPS)
        else:
            steps.extend(BUILD_TASK_STEPS)

    # Shared lineage IDs for the entire plan
    correlation_id = uuid4().hex
    trace_id = uuid4().hex

    # Resolved config = applied_defaults merged with execution_overrides
    resolved_config = {**cycle.applied_defaults, **cycle.execution_overrides}

    # Routing reason for build step metadata (D14)
    routing_reason = ROUTING_BUILDER_PRESENT if builder_used else ROUTING_FALLBACK_NO_BUILDER

    envelopes: list[TaskEnvelope] = []
    prev_task_id: str | None = None

    for step_index, (task_type, role) in enumerate(steps):
        task_id = uuid4().hex
        pulse_id = uuid4().hex
        span_id = uuid4().hex
        causation_id = prev_task_id or correlation_id

        agent_id = _resolve_agent_id(profile, role)

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
            },
            metadata=metadata,
        )
        envelopes.append(envelope)
        prev_task_id = task_id

    return envelopes

"""Static task plan generator for cycle execution pipeline.

Produces a deterministic task sequence for the standard squad roles
using pinned task_type values from SIP-0066 §5.4, with optional
build steps from SIP-Enhanced-Agent-Build-Capabilities.

Part of SIP-0066 Phase 4 + build capabilities extension.
"""

from __future__ import annotations

from uuid import uuid4

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


def _resolve_agent_id(profile: SquadProfile, role: str) -> str:
    """Resolve agent_id from profile by role, fallback to role name."""
    for agent in profile.agents:
        if agent.role == role and agent.enabled:
            return agent.agent_id
    return role


def generate_task_plan(
    cycle: Cycle, run: Run, profile: SquadProfile
) -> list[TaskEnvelope]:
    """Generate a task plan for a cycle run.

    Produces plan steps (5 standard) and/or build steps (2) based on
    ``applied_defaults``:

    - ``plan_tasks`` (default True): include the 5 standard plan steps
    - ``build_tasks`` (default falsy): if non-empty, append the 2 build steps

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

    steps: list[tuple[str, str]] = []
    if include_plan:
        steps.extend(CYCLE_TASK_STEPS)
    if include_build:
        steps.extend(BUILD_TASK_STEPS)

    # Shared lineage IDs for the entire plan
    correlation_id = uuid4().hex
    trace_id = uuid4().hex

    # Resolved config = applied_defaults merged with execution_overrides
    resolved_config = {**cycle.applied_defaults, **cycle.execution_overrides}

    envelopes: list[TaskEnvelope] = []
    prev_task_id: str | None = None

    for step_index, (task_type, role) in enumerate(steps):
        task_id = uuid4().hex
        pulse_id = uuid4().hex
        span_id = uuid4().hex
        causation_id = prev_task_id or correlation_id

        agent_id = _resolve_agent_id(profile, role)

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
            metadata={
                "step_index": step_index,
                "role": role,
            },
        )
        envelopes.append(envelope)
        prev_task_id = task_id

    return envelopes

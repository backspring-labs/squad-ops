"""Static task plan generator for cycle execution pipeline.

Produces a deterministic 5-step task sequence for the standard squad roles
using pinned task_type values from SIP-0066 §5.4.

Part of SIP-0066 Phase 4.
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


def _resolve_agent_id(profile: SquadProfile, role: str) -> str:
    """Resolve agent_id from profile by role, fallback to role name."""
    for agent in profile.agents:
        if agent.role == role and agent.enabled:
            return agent.agent_id
    return role



def generate_task_plan(
    cycle: Cycle, run: Run, profile: SquadProfile
) -> list[TaskEnvelope]:
    """Generate a deterministic 5-step task plan for a cycle run.

    Args:
        cycle: The cycle containing experiment config.
        run: The run to generate tasks for.
        profile: The squad profile for agent resolution.

    Returns:
        Ordered list of TaskEnvelopes, one per pipeline step.
    """
    # Shared lineage IDs for the entire plan
    correlation_id = uuid4().hex
    trace_id = uuid4().hex

    # Resolved config = applied_defaults merged with execution_overrides
    resolved_config = {**cycle.applied_defaults, **cycle.execution_overrides}

    envelopes: list[TaskEnvelope] = []
    prev_task_id: str | None = None

    for step_index, (task_type, role) in enumerate(CYCLE_TASK_STEPS):
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

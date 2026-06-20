"""Prefect task-name formatting (extracted from DispatchedFlowExecutor, #185).

The Gantt/flow-graph label for a dispatched task. Kept as a pure function in
its own module so it can be unit-tested in isolation and shared by the three
sites that previously each inlined a divergent copy. This is the first
strangler slice of the executor decomposition (#186).
"""

from __future__ import annotations

from squadops.tasks.models import TaskEnvelope


def build_task_name(envelope: TaskEnvelope) -> str:
    """Build a Gantt-friendly Prefect task name for a dispatched envelope.

    Prefixes with the **agent** that ran the task (``envelope.agent_id``) rather
    than the role: the role already duplicates the ``task_type`` domain segment
    (``qa: qa.define_test_strategy``), whereas the agent identity is strictly
    more informative (``eve: qa.define_test_strategy``). Falls back to the role
    when ``agent_id`` is unset — correction/repair and gate-boundary envelopes
    leave it empty — and to ``"unknown"`` when neither is present. ``agent_id``
    comes from the squad profile, so the label stays profile-configurable.

    Focused-mode envelopes (manifest-decomposed subtasks) render
    ``prefix[idx]: focus`` so the Gantt distinguishes parallel subtasks instead
    of showing N identical ``prefix: task_type`` rows. Non-focused envelopes
    keep ``prefix: task_type``.
    """
    role = envelope.metadata.get("role", "unknown") if envelope.metadata else "unknown"
    prefix = envelope.agent_id or role
    inputs = envelope.inputs or {}
    focus = inputs.get("subtask_focus")
    idx = inputs.get("subtask_index")
    if focus:
        focus_short = str(focus)[:60]
        return f"{prefix}[{idx}]: {focus_short}" if idx is not None else f"{prefix}: {focus_short}"
    return f"{prefix}: {envelope.task_type}"

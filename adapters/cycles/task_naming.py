"""Prefect task-name formatting (extracted from DispatchedFlowExecutor, #185).

The Gantt/flow-graph label for a dispatched task. Kept as a pure function in
its own module so it can be unit-tested in isolation and shared by the three
sites that previously each inlined a divergent copy. This is the first
strangler slice of the executor decomposition (#186).
"""

from __future__ import annotations

from squadops.tasks.models import TaskEnvelope


def _humanize_task_type(task_type: str) -> str:
    """Title for a non-focused task, derived from its ``task_type``.

    Takes the leaf segment and makes it read like a title:
    ``strategy.frame_objective`` → ``Frame objective``,
    ``qa.define_test_strategy`` → ``Define test strategy``. Falls back to the
    raw ``task_type`` if it has no usable leaf.
    """
    leaf = task_type.rsplit(".", 1)[-1].replace("_", " ").replace("-", " ").strip()
    return leaf[:1].upper() + leaf[1:] if leaf else task_type


def build_task_name(envelope: TaskEnvelope) -> str:
    """Build a Gantt-friendly Prefect task name for a dispatched envelope.

    Prefixes with the **agent** that ran the task (``envelope.agent_id``) rather
    than the role: the role already duplicates the ``task_type`` domain segment
    (``qa: qa.define_test_strategy``), whereas the agent identity is strictly
    more informative (``eve: qa.define_test_strategy``). Falls back to the role
    when ``agent_id`` is unset — correction/repair and gate-boundary envelopes
    leave it empty — and to ``"unknown"`` when neither is present. ``agent_id``
    comes from the squad profile, so the label stays profile-configurable.

    Planned-run envelopes (framing + implementation) carry per-agent
    ``role_index``/``role_total`` (#94) and render ``prefix[n/total]: title`` —
    1-based position within that agent's work, so "how far through dev work are
    we" is answerable at a glance and the count reflects per-role progress, not a
    global index. The title is the manifest ``subtask_focus`` when present, else
    the humanized ``task_type`` (so framing tasks gain a readable title too).

    Envelopes without per-agent counts (correction/repair, gate boundaries) keep
    the legacy shape: ``prefix[idx]: focus`` for focused subtasks, else
    ``prefix: task_type``.
    """
    role = envelope.metadata.get("role", "unknown") if envelope.metadata else "unknown"
    prefix = envelope.agent_id or role
    inputs = envelope.inputs or {}
    focus = inputs.get("subtask_focus")
    title = str(focus)[:60] if focus else _humanize_task_type(envelope.task_type)

    n = inputs.get("role_index")
    total = inputs.get("role_total")
    if n is not None and total is not None:
        return f"{prefix}[{n}/{total}]: {title}"

    # Legacy fallback for envelopes built outside the plan (no per-agent counts).
    idx = inputs.get("subtask_index")
    if focus:
        return f"{prefix}[{idx}]: {title}" if idx is not None else f"{prefix}: {title}"
    return f"{prefix}: {envelope.task_type}"

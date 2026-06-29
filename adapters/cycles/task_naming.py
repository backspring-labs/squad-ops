"""Prefect task-name formatting (extracted from DispatchedFlowExecutor, #185).

The Gantt/flow-graph label for a dispatched task. Kept as a pure function in
its own module so it can be unit-tested in isolation and shared by the three
sites that previously each inlined a divergent copy. This is the first
strangler slice of the executor decomposition (#186).
"""

from __future__ import annotations

from squadops.tasks.models import TaskEnvelope

# Separates the structural task_type from a subtask's free-text focus, e.g.
# ``development.develop — implement POST /runs``.
_FOCUS_SEPARATOR = " — "
_FOCUS_MAX_LEN = 60


def build_task_name(envelope: TaskEnvelope) -> str:
    """Build a Gantt-friendly Prefect task name for a dispatched envelope.

    Shape: ``{agent} [{n}/{total}]: {task_type}[ — {focus}]``.

    **Prefix** — the *agent* that ran the task (``envelope.agent_id``), falling
    back to the role (``metadata["role"]``) when ``agent_id`` is unset
    (correction/repair and gate-boundary envelopes leave it empty), then to
    ``"unknown"``. ``agent_id`` comes from the squad profile, so the label stays
    profile-configurable.

    **Descriptor** — the raw ``task_type`` (#277). Its domain segment is the
    role (``qa.define_test_strategy``), so the raw value restores the role
    identity the agent prefix alone would lose, *and* keeps the verb — strictly
    more information than a humanized leaf (``qa.define_test_strategy`` →
    "Test"). When a subtask carries a free-text ``subtask_focus`` (build
    subtasks, e.g. "implement POST /runs"), it is appended after an em dash and
    truncated to keep the label Gantt-sized; the ``task_type`` spine stays so the
    label is uniform and greppable.

    **Count** — planned-run envelopes (framing + implementation) carry per-agent
    ``role_index``/``role_total`` (#94) and render ``[n/total]`` — 1-based
    position within *that agent's* work, so "how far through dev work are we" is
    answerable at a glance. The bracket is spaced off the prefix (``neo [2/5]``,
    not ``neo[2/5]``) so it doesn't read as an array subscript (#277). Envelopes
    built outside the plan (correction/repair, gate boundaries) carry no per-agent
    count; a legacy ``subtask_index`` still renders as ``[idx]``, otherwise the
    count is omitted.
    """
    role = envelope.metadata.get("role", "unknown") if envelope.metadata else "unknown"
    prefix = envelope.agent_id or role
    inputs = envelope.inputs or {}

    descriptor = envelope.task_type
    focus = inputs.get("subtask_focus")
    if focus:
        descriptor = f"{envelope.task_type}{_FOCUS_SEPARATOR}{str(focus)[:_FOCUS_MAX_LEN]}"

    n = inputs.get("role_index")
    total = inputs.get("role_total")
    if n is not None and total is not None:
        return f"{prefix} [{n}/{total}]: {descriptor}"

    # Legacy fallback for envelopes built outside the plan (no per-agent counts).
    idx = inputs.get("subtask_index")
    if idx is not None:
        return f"{prefix} [{idx}]: {descriptor}"
    return f"{prefix}: {descriptor}"

"""
Cycle/Run lifecycle state machine and hash computation (SIP-0064 §6).

Declarative transition tuples, status derivation, and deterministic hash functions.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from enum import Enum

from squadops.cycles.models import (
    CycleStatus,
    GateDecisionValue,
    IllegalStateTransitionError,
    Run,
    RunStatus,
    SquadProfile,
)

# =============================================================================
# Run state machine — declarative transition tuples (SIP-0064 §6.2)
# =============================================================================

_RUN_TRANSITIONS: list[tuple[str, RunStatus, RunStatus]] = [
    ("start", RunStatus.QUEUED, RunStatus.RUNNING),
    ("complete", RunStatus.RUNNING, RunStatus.COMPLETED),
    ("fail", RunStatus.RUNNING, RunStatus.FAILED),
    ("pause", RunStatus.RUNNING, RunStatus.PAUSED),
    ("resume", RunStatus.PAUSED, RunStatus.RUNNING),
    ("cancel", RunStatus.QUEUED, RunStatus.CANCELLED),
    ("cancel", RunStatus.RUNNING, RunStatus.CANCELLED),
    ("cancel", RunStatus.PAUSED, RunStatus.CANCELLED),
    ("resume_from_failed", RunStatus.FAILED, RunStatus.RUNNING),
    # #522 / pf-43: a framing run whose inter-workload gate is REJECTED by system plan
    # validation is superseded by its re-roll. Inter-workload gates are decided on
    # COMPLETED runs by design (SIP-0083 D15 — see GATE_REJECTED_STATES below, which
    # excludes COMPLETED for exactly that reason), so by the time the rejection is
    # recorded the run is already terminal. The re-roll cancels it to keep the positional
    # run<->workload invariant (#257/D14: exactly one non-cancelled run per position) —
    # and without this edge that cancel raised IllegalStateTransitionError, killing the
    # re-roll before it created the replacement run. That is why #522 passed its harness
    # (which drives a still-RUNNING run) and never once fired live.
    ("supersede", RunStatus.COMPLETED, RunStatus.CANCELLED),
]

# Derived lookup: source → set of valid destinations
_VALID_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {}
for _trigger, _src, _dst in _RUN_TRANSITIONS:
    _VALID_TRANSITIONS.setdefault(_src, set()).add(_dst)

# Terminal states — no outgoing transitions allowed
TERMINAL_STATES: frozenset[RunStatus] = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
)

# States that reject gate decisions — COMPLETED is intentionally excluded
# because inter-workload gates are decided on completed runs (SIP-0083 D15).
GATE_REJECTED_STATES: frozenset[RunStatus] = frozenset({RunStatus.FAILED, RunStatus.CANCELLED})


def validate_run_transition(current: RunStatus, target: RunStatus) -> None:
    """Raise IllegalStateTransitionError if transition is illegal.

    Args:
        current: Current RunStatus.
        target: Desired RunStatus.

    Raises:
        IllegalStateTransitionError: If the transition is not allowed.
    """
    valid = _VALID_TRANSITIONS.get(current, set())
    if target not in valid:
        raise IllegalStateTransitionError(
            f"Cannot transition Run from {current.value!r} to {target.value!r}"
        )


def derive_cycle_status(runs: Sequence[Run], cycle_cancelled: bool) -> CycleStatus:
    """Derive CycleStatus from the latest non-cancelled Run. SIP-0064 §6.3.

    Rules:
    - No runs → CREATED
    - Cycle explicitly cancelled → CANCELLED
    - Latest non-cancelled run determines status:
        queued/running/paused → ACTIVE
        completed → COMPLETED
        failed → FAILED
    - All runs cancelled but cycle not cancelled → CREATED
    """
    if cycle_cancelled:
        return CycleStatus.CANCELLED

    if not runs:
        return CycleStatus.CREATED

    # Find the latest non-cancelled run (by run_number descending)
    non_cancelled = [r for r in runs if r.status != RunStatus.CANCELLED.value]
    if not non_cancelled:
        return CycleStatus.CREATED

    latest = max(non_cancelled, key=lambda r: r.run_number)
    status = latest.status

    if status in (RunStatus.QUEUED.value, RunStatus.RUNNING.value, RunStatus.PAUSED.value):
        return CycleStatus.ACTIVE
    elif status == RunStatus.COMPLETED.value:
        return CycleStatus.COMPLETED
    elif status == RunStatus.FAILED.value:
        return CycleStatus.FAILED

    return CycleStatus.ACTIVE


def resolve_cycle_status(
    runs: Sequence[Run],
    cycle_cancelled: bool,
    workload_statuses: Sequence[str] | None = None,
) -> CycleStatus:
    """Resolve cycle status with workload awareness (SIP-0083 D5).

    Composes on top of derive_cycle_status() with explicit precedence:
    0. If cycle_cancelled → CANCELLED (operator intent always wins)
    1. If any workload status is "gate_awaiting" → PAUSED
    2. If any workload status is "rejected" → FAILED
    3. If "pending" workloads remain and derive would return COMPLETED → ACTIVE
    4. Otherwise → derive_cycle_status(runs, cycle_cancelled)

    Precedence: cancelled > gate_awaiting > rejected > pending-guard > derive.
    A cycle with an undecided gate is still actionable (the operator can
    approve or reject), so PAUSED wins over FAILED if both appear.
    Rule 3 prevents showing COMPLETED when the pipeline still has pending
    workloads (e.g., between gate approval and next-Run creation).

    When workload_statuses is None or empty, this is equivalent to
    derive_cycle_status() — preserving backward compatibility for
    single-workload cycles.

    Args:
        runs: All runs for the cycle.
        cycle_cancelled: Whether the cycle was explicitly cancelled.
        workload_statuses: Normalized status strings extracted from
            WorkloadProgressEntry objects (e.g., ["completed",
            "gate_awaiting", "pending"]). Callers extract these
            before calling to avoid coupling lifecycle resolution
            to DTO types.
    """
    # Explicit cancellation always wins — operator intent overrides gate state.
    if cycle_cancelled:
        return CycleStatus.CANCELLED

    if workload_statuses:
        if "gate_awaiting" in workload_statuses:
            return CycleStatus.PAUSED
        if "rejected" in workload_statuses:
            return CycleStatus.FAILED

    derived = derive_cycle_status(runs, cycle_cancelled)

    # Rule 3: if pending workloads remain, the pipeline isn't done —
    # don't show COMPLETED just because the latest run completed.
    if workload_statuses and "pending" in workload_statuses and derived == CycleStatus.COMPLETED:
        return CycleStatus.ACTIVE

    return derived


class WorkloadStranding(Enum):
    """Classification of a cycle stalled between workloads (#481).

    ``STRANDED`` is the only class safe to act on: the sequence owes a
    successor run, nothing gates it, and only a dead ``execute_cycle`` loop
    explains its absence. The two gate classes are *visibility* verdicts —
    an undecided gate is the supported operator path (approve + retry), and a
    recorded rejection means the supersede/re-roll died with the process;
    both must never be auto-acted on.
    """

    STRANDED = "stranded"
    GATE_PENDING = "gate_pending"
    GATE_REJECTED = "gate_rejected"


def classify_workload_stranding(
    workload_sequence: Sequence[dict],
    runs: Sequence[Run],
    cycle_cancelled: bool,
) -> WorkloadStranding | None:
    """Classify a cycle stalled between workloads, or ``None`` (#481).

    Pure function of durable state: the positional run↔workload invariant
    (#257/D14 — the Nth non-cancelled run occupies sequence position N) plus
    the latest run's own ``gate_decisions``. A successor's absence is
    positional: the latest non-cancelled run sitting COMPLETED at a
    non-final position IS the missing successor.

    ``None`` for everything this predicate does not recognize with high
    confidence — cancelled cycles, sequence-less (legacy) cycles, exhausted
    sequences, and any latest-run status other than COMPLETED (a running or
    failed run has an owner; ``resolve_cycle_status`` rule 3 names the
    COMPLETED-mid-sequence window this predicate detects).
    """
    if cycle_cancelled or not workload_sequence:
        return None

    non_cancelled = sorted(
        (r for r in runs if r.status != RunStatus.CANCELLED.value),
        key=lambda r: r.run_number,
    )
    if not non_cancelled or len(non_cancelled) >= len(workload_sequence):
        return None

    latest = non_cancelled[-1]
    if latest.status != RunStatus.COMPLETED.value:
        return None

    gate_name = workload_sequence[len(non_cancelled) - 1].get("gate")
    if not gate_name:
        return WorkloadStranding.STRANDED

    decisions = {gd.decision for gd in latest.gate_decisions if gd.gate_name == gate_name}
    # Mirrors the executor's #466 exhaustive dispatch. Rejection first: if
    # contradictory decisions somehow coexist, the conservative read wins.
    if GateDecisionValue.REJECTED in decisions:
        return WorkloadStranding.GATE_REJECTED
    if decisions & {GateDecisionValue.APPROVED, GateDecisionValue.APPROVED_WITH_REFINEMENTS}:
        return WorkloadStranding.STRANDED
    if not decisions:
        return WorkloadStranding.GATE_PENDING
    # RETURNED_FOR_REVISION (a deliberate, recorded stop awaiting a manual
    # retry — #466) and any unrecognized future value: never treat an
    # un-approving decision as stranding.
    return None


def _canonical_json(obj: dict) -> str:
    """Produce deterministic JSON (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_config_hash(applied_defaults: dict, execution_overrides: dict) -> str:
    """SHA-256 of canonical JSON merge of defaults + overrides (T5).

    Args:
        applied_defaults: System-applied defaults.
        execution_overrides: Caller-provided overrides.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    merged = {**applied_defaults, **execution_overrides}
    canonical = _canonical_json(merged)
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_profile_snapshot_hash(profile: SquadProfile) -> str:
    """Deterministic SHA-256 hash of a SquadProfile for immutable snapshotting.

    Args:
        profile: SquadProfile to hash.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    snapshot = {
        "profile_id": profile.profile_id,
        "version": profile.version,
        "agents": [
            {
                "agent_id": a.agent_id,
                "role": a.role,
                "model": a.model,
                "enabled": a.enabled,
                "config_overrides": a.config_overrides,
            }
            for a in profile.agents
        ],
    }
    canonical = _canonical_json(snapshot)
    return hashlib.sha256(canonical.encode()).hexdigest()

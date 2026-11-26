"""
Cycle/Run lifecycle state machine and hash computation (SIP-0064 §6).

Declarative transition tuples, status derivation, and deterministic hash functions.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, StrEnum

from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
from squadops.cycles.models import (
    APPROVING_DECISIONS,
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
    # A run that fails before it starts: refused at admission (the box held past one full lease,
    # SIP-0109 §9.3, #1928) or failing in provisioning before the run is moved to running. Without
    # this edge the failure raised IllegalStateTransitionError, the run stayed queued for ever, and
    # its cycle and campaign never ended. #1928's harness drove a registry that checked no
    # transition, so it passed and never fired live; the 2.1 final deploy's #1824 diagnostic found it.
    ("fail_unstarted", RunStatus.QUEUED, RunStatus.FAILED),
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

#: The terminal states that reject a gate decision — **derived**, so it cannot disagree with
#: ``TERMINAL_STATES`` (#1150).
#:
#: A gate decision is refused on a run that has already ended, with one exception:
#: ``COMPLETED`` is excluded because inter-workload gates are decided *on* completed runs
#: (SIP-0083 D15) — which is also why the ``supersede`` edge ``COMPLETED → CANCELLED``
#: exists, for the re-roll. That single design fact is the whole content of this set.
#:
#: It used to be a second literal, ``frozenset({FAILED, CANCELLED})``, written beside a
#: comment explaining the exclusion. Two homes for one fact, and the comment at the
#: transition table already recorded that the original fix "passed its harness and never
#: once fired live". Adding a fourth terminal state would have left this set silently
#: wrong. Same class as #1070.
GATE_REJECTED_STATES: frozenset[RunStatus] = TERMINAL_STATES - {RunStatus.COMPLETED}


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


#: How each recorded ending reads on the cycle's status (#3201). The durable ``cycle_ends`` row is
#: the cycle's own record of how it stopped, so it decides the status once the cycle has ended.
#: ``None`` marks a stop that isn't an ending of the cycle: a paused run resumes, a run returned
#: still going is read from its runs, and a single workload's end is how its one run ended.
STATUS_OF_ENDING: dict[CycleStopReason, CycleStatus | None] = {
    CycleStopReason.SEQUENCE_COMPLETED: CycleStatus.COMPLETED,
    CycleStopReason.SINGLE_WORKLOAD_ENDED: None,
    CycleStopReason.RUN_FAILED: CycleStatus.FAILED,
    CycleStopReason.RUN_CANCELLED: CycleStatus.CANCELLED,
    CycleStopReason.RUN_PAUSED: None,
    CycleStopReason.RUN_NOT_TERMINAL: None,
    CycleStopReason.PLAN_REJECTED: CycleStatus.FAILED,
    CycleStopReason.GATE_REJECTED: CycleStatus.FAILED,
    CycleStopReason.REVISION_UNAVAILABLE: CycleStatus.FAILED,
    CycleStopReason.GATE_DECISION_UNRECOGNIZED: CycleStatus.FAILED,
    CycleStopReason.GATE_FAILED: CycleStatus.FAILED,
    CycleStopReason.GATE_INPUT_UNAVAILABLE: CycleStatus.FAILED,
    CycleStopReason.CRITERIA_NOT_CHECKABLE: CycleStatus.FAILED,
    CycleStopReason.SKILL_STOPPED: CycleStatus.FAILED,
}

_LIVE_RUN = frozenset({RunStatus.QUEUED.value, RunStatus.RUNNING.value, RunStatus.PAUSED.value})


class StatusConflict(StrEnum):
    """Two records of one cycle that disagree, named on the read and never resolved silently."""

    #: The cycle recorded an ending, and a run from before it still reads queued, running or
    #: paused. The status is the run's, so an end row never hides work that is really going.
    RUN_LIVE_AFTER_ENDING = "run_live_after_ending"
    #: The cycle recorded an ending, and was cancelled afterwards (#3201: an abort cancelled a
    #: cycle that had ended at the gate 40 minutes earlier). The ending came first, so it stands.
    CANCELLED_AFTER_ENDING = "cancelled_after_ending"


@dataclass(frozen=True)
class CycleReading:
    """A cycle's status, the recorded ending it reads from (if any), and any conflict."""

    status: CycleStatus
    recorded_ending: CycleStopReason | None
    conflict: StatusConflict | None


def read_cycle_status(
    runs: Sequence[Run],
    cycle_cancelled: bool,
    workload_statuses: Sequence[str] | None,
    end: RecordedEnd | None,
) -> CycleReading:
    """The cycle's status with its recorded ending authoritative (#3201).

    Precedence, in order:
    1. no recorded ending, or one that isn't an ending (``STATUS_OF_ENDING`` is ``None``): the
       runs and workloads decide, as ``resolve_cycle_status`` reads them;
    2. a run newer than the ending's last run: the cycle was reopened after it ended, so the runs
       decide and the ending is history;
    3. a run from before the ending still live: the runs decide, and the conflict is named;
    4. otherwise the ending decides. A cancellation on top of an ending that wasn't one is named
       as the conflict, and the ending stands, because it was recorded first: cancelling a live
       cycle ends its run cancelled, which records ``run_cancelled``.
    """

    derived = resolve_cycle_status(runs, cycle_cancelled, workload_statuses=workload_statuses)
    ending_status = STATUS_OF_ENDING[end.stopped_because] if end is not None else None
    if end is None or ending_status is None:
        return CycleReading(derived, None, None)
    last = next((r for r in runs if r.run_id == end.last_run_id), None)
    if last is not None and any(r.run_number > last.run_number for r in runs):
        return CycleReading(derived, None, None)
    if any(r.status in _LIVE_RUN for r in runs):
        # The latest run alone can read completed while an earlier one still runs: live wins.
        live = (
            derived if derived in (CycleStatus.ACTIVE, CycleStatus.PAUSED) else CycleStatus.ACTIVE
        )
        return CycleReading(live, end.stopped_because, StatusConflict.RUN_LIVE_AFTER_ENDING)
    conflict = (
        StatusConflict.CANCELLED_AFTER_ENDING
        if cycle_cancelled and ending_status is not CycleStatus.CANCELLED
        else None
    )
    return CycleReading(ending_status, end.stopped_because, conflict)


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
    if decisions & APPROVING_DECISIONS:
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

    The payload is every field that decides how a cycle executes under this profile —
    including ``serves_roles`` since 1.8.1, which decides WHICH agent runs each planned step
    (SIP-0108 §10i item 1). A routing field outside the content identity means two profiles
    that dispatch differently snapshot the same, and a set frozen on one could run the other.

    **Canonicalization.** Agent order is the authored order and is preserved: a profile is a
    list its author wrote. Each agent's ``serves_roles`` is sorted, because role service is a
    set — the same map written in two orders is the same map and must hash the same.

    **Refs stamped before 1.8.1 are not recomputable.** They were taken over a payload that
    omitted ``serves_roles``, so a historical cycle's stored
    ``squad_profile_snapshot_ref`` cannot be reproduced by this function and is read as opaque
    evidence of the squad that ran, never re-derived. Nothing recomputes one: the only
    comparisons are current-era (the verification driver's pre-launch check against the prefix
    a set is frozen on, and the post-run check against the same). A set pinned before 1.8.1
    therefore pins a prefix this formula no longer produces, and a new set pins the ref its
    own deploy stamps.

    **``skillsets`` is covered only where declared** (SIP-0116 Q57). An agent that carries
    none contributes no key, so every profile written before skillsets existed keeps the
    ref it had. A declared list is sorted: what an agent carries is a set.

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
                "serves_roles": sorted(a.serves_roles),
                **({"skillsets": sorted(a.skillsets)} if a.skillsets else {}),
            }
            for a in profile.agents
        ],
    }
    canonical = _canonical_json(snapshot)
    return hashlib.sha256(canonical.encode()).hexdigest()

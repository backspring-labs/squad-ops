"""
Cycle/Run lifecycle state machine and hash computation (SIP-0064 §6).

Declarative transition tuples, status derivation, and deterministic hash functions.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from squadops.cycles.models import (
    CycleStatus,
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
]

# Derived lookup: source → set of valid destinations
_VALID_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {}
for _trigger, _src, _dst in _RUN_TRANSITIONS:
    _VALID_TRANSITIONS.setdefault(_src, set()).add(_dst)

# Terminal states — no outgoing transitions allowed
TERMINAL_STATES: frozenset[RunStatus] = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
)


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

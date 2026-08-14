"""SIP-0100 Task 0.5 — contract-compliance reason-code taxonomy (plan D4-D6 / review #15)."""

from __future__ import annotations

from squadops.cycles.task_outcome import (
    CONTRACT_COMPLIANCE_ACTIONS as ACTIONS,
)
from squadops.cycles.task_outcome import (
    ContractComplianceViolation as V,
)


def test_every_code_has_a_distinct_corrective_action():
    codes = {
        V.FROZEN_PATH_EMISSION,
        V.UNAUTHORIZED_SLOT_EMISSION,
        V.UNDECLARED_PATH_EMISSION,
        V.POST_WRITE_INTEGRITY_FAULT,
        # SIP-0104 P4: the region-level pair — spine/structure vs slot-body containment.
        V.SCAFFOLD_REGION_VIOLATION,
        V.PROHIBITED_FILL_EMISSION,
    }
    assert len(codes) == 6  # distinct codes
    assert set(ACTIONS) == codes  # complete mapping — no code without an action
    assert len(set(ACTIONS.values())) == 6  # each maps to a distinct disposition


def test_only_the_system_fault_stops_the_attempt():
    """D4/#16: the post-write integrity fault is a SYSTEM fault that stops the attempt; the
    producer faults are correctable rejections. This split is the point of the taxonomy."""
    stops = {c for c, a in ACTIONS.items() if "stop" in a}
    assert stops == {V.POST_WRITE_INTEGRITY_FAULT}
    producer_faults = {
        V.FROZEN_PATH_EMISSION,
        V.UNAUTHORIZED_SLOT_EMISSION,
        V.UNDECLARED_PATH_EMISSION,
        V.SCAFFOLD_REGION_VIOLATION,
        V.PROHIBITED_FILL_EMISSION,
    }
    assert all("reject" in ACTIONS[c] for c in producer_faults)

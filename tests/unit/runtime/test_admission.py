"""
Unit tests for cycle recruitment admission — SIP-0089 §3.5 (#233).

Exercises :func:`squadops.runtime.admission.admit_participants` /
:func:`release_participants` against a fake coordinator that records every
``request_transition`` call and returns scripted outcomes. The bugs these guard
against: stranding agents in ``cycle`` mode when a later participant's lease
conflicts, releasing a lease the run never acquired, and a single release failure
stranding the remaining agents' leases.
"""

from __future__ import annotations

from squadops.runtime import reasons
from squadops.runtime.admission import (
    AdmissionResult,
    admit_participants,
    release_participants,
)
from squadops.runtime.coordinator import TransitionOutcome


def _applied(agent_id: str, from_mode: str, to_mode: str) -> TransitionOutcome:
    return TransitionOutcome(
        applied=True,
        agent_id=agent_id,
        from_mode=from_mode,  # type: ignore[arg-type]
        to_mode=to_mode,
        reason_code=reasons.CYCLE_RECRUITED,
        event_name="agent.mode.transition",
    )


def _rejected(agent_id: str, rejected_reason: str | None) -> TransitionOutcome:
    return TransitionOutcome(
        applied=False,
        agent_id=agent_id,
        from_mode="ambient",
        to_mode="cycle",
        reason_code=reasons.CYCLE_RECRUITED,
        rejected_reason=rejected_reason,
    )


def _idempotent(agent_id: str) -> TransitionOutcome:
    return TransitionOutcome(
        applied=False,
        agent_id=agent_id,
        from_mode="cycle",
        to_mode="cycle",
        reason_code=reasons.CYCLE_RECRUITED,
        idempotent_skip=True,
    )


class FakeCoordinator:
    """Records transitions; scripts the ``ambient → cycle`` outcome per agent."""

    def __init__(
        self,
        *,
        cycle_outcomes: dict[str, TransitionOutcome] | None = None,
        raise_on_release: set[str] | None = None,
    ) -> None:
        self._cycle_outcomes = cycle_outcomes or {}
        self._raise_on_release = raise_on_release or set()
        # each entry: (agent_id, target_mode, reason_code, owner_ref, requester_kind)
        self.calls: list[tuple[str, str, str, str, str]] = []

    async def request_transition(
        self,
        agent_id: str,
        target_mode: str,
        reason_code: str,
        *,
        requester_kind: str,
        owner_ref: str,
        assignment_id: str | None = None,
        scheduled_at: object | None = None,
    ) -> TransitionOutcome:
        self.calls.append((agent_id, target_mode, reason_code, owner_ref, requester_kind))
        if target_mode == "ambient":
            if agent_id in self._raise_on_release:
                raise RuntimeError(f"release blew up for {agent_id}")
            return _applied(agent_id, "cycle", "ambient")
        return self._cycle_outcomes.get(agent_id, _applied(agent_id, "ambient", "cycle"))

    def cycle_calls(self) -> list[tuple[str, str, str, str, str]]:
        return [c for c in self.calls if c[1] == "cycle"]

    def release_calls(self) -> list[tuple[str, str, str, str, str]]:
        return [c for c in self.calls if c[1] == "ambient"]


async def test_admit_all_participants_recruits_each_to_cycle_in_sorted_order():
    coord = FakeCoordinator()

    result = await admit_participants(coord, ["neo", "bob", "max"], owner_ref="run-1")

    assert result == AdmissionResult(admitted=True, recruited_agent_ids=("bob", "max", "neo"))
    # one ambient→cycle per agent, deterministic sorted order, correct reason/owner/requester
    assert [(c[0], c[2], c[3], c[4]) for c in coord.cycle_calls()] == [
        ("bob", reasons.CYCLE_RECRUITED, "run-1", "external"),
        ("max", reasons.CYCLE_RECRUITED, "run-1", "external"),
        ("neo", reasons.CYCLE_RECRUITED, "run-1", "external"),
    ]
    assert coord.release_calls() == []  # nobody released on a clean admit


async def test_lease_conflict_defers_and_rolls_back_prior_recruits():
    # sorted order is bob, max, neo → bob+max admit, neo conflicts.
    coord = FakeCoordinator(cycle_outcomes={"neo": _rejected("neo", reasons.FOCUS_LEASE_CONFLICT)})

    result = await admit_participants(coord, ["neo", "bob", "max"], owner_ref="run-1")

    assert result.admitted is False
    assert result.blocking_agent_id == "neo"
    assert result.reason == reasons.FOCUS_LEASE_CONFLICT
    assert result.recruited_agent_ids == ()
    # the two agents already in cycle are rolled back to ambient (no strands)…
    assert sorted(c[0] for c in coord.release_calls()) == ["bob", "max"]
    assert all(c[2] == reasons.CYCLE_COMPLETED for c in coord.release_calls())
    # …and the blocking agent, never recruited, is never released
    assert "neo" not in [c[0] for c in coord.release_calls()]


async def test_agent_already_in_cycle_is_admitted_but_not_recorded_as_recruited():
    coord = FakeCoordinator(cycle_outcomes={"neo": _idempotent("neo")})

    result = await admit_participants(coord, ["max", "neo"], owner_ref="run-1")

    assert result.admitted is True
    # neo was already in cycle for someone else — we must NOT release it on finalize
    assert result.recruited_agent_ids == ("max",)
    assert coord.release_calls() == []


async def test_release_participants_is_best_effort_across_a_failure():
    # max's release raises; neo and bob must still be released or their leases strand.
    coord = FakeCoordinator(raise_on_release={"max"})

    await release_participants(coord, ["max", "neo", "bob"], owner_ref="run-1")

    released = [c[0] for c in coord.release_calls()]
    assert released == ["max", "neo", "bob"]  # loop continued past the failure
    assert all(c[2] == reasons.CYCLE_COMPLETED for c in coord.release_calls())


async def test_empty_participants_admits_with_no_transitions():
    coord = FakeCoordinator()

    result = await admit_participants(coord, [], owner_ref="run-1")

    assert result == AdmissionResult(admitted=True, recruited_agent_ids=())
    assert coord.calls == []


async def test_rejection_without_a_reason_falls_back_to_focus_lease_conflict():
    coord = FakeCoordinator(cycle_outcomes={"max": _rejected("max", None)})

    result = await admit_participants(coord, ["max"], owner_ref="run-1")

    assert result.admitted is False
    assert result.blocking_agent_id == "max"
    assert result.reason == reasons.FOCUS_LEASE_CONFLICT

"""Every contract criterion is accounted for, by name (#945).

Bug this guards: SIP-0104 window roll 1 reported "Contract criteria: 12/14" with an
EMPTY unverified list. The two it lost -- `vc-compiles-app-api-runs-run-id-route` and
its join sibling -- were recoverable only by diffing two lists by hand. The count was
honest; the identity of the gap was available nowhere, so a reader could not tell a
compile criterion for a file that shipped fine from the one behaviour the product
exists for.
"""

from __future__ import annotations

import pytest

from squadops.cycles.run_report_builder import _build_verification_lines
from squadops.cycles.verification_integrity import (
    CycleOutcome,
    RunVerdict,
    RunVerificationSummary,
)

pytestmark = [pytest.mark.domain_contracts]

#: Roll 1's real shortfall.
_LOST = (
    "vc-compiles-app-api-runs-run-id-join-route",
    "vc-compiles-app-api-runs-run-id-route",
)


def _summary(*, verified: tuple[str, ...], total: tuple[str, ...]) -> RunVerificationSummary:
    return RunVerificationSummary(
        verdict=RunVerdict.ACCEPTED,
        verified=(),
        failed=(),
        unverified=(),
        required_unmet=(),
        executed_count=len(verified),
        passed_count=len(verified),
        criteria_verified=verified,
        criteria_total=total,
    )


class TestTheInvariant:
    def test_verified_and_unverified_account_for_every_criterion(self):
        s = _summary(verified=("a", "b"), total=("a", "b", *_LOST))
        assert set(s.criteria_verified) | set(s.criteria_unverified) == set(s.criteria_total)

    def test_roll_ones_lost_criteria_are_named(self):
        """The whole point: 12/14 must be able to say WHICH two."""
        total = tuple(f"c{i}" for i in range(12)) + _LOST
        s = _summary(verified=tuple(f"c{i}" for i in range(12)), total=total)
        assert s.criteria_unverified == _LOST

    def test_full_coverage_reports_nothing_unverified(self):
        s = _summary(verified=("a", "b"), total=("a", "b"))
        assert s.criteria_unverified == ()

    def test_declaration_order_is_preserved(self):
        """Sorted by the total's own order so the list reads against the contract."""
        s = _summary(verified=("b",), total=("z", "b", "a"))
        assert s.criteria_unverified == ("z", "a")

    def test_a_verified_criterion_absent_from_total_does_not_corrupt_the_gap(self):
        """Defensive: the derivation walks `total`, so an id that somehow appears only
        in `verified` cannot produce a negative or phantom entry."""
        s = _summary(verified=("a", "ghost"), total=("a", "b"))
        assert s.criteria_unverified == ("b",)


class TestTheCycleRollUp:
    def _outcome(self) -> CycleOutcome:
        return CycleOutcome(
            verdict=RunVerdict.ACCEPTED,
            verified=(),
            failed=(),
            unverified=(),
            run_count=1,
            criteria_verified=("a",),
            criteria_total=("a", *_LOST),
        )

    def test_the_roll_up_names_its_own_shortfall(self):
        assert self._outcome().criteria_unverified == _LOST

    def test_the_wire_shape_carries_it(self):
        """A consumer reading only the dict would otherwise have to rediscover the
        shortfall by set arithmetic, which is exactly what nobody did on roll 1."""
        d = self._outcome().to_dict()
        assert d["criteria_unverified"] == list(_LOST)
        assert len(d["criteria_verified"]) + len(d["criteria_unverified"]) == len(
            d["criteria_total"]
        )


def test_the_report_names_the_missing_criteria():
    """The surface a human actually reads. `12/14` alone sends them to the artifacts."""
    total = tuple(f"c{i}" for i in range(12)) + _LOST
    section = "\n".join(
        _build_verification_lines(_summary(verified=tuple(f"c{i}" for i in range(12)), total=total))
    )
    assert "Contract criteria: 12/14 executed-and-passed" in section
    assert "vc-compiles-app-api-runs-run-id-route" in section


def test_the_report_stays_quiet_when_nothing_is_missing():
    section = "\n".join(_build_verification_lines(_summary(verified=("a",), total=("a",))))
    assert "NOT verified" not in section

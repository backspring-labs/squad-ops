"""Assessment and its rate (SIP-0110 §0.10; slice 3d, #2096): §0.15's feedback and quality rows.

What bugs would these catch? A target counted absent because the output left the work out; an
unassessed or inapplicable exposure earning credit; a reassessment counted beside the one it
replaces; and the memory-on and memory-off series mixed into one rate.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from squadops.memory.assessment import (
    AssessmentRefused,
    TargetState,
    assess,
    supplied_to,
    target_absence_rates,
)
from tests.unit.memory.test_lessons import T0

pytestmark = [pytest.mark.domain_memory]


def _a(exposure, state, *, supplied=True, work=True, minutes=0, pattern="pat_a"):
    return assess(
        project_id="group_run",
        exposure_id=exposure,
        pattern_id=pattern,
        state=state,
        required_work_done=work,
        supplied=supplied,
        rubric="lesson.criterion_already_satisfied@1",
        evidence=f"artifact:{exposure}",
        assessed_by="auditor",
        now=T0 + timedelta(minutes=minutes),
    )


@pytest.mark.parametrize("work", [None, False])
def test_a_target_avoided_by_leaving_the_work_out_is_not_an_absence(work):
    """§0.15 quality. Bug caught: a proposal with no criterion at all scored as having avoided the
    criterion-already-satisfied target, so omitting work reads as the lesson working."""
    with pytest.raises(AssessmentRefused, match="did its required work"):
        _a("exp_1", TargetState.ABSENT, work=work)
    assert _a("exp_1", TargetState.UNASSESSED, work=work).state is TargetState.UNASSESSED


def test_the_rate_counts_only_applicable_assessed_exposures_and_keeps_the_series_apart():
    """§0.15 feedback. Bugs caught: unassessed or inapplicable exposures in the denominator; the
    memory-on and memory-off series added together; a reassessment counted twice."""
    assessments = [
        _a("exp_1", TargetState.PRESENT),
        _a("exp_1", TargetState.ABSENT, minutes=5),  # the reassessment replaces it
        _a("exp_2", TargetState.PRESENT),
        _a("exp_3", TargetState.NOT_APPLICABLE),
        _a("exp_4", TargetState.UNASSESSED, work=None),
        _a("exp_5", TargetState.PRESENT, supplied=False),
    ]

    rates = {r.supplied: r for r in target_absence_rates(assessments)}

    on, off = rates[True], rates[False]
    assert (on.absent, on.assessed, on.not_applicable, on.unassessed) == (1, 2, 1, 1)
    assert on.rate == 0.5
    assert (off.absent, off.assessed, off.rate) == (0, 1, 0.0)


def test_a_target_with_nothing_assessed_has_no_rate_not_zero():
    [only] = target_absence_rates([_a("exp_1", TargetState.UNASSESSED, work=None)])

    assert only.rate is None


@pytest.mark.parametrize(
    ("intervention", "supplied"),
    [
        ([{"revision_id": "pat_a@2"}], True),
        ([{"revision_id": "pat_ab@1"}], False),
        (None, False),
    ],
)
def test_whether_a_target_was_supplied_is_read_from_the_exposures_intervention(
    intervention, supplied
):
    assert supplied_to(intervention, "pat_a") is supplied

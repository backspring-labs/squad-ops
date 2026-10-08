"""The app-build indicators beside each exposure (SIP-0110 §0.10; slice 3d, #2096): §0.15's app-build
indicators and indicator aggregation rows.

What bugs would these catch? A run that fed several exposures counted once per exposure; a returned
proposal credited with the build a later version produced; a pending or evidence-less build read as
a failure; rounds to green reported for a build that never went green.
"""

from __future__ import annotations

import pytest

from squadops.cycles.models import Run
from squadops.cycles.run_loop_summary import RoundFailure, RunLoopSummary
from squadops.memory.exposures import Exposure
from squadops.memory.indicators import (
    BuildIndicators,
    BuildState,
    build_run_of,
    indicators_of,
    once_per_build,
)
from squadops.memory.lessons import RecallDisposition, Recalled
from squadops.memory.recall import RecallQuery
from tests.unit.memory.test_lessons import T0

pytestmark = [pytest.mark.domain_memory]


def _run(run_id, workload, status="completed", number=1):
    return Run(
        run_id=run_id,
        cycle_id="cyc_1",
        run_number=number,
        status=status,
        initiated_by="api",
        resolved_config_hash="h",
        workload_type=workload,
    )


def _exposure(run_id, task="t"):
    return Exposure.of(
        run_id=run_id,
        task_id=task,
        cycle_id="cyc_1",
        agent_id="neo",
        seam="plan_writing",
        query=RecallQuery("group_run", "development.design_plan"),
        recalled=Recalled(None, RecallDisposition.DISABLED),
        recorded_at=T0,
    )


FRAMING, BUILD = _run("run_f", "framing"), _run("run_i", "implementation", number=2)


@pytest.mark.parametrize(
    ("exposure_run", "runs", "returned", "ended", "expected"),
    [
        ("run_i", [FRAMING, BUILD], False, True, (BuildState.BUILT, "run_i")),
        ("run_f", [FRAMING, BUILD], False, True, (BuildState.BUILT, "run_i")),
        # A returned output fed no build, whatever a later version built.
        ("run_f", [FRAMING, BUILD], True, True, (BuildState.NO_DOWNSTREAM_BUILD, None)),
        ("run_f", [FRAMING], False, False, (BuildState.PENDING, None)),
        ("run_f", [FRAMING], False, True, (BuildState.NO_DOWNSTREAM_BUILD, None)),
        (
            "run_f",
            [FRAMING, _run("run_i", "implementation", "running", 2)],
            False,
            False,
            (BuildState.PENDING, "run_i"),
        ),
    ],
)
def test_an_exposure_is_joined_to_the_build_its_output_fed(
    exposure_run, runs, returned, ended, expected
):
    build = build_run_of(_exposure(exposure_run), runs, returned=returned, cycle_ended=ended)

    assert (build.state, build.run_id) == expected


def _summary(failures: int | None) -> RunLoopSummary:
    from squadops.cycles.llm_usage import RunUsage

    rounds = (
        None
        if failures is None
        else tuple(
            RoundFailure(task_id="t", round_index=n, category="work_product", locus="own")
            for n in range(failures)
        )
    )
    return RunLoopSummary(
        run_id="run_i",
        usage=RunUsage(by_task_type={}, tasks_reported=0, tasks_unreported=()),
        round_failures=rounds,
    )


@pytest.mark.parametrize(
    ("failures", "verdict", "expected"),
    [
        (2, "accepted", (2, 2)),
        (3, "rejected", (3, None)),
        (None, "accepted", None),  # a row from before rounds were recorded: evidence missing
        (1, None, None),  # no verdict: evidence missing
    ],
)
def test_a_builds_indicators_say_whether_and_when_it_went_green(failures, verdict, expected):
    got = indicators_of("run_i", _summary(failures), verdict, accepted=None)

    assert (got and (got.failed_rounds, got.rounds_to_green)) == expected


def test_a_run_that_fed_several_exposures_is_reported_once_and_no_unbuilt_state_is_a_failure():
    """§0.15 indicator aggregation."""
    indicators = {"run_i": BuildIndicators("run_i", 1, 0, "accepted", 1, True), "run_x": None}
    builds = [
        build_run_of(_exposure("run_f", "a"), [FRAMING, BUILD], returned=False, cycle_ended=True),
        build_run_of(_exposure("run_i", "b"), [FRAMING, BUILD], returned=False, cycle_ended=True),
        build_run_of(_exposure("run_f", "c"), [FRAMING], returned=True, cycle_ended=True),
        build_run_of(_exposure("run_f", "d"), [FRAMING], returned=False, cycle_ended=False),
        build_run_of(
            _exposure("run_x", "e"),
            [_run("run_x", "implementation")],
            returned=False,
            cycle_ended=True,
        ),
    ]

    report = once_per_build(builds, indicators)

    [row] = report.builds
    assert (row.run_id, len(row.exposures)) == ("run_i", 2)
    assert {s: len(ids) for s, ids in report.unbuilt.items()} == {
        BuildState.NO_DOWNSTREAM_BUILD: 1,
        BuildState.PENDING: 1,
        BuildState.EVIDENCE_MISSING: 1,
    }

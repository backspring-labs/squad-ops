"""A run's lint reading as its record (#1937): taken from the qa task's reply where every dispatch
returns, kept on the run's summary, and never moving an assessment's identity. Evidence only:
nothing that judges the run reads it."""

from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, patch

import pytest

from squadops.cycles.llm_usage import RunUsageAccumulator
from squadops.cycles.run_loop_summary import RunLoopSummary
from squadops.tasks.models import TaskResult
from tests.unit.cycles.test_llm_usage import _envelope

_READING = {"version": 1, "total": 2, "by_rule": {"ruff:F401": 2}, "by_file": {"a.py": 2}}


@pytest.fixture
def dispatcher(reply_router):
    from adapters.cycles.task_dispatcher import TaskDispatcher

    return TaskDispatcher(
        queue=reply_router.bind(AsyncMock()), reply_router=reply_router, task_timeout=5.0
    )


async def test_the_runs_latest_reading_is_taken_once_with_its_task(dispatcher, reply_router):
    """Entry point: ``TaskDispatcher.dispatch_task``, the one path every dispatch takes.
    Bugs caught: an earlier qa task's reading kept over the retest's, a reading credited to no
    task, or one never released (and so carried into the next run)."""
    later = {**_READING, "total": 1}
    reply_router.results["t-1"] = TaskResult(
        task_id="t-1", status="SUCCEEDED", outputs={"lint_findings": _READING}
    )
    reply_router.results["t-2"] = TaskResult(task_id="t-2", status="SUCCEEDED", outputs={})
    reply_router.results["t-3"] = TaskResult(
        task_id="t-3", status="SUCCEEDED", outputs={"lint_findings": later}
    )
    with patch("adapters.cycles.task_dispatcher.asyncio.sleep", new_callable=AsyncMock):
        for task in ("t-1", "t-2", "t-3"):
            await dispatcher.dispatch_task(_envelope(task), "run_a")

    assert dispatcher.take_run_lint_findings("run_a") == {"task_id": "t-3", **later}
    assert dispatcher.take_run_lint_findings("run_a") is None


def test_a_summary_written_before_the_reading_reads_none_and_a_new_one_round_trips():
    """Bug caught: an old row read as a run whose app had no findings."""
    new = RunLoopSummary(
        run_id="r",
        usage=RunUsageAccumulator().summary(),
        lint_findings={"task_id": "t", **_READING},
    )
    old = new.to_dict()
    del old["lint_findings"]

    assert RunLoopSummary.from_dict(new.to_dict()).lint_findings == {"task_id": "t", **_READING}
    assert RunLoopSummary.from_dict(old).lint_findings is None


def test_the_reading_never_moves_an_assessments_identity():
    """Bug caught: the field moving every identity the benchmark registry and the set records
    hold (#1813's rule)."""
    from squadops.cycles.cycle_assessment import evidence_identity
    from tests.unit.cycles.test_cycle_assessment import _accepted_cycle

    outcome, evidence = _accepted_cycle()
    summaries = {
        k: dataclasses.replace(v, lint_findings=_READING)
        for k, v in (evidence.loop_summaries or {}).items()
    }
    assert summaries, "the fixture carries a run summary"
    with_reading = dataclasses.replace(evidence, loop_summaries=summaries)
    assert evidence_identity(outcome, with_reading) == evidence_identity(outcome, evidence)

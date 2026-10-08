"""The recall behind the port (SIP-0110 §0.8; #2096): five outcomes kept apart, bounded retries, and
a disclosure that never stops the task.

What bugs would these catch? A store outage read as nothing eligible, so the measurement counts an
unasked task as a memory trial; a retry loop that never ends; a pin this code cannot read answered
as a failed read, hiding a version skew; and an exposure write that raises into the run.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall, create_failure_recall
from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.llm.model_registry import model_family_of
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import RecallDisposition, Recalled, UnitKind
from squadops.memory.pinning import pin_unit
from squadops.memory.recall import RecallQuery
from squadops.ports.memory.cross_cycle import RecordIncompatible
from tests.unit.memory.test_lessons import ASK, T0, _approve, _revision

pytestmark = [pytest.mark.domain_memory]

_UNIT = ASK.__class__(**{**ASK.__dict__, "unit_kind": UnitKind.CAMPAIGN, "unit_id": "cmp_x"})


class _Flaky(InMemoryCrossCycleMemoryStore):
    """A store whose snapshot reads, once armed, raise ``failures`` times first, or raise
    ``error``; and whose exposure writes always raise."""

    def __init__(self) -> None:
        super().__init__()
        self.failures, self.error, self.reads = 0, None, 0

    def arm(self, failures: int = 0, error: Exception | None = None) -> None:
        self.failures, self.error, self.reads = failures, error, 0

    async def get_snapshot(self, unit_kind, unit_id):
        self.reads += 1
        if self.error is not None:
            raise self.error
        if self.reads <= self.failures:
            raise ConnectionError("the store is down")
        return await super().get_snapshot(unit_kind, unit_id)

    async def record_exposure(self, exposure):
        raise ConnectionError("the store is down")


async def _with_a_lesson(store):
    rev = _revision("criterion_already_satisfied")
    await store.record_revision(rev)
    await store.record_approval(_approve(rev))
    await pin_unit(
        store,
        unit_kind=UnitKind.CAMPAIGN,
        unit_id="cmp_x",
        project_id="group_run",
        pinned_at=T0.replace(hour=1),
        disabled=False,
    )
    return store


_UNPINNED = RecallQuery("group_run", "x", unit_kind=UnitKind.CYCLE, unit_id="cyc_unpinned")


@pytest.mark.parametrize(
    "failures, error, query, disposition, reads",
    [
        (1, None, _UNIT, RecallDisposition.SUPPLIED, 2),  # a retry recovers
        (5, None, _UNIT, RecallDisposition.FAILED, 2),  # bounded
        (0, RecordIncompatible("v9"), _UNIT, RecallDisposition.INCOMPATIBLE, 1),
        (0, None, ASK, RecallDisposition.FAILED, 0),  # a query naming no unit
        (0, None, _UNPINNED, RecallDisposition.FAILED, 1),  # a unit with no pin
    ],
)
async def test_each_outcome_is_its_own_answer_and_retries_are_bounded(
    failures, error, query, disposition, reads
):
    store = await _with_a_lesson(_Flaky())
    store.arm(failures, error)

    out = await SnapshotRecall(store).recall(query)

    assert (out.disposition, store.reads) == (disposition, reads)
    assert bool(out.supplied) is (disposition is RecallDisposition.SUPPLIED)


async def test_a_disclosure_the_store_refuses_is_logged_and_the_task_runs(caplog):
    exposure = Exposure.of(
        run_id="run_1",
        task_id="t",
        cycle_id="cyc_1",
        seam="plan_writing",
        query=_UNIT,
        recalled=Recalled(None, RecallDisposition.FAILED),
        recorded_at=datetime(2026, 10, 8, tzinfo=UTC),
    )

    await SnapshotRecall(_Flaky()).disclose(exposure)

    assert "memory_exposure_not_recorded" in caplog.text


async def test_an_exposure_is_recorded_once_per_task_and_round_trips():
    """Bug caught: composing a run's plan again (a restart) recording a second exposure for the
    same task, so a task reads as asked twice."""
    store = InMemoryCrossCycleMemoryStore()
    exposure = Exposure.of(
        run_id="run_1",
        task_id="t",
        cycle_id="cyc_1",
        seam="build_authoring",
        query=_UNIT,
        recalled=Recalled("snp_x", RecallDisposition.NONE_ELIGIBLE),
        recorded_at=datetime(2026, 10, 8, tzinfo=UTC),
    )

    assert await store.record_exposure(exposure) is True
    assert await store.record_exposure(exposure) is False
    assert await store.list_exposures("run_1") == [Exposure.from_dict(exposure.to_dict())]


def test_the_factory_requires_its_kind():
    assert isinstance(create_failure_recall("disabled"), NoOpFailurePatternRecall)
    with pytest.raises(ValueError, match="unknown failure recall"):
        create_failure_recall("lancedb")


@pytest.mark.parametrize(
    "model, family",
    [
        ("qwen3.8:27b", "qwen3.8"),
        ("Qwen/Qwen3.8-27B-FP8", "qwen3.8"),  # the same weights, served by Atlas
        ("qwen3.6:27b", "qwen3.6"),
        ("qwen2.5:7b", "qwen2.5"),
        ("mystery:3b", ""),
    ],
)
def test_a_models_family_is_the_registrys_and_an_unknown_model_has_none(model, family):
    """§0.6 model scope. Bugs caught: the Atlas arm's name for the same weights given no family, so
    a lesson approved for them never reaches that arm; or an unregistered model given a family by
    a guess at its name, so it receives lessons approved for another model."""
    assert model_family_of(model) == family

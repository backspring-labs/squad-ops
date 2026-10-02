"""SIP-0109 §14 (#1710): a cycle's failure records, persisted at its ending by the one producer,
and the attribution read back from exactly them.

The completion tests enter at ``CycleCompletion.end`` — the one place every cycle ends — over a
real ``MemoryCycleRegistry`` and ``FilesystemArtifactVault``, and read back through
``assess_cycle``, the function the assessment route calls.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from adapters.cycles.cycle_completion import CycleCompletion
from adapters.cycles.cycle_evidence import assess_cycle, record_cycle_failures
from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.cycle_assessment import (
    UNRECORDED_ROUND_FAILURE_EVENTS,
    AssessorIdentity,
    evidence_identity,
)
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.failure_attribution import (
    ATTRIBUTION_REGISTRY_VERSION,
    AttributionClass,
    FailureEvent,
    TerminalKind,
)
from squadops.cycles.failure_records import (
    FailureRecord,
    FailureRecordState,
    events_of,
    failure_records,
)
from squadops.cycles.llm_usage import RunUsage
from squadops.cycles.models import Cycle, Run, TaskFlowPolicy
from squadops.cycles.run_loop_summary import RoundFailure, RunLoopSummary, RunTerminalDecision
from squadops.cycles.verification_integrity import aggregate_verification

pytestmark = [pytest.mark.domain_orchestration]

T0 = datetime(2026, 10, 2, 4, 0, tzinfo=UTC)
ASSESSOR = AssessorIdentity(framework_version="2.0.0", git_sha="abc1234")
_MIGRATION = (
    Path(__file__).resolve().parents[3] / "infra" / "migrations" / "1620_cycle_failure_records.sql"
)

_EXEC = RoundFailure("t-qa", 0, "executed_and_failed", "subject")
_ABSENT = RoundFailure("t-qa", 1, "emission_absent", "own_artifact", "cap_exhausted")


# ---------------------------------------------------------------------------------------------
# The records themselves
# ---------------------------------------------------------------------------------------------


def _event(round_index, category, locus=None, signature=None):
    return FailureEvent(
        run_id="run_i1",
        task_id="t-qa",
        round_index=round_index,
        category=category,
        locus=locus,
        emission_signature=signature,
    )


def test_records_are_the_events_in_order_then_one_unaskable_record_per_unread_input():
    """Bug caught: an unreadable input silently absent from the records (§14), or an event's
    class not the one compose() gives it under the recorded registry version."""
    events = (
        _event(0, "executed_and_failed", "subject"),
        _event(1, "emission_absent", "own_artifact", "cap_exhausted"),
    )

    records = failure_records("cyc_1", events, ("input_x: not stored",), campaign_id="cmp_1")

    assert [(r.event_index, r.state, r.attribution_class, r.unasked_input) for r in records] == [
        (0, FailureRecordState.RECORDED, AttributionClass.PRODUCER_OUTPUT_FAILURE, None),
        (1, FailureRecordState.RECORDED, AttributionClass.BUDGET_EXHAUSTION, None),
        (2, FailureRecordState.UNASKABLE, None, "input_x: not stored"),
    ]
    assert {(r.registry_version, r.campaign_id) for r in records} == {
        (ATTRIBUTION_REGISTRY_VERSION, "cmp_1")
    }
    assert events_of(tuple(reversed(records))) == events


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(state=FailureRecordState.RECORDED),
        dict(state=FailureRecordState.UNASKABLE),
        dict(state=FailureRecordState.RECORDED, event=_event(0, "x"), unasked_input="y"),
        dict(state=FailureRecordState.UNASKABLE, event=_event(0, "x"), unasked_input="y"),
    ],
    ids=["recorded-without-event", "unaskable-without-input", "recorded-both", "unaskable-both"],
)
def test_a_record_carries_its_event_or_names_its_input_never_neither_or_both(kwargs):
    with pytest.raises(ValueError, match="neither carries both"):
        FailureRecord(cycle_id="cyc_1", event_index=0, registry_version=1, **kwargs)


@pytest.mark.parametrize(
    ("column", "values"),
    [
        ("state", {m.value for m in FailureRecordState}),
        ("attribution_class", {m.value for m in AttributionClass}),
    ],
)
def test_the_migrations_check_lists_hold_the_enums_values(column, values):
    """Bug caught: a class added to the registry without the migration — every completion that
    composes it would fail its write on the live deploy."""
    sql = _MIGRATION.read_text()
    match = re.search(rf"\b{column} TEXT[^,]*CHECK \({column} IN \(([^)]*)\)\)", sql)
    assert match, f"no CHECK list for {column}"
    assert set(re.findall(r"'([^']+)'", match.group(1))) == values


def test_an_identity_recorded_before_the_records_existed_is_unchanged():
    """Bug caught: adding ``persisted_failure_events`` to the evidence moving every identity the
    benchmark registry and the verification-set records already hold. The value is the
    identity main computed for this evidence before the field existed (22df6399)."""
    from tests.unit.cycles.test_cycle_assessment import _accepted_cycle

    outcome, evidence = _accepted_cycle()
    assert evidence.persisted_failure_events is None
    assert evidence_identity(outcome, evidence) == (
        "bdafb6952f9c35889138f000e5e03c9718a614e3f76be71f0bc58f6afbaefc70"
    )


# ---------------------------------------------------------------------------------------------
# At the cycle's ending, and read back
# ---------------------------------------------------------------------------------------------


class _Executor:
    def __init__(self, registry, vault):
        self._cycle_registry = registry
        self._artifact_vault = vault


async def _failed_cycle(tmp_path, *, round_failures, status="failed"):
    registry = MemoryCycleRegistry()
    vault = FilesystemArtifactVault(tmp_path / "vault")
    await registry.create_cycle(
        Cycle(
            cycle_id="cyc_1",
            project_id="proj",
            created_at=T0,
            created_by="admin",
            prd_ref=None,
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )
    )
    run = Run(
        run_id="run_i1",
        cycle_id="cyc_1",
        run_number=1,
        status=status,
        initiated_by="api",
        resolved_config_hash="h",
        started_at=T0,
        finished_at=T0 + timedelta(minutes=30),
        workload_type="implementation",
    )
    await registry.create_run(run)
    await registry.record_run_verification_summary("run_i1", aggregate_verification([]))
    await _record_summary(registry, round_failures)
    return registry, vault, run


async def _record_summary(registry, round_failures):
    await registry.record_run_loop_summary(
        "run_i1",
        RunLoopSummary(
            run_id="run_i1",
            usage=RunUsage(by_task_type={}, tasks_reported=0, tasks_unreported=()),
            terminal=RunTerminalDecision(
                kind=TerminalKind.CORRECTION_TERMINATED,
                termination_reason="exhausted",
                task_id="t-qa",
            ),
            round_failures=round_failures,
        ),
    )


async def test_a_cycles_ending_persists_its_failure_records(tmp_path):
    """Wiring, entered at ``CycleCompletion.end``. Bug caught: the boundary every cycle ends at
    writing no records, or records from anything but the one producer."""
    registry, vault, run = await _failed_cycle(tmp_path, round_failures=(_EXEC, _ABSENT))

    end = await CycleCompletion(executor=lambda: _Executor(registry, vault)).end(
        "cyc_1", run, CycleStopReason.RUN_FAILED
    )

    records = await registry.get_failure_records("cyc_1")
    assert end.last_run_id == "run_i1"
    assert [(r.state, r.event.round_index, r.attribution_class) for r in records] == [
        (FailureRecordState.RECORDED, 0, AttributionClass.PRODUCER_OUTPUT_FAILURE),
        (FailureRecordState.RECORDED, 1, AttributionClass.BUDGET_EXHAUSTION),
    ]


async def test_the_attribution_is_read_from_the_persisted_records_not_rederived(tmp_path):
    """§14: no consumer re-derives the events. Bug caught: the assessment recomputing from the
    current evidence, so a record that disagrees with today's producer is silently overruled."""
    registry, vault, run = await _failed_cycle(tmp_path, round_failures=(_EXEC, _ABSENT))
    await record_cycle_failures(registry, vault, "cyc_1", "run_i1")
    # The stored evidence moves after the ending: the producer would now derive one event.
    await _record_summary(registry, (_EXEC,))

    reading = (await assess_cycle(registry, vault, "cyc_1", assessor=ASSESSOR)).attribution

    assert [(c.round_index, c.value) for c in reading.attribution.contributing] == [
        (0, "executed_and_failed"),
        (1, "emission_absent"),
    ]


async def test_an_unrecorded_input_is_an_unaskable_record(tmp_path):
    registry, vault, _ = await _failed_cycle(tmp_path, round_failures=None)

    records = await record_cycle_failures(registry, vault, "cyc_1", "run_i1")

    assert [(r.state, r.unasked_input) for r in records] == [
        (FailureRecordState.UNASKABLE, UNRECORDED_ROUND_FAILURE_EVENTS)
    ]


async def test_never_recorded_and_recorded_empty_are_different_answers(tmp_path):
    """Bug caught: a cycle that ended before the records existed read as one with no failures."""
    registry, vault, _ = await _failed_cycle(tmp_path, round_failures=())
    assert await registry.get_failure_records("cyc_1") is None

    await record_cycle_failures(registry, vault, "cyc_1", "run_i1")

    assert await registry.get_failure_records("cyc_1") == ()


async def test_each_ending_appends_a_set_and_the_latest_is_the_cycles(tmp_path):
    """A resumed run ends the cycle again. Bug caught: the second ending refused as a duplicate,
    or the first ending's records still read as the cycle's."""
    registry, vault, _ = await _failed_cycle(tmp_path, round_failures=(_EXEC, _ABSENT))
    await record_cycle_failures(registry, vault, "cyc_1", "run_i1")
    await _record_summary(registry, (_EXEC,))

    await record_cycle_failures(registry, vault, "cyc_1", "run_i1")

    assert [r.event.round_index for r in await registry.get_failure_records("cyc_1")] == [0]


async def test_an_ending_on_a_paused_run_records_nothing(tmp_path):
    registry, vault, _ = await _failed_cycle(tmp_path, round_failures=(_EXEC,), status="paused")

    assert await record_cycle_failures(registry, vault, "cyc_1", "run_i1") is None
    assert await registry.get_failure_records("cyc_1") is None


async def test_a_failed_write_is_logged_and_the_cycle_still_ends(tmp_path, caplog):
    """The records are evidence about the ending, not a condition of it. Bug caught: a storage
    fault at completion crashing the cycle's end, or passing silently."""
    registry, vault, run = await _failed_cycle(tmp_path, round_failures=(_EXEC,))

    async def refuse(*args, **kwargs):
        raise RuntimeError("the store is down")

    registry.record_failure_records = refuse

    end = await CycleCompletion(executor=lambda: _Executor(registry, vault)).end(
        "cyc_1", run, CycleStopReason.RUN_FAILED
    )

    assert end.cycle_id == "cyc_1"
    assert "failure_records_not_written" in caplog.text

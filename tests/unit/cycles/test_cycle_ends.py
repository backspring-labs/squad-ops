"""SIP-0109 §12a (#1803): each ending of a cycle is recorded, and the latest is the cycle's.

What a campaign's startup re-entry reads, so a hook that failed to decide is heard again from the
stop reason the cycle actually recorded — never one reconstructed from its runs.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
from squadops.cycles.models import Cycle, CycleNotFoundError, TaskFlowPolicy

_MIGRATION = Path(__file__).resolve().parents[3] / "infra/migrations/1670_cycle_ends.sql"


def test_the_migrations_check_list_holds_every_stop_reason():
    """Bug caught: a stop reason added without the migration — every ending for that reason
    fails its write on the live deploy, and that ending can never be re-heard."""
    sql = _MIGRATION.read_text()
    match = re.search(r"\bstopped_because TEXT[^,]*CHECK \(stopped_because IN \(([^)]*)\)\)", sql)
    assert match, "no CHECK list for stopped_because"
    assert set(re.findall(r"'([^']+)'", match.group(1))) == {m.value for m in CycleStopReason}


async def test_the_latest_ending_is_the_cycles_and_none_means_none_was_recorded():
    """Bugs caught: a resumed cycle re-heard on its first (paused) ending instead of its last;
    or a cycle that never recorded an ending read as having one."""
    registry = MemoryCycleRegistry()
    await registry.create_cycle(
        Cycle(
            cycle_id="cyc_1",
            project_id="p",
            created_at=datetime(2026, 10, 2, tzinfo=UTC),
            created_by="t",
            prd_ref=None,
            squad_profile_id="full",
            squad_profile_snapshot_ref="x",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )
    )
    assert await registry.get_cycle_end("cyc_1") is None

    paused = RecordedEnd("cyc_1", "run_1", CycleStopReason.RUN_PAUSED)
    completed = RecordedEnd("cyc_1", "run_1", CycleStopReason.SEQUENCE_COMPLETED)
    assert await registry.record_cycle_end(paused) == 1
    assert await registry.record_cycle_end(completed) == 2

    assert await registry.get_cycle_end("cyc_1") == completed
    with pytest.raises(CycleNotFoundError):
        await registry.record_cycle_end(
            RecordedEnd("cyc_none", "run_1", CycleStopReason.RUN_FAILED)
        )

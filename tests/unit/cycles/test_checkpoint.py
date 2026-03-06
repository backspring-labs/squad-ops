"""Tests for RunCheckpoint model + registry adapter checkpoint methods (SIP-0079 §7.4)."""

import dataclasses
from datetime import UTC, datetime

import pytest

from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.models import Cycle, Run, RunStatus, TaskFlowPolicy

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)


def _make_checkpoint(
    run_id: str = "run-001",
    checkpoint_index: int = 0,
    **overrides,
) -> RunCheckpoint:
    defaults = {
        "run_id": run_id,
        "checkpoint_index": checkpoint_index,
        "completed_task_ids": ("task-1", "task-2"),
        "prior_outputs": {"task-1": {"status": "ok"}},
        "artifact_refs": ("art-001",),
        "plan_delta_refs": (),
        "created_at": NOW,
    }
    defaults.update(overrides)
    return RunCheckpoint(**defaults)


# =============================================================================
# RunCheckpoint model tests
# =============================================================================


class TestRunCheckpointModel:
    def test_frozen_immutability(self):
        cp = _make_checkpoint()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cp.run_id = "changed"  # type: ignore[misc]

    def test_all_fields_accessible(self):
        cp = _make_checkpoint()
        assert cp.run_id == "run-001"
        assert cp.checkpoint_index == 0
        assert cp.completed_task_ids == ("task-1", "task-2")
        assert cp.prior_outputs == {"task-1": {"status": "ok"}}
        assert cp.artifact_refs == ("art-001",)
        assert cp.plan_delta_refs == ()
        assert cp.created_at == NOW

    def test_to_dict_round_trip(self):
        cp = _make_checkpoint()
        d = cp.to_dict()
        restored = RunCheckpoint.from_dict(d)
        assert restored == cp

    def test_to_dict_serializes_datetime_as_iso(self):
        cp = _make_checkpoint()
        d = cp.to_dict()
        assert isinstance(d["created_at"], str)
        assert d["created_at"] == NOW.isoformat()

    def test_from_dict_coerces_lists_to_tuples(self):
        d = {
            "run_id": "run-001",
            "checkpoint_index": 0,
            "completed_task_ids": ["t1", "t2"],
            "prior_outputs": {},
            "artifact_refs": ["a1"],
            "plan_delta_refs": ["pd1"],
            "created_at": NOW.isoformat(),
        }
        cp = RunCheckpoint.from_dict(d)
        assert isinstance(cp.completed_task_ids, tuple)
        assert isinstance(cp.artifact_refs, tuple)
        assert isinstance(cp.plan_delta_refs, tuple)

    def test_from_dict_parses_iso_datetime(self):
        d = {
            "run_id": "run-001",
            "checkpoint_index": 0,
            "completed_task_ids": (),
            "prior_outputs": {},
            "artifact_refs": (),
            "plan_delta_refs": (),
            "created_at": "2026-03-01T12:00:00+00:00",
        }
        cp = RunCheckpoint.from_dict(d)
        assert isinstance(cp.created_at, datetime)


# =============================================================================
# MemoryCycleRegistry checkpoint tests
# =============================================================================


def _make_cycle(cycle_id: str = "cyc-001") -> Cycle:
    return Cycle(
        cycle_id=cycle_id,
        project_id="proj-001",
        created_at=NOW,
        created_by="test",
        prd_ref="prd-001",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="snap-001",
        task_flow_policy=TaskFlowPolicy(mode="sequential", gates=()),
        build_strategy="standard",
        applied_defaults={},
        execution_overrides={},
        expected_artifact_types=(),
    )


def _make_run(run_id: str = "run-001", cycle_id: str = "cyc-001") -> Run:
    return Run(
        run_id=run_id,
        cycle_id=cycle_id,
        run_number=1,
        status=RunStatus.RUNNING.value,
        initiated_by="test",
        resolved_config_hash="hash-001",
    )


class TestMemoryCycleRegistryCheckpoints:
    @pytest.fixture
    async def registry(self):
        from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry

        reg = MemoryCycleRegistry()
        await reg.create_cycle(_make_cycle())
        await reg.create_run(_make_run())
        return reg

    async def test_save_and_get_latest(self, registry):
        cp = _make_checkpoint(checkpoint_index=0)
        await registry.save_checkpoint(cp)
        latest = await registry.get_latest_checkpoint("run-001")
        assert latest == cp

    async def test_get_latest_returns_none_when_empty(self, registry):
        latest = await registry.get_latest_checkpoint("run-001")
        assert latest is None

    async def test_save_multiple_get_latest_returns_last(self, registry):
        cp0 = _make_checkpoint(checkpoint_index=0)
        cp1 = _make_checkpoint(checkpoint_index=1, completed_task_ids=("t1", "t2", "t3"))
        await registry.save_checkpoint(cp0)
        await registry.save_checkpoint(cp1)
        latest = await registry.get_latest_checkpoint("run-001")
        assert latest == cp1

    async def test_list_checkpoints_returns_all(self, registry):
        cp0 = _make_checkpoint(checkpoint_index=0)
        cp1 = _make_checkpoint(checkpoint_index=1)
        await registry.save_checkpoint(cp0)
        await registry.save_checkpoint(cp1)
        result = await registry.list_checkpoints("run-001")
        assert len(result) == 2
        assert result[0] == cp0
        assert result[1] == cp1

    async def test_list_checkpoints_empty(self, registry):
        result = await registry.list_checkpoints("run-001")
        assert result == []

    async def test_pruning_max_keep(self, registry):
        """Save 7 checkpoints with max_keep=5, verify only 5 remain."""
        for i in range(7):
            cp = _make_checkpoint(checkpoint_index=i)
            await registry.save_checkpoint(cp, max_keep=5)
        result = await registry.list_checkpoints("run-001")
        assert len(result) == 5
        # Should keep the latest 5 (indices 2-6)
        assert result[0].checkpoint_index == 2
        assert result[-1].checkpoint_index == 6

    async def test_default_max_keep_is_5(self, registry):
        """Default max_keep=5: save 6, verify 5 remain."""
        for i in range(6):
            cp = _make_checkpoint(checkpoint_index=i)
            await registry.save_checkpoint(cp)
        result = await registry.list_checkpoints("run-001")
        assert len(result) == 5

    async def test_checkpoints_isolated_by_run_id(self, registry):
        """Checkpoints for different runs are independent."""
        await registry.create_run(_make_run(run_id="run-002"))
        cp1 = _make_checkpoint(run_id="run-001", checkpoint_index=0)
        cp2 = _make_checkpoint(run_id="run-002", checkpoint_index=0)
        await registry.save_checkpoint(cp1)
        await registry.save_checkpoint(cp2)
        assert await registry.get_latest_checkpoint("run-001") == cp1
        assert await registry.get_latest_checkpoint("run-002") == cp2

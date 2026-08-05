"""SIP-0101 Slice 2 — boundary retention.

The defect this closes: ``max_keep=5`` pruning deletes a long run's
post-framing/post-dev boundaries *before the run finishes* — exactly the
checkpoints a replay would restore from. Retained boundary checkpoints must
survive pruning; unretained pruning must be byte-identical to before.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_cycles]


def _checkpoint(index: int) -> RunCheckpoint:
    return RunCheckpoint(
        run_id="run_1",
        checkpoint_index=index,
        completed_task_ids=tuple(f"t{i}" for i in range(1, index + 1)),
        prior_outputs={},
        artifact_refs=(),
        plan_delta_refs=(),
        created_at=datetime.now(UTC),
    )


def _envelope(role: str) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="t1",
        agent_id="a1",
        cycle_id="c1",
        pulse_id="p1",
        project_id="pr1",
        task_type="development.develop",
        correlation_id="x",
        causation_id="y",
        trace_id="z",
        span_id="s",
        metadata={"role": role},
    )


class TestMemoryRegistryRetention:
    async def test_retained_boundary_survives_max_keep_overflow(self):
        """The Slice 2 headline: a boundary marked at index 1 must still exist
        after six more saves push it far outside the prune window."""
        reg = MemoryCycleRegistry()
        await reg.save_checkpoint(_checkpoint(1), max_keep=5, retain=True)
        for i in range(2, 9):
            await reg.save_checkpoint(_checkpoint(i), max_keep=5)

        indices = [c.checkpoint_index for c in await reg.list_checkpoints("run_1")]
        assert 1 in indices  # the retained boundary survived
        assert indices == [1, 4, 5, 6, 7, 8]  # plus the normal latest-5 window

    async def test_unretained_pruning_unchanged(self):
        """No retention in play → exactly the pre-Slice-2 latest-5 behavior."""
        reg = MemoryCycleRegistry()
        for i in range(1, 9):
            await reg.save_checkpoint(_checkpoint(i), max_keep=5)

        indices = [c.checkpoint_index for c in await reg.list_checkpoints("run_1")]
        assert indices == [4, 5, 6, 7, 8]

    async def test_get_latest_ignores_retention(self):
        """Latest means latest — an old retained boundary must never shadow
        the current resume point."""
        reg = MemoryCycleRegistry()
        await reg.save_checkpoint(_checkpoint(1), max_keep=5, retain=True)
        for i in range(2, 8):
            await reg.save_checkpoint(_checkpoint(i), max_keep=5)

        latest = await reg.get_latest_checkpoint("run_1")
        assert latest is not None
        assert latest.checkpoint_index == 7


class TestPhaseBoundaryPredicate:
    def test_last_task_is_a_boundary(self):
        plan = [_envelope("dev"), _envelope("dev")]
        assert DispatchedFlowExecutor._is_phase_boundary(plan, 1) is True

    def test_role_transition_is_a_boundary(self):
        # dev → qa: the post-dev checkpoint is what a QA-phase replay restores
        plan = [_envelope("dev"), _envelope("dev"), _envelope("qa")]
        assert DispatchedFlowExecutor._is_phase_boundary(plan, 1) is True

    def test_mid_phase_task_is_not_a_boundary(self):
        # dev → dev: pruning this one costs nothing a replay wants
        plan = [_envelope("dev"), _envelope("dev"), _envelope("qa")]
        assert DispatchedFlowExecutor._is_phase_boundary(plan, 0) is False

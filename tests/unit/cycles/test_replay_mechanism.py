"""SIP-0101 Slice 3 — the replay mechanism.

Declaration parsing, the interim strict-equality compatibility gate, checkpoint
translation into the target run's task-id namespace (the premise correction to
the SIP plan's 3.3 — ids embed the producing run, so cross-run suppression
requires rebinding), executor resolution, and outcome/report provenance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor, _ExecutionError
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.models import Run
from squadops.cycles.replay import (
    REPLAY_COMPATIBILITY_ELEMENTS,
    check_replay_compatibility,
    parse_replay_declaration,
    translate_checkpoint_for_replay,
)
from squadops.cycles.verification_integrity import (
    ReplayProvenance,
    RunVerdict,
    aggregate_cycle_outcome,
)

pytestmark = [pytest.mark.domain_cycles]

_DECL = {"execution_mode": "replay", "replay": {"source_run_id": "run_src", "boundary_index": 2}}


def _source_checkpoint() -> RunCheckpoint:
    return RunCheckpoint(
        run_id="run_aaaabbbbcccc",
        checkpoint_index=2,
        completed_task_ids=(
            "task-run_aaaabbbb-m000-development.develop",
            "task-run_aaaabbbb-m001-builder.assemble",
        ),
        prior_outputs={"dev": {"summary": "done"}},
        artifact_refs=("art_1", "art_2"),
        plan_delta_refs=("delta_1",),
        created_at=datetime.now(UTC),
    )


class TestParseDeclaration:
    def test_absent_means_normal_cycle(self):
        assert parse_replay_declaration({}) is None
        assert parse_replay_declaration({"time_budget_seconds": 60}) is None

    def test_valid_declaration_parses(self):
        req = parse_replay_declaration(_DECL)
        assert req is not None
        assert req.source_run_id == "run_src"
        assert req.boundary_index == 2

    @pytest.mark.parametrize(
        "overrides",
        [
            {"execution_mode": "replay"},  # mode without block
            {"replay": {"source_run_id": "run_src", "boundary_index": 2}},  # block, no mode
            {"execution_mode": "resume", "replay": {}},  # unknown mode
            {"execution_mode": "replay", "replay": {"source_run_id": "run_src"}},  # no boundary
            {"execution_mode": "replay", "replay": "run_src@2"},  # non-mapping block
        ],
    )
    def test_half_declared_replay_is_rejected(self, overrides):
        # a half-declared replay must never execute as a normal run (or vice versa)
        with pytest.raises(ValueError):
            parse_replay_declaration(overrides)


class TestCompatibilityGate:
    _SOURCE = {"prd_ref": "prd_1", "build_profile": "fullstack", "contract_ref": "art_c9"}

    def test_identical_elements_pass(self):
        assert check_replay_compatibility(self._SOURCE, dict(self._SOURCE)) == []

    @pytest.mark.parametrize("element", REPLAY_COMPATIBILITY_ELEMENTS)
    def test_each_mismatch_is_named(self, element):
        # the refusal must name the failing element (SIP plan Slice 3 test spec)
        target = dict(self._SOURCE)
        target[element] = "different"
        errors = check_replay_compatibility(self._SOURCE, target)
        assert len(errors) == 1
        assert element in errors[0]

    def test_absent_vs_present_is_a_mismatch(self):
        # author-mode source (no contract_ref) vs bind-mode target must refuse
        target = dict(self._SOURCE)
        source = dict(self._SOURCE)
        source["contract_ref"] = None
        errors = check_replay_compatibility(source, target)
        assert any("contract_ref" in e for e in errors)


class TestCheckpointTranslation:
    def test_task_ids_rebound_to_target_namespace(self):
        translated = translate_checkpoint_for_replay(_source_checkpoint(), "run_ddddeeeeffff")
        assert translated.completed_task_ids == (
            "task-run_ddddeeee-m000-development.develop",
            "task-run_ddddeeee-m001-builder.assemble",
        )
        assert translated.run_id == "run_ddddeeeeffff"

    def test_everything_else_carried_verbatim(self):
        # the SIP §3.4 determinism contract: restored state byte-equal to the
        # source's state at the boundary (only the id namespace rebinds)
        src = _source_checkpoint()
        translated = translate_checkpoint_for_replay(src, "run_ddddeeeeffff")
        assert translated.checkpoint_index == src.checkpoint_index
        assert translated.prior_outputs == src.prior_outputs
        assert translated.artifact_refs == src.artifact_refs
        assert translated.plan_delta_refs == src.plan_delta_refs
        assert translated.created_at == src.created_at

    def test_foreign_task_id_fails_closed(self):
        # an id outside the source's deterministic namespace cannot be
        # translated — guessing would suppress the wrong task
        src = _source_checkpoint()
        import dataclasses

        broken = dataclasses.replace(
            src, completed_task_ids=src.completed_task_ids + ("adhoc-uuid-task",)
        )
        with pytest.raises(ValueError, match="cannot translate"):
            translate_checkpoint_for_replay(broken, "run_ddddeeeeffff")


class TestOutcomeCarriesProvenance:
    def test_aggregate_threads_replay(self):
        p = ReplayProvenance("run_src", 2, REPLAY_COMPATIBILITY_ELEMENTS)
        outcome = aggregate_cycle_outcome([], replay=p)
        assert outcome.replay == p
        assert outcome.verdict is RunVerdict.ACCEPTED  # empty-evidence default unchanged

    async def test_resolve_cycle_outcome_derives_provenance_from_declaration(self):
        from squadops.cycles.cycle_outcome import resolve_cycle_outcome

        registry = AsyncMock()
        registry.list_run_verification_summaries.return_value = []
        cycle = MagicMock()
        cycle.execution_overrides = dict(_DECL)
        registry.get_cycle.return_value = cycle

        outcome = await resolve_cycle_outcome(registry, "cyc_1")

        assert outcome.replay is not None
        assert outcome.replay.source_run_id == "run_src"
        assert outcome.replay.boundary_index == 2
        assert outcome.replay.compatibility_set == REPLAY_COMPATIBILITY_ELEMENTS

    async def test_resolve_cycle_outcome_normal_cycle_unmarked(self):
        from squadops.cycles.cycle_outcome import resolve_cycle_outcome

        registry = AsyncMock()
        registry.list_run_verification_summaries.return_value = []
        cycle = MagicMock()
        cycle.execution_overrides = {}
        registry.get_cycle.return_value = cycle

        outcome = await resolve_cycle_outcome(registry, "cyc_1")
        assert outcome.replay is None


def _run(run_id: str, workload: str) -> Run:
    return Run(
        run_id=run_id,
        cycle_id="cyc_1",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="h",
        workload_type=workload,
    )


class TestExecutorReplayResolution:
    def _executor(self, registry) -> DispatchedFlowExecutor:
        return DispatchedFlowExecutor(cycle_registry=registry)

    def _cycle(self, overrides) -> MagicMock:
        cycle = MagicMock()
        cycle.execution_overrides = overrides
        return cycle

    async def test_normal_cycle_resolves_none(self):
        registry = AsyncMock()
        executor = self._executor(registry)
        assert await executor._resolve_replay_checkpoint(self._cycle({}), "run_t") is None
        registry.get_run.assert_not_awaited()

    async def test_workload_mismatch_resolves_none(self):
        # replay targets the run matching the source's workload; a framing run
        # in the same cycle executes normally
        registry = AsyncMock()
        registry.get_run.side_effect = lambda rid: _run(
            rid, "implementation" if rid == "run_src" else "framing"
        )
        executor = self._executor(registry)
        result = await executor._resolve_replay_checkpoint(self._cycle(dict(_DECL)), "run_t")
        assert result is None

    async def test_missing_boundary_fails_closed(self):
        registry = AsyncMock()
        registry.get_run.side_effect = lambda rid: _run(rid, "implementation")
        registry.list_checkpoints.return_value = []  # pruned or never written
        executor = self._executor(registry)
        with pytest.raises(_ExecutionError, match="boundary 2 not found"):
            await executor._resolve_replay_checkpoint(self._cycle(dict(_DECL)), "run_t")

    async def test_matching_run_gets_translated_checkpoint(self):
        registry = AsyncMock()
        registry.get_run.side_effect = lambda rid: _run(rid, "implementation")
        src = _source_checkpoint()
        registry.list_checkpoints.return_value = [src]
        decl = {
            "execution_mode": "replay",
            "replay": {"source_run_id": src.run_id, "boundary_index": 2},
        }
        executor = self._executor(registry)

        result = await executor._resolve_replay_checkpoint(self._cycle(decl), "run_ddddeeeeffff")

        assert result is not None
        assert result.run_id == "run_ddddeeeeffff"
        assert all(t.startswith("task-run_ddddeeee-") for t in result.completed_task_ids)

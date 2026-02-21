"""Tests for run report generation (SIP-Enhanced-Agent-Build-Capabilities).

Validates that _generate_run_report() produces a structured markdown report
stored as a documentation artifact, and that failures don't affect run status.

Part of Phase 3.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.cycles.models import (
    Cycle,
    GateDecision,
    Run,
    RunStatus,
    TaskFlowPolicy,
)
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_cycle() -> Cycle:
    return Cycle(
        cycle_id="cyc_001",
        project_id="play_game",
        created_at=NOW,
        created_by="system",
        prd_ref="Build a game",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
    )


def _make_run(
    gate_decisions=(),
    artifact_refs=(),
    started_at=None,
    finished_at=None,
) -> Run:
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="completed",
        initiated_by="api",
        resolved_config_hash="hash",
        started_at=started_at,
        finished_at=finished_at,
        gate_decisions=gate_decisions,
        artifact_refs=artifact_refs,
    )


def _make_plan(count: int = 3) -> list[TaskEnvelope]:
    steps = [
        ("strategy.analyze_prd", "strat", "nat"),
        ("development.implement", "dev", "neo"),
        ("qa.validate", "qa", "eve"),
    ]
    envelopes = []
    for i in range(min(count, len(steps))):
        task_type, role, agent = steps[i]
        envelopes.append(TaskEnvelope(
            task_id=f"task_{i}",
            agent_id=agent,
            cycle_id="cyc_001",
            pulse_id="pulse_1",
            project_id="play_game",
            task_type=task_type,
            correlation_id="corr_1",
            causation_id="corr_1" if i == 0 else f"task_{i - 1}",
            trace_id="trace_1",
            span_id=f"span_{i}",
            inputs={"prd": "test"},
            metadata={"role": role, "step_index": i},
        ))
    return envelopes


@pytest.fixture
def executor():
    """Create a DistributedFlowExecutor with mocked ports."""
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    vault = AsyncMock()
    vault.store = AsyncMock(side_effect=lambda ref, content: ref)
    registry = AsyncMock()

    ex = DistributedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=vault,
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
    )
    return ex


class TestReportContainsMetadata:
    async def test_report_contains_metadata(self, executor):
        """Run report includes cycle/run metadata."""
        cycle = _make_cycle()
        run = _make_run(
            started_at=NOW,
            artifact_refs=("art_001", "art_002"),
        )
        executor._cycle_registry.get_run = AsyncMock(return_value=run)

        await executor._generate_run_report(
            "cyc_001", "run_001", "COMPLETED",
            cycle=cycle, plan=_make_plan(),
        )

        # Verify vault.store was called with the report content
        call_args = executor._artifact_vault.store.call_args
        ref = call_args[0][0]
        content_bytes = call_args[0][1]
        content = content_bytes.decode()

        assert ref.filename == "run_report.md"
        assert ref.artifact_type == "document"
        assert "cyc_001" in content
        assert "run_001" in content
        assert "COMPLETED" in content
        assert "play_game" in content
        assert "fresh" in content

    async def test_report_includes_quality_notes(self, executor):
        """Run report includes quality notes section."""
        cycle = _make_cycle()
        run = _make_run()
        executor._cycle_registry.get_run = AsyncMock(return_value=run)

        await executor._generate_run_report(
            "cyc_001", "run_001", "COMPLETED",
            cycle=cycle, plan=None,
        )

        content = executor._artifact_vault.store.call_args[0][1].decode()
        assert "Quality Notes" in content
        assert "All tasks completed successfully" in content

    async def test_report_quality_notes_failed(self, executor):
        """Run report quality notes reflect FAILED status."""
        cycle = _make_cycle()
        run = _make_run()
        executor._cycle_registry.get_run = AsyncMock(return_value=run)

        await executor._generate_run_report(
            "cyc_001", "run_001", "FAILED",
            cycle=cycle, plan=None,
        )

        content = executor._artifact_vault.store.call_args[0][1].decode()
        assert "Quality Notes" in content
        assert "failed" in content.lower()

    async def test_report_includes_task_plan(self, executor):
        """Run report includes task plan breakdown."""
        cycle = _make_cycle()
        run = _make_run()
        executor._cycle_registry.get_run = AsyncMock(return_value=run)
        plan = _make_plan(3)

        await executor._generate_run_report(
            "cyc_001", "run_001", "COMPLETED",
            cycle=cycle, plan=plan,
        )

        content = executor._artifact_vault.store.call_args[0][1].decode()
        assert "Task Plan" in content
        assert "strategy.analyze_prd" in content
        assert "development.implement" in content
        assert "qa.validate" in content
        assert "Total tasks: 3" in content

    async def test_report_includes_gate_decisions(self, executor):
        """Run report includes gate decisions when present."""
        cycle = _make_cycle()
        run = _make_run(
            gate_decisions=(
                GateDecision(
                    gate_name="plan-review",
                    decision="approved",
                    decided_by="user",
                    decided_at=NOW,
                    notes="LGTM",
                ),
            ),
        )
        executor._cycle_registry.get_run = AsyncMock(return_value=run)

        await executor._generate_run_report(
            "cyc_001", "run_001", "COMPLETED",
            cycle=cycle, plan=None,
        )

        content = executor._artifact_vault.store.call_args[0][1].decode()
        assert "Gate Decisions" in content
        assert "plan-review" in content
        assert "approved" in content
        assert "LGTM" in content

    async def test_report_includes_artifact_count(self, executor):
        """Run report includes artifact inventory count."""
        cycle = _make_cycle()
        run = _make_run(artifact_refs=("a1", "a2", "a3"))
        executor._cycle_registry.get_run = AsyncMock(return_value=run)

        await executor._generate_run_report(
            "cyc_001", "run_001", "COMPLETED",
            cycle=cycle, plan=None,
        )

        content = executor._artifact_vault.store.call_args[0][1].decode()
        assert "Total artifacts: 3" in content


class TestReportFailureNoStatusChange:
    async def test_report_failure_no_status_change(self, executor):
        """Report generation failure doesn't affect run status."""
        executor._cycle_registry.get_run = AsyncMock(
            side_effect=Exception("registry down"),
        )

        # Should not raise — caller wraps in try/except
        with pytest.raises(Exception, match="registry down"):
            await executor._generate_run_report(
                "cyc_001", "run_001", "COMPLETED",
            )

        # The run status was NOT updated (no update_run_status calls)
        executor._cycle_registry.update_run_status.assert_not_called()


class TestReportWithoutCycleOrPlan:
    async def test_report_without_cycle_or_plan(self, executor):
        """Report works with minimal data (no cycle, no plan)."""
        run = _make_run()
        executor._cycle_registry.get_run = AsyncMock(return_value=run)

        await executor._generate_run_report(
            "cyc_001", "run_001", "FAILED",
            cycle=None, plan=None,
        )

        call_args = executor._artifact_vault.store.call_args
        ref = call_args[0][0]
        content = call_args[0][1].decode()

        assert ref.project_id == "unknown"
        assert "FAILED" in content
        assert "cyc_001" in content

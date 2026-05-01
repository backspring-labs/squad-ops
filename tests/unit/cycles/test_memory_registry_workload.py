"""Tests for MemoryCycleRegistry workload_type filter (Phase 2).

Covers AC 10 (adapter level).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.models import (
    Cycle,
    Run,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def registry():
    return MemoryCycleRegistry()


@pytest.fixture
async def seeded_registry(registry):
    """Registry with a cycle and 3 runs (planning, implementation, None)."""
    cycle = Cycle(
        cycle_id="cyc_001",
        project_id="proj_001",
        created_at=NOW,
        created_by="system",
        prd_ref=None,
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
    )
    await registry.create_cycle(cycle)

    for i, wt in enumerate(["framing", "implementation", None], start=1):
        run = Run(
            run_id=f"run_{i:03d}",
            cycle_id="cyc_001",
            run_number=i,
            status="queued",
            initiated_by="api",
            resolved_config_hash="h",
            workload_type=wt,
        )
        await registry.create_run(run)
    return registry


class TestWorkloadTypeFilter:
    async def test_list_all_runs(self, seeded_registry):
        runs = await seeded_registry.list_runs("cyc_001")
        assert len(runs) == 3

    async def test_filter_planning(self, seeded_registry):
        runs = await seeded_registry.list_runs("cyc_001", workload_type="framing")
        assert len(runs) == 1
        assert runs[0].workload_type == "framing"

    async def test_filter_implementation(self, seeded_registry):
        runs = await seeded_registry.list_runs("cyc_001", workload_type="implementation")
        assert len(runs) == 1
        assert runs[0].workload_type == "implementation"

    async def test_filter_no_match(self, seeded_registry):
        runs = await seeded_registry.list_runs("cyc_001", workload_type="evaluation")
        assert len(runs) == 0

    async def test_workload_type_persisted(self, seeded_registry):
        run = await seeded_registry.get_run("run_001")
        assert run.workload_type == "framing"

    async def test_null_workload_type_persisted(self, seeded_registry):
        run = await seeded_registry.get_run("run_003")
        assert run.workload_type is None

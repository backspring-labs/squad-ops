"""Tests for executor manifest loading and artifact chaining (SIP-0086 Phase 3b/3c)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor


# ---------------------------------------------------------------------------
# Lightweight fakes
# ---------------------------------------------------------------------------

MANIFEST_YAML = """\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend models"
    description: "Create models"
    expected_artifacts: ["backend/models.py"]
    depends_on: []
  - task_index: 1
    task_type: development.develop
    role: dev
    focus: "Backend API"
    description: "Create endpoints"
    expected_artifacts: ["backend/main.py"]
    depends_on: [0]
  - task_index: 2
    task_type: qa.test
    role: qa
    focus: "Tests"
    description: "Write tests"
    expected_artifacts: ["tests/test_api.py"]
    depends_on: [0, 1]
summary:
  total_dev_tasks: 2
  total_qa_tasks: 1
  total_tasks: 3
  estimated_layers: [backend, test]
"""


@dataclass
class _FakeArtifactRef:
    artifact_id: str = "art_manifest"
    filename: str = "build_task_manifest.yaml"
    artifact_type: str = "control_manifest"
    metadata: dict = field(default_factory=dict)


@dataclass
class _FakeSourceArtifactRef:
    artifact_id: str = "art_src"
    filename: str = "backend/models.py"
    artifact_type: str = "source"
    metadata: dict = field(default_factory=lambda: {"producing_task_type": "development.develop"})


@dataclass
class _FakeDocArtifactRef:
    artifact_id: str = "art_doc"
    filename: str = "strategy_analysis.md"
    artifact_type: str = "document"
    metadata: dict = field(default_factory=lambda: {"producing_task_type": "strategy.analyze_prd"})


# ---------------------------------------------------------------------------
# Phase 3b: _maybe_rematerialize_from_manifest
# ---------------------------------------------------------------------------


class TestMaybeRematerializeFromManifest:
    def _make_executor(self) -> DistributedFlowExecutor:
        executor = DistributedFlowExecutor.__new__(DistributedFlowExecutor)
        executor._artifact_vault = MagicMock()
        executor._artifact_vault.retrieve = AsyncMock()
        executor._cycle_registry = MagicMock()
        return executor

    def _make_plan_stub(self, n: int = 7) -> list:
        """Create a stub plan list with n items."""
        return [MagicMock(task_id=f"task_{i}") for i in range(n)]

    def _make_profile(self) -> MagicMock:
        from squadops.cycles.models import AgentProfileEntry

        profile = MagicMock()
        profile.profile_id = "full-squad"
        profile.agents = [
            AgentProfileEntry(agent_id="neo", role="dev", model="test", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="test", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="test", enabled=True),
            AgentProfileEntry(agent_id="nat", role="strat", model="test", enabled=True),
            AgentProfileEntry(agent_id="data", role="data", model="test", enabled=True),
        ]
        return profile

    async def test_no_manifest_returns_original_plan(self):
        executor = self._make_executor()
        plan = self._make_plan_stub()

        # No manifest in stored artifacts
        result = await executor._maybe_rematerialize_from_manifest(
            plan=plan,
            task_idx=4,
            stored_artifacts=[],
            cycle=MagicMock(),
            run=MagicMock(),
            profile=self._make_profile(),
        )

        assert result is plan  # Same object, unchanged

    async def test_manifest_found_replaces_build_steps(self):
        executor = self._make_executor()
        plan = self._make_plan_stub(7)  # 5 planning + 2 static build

        # Manifest in stored artifacts
        manifest_ref = _FakeArtifactRef()
        stored = [("art_manifest", manifest_ref)]
        executor._artifact_vault.retrieve.return_value = (
            manifest_ref,
            MANIFEST_YAML.encode(),
        )

        from datetime import datetime, timezone

        from squadops.cycles.models import (
            AgentProfileEntry,
            Cycle,
            Run,
            SquadProfile,
            TaskFlowPolicy,
        )

        cycle = Cycle(
            cycle_id="cyc_test",
            project_id="group_run",
            created_at=datetime.now(timezone.utc),
            created_by="system",
            prd_ref="Build a group run app",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={"plan_tasks": True, "build_tasks": True},
            execution_overrides={},
        )
        run = Run(
            run_id="run_abcdef123456",
            cycle_id="cyc_test",
            run_number=1,
            status="running",
            initiated_by="api",
            resolved_config_hash="hash123",
        )
        profile = SquadProfile(
            profile_id="full-squad",
            name="Full Squad",
            description="Test",
            version=1,
            agents=[
                AgentProfileEntry(
                    agent_id="neo", role="dev", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="eve", role="qa", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="max", role="lead", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="nat", role="strat", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="data", role="data", model="test", enabled=True
                ),
            ],
            created_at=datetime.now(timezone.utc),
        )

        # Gate fires after task_idx=4 (governance.review, the 5th planning task)
        result = await executor._maybe_rematerialize_from_manifest(
            plan=plan,
            task_idx=4,
            stored_artifacts=stored,
            cycle=cycle,
            run=run,
            profile=profile,
        )

        # Should have 5 original planning stubs + 3 manifest-derived envelopes
        assert len(result) == 8
        # First 5 are the original plan stubs
        assert result[:5] == plan[:5]
        # Last 3 are manifest-derived envelopes with deterministic IDs
        assert result[5].task_id == "task-run_abcdef12-m000-development.develop"
        assert result[6].task_id == "task-run_abcdef12-m001-development.develop"
        assert result[7].task_id == "task-run_abcdef12-m002-qa.test"
        # Verify subtask_focus present on manifest envelopes
        assert result[5].inputs["subtask_focus"] == "Backend models"

    async def test_manifest_parse_failure_returns_original(self):
        executor = self._make_executor()
        plan = self._make_plan_stub()

        manifest_ref = _FakeArtifactRef()
        stored = [("art_manifest", manifest_ref)]
        executor._artifact_vault.retrieve.return_value = (
            manifest_ref,
            b"{{invalid yaml",
        )

        result = await executor._maybe_rematerialize_from_manifest(
            plan=plan,
            task_idx=4,
            stored_artifacts=stored,
            cycle=MagicMock(),
            run=MagicMock(),
            profile=MagicMock(),
        )

        assert result is plan

    async def test_vault_failure_returns_original(self):
        executor = self._make_executor()
        plan = self._make_plan_stub()

        manifest_ref = _FakeArtifactRef()
        stored = [("art_manifest", manifest_ref)]
        executor._artifact_vault.retrieve.side_effect = Exception("vault down")

        result = await executor._maybe_rematerialize_from_manifest(
            plan=plan,
            task_idx=4,
            stored_artifacts=stored,
            cycle=MagicMock(),
            run=MagicMock(),
            profile=MagicMock(),
        )

        assert result is plan

    async def test_planning_tasks_preserved_not_recreated(self):
        """After rematerialization, planning entries are the exact same objects."""
        executor = self._make_executor()
        plan = self._make_plan_stub(7)

        manifest_ref = _FakeArtifactRef()
        stored = [("art_manifest", manifest_ref)]
        executor._artifact_vault.retrieve.return_value = (
            manifest_ref,
            MANIFEST_YAML.encode(),
        )

        from datetime import datetime, timezone

        from squadops.cycles.models import (
            AgentProfileEntry,
            Cycle,
            Run,
            SquadProfile,
            TaskFlowPolicy,
        )

        cycle = Cycle(
            cycle_id="cyc_test",
            project_id="group_run",
            created_at=datetime.now(timezone.utc),
            created_by="system",
            prd_ref="Build a group run app",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={"plan_tasks": True, "build_tasks": True},
            execution_overrides={},
        )
        run = Run(
            run_id="run_abcdef123456",
            cycle_id="cyc_test",
            run_number=1,
            status="running",
            initiated_by="api",
            resolved_config_hash="hash123",
        )
        profile = SquadProfile(
            profile_id="full-squad",
            name="Full Squad",
            description="Test",
            version=1,
            agents=[
                AgentProfileEntry(
                    agent_id="neo", role="dev", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="eve", role="qa", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="max", role="lead", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="nat", role="strat", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="data", role="data", model="test", enabled=True
                ),
            ],
            created_at=datetime.now(timezone.utc),
        )

        result = await executor._maybe_rematerialize_from_manifest(
            plan=plan, task_idx=4, stored_artifacts=stored,
            cycle=cycle, run=run, profile=profile,
        )

        # First 5 entries are the exact same stub objects (not recreated)
        for i in range(5):
            assert result[i] is plan[i]

    async def test_manifest_task_ids_are_deterministic_across_calls(self):
        """RC-2: Manifest-derived IDs are stable across rematerialization calls."""
        executor = self._make_executor()

        manifest_ref = _FakeArtifactRef()
        stored = [("art_manifest", manifest_ref)]
        executor._artifact_vault.retrieve.return_value = (
            manifest_ref,
            MANIFEST_YAML.encode(),
        )

        from datetime import datetime, timezone

        from squadops.cycles.models import (
            AgentProfileEntry,
            Cycle,
            Run,
            SquadProfile,
            TaskFlowPolicy,
        )

        cycle = Cycle(
            cycle_id="cyc_test",
            project_id="group_run",
            created_at=datetime.now(timezone.utc),
            created_by="system",
            prd_ref="Build a group run app",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={"plan_tasks": True, "build_tasks": True},
            execution_overrides={},
        )
        run = Run(
            run_id="run_abcdef123456",
            cycle_id="cyc_test",
            run_number=1,
            status="running",
            initiated_by="api",
            resolved_config_hash="hash123",
        )
        profile = SquadProfile(
            profile_id="full-squad",
            name="Full Squad",
            description="Test",
            version=1,
            agents=[
                AgentProfileEntry(
                    agent_id="neo", role="dev", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="eve", role="qa", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="max", role="lead", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="nat", role="strat", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="data", role="data", model="test", enabled=True
                ),
            ],
            created_at=datetime.now(timezone.utc),
        )

        plan1 = self._make_plan_stub(7)
        result1 = await executor._maybe_rematerialize_from_manifest(
            plan=plan1, task_idx=4, stored_artifacts=stored,
            cycle=cycle, run=run, profile=profile,
        )

        plan2 = self._make_plan_stub(7)
        result2 = await executor._maybe_rematerialize_from_manifest(
            plan=plan2, task_idx=4, stored_artifacts=stored,
            cycle=cycle, run=run, profile=profile,
        )

        # Manifest-derived task IDs must be identical across both calls
        ids1 = [e.task_id for e in result1[5:]]
        ids2 = [e.task_id for e in result2[5:]]
        assert ids1 == ids2

    def test_rc1_manifest_is_frozen_dataclass(self):
        """RC-1: BuildTaskManifest is a frozen dataclass — field reassignment blocked."""
        from squadops.cycles.build_manifest import BuildTaskManifest, ManifestTask

        manifest = BuildTaskManifest.from_yaml(MANIFEST_YAML)

        # Cannot reassign top-level fields
        with pytest.raises(AttributeError):
            manifest.version = 99  # type: ignore[misc]

        with pytest.raises(AttributeError):
            manifest.tasks = []  # type: ignore[misc]

        # ManifestTask is also frozen
        task = manifest.tasks[0]
        with pytest.raises(AttributeError):
            task.focus = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Phase 3c: Artifact chaining — dev→dev via _BUILD_ARTIFACT_FILTER
# ---------------------------------------------------------------------------


class TestBuildArtifactFilterChaining:
    def test_dev_develop_filter_includes_prior_dev_develop(self):
        """development.develop must see artifacts from prior development.develop tasks."""
        filt = DistributedFlowExecutor._BUILD_ARTIFACT_FILTER["development.develop"]
        assert "development.develop" in filt["by_producing_task"]

    def test_dev_develop_filter_includes_planning_artifacts(self):
        """development.develop must also see strategy and design artifacts."""
        filt = DistributedFlowExecutor._BUILD_ARTIFACT_FILTER["development.develop"]
        assert "strategy.analyze_prd" in filt["by_producing_task"]
        assert "development.design" in filt["by_producing_task"]

    def test_qa_test_filter_includes_dev_develop(self):
        """qa.test must see artifacts from development.develop subtasks."""
        filt = DistributedFlowExecutor._BUILD_ARTIFACT_FILTER["qa.test"]
        assert "development.develop" in filt["by_producing_task"]

    def test_builder_assemble_unchanged(self):
        """builder.assemble filter should still work as before."""
        filt = DistributedFlowExecutor._BUILD_ARTIFACT_FILTER["builder.assemble"]
        assert "development.develop" in filt["by_producing_task"]


class TestResolveArtifactContentsChaining:
    """Verify _resolve_artifact_contents chains dev→dev artifacts."""

    def _make_executor(self) -> DistributedFlowExecutor:
        executor = DistributedFlowExecutor.__new__(DistributedFlowExecutor)
        executor._artifact_vault = MagicMock()
        executor._artifact_vault.retrieve = AsyncMock()
        return executor

    async def test_dev_task_receives_prior_dev_artifacts(self):
        executor = self._make_executor()

        # Prior artifacts: one from strategy, one from earlier dev.develop
        strategy_ref = _FakeDocArtifactRef()
        dev_ref = _FakeSourceArtifactRef()
        stored = [
            ("art_strat", strategy_ref),
            ("art_dev0", dev_ref),
        ]

        executor._artifact_vault.retrieve.side_effect = [
            (strategy_ref, b"strategy content"),
            (dev_ref, b"models content"),
        ]

        contents = await executor._resolve_artifact_contents(
            "development.develop", stored
        )

        assert "strategy_analysis.md" in contents
        assert "backend/models.py" in contents

    async def test_qa_task_receives_dev_artifacts(self):
        executor = self._make_executor()

        dev_ref = _FakeSourceArtifactRef()
        stored = [("art_dev0", dev_ref)]

        executor._artifact_vault.retrieve.return_value = (
            dev_ref,
            b"models content",
        )

        contents = await executor._resolve_artifact_contents("qa.test", stored)

        assert "backend/models.py" in contents

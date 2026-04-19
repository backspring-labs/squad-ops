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
    metadata: dict = field(
        default_factory=lambda: {"producing_task_type": "development.develop"}
    )


@dataclass
class _FakeDocArtifactRef:
    artifact_id: str = "art_doc"
    filename: str = "strategy_analysis.md"
    artifact_type: str = "document"
    metadata: dict = field(
        default_factory=lambda: {"producing_task_type": "strategy.analyze_prd"}
    )


# ---------------------------------------------------------------------------
# Phase 3b: _load_manifest_for_run
# ---------------------------------------------------------------------------


class TestLoadManifestForRun:
    def _make_executor(self) -> DistributedFlowExecutor:
        executor = DistributedFlowExecutor.__new__(DistributedFlowExecutor)
        executor._artifact_vault = MagicMock()
        executor._artifact_vault.retrieve = AsyncMock()
        return executor

    def _make_cycle(self, **overrides) -> MagicMock:
        cycle = MagicMock()
        cycle.applied_defaults = {"build_manifest": True}
        cycle.execution_overrides = {}
        for k, v in overrides.items():
            setattr(cycle, k, v)
        return cycle

    def _make_run(self) -> MagicMock:
        run = MagicMock()
        run.run_id = "run_abcdef123456"
        return run

    async def test_no_plan_refs_returns_none(self):
        executor = self._make_executor()
        cycle = self._make_cycle(execution_overrides={})

        result = await executor._load_manifest_for_run(cycle, self._make_run())

        assert result is None

    async def test_build_manifest_disabled_returns_none(self):
        executor = self._make_executor()
        cycle = self._make_cycle(
            applied_defaults={"build_manifest": False},
            execution_overrides={"plan_artifact_refs": ["art_manifest"]},
        )

        result = await executor._load_manifest_for_run(cycle, self._make_run())

        assert result is None

    async def test_manifest_found_in_plan_refs(self):
        executor = self._make_executor()
        manifest_ref = _FakeArtifactRef()
        executor._artifact_vault.retrieve.return_value = (
            manifest_ref,
            MANIFEST_YAML.encode(),
        )
        cycle = self._make_cycle(
            execution_overrides={"plan_artifact_refs": ["art_manifest"]},
        )

        result = await executor._load_manifest_for_run(cycle, self._make_run())

        assert result is not None
        assert len(result.tasks) == 3
        assert result.tasks[0].focus == "Backend models"

    async def test_non_manifest_refs_skipped(self):
        executor = self._make_executor()
        doc_ref = _FakeDocArtifactRef()
        executor._artifact_vault.retrieve.return_value = (
            doc_ref,
            b"# Strategy\nSome content",
        )
        cycle = self._make_cycle(
            execution_overrides={"plan_artifact_refs": ["art_doc"]},
        )

        result = await executor._load_manifest_for_run(cycle, self._make_run())

        assert result is None

    async def test_vault_failure_returns_none(self):
        executor = self._make_executor()
        executor._artifact_vault.retrieve.side_effect = Exception("vault down")
        cycle = self._make_cycle(
            execution_overrides={"plan_artifact_refs": ["art_manifest"]},
        )

        result = await executor._load_manifest_for_run(cycle, self._make_run())

        assert result is None

    async def test_malformed_yaml_returns_none(self):
        executor = self._make_executor()
        manifest_ref = _FakeArtifactRef()
        executor._artifact_vault.retrieve.return_value = (
            manifest_ref,
            b"{{invalid yaml",
        )
        cycle = self._make_cycle(
            execution_overrides={"plan_artifact_refs": ["art_manifest"]},
        )

        result = await executor._load_manifest_for_run(cycle, self._make_run())

        assert result is None

    def test_rc1_manifest_is_frozen_dataclass(self):
        """RC-1: BuildTaskManifest is a frozen dataclass — field reassignment blocked."""
        from squadops.cycles.build_manifest import BuildTaskManifest

        manifest = BuildTaskManifest.from_yaml(MANIFEST_YAML)

        with pytest.raises(AttributeError):
            manifest.version = 99  # type: ignore[misc]

        with pytest.raises(AttributeError):
            manifest.tasks = []  # type: ignore[misc]

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

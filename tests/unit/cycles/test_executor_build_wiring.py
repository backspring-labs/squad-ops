"""Tests for executor build task wiring (SIP-Enhanced-Agent-Build-Capabilities).

Tests artifact content pre-resolution, build-only validation, and
producing_task_type metadata tracking in DistributedFlowExecutor.

Part of Phase 2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    Run,
    RunStatus,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_artifact_ref(
    artifact_id: str,
    filename: str,
    artifact_type: str = "document",
    producing_task_type: str = "",
) -> ArtifactRef:
    metadata = {"task_id": "task_1", "role": "dev"}
    if producing_task_type:
        metadata["producing_task_type"] = producing_task_type
    return ArtifactRef(
        artifact_id=artifact_id,
        project_id="test",
        artifact_type=artifact_type,
        filename=filename,
        content_hash="abc",
        size_bytes=100,
        media_type="text/markdown",
        created_at=NOW,
        metadata=metadata,
    )


@pytest.fixture
def executor():
    """Create a DistributedFlowExecutor with mocked ports."""
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    vault = AsyncMock()
    registry = AsyncMock()
    queue = AsyncMock()
    squad = AsyncMock()
    project = AsyncMock()

    registry.get_latest_checkpoint.return_value = None
    registry.save_checkpoint.return_value = None

    ex = DistributedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=vault,
        queue=queue,
        squad_profile=squad,
        project_registry=project,
    )
    return ex


# ---------------------------------------------------------------------------
# Artifact content pre-resolution
# ---------------------------------------------------------------------------


class TestArtifactContentsPreResolution:
    async def test_artifact_contents_injected_for_build_task(self, executor):
        """Pre-resolution returns content keyed by filename."""
        ref_strategy = _make_artifact_ref(
            "art_001",
            "strategy_analysis.md",
            "document",
            producing_task_type="strategy.analyze_prd",
        )
        ref_impl = _make_artifact_ref(
            "art_002",
            "implementation_plan.md",
            "document",
            producing_task_type="development.design",
        )

        stored = [("art_001", ref_strategy), ("art_002", ref_impl)]

        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[
                (ref_strategy, b"Strategy content"),
                (ref_impl, b"Implementation content"),
            ]
        )

        contents = await executor._resolve_artifact_contents(
            "development.develop",
            stored,
        )

        assert "strategy_analysis.md" in contents
        assert contents["strategy_analysis.md"] == "Strategy content"
        assert "implementation_plan.md" in contents
        assert contents["implementation_plan.md"] == "Implementation content"

    async def test_no_resolution_for_plan_tasks(self, executor):
        """Plan tasks (e.g., strategy.analyze_prd) get no pre-resolution."""
        contents = await executor._resolve_artifact_contents(
            "strategy.analyze_prd",
            [],
        )
        assert contents == {}

    async def test_qa_build_gets_source_artifacts(self, executor):
        """qa.test receives source artifacts by type."""
        ref_val = _make_artifact_ref(
            "art_001",
            "validation_plan.md",
            "document",
            producing_task_type="qa.validate",
        )
        ref_src = _make_artifact_ref(
            "art_002",
            "src/main.py",
            "source",
            producing_task_type="development.develop",
        )

        stored = [("art_001", ref_val), ("art_002", ref_src)]

        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[
                (ref_val, b"Validation plan"),
                (ref_src, b"print('hello')"),
            ]
        )

        contents = await executor._resolve_artifact_contents(
            "qa.test",
            stored,
        )

        assert "validation_plan.md" in contents
        assert "src/main.py" in contents

    async def test_size_limit_stops_resolution(self, executor):
        """If content exceeds 512KB, resolution stops early."""
        big_content = b"x" * (256 * 1024)  # 256KB each, 2 = 512KB

        ref1 = _make_artifact_ref(
            "art_001",
            "file1.md",
            "document",
            producing_task_type="strategy.analyze_prd",
        )
        ref2 = _make_artifact_ref(
            "art_002",
            "file2.md",
            "document",
            producing_task_type="development.design",
        )
        ref3 = _make_artifact_ref(
            "art_003",
            "file3.md",
            "document",
            producing_task_type="strategy.analyze_prd",
        )

        stored = [("art_001", ref1), ("art_002", ref2), ("art_003", ref3)]

        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[
                (ref1, big_content),
                (ref2, big_content),
                (ref3, big_content),  # Should not be reached
            ]
        )

        contents = await executor._resolve_artifact_contents(
            "development.develop",
            stored,
        )

        # First two fit (256+256=512), third would exceed limit
        assert len(contents) == 2


class TestProducingTaskTypeMetadata:
    async def test_store_artifact_includes_producing_task_type(self, executor):
        from squadops.tasks.models import TaskEnvelope

        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )

        envelope = TaskEnvelope(
            task_id="task_1",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="pulse_1",
            project_id="test",
            task_type="development.develop",
            correlation_id="corr_1",
            causation_id="corr_1",
            trace_id="trace_1",
            span_id="span_1",
            inputs={"prd": "test"},
            metadata={"role": "dev", "step_index": 5},
        )

        # Mock vault.store to return the ref as-is
        executor._artifact_vault.store = AsyncMock(side_effect=lambda ref, content: ref)

        art_dict = {
            "name": "src/main.py",
            "content": "print('hello')",
            "type": "source",
            "media_type": "text/x-python",
        }

        ref = await executor._store_artifact(
            art_dict,
            cycle,
            "run_001",
            envelope,
            producing_task_type="development.develop",
        )

        assert ref.metadata["producing_task_type"] == "development.develop"
        assert ref.metadata["task_id"] == "task_1"
        assert ref.metadata["role"] == "dev"


# ---------------------------------------------------------------------------
# Build-only validation
# ---------------------------------------------------------------------------


class TestBuildOnlyValidation:
    async def test_build_only_missing_refs_fails(self):
        """Build-only cycle without plan_artifact_refs raises _ExecutionError."""
        from adapters.cycles.distributed_flow_executor import (
            DistributedFlowExecutor,
        )

        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={
                "plan_tasks": False,
                "build_tasks": ["development.develop", "qa.test"],
            },
            execution_overrides={},  # no plan_artifact_refs
        )

        run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        registry = AsyncMock()
        registry.get_cycle = AsyncMock(return_value=cycle)
        registry.get_run = AsyncMock(return_value=run)
        registry.update_run_status = AsyncMock()
        registry.get_latest_checkpoint = AsyncMock(return_value=None)
        registry.save_checkpoint = AsyncMock(return_value=None)

        squad = AsyncMock()
        from squadops.cycles.models import AgentProfileEntry, SquadProfile

        squad.resolve_snapshot = AsyncMock(
            return_value=(
                SquadProfile(
                    profile_id="full-squad",
                    name="Full",
                    description="",
                    version=1,
                    agents=(
                        AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
                        AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
                    ),
                    created_at=NOW,
                ),
                "snap",
            )
        )

        ex = DistributedFlowExecutor(
            cycle_registry=registry,
            artifact_vault=AsyncMock(),
            queue=AsyncMock(),
            squad_profile=squad,
        )

        await ex.execute_run("cyc_001", "run_001")

        # Run should transition to FAILED
        registry.update_run_status.assert_any_call("run_001", RunStatus.RUNNING)
        # The executor catches _ExecutionError and transitions to FAILED
        calls = [c.args for c in registry.update_run_status.call_args_list]
        assert ("run_001", RunStatus.FAILED) in calls


class TestBuildOnlySeeding:
    """Build-only runs seed stored_artifacts from plan_artifact_refs."""

    async def test_build_only_seeds_from_plan_refs(self, executor):
        """When seed_artifact_refs is provided, _execute_sequential loads them."""
        ref_plan = _make_artifact_ref(
            "art_plan_001",
            "implementation_plan.md",
            "document",
        )

        executor._artifact_vault.retrieve = AsyncMock(
            return_value=(ref_plan, b"Plan content here"),
        )

        # We can't easily run the full _execute_sequential (needs queue/dispatch),
        # but we can verify the seeding logic by testing _resolve_artifact_contents
        # after manually seeding stored_artifacts the same way the executor does.
        stored_artifacts: list[tuple[str, ArtifactRef]] = []
        seed_refs = ["art_plan_001"]

        for art_id in seed_refs:
            ref, _ = await executor._artifact_vault.retrieve(art_id)
            stored_artifacts.append((art_id, ref))

        # Now pre-resolve for a build task — the seeded artifact should be found
        # via by_type_fallback (document type, no producing_task_type)
        executor._artifact_vault.retrieve = AsyncMock(
            return_value=(ref_plan, b"Plan content here"),
        )
        contents = await executor._resolve_artifact_contents(
            "development.develop",
            stored_artifacts,
        )

        assert "implementation_plan.md" in contents
        assert contents["implementation_plan.md"] == "Plan content here"

    async def test_build_only_with_valid_refs_passes_validation(self):
        """Build-only cycle with plan_artifact_refs does not raise."""
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        ref_plan = _make_artifact_ref("art_plan_001", "implementation_plan.md", "document")

        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={
                "plan_tasks": False,
                "build_tasks": ["development.develop", "qa.test"],
            },
            execution_overrides={
                "plan_artifact_refs": ["art_plan_001"],
            },
        )

        run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        registry = AsyncMock()
        registry.get_cycle = AsyncMock(return_value=cycle)
        registry.get_run = AsyncMock(return_value=run)
        registry.update_run_status = AsyncMock()
        registry.append_artifact_refs = AsyncMock()
        registry.get_latest_checkpoint = AsyncMock(return_value=None)
        registry.save_checkpoint = AsyncMock(return_value=None)

        vault = AsyncMock()
        vault.retrieve = AsyncMock(return_value=(ref_plan, b"Plan content"))
        vault.store = AsyncMock(side_effect=lambda ref, content: ref)

        from squadops.cycles.models import AgentProfileEntry, SquadProfile

        squad = AsyncMock()
        squad.resolve_snapshot = AsyncMock(
            return_value=(
                SquadProfile(
                    profile_id="full-squad",
                    name="Full",
                    description="",
                    version=1,
                    agents=(
                        AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
                        AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
                    ),
                    created_at=NOW,
                ),
                "snap",
            )
        )

        ex = DistributedFlowExecutor(
            cycle_registry=registry,
            artifact_vault=vault,
            queue=AsyncMock(),
            squad_profile=squad,
        )

        # Mock dispatch to succeed
        async def fake_dispatch(envelope, rid, **_kwargs):
            from squadops.tasks.models import TaskResult

            return TaskResult(
                task_id=envelope.task_id,
                status="SUCCEEDED",
                outputs={
                    "summary": "done",
                    "role": envelope.metadata.get("role"),
                    "artifacts": [
                        {
                            "name": "src/main.py",
                            "content": "print(1)",
                            "type": "source",
                            "media_type": "text/x-python",
                        },
                    ],
                },
            )

        ex._dispatch_task = fake_dispatch

        await ex.execute_run("cyc_001", "run_001")

        # Should complete successfully
        calls = [c.args for c in registry.update_run_status.call_args_list]
        assert ("run_001", RunStatus.COMPLETED) in calls

        # Vault.retrieve should have been called for the seeded ref
        vault.retrieve.assert_any_call("art_plan_001")


class TestPlanOnlyCyclesUnaffected:
    """Regression: plan-only cycles still work as before."""

    async def test_plan_only_cycle_no_build_validation(self):
        """Plan-only cycle doesn't trigger build-only validation."""
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={"build_strategy": "fresh"},
            execution_overrides={},
        )

        run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        registry = AsyncMock()
        registry.get_cycle = AsyncMock(return_value=cycle)
        registry.get_run = AsyncMock(return_value=run)
        registry.update_run_status = AsyncMock()
        registry.get_latest_checkpoint = AsyncMock(return_value=None)
        registry.save_checkpoint = AsyncMock(return_value=None)

        queue = AsyncMock()
        # Simulate task results
        msg = MagicMock()
        import json

        msg.payload = json.dumps(
            {
                "payload": {
                    "task_id": "placeholder",
                    "status": "SUCCEEDED",
                    "outputs": {"summary": "done", "role": "strat"},
                }
            }
        )
        queue.consume = AsyncMock(return_value=[msg])
        queue.ack = AsyncMock()

        vault = AsyncMock()
        vault.store = AsyncMock(side_effect=lambda ref, content: ref)

        squad = AsyncMock()
        from squadops.cycles.models import AgentProfileEntry, SquadProfile

        squad.resolve_snapshot = AsyncMock(
            return_value=(
                SquadProfile(
                    profile_id="full-squad",
                    name="Full",
                    description="",
                    version=1,
                    agents=(
                        AgentProfileEntry(agent_id="nat", role="strat", model="m", enabled=True),
                        AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
                        AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
                        AgentProfileEntry(agent_id="data", role="data", model="m", enabled=True),
                        AgentProfileEntry(agent_id="max", role="lead", model="m", enabled=True),
                    ),
                    created_at=NOW,
                ),
                "snap",
            )
        )

        ex = DistributedFlowExecutor(
            cycle_registry=registry,
            artifact_vault=vault,
            queue=queue,
            squad_profile=squad,
        )

        # Mock _dispatch_task to return success for any task
        async def fake_dispatch(envelope, rid, **_kwargs):
            from squadops.tasks.models import TaskResult

            return TaskResult(
                task_id=envelope.task_id,
                status="SUCCEEDED",
                outputs={"summary": "done", "role": envelope.metadata.get("role")},
            )

        ex._dispatch_task = fake_dispatch

        await ex.execute_run("cyc_001", "run_001")

        # Should complete successfully (not fail with build-only error)
        calls = [c.args for c in registry.update_run_status.call_args_list]
        assert ("run_001", RunStatus.COMPLETED) in calls

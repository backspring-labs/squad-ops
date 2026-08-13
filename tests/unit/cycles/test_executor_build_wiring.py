"""Tests for executor build task wiring (SIP-Enhanced-Agent-Build-Capabilities).

Tests artifact content pre-resolution, build-only validation, and
producing_task_type metadata tracking in DispatchedFlowExecutor.

Part of Phase 2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from squadops.capabilities.context_assembly import ACCEPTANCE_WORKSPACE_FILTER
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
def executor(reply_router):
    """Create a DispatchedFlowExecutor with mocked ports."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    vault = AsyncMock()
    registry = AsyncMock()
    queue = reply_router.bind(AsyncMock())
    squad = AsyncMock()
    project = AsyncMock()

    registry.get_latest_checkpoint.return_value = None
    registry.save_checkpoint.return_value = None

    ex = DispatchedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=vault,
        queue=queue,
        squad_profile=squad,
        project_registry=project,
        reply_router=reply_router,
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

    # ------------------------------------------------------------------
    # #881 consumer side: a scaffold-seeded stub never shadows produced code
    # ------------------------------------------------------------------

    @staticmethod
    def _source_ref(art_id: str, filename: str, *, seeded: bool = False) -> ArtifactRef:
        metadata: dict = (
            {"producing_task_type": "scaffold.expand", "scaffold_seeded": True}
            if seeded
            else {"producing_task_type": "development.develop"}
        )
        return ArtifactRef(
            artifact_id=art_id,
            project_id="test",
            artifact_type="source",
            filename=filename,
            content_hash="abc",
            size_bytes=100,
            media_type="text/plain",
            created_at=NOW,
            metadata=metadata,
        )

    async def _resolve(self, executor, entries):
        stored = [(ref.artifact_id, ref) for ref, _ in entries]
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[(ref, content) for ref, content in entries]
        )
        return await executor._resolve_artifact_contents("qa.test", stored)

    async def test_reseeded_stub_after_fill_loses(self, executor):
        """The checkpoint-21 shape from roll 14's resume: the re-seeded stub sits
        AFTER the dev fill in the restored order and previously won last-writer-
        wins, so the qa workspace materialized a route that throws by design."""
        fill = self._source_ref("art_fill", "app/api/runs/route.ts")
        stub = self._source_ref("art_stub", "app/api/runs/route.ts", seeded=True)

        contents = await self._resolve(
            executor, [(fill, b"export async function POST() {}"), (stub, b"throw stub")]
        )

        assert contents["app/api/runs/route.ts"] == "export async function POST() {}"

    async def test_produced_after_stub_wins(self, executor):
        """The normal fresh-run shape: seed first, develop fills later."""
        stub = self._source_ref("art_stub", "app/api/runs/route.ts", seeded=True)
        fill = self._source_ref("art_fill", "app/api/runs/route.ts")

        contents = await self._resolve(executor, [(stub, b"throw stub"), (fill, b"filled")])

        assert contents["app/api/runs/route.ts"] == "filled"

    async def test_latest_produced_version_still_wins(self, executor):
        """RC3: the latest correction attempt supersedes earlier produced
        versions — the #881 rule must not freeze the first fill."""
        v1 = self._source_ref("art_v1", "lib/store_use.ts")
        v2 = self._source_ref("art_v2", "lib/store_use.ts")

        contents = await self._resolve(executor, [(v1, b"attempt 1"), (v2, b"attempt 2")])

        assert contents["lib/store_use.ts"] == "attempt 2"

    async def test_frozen_file_latest_seeded_wins(self, executor):
        """Frozen files exist ONLY as seeded artifacts — among seeded versions
        the latest must still win, or a re-seeded frozen fix would be invisible."""
        s1 = self._source_ref("art_s1", "lib/errors.ts", seeded=True)
        s2 = self._source_ref("art_s2", "lib/errors.ts", seeded=True)

        contents = await self._resolve(executor, [(s1, b"frozen v1"), (s2, b"frozen v2")])

        assert contents["lib/errors.ts"] == "frozen v2"

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

    async def test_repair_patch_wins_over_original_on_filename_collision(self, executor):
        """RC3 (pf-23): when stored_artifacts accumulates a correction repair's
        patched file AFTER the original (same filename), re-resolution returns the
        PATCH — not the stale original. This is the property the correction loop
        relies on after the RC3 fix: re-resolving artifact_contents from the live
        stored_artifacts hands the drift detector the accumulated fix, so it stops
        re-reporting drift the prior attempt already corrected. Note the repair's
        producing_task_type (development.correction_repair) is NOT in the qa.test
        by_producing_task list — it survives only via by_type=source."""
        ref_orig = _make_artifact_ref(
            "art_001",
            "backend/models.py",
            "source",
            producing_task_type="development.develop",
        )
        ref_patch = _make_artifact_ref(
            "art_002",
            "backend/models.py",
            "source",
            producing_task_type="development.correction_repair",
        )
        # Append order: original dev output first, repair patch last (as the
        # executor accumulates them across attempts).
        stored = [("art_001", ref_orig), ("art_002", ref_patch)]
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[
                (ref_orig, b"class RunEvent:\n    pace: str\n"),
                (ref_patch, b"class RunEvent:\n    pace_target: str\n"),
            ]
        )

        contents = await executor._resolve_artifact_contents("qa.test", stored)

        # Last-wins: the repair's patched content supersedes the original.
        assert contents["backend/models.py"] == "class RunEvent:\n    pace_target: str\n"
        assert "pace_target" in contents["backend/models.py"]
        assert "    pace:" not in contents["backend/models.py"]


class TestAcceptanceWorkspaceResolution:
    """#643 (fay-1): the dev prompt filter has no by_type clause, so scaffold
    source files never reached the dev envelope and module_imports evaluated
    in a routes.py-only workspace. The acceptance workspace resolves with the
    full-tree spec regardless of task type."""

    async def test_full_tree_spec_includes_scaffold_source_for_dev(self, executor):
        # The scaffold sibling (source, scaffold.expand provenance) is exactly
        # what development.develop's own filter excludes.
        ref_scaffold = _make_artifact_ref(
            "art_001",
            "backend/errors.py",
            "source",
            producing_task_type="scaffold.expand",
        )
        stored = [("art_001", ref_scaffold)]
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[(ref_scaffold, b"class ApiError(Exception):\n    pass\n")]
        )

        default = await executor._resolve_artifact_contents("development.develop", stored)
        assert "backend/errors.py" not in default

        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[(ref_scaffold, b"class ApiError(Exception):\n    pass\n")]
        )
        workspace = await executor._resolve_artifact_contents(
            "development.develop",
            stored,
            filter_spec=ACCEPTANCE_WORKSPACE_FILTER.to_spec(),
        )
        assert workspace["backend/errors.py"] == "class ApiError(Exception):\n    pass\n"

    async def test_workspace_spec_excludes_rejected_repair_candidates(self, executor):
        # pf-31 Fix E composes with #643: a rejected repair candidate must not
        # enter the acceptance workspace of a fresh dispatch.
        ref_scaffold = _make_artifact_ref(
            "art_001",
            "backend/errors.py",
            "source",
            producing_task_type="scaffold.expand",
        )
        ref_candidate = _make_artifact_ref(
            "art_002",
            "backend/routes.py",
            "source",
            producing_task_type="development.correction_repair",
        )
        stored = [("art_001", ref_scaffold), ("art_002", ref_candidate)]
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[(ref_scaffold, b"class ApiError(Exception):\n    pass\n")]
        )

        workspace = await executor._resolve_artifact_contents(
            "development.develop",
            stored,
            include_repair_candidates=False,
            filter_spec=ACCEPTANCE_WORKSPACE_FILTER.to_spec(),
        )
        assert "backend/errors.py" in workspace
        assert "backend/routes.py" not in workspace


class TestProducingTaskTypeMetadata:
    async def test_store_artifact_includes_producing_task_type(self, executor):
        from squadops.tasks.models import TaskEnvelope

        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full",
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
    async def test_build_only_missing_refs_fails(self, reply_router):
        """Build-only cycle without plan_artifact_refs raises _ExecutionError."""
        from adapters.cycles.dispatched_flow_executor import (
            DispatchedFlowExecutor,
        )

        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full",
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
                    profile_id="full",
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

        ex = DispatchedFlowExecutor(
            cycle_registry=registry,
            artifact_vault=AsyncMock(),
            queue=reply_router.bind(AsyncMock()),
            squad_profile=squad,
            reply_router=reply_router,
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

    async def test_build_only_with_valid_refs_passes_validation(self, reply_router):
        """Build-only cycle with plan_artifact_refs does not raise."""
        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

        ref_plan = _make_artifact_ref("art_plan_001", "implementation_plan.md", "document")

        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full",
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
                    profile_id="full",
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

        from squadops.tasks.models import TaskResult

        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"],
            status="SUCCEEDED",
            outputs={
                "summary": "done",
                "role": env["metadata"].get("role"),
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

        ex = DispatchedFlowExecutor(
            cycle_registry=registry,
            artifact_vault=vault,
            queue=reply_router.bind(AsyncMock()),
            squad_profile=squad,
            reply_router=reply_router,
        )

        await ex.execute_run("cyc_001", "run_001")

        # Should complete successfully
        calls = [c.args for c in registry.update_run_status.call_args_list]
        assert ("run_001", RunStatus.COMPLETED) in calls

        # Vault.retrieve should have been called for the seeded ref
        vault.retrieve.assert_any_call("art_plan_001")


class TestBuilderDeliverableCompleteness:
    """#291: the executor fails a builder run whose emitted set is missing a
    file the build profile requires — the run-level net the per-task validator
    (#107) can't provide once framing decomposes builder work."""

    @staticmethod
    def _builder_squad():
        from squadops.cycles.models import AgentProfileEntry, SquadProfile

        squad = AsyncMock()
        squad.resolve_snapshot = AsyncMock(
            return_value=(
                SquadProfile(
                    profile_id="full",
                    name="Full",
                    description="",
                    version=1,
                    agents=(
                        AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
                        AgentProfileEntry(agent_id="bob", role="builder", model="m", enabled=True),
                        AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
                    ),
                    created_at=NOW,
                ),
                "snap",
            )
        )
        return squad

    @staticmethod
    def _builder_cycle():
        return Cycle(
            cycle_id="cyc_001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={
                "plan_tasks": False,
                # truthy build_tasks + a builder role → BUILDER_ASSEMBLY_TASK_STEPS
                # (development.develop → builder.assemble → qa.test).
                "build_tasks": ["builder.assemble"],
                "build_profile": "fullstack_fastapi_react",
            },
            # build-only run: seed the approved plan so it isn't rejected before
            # dispatch (the deliverable-completeness gate is what we're testing).
            execution_overrides={"plan_artifact_refs": ["art_plan_001"]},
        )

    @staticmethod
    def _vault():
        ref_plan = _make_artifact_ref("art_plan_001", "implementation_plan.md", "document")
        vault = AsyncMock()
        vault.store = AsyncMock(side_effect=lambda ref, content: ref)
        vault.retrieve = AsyncMock(return_value=(ref_plan, b"Plan content"))
        return vault

    @staticmethod
    def _registry(cycle, run):
        registry = AsyncMock()
        registry.get_cycle = AsyncMock(return_value=cycle)
        registry.get_run = AsyncMock(return_value=run)
        registry.update_run_status = AsyncMock()
        registry.append_artifact_refs = AsyncMock()
        registry.get_latest_checkpoint = AsyncMock(return_value=None)
        registry.save_checkpoint = AsyncMock(return_value=None)
        return registry

    async def test_builder_run_missing_required_file_fails(self, reply_router):
        """fullstack_fastapi_react requires Dockerfile + qa_handoff.md. The build
        emits only qa_handoff.md (no Dockerfile) → the run must transition FAILED,
        not COMPLETED. This is the exact #276 green-on-broken-deliverable bug."""
        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
        from squadops.tasks.models import TaskResult

        cycle = self._builder_cycle()
        run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )
        registry = self._registry(cycle, run)
        vault = self._vault()

        # Builder emits qa_handoff.md but never a Dockerfile.
        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"],
            status="SUCCEEDED",
            outputs={
                "summary": "done",
                "role": env["metadata"].get("role"),
                "artifacts": [
                    {
                        "name": "qa_handoff.md",
                        "content": "## How to Run\n## How to Test\n## Expected Behavior\n",
                        "type": "document",
                        "media_type": "text/markdown",
                    }
                ],
            },
        )

        ex = DispatchedFlowExecutor(
            cycle_registry=registry,
            artifact_vault=vault,
            queue=reply_router.bind(AsyncMock()),
            squad_profile=self._builder_squad(),
            reply_router=reply_router,
        )

        await ex.execute_run("cyc_001", "run_001")

        calls = [c.args for c in registry.update_run_status.call_args_list]
        assert ("run_001", RunStatus.FAILED) in calls
        assert ("run_001", RunStatus.COMPLETED) not in calls

    async def test_builder_run_with_all_required_files_completes(self, reply_router):
        """The gate must not over-fire: when the build emits both Dockerfile and
        qa_handoff.md, the run completes — proving the FAILED case above is the
        missing file, not merely 'a builder run'."""
        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
        from squadops.tasks.models import TaskResult

        cycle = self._builder_cycle()
        run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )
        registry = self._registry(cycle, run)
        vault = self._vault()

        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"],
            status="SUCCEEDED",
            outputs={
                "summary": "done",
                "role": env["metadata"].get("role"),
                "artifacts": [
                    {
                        "name": "Dockerfile",
                        "content": "FROM python:3.12\n",
                        "type": "source",
                        "media_type": "text/plain",
                    },
                    {
                        "name": "qa_handoff.md",
                        "content": "## How to Run\n## How to Test\n## Expected Behavior\n",
                        "type": "document",
                        "media_type": "text/markdown",
                    },
                ],
            },
        )

        ex = DispatchedFlowExecutor(
            cycle_registry=registry,
            artifact_vault=vault,
            queue=reply_router.bind(AsyncMock()),
            squad_profile=self._builder_squad(),
            reply_router=reply_router,
        )

        await ex.execute_run("cyc_001", "run_001")

        calls = [c.args for c in registry.update_run_status.call_args_list]
        assert ("run_001", RunStatus.COMPLETED) in calls
        assert ("run_001", RunStatus.FAILED) not in calls


class TestPlanOnlyCyclesUnaffected:
    """Regression: plan-only cycles still work as before."""

    async def test_plan_only_cycle_no_build_validation(self, reply_router):
        """Plan-only cycle doesn't trigger build-only validation."""
        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full",
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

        vault = AsyncMock()
        vault.store = AsyncMock(side_effect=lambda ref, content: ref)

        squad = AsyncMock()
        from squadops.cycles.models import AgentProfileEntry, SquadProfile

        squad.resolve_snapshot = AsyncMock(
            return_value=(
                SquadProfile(
                    profile_id="full",
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

        from squadops.tasks.models import TaskResult

        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"],
            status="SUCCEEDED",
            outputs={"summary": "done", "role": env["metadata"].get("role")},
        )

        ex = DispatchedFlowExecutor(
            cycle_registry=registry,
            artifact_vault=vault,
            queue=reply_router.bind(AsyncMock()),
            squad_profile=squad,
            reply_router=reply_router,
        )

        await ex.execute_run("cyc_001", "run_001")

        # Should complete successfully (not fail with build-only error)
        calls = [c.args for c in registry.update_run_status.call_args_list]
        assert ("run_001", RunStatus.COMPLETED) in calls


class TestSeededScaffoldReachesVerification:
    """#443: provenance-less seeded scaffold documents must reach qa.test and
    builder.assemble — attempt 3.5 ran frontend_build/tests_pass against a
    workspace missing package.json and the backend modules and failed both."""

    def _scaffold_and_source(self):
        ref_scaffold = _make_artifact_ref(
            "art_001",
            "frontend/package.json",
            "document",  # uploaded seed: no producing_task_type, type document
        )
        ref_src = _make_artifact_ref(
            "art_002",
            "backend/routes.py",
            "source",
            producing_task_type="development.develop",
        )
        return ref_scaffold, ref_src

    async def test_qa_test_receives_seeded_scaffold(self, executor):
        ref_scaffold, ref_src = self._scaffold_and_source()
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[
                (ref_scaffold, b'{"name": "app"}'),
                (ref_src, b"routes"),
            ]
        )
        contents = await executor._resolve_artifact_contents(
            "qa.test", [("art_001", ref_scaffold), ("art_002", ref_src)]
        )
        assert "frontend/package.json" in contents
        assert "backend/routes.py" in contents

    async def test_builder_assemble_receives_seeded_scaffold(self, executor):
        ref_scaffold, ref_src = self._scaffold_and_source()
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[
                (ref_scaffold, b'{"name": "app"}'),
                (ref_src, b"routes"),
            ]
        )
        contents = await executor._resolve_artifact_contents(
            "builder.assemble", [("art_001", ref_scaffold), ("art_002", ref_src)]
        )
        assert "frontend/package.json" in contents

    async def test_framing_documents_with_provenance_stay_excluded_from_qa(self, executor):
        """The fallback is for provenance-less seeds only — framing docs carry
        producing_task_type and must not flood the qa workspace."""
        ref_framing = _make_artifact_ref(
            "art_001",
            "context_research.md",
            "document",
            producing_task_type="data.research_context",
        )
        executor._artifact_vault.retrieve = AsyncMock()
        contents = await executor._resolve_artifact_contents("qa.test", [("art_001", ref_framing)])
        assert contents == {}


class TestRepairCandidateExclusion:
    """pf-31 Fix E: fresh dispatches see the ACCEPTED state only.

    A rejected repair candidate's emission (stored for RC3 accumulation)
    must not supersede the accepted version in a later task's workspace —
    the pf-31 endpoint_defined final-verification regression: repair-04's
    rejected {run_id} routes.py was the last-stored version, so the final
    qa attempt evaluated (and failed) the discarded candidate."""

    async def test_fresh_dispatch_excludes_rejected_candidate(self, executor):
        accepted = _make_artifact_ref(
            "art_ok",
            "backend/routes.py",
            "source",
            producing_task_type="development.develop",
        )
        candidate = _make_artifact_ref(
            "art_candidate",
            "backend/routes.py",
            "source",
            producing_task_type="development.correction_repair",
        )
        stored = [("art_ok", accepted), ("art_candidate", candidate)]
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[(accepted, b"ACCEPTED = True\n")]
        )

        contents = await executor._resolve_artifact_contents(
            "qa.test", stored, include_repair_candidates=False
        )

        # Last-wins would have given the candidate; the accepted version survives.
        assert contents["backend/routes.py"] == "ACCEPTED = True\n"

    async def test_correction_path_keeps_candidates_by_default(self, executor):
        """RC3: the correction loop's own re-resolution must keep candidate
        accumulation — analyze needs each attempt's content."""
        accepted = _make_artifact_ref(
            "art_ok",
            "backend/routes.py",
            "source",
            producing_task_type="development.develop",
        )
        candidate = _make_artifact_ref(
            "art_candidate",
            "backend/routes.py",
            "source",
            producing_task_type="development.correction_repair",
        )
        stored = [("art_ok", accepted), ("art_candidate", candidate)]
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=[(accepted, b"ACCEPTED = True\n"), (candidate, b"CANDIDATE = True\n")]
        )

        contents = await executor._resolve_artifact_contents("qa.test", stored)

        assert contents["backend/routes.py"] == "CANDIDATE = True\n"


class TestRepairTaskTypesDerivation:
    def test_repair_task_types_derived_from_dispatch_tables(self):
        """The provenance filter and the dispatch tables must never drift: a
        new repair step type added to the tables is automatically a candidate
        type (#559 — no re-typed literals)."""
        from squadops.cycles.task_plan import (
            _REPAIR_STEPS_BY_FAILED_TASK_TYPE,
            REPAIR_TASK_TYPES,
        )

        table_types = {
            task_type
            for steps in _REPAIR_STEPS_BY_FAILED_TASK_TYPE.values()
            for task_type, _ in steps
        }
        assert table_types <= REPAIR_TASK_TYPES
        assert "development.develop" not in REPAIR_TASK_TYPES


# ---------------------------------------------------------------------------
# #657: planning-chain context threading (RC-22 pre-resolution)
# ---------------------------------------------------------------------------


class TestPlanningContextThreading:
    """The brief author and plan-task proposers receive upstream documents.

    Bug caught: the executor drops planning artifact content when chaining
    ``prior_outputs`` (role-keyed summaries only), so the qa proposer is
    instructed to gap-catch against Development's proposal while rendering
    "(brief not yet provided)" and PRD-prefix stubs — the #657 blindness that
    produced the fill-slot-claiming qa tasks across FAY windows 1–2.
    """

    @staticmethod
    def _envelope(task_type: str, agent_id: str = "eve"):
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="t1",
            agent_id=agent_id,
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type=task_type,
            correlation_id="c",
            causation_id="ca",
            trace_id="tr",
            span_id="s",
        )

    @staticmethod
    def _planning_stored():
        refs = [
            _make_artifact_ref(
                "art_ctx",
                "context_research.md",
                producing_task_type="data.research_context",
            ),
            _make_artifact_ref(
                "art_objective",
                "objective_frame.md",
                producing_task_type="strategy.frame_objective",
            ),
            _make_artifact_ref(
                "art_design",
                "technical_design.md",
                producing_task_type="development.design_plan",
            ),
            _make_artifact_ref(
                "art_strategy",
                "test_strategy.md",
                producing_task_type="qa.define_test_strategy",
            ),
            _make_artifact_ref(
                "art_brief",
                "plan_authoring_brief.yaml",
                producing_task_type="governance.prepare_plan_authoring_brief",
            ),
            _make_artifact_ref(
                "art_dev_prop",
                "proposed_plan_tasks.yaml",
                producing_task_type="development.propose_plan_tasks",
            ),
        ]
        return [(r.artifact_id, r) for r in refs]

    @staticmethod
    def _wire_vault(executor, stored):
        by_id = {art_id: (ref, f"body of {ref.filename}".encode()) for art_id, ref in stored}

        async def retrieve(art_id):
            return by_id[art_id]

        executor._artifact_vault.retrieve = AsyncMock(side_effect=retrieve)

    async def test_qa_proposer_receives_upstream_documents(self, executor):
        """Brief + design + test strategy + dev proposal reach the qa proposer;
        out-of-map documents (context research) stay excluded."""
        stored = self._planning_stored()
        self._wire_vault(executor, stored)

        enriched = await executor._enrich_envelope(
            self._envelope("qa.propose_plan_tasks"),
            {"dev": {"summary": "[dev] designed"}},
            [],
            stored,
        )

        contents = enriched.inputs["prior_outputs"]["artifact_contents"]
        assert set(contents) == {
            "plan_authoring_brief.yaml",
            "technical_design.md",
            "test_strategy.md",
            "proposed_plan_tasks.yaml",
        }
        assert contents["plan_authoring_brief.yaml"] == "body of plan_authoring_brief.yaml"
        assert contents["proposed_plan_tasks.yaml"] == "body of proposed_plan_tasks.yaml"
        # role-keyed chain context is preserved alongside
        assert enriched.inputs["prior_outputs"]["dev"] == {"summary": "[dev] designed"}

    async def test_loop_prior_outputs_dict_not_mutated(self, executor):
        """The threaded contents live on an envelope-local copy — the loop-level
        dict is checkpointed per task (RC-4) and must stay lean."""
        stored = self._planning_stored()
        self._wire_vault(executor, stored)
        loop_dict = {"dev": {"summary": "[dev] designed"}}

        await executor._enrich_envelope(
            self._envelope("qa.propose_plan_tasks"),
            loop_dict,
            [],
            stored,
        )

        assert "artifact_contents" not in loop_dict

    async def test_brief_author_receives_all_four_framing_documents(self, executor):
        """The brief distills must_cover_requirements from the framing docs —
        authored blind, it pins requirements no one researched."""
        stored = self._planning_stored()
        self._wire_vault(executor, stored)

        enriched = await executor._enrich_envelope(
            self._envelope("governance.prepare_plan_authoring_brief", agent_id="max"),
            {},
            [],
            stored,
        )

        contents = enriched.inputs["prior_outputs"]["artifact_contents"]
        assert set(contents) == {
            "context_research.md",
            "objective_frame.md",
            "technical_design.md",
            "test_strategy.md",
        }
        assert "proposed_plan_tasks.yaml" not in contents
        assert "plan_authoring_brief.yaml" not in contents

    async def test_merger_gets_no_artifact_contents(self, executor):
        """The merger consumes brief_outcome/proposal_outcome output keys; by
        merge time both proposals collide on the proposed_plan_tasks.yaml
        filename, so threading there would silently drop one proposal."""
        stored = self._planning_stored()
        self._wire_vault(executor, stored)

        enriched = await executor._enrich_envelope(
            self._envelope("governance.merge_plan", agent_id="max"),
            {"lead": {"brief_outcome": {"yaml_content": "brief_id: b1"}}},
            [],
            stored,
        )

        assert "artifact_contents" not in enriched.inputs["prior_outputs"]

    async def test_build_task_prior_outputs_untouched(self, executor):
        """D3's top-level artifact_contents channel for build tasks is a
        different transport — the planning branch must not leak into it."""
        stored = self._planning_stored()
        self._wire_vault(executor, stored)

        enriched = await executor._enrich_envelope(
            self._envelope("development.develop", agent_id="neo"),
            {"strat": {"summary": "[strat] framed"}},
            [],
            stored,
        )

        assert "artifact_contents" not in enriched.inputs["prior_outputs"]

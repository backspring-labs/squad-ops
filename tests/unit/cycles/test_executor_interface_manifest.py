"""Tests for executor interface-manifest materialization (SIP-0099 phase 99.3).

The executor loads the framing-emitted interface manifest, expands it into a walking
skeleton, and seeds those files so ``develop`` fills fixed slots. Mirrors the
``_load_plan_for_run`` test pattern in ``test_executor_plan_loading.py``. Data-driven:
no manifest artifact -> nothing seeded -> byte-identical to today.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

_GROUP_RUN_MANIFEST = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
).read_text(encoding="utf-8")


@dataclass
class _FakeManifestRef:
    artifact_id: str = "art_iface"
    filename: str = "interface_manifest.yaml"
    artifact_type: str = "interface_manifest"
    metadata: dict = field(default_factory=dict)


@dataclass
class _FakePlanRef:
    artifact_id: str = "art_plan"
    filename: str = "implementation_plan.yaml"
    artifact_type: str = "control_implementation_plan"
    metadata: dict = field(default_factory=dict)


def _make_executor() -> DispatchedFlowExecutor:
    executor = DispatchedFlowExecutor.__new__(DispatchedFlowExecutor)
    executor._artifact_vault = MagicMock()
    executor._artifact_vault.retrieve = AsyncMock()
    executor._artifact_vault.store = AsyncMock()
    return executor


def _make_cycle(**overrides) -> MagicMock:
    cycle = MagicMock()
    cycle.execution_overrides = {}
    cycle.project_id = "group_run"
    cycle.cycle_id = "cyc_test"
    for k, v in overrides.items():
        setattr(cycle, k, v)
    return cycle


def _make_run() -> MagicMock:
    run = MagicMock()
    run.run_id = "run_abcdef123456"
    return run


class TestLoadInterfaceManifestForRun:
    async def test_manifest_found_in_plan_refs(self):
        executor = _make_executor()
        executor._artifact_vault.retrieve.return_value = (
            _FakeManifestRef(),
            _GROUP_RUN_MANIFEST.encode(),
        )
        cycle = _make_cycle(execution_overrides={"plan_artifact_refs": ["art_iface"]})

        manifest = await executor._load_interface_manifest_for_run(cycle, _make_run())

        assert manifest is not None
        assert manifest.stack == "fullstack_fastapi_react"
        assert {e.name for e in manifest.entities} == {"Participant", "RunEvent"}

    async def test_no_plan_refs_returns_none(self):
        executor = _make_executor()
        cycle = _make_cycle(execution_overrides={})
        assert await executor._load_interface_manifest_for_run(cycle, _make_run()) is None

    async def test_non_manifest_ref_skipped_returns_none(self):
        # the plan artifact is present but not the interface manifest -> None (data-driven)
        executor = _make_executor()
        executor._artifact_vault.retrieve.return_value = (_FakePlanRef(), b"version: 1\ntasks: []")
        cycle = _make_cycle(execution_overrides={"plan_artifact_refs": ["art_plan"]})
        assert await executor._load_interface_manifest_for_run(cycle, _make_run()) is None

    async def test_malformed_manifest_returns_none(self):
        # graceful: an unparseable manifest leaves the run on today's non-scaffolded path
        executor = _make_executor()
        executor._artifact_vault.retrieve.return_value = (
            _FakeManifestRef(),
            b"::: not yaml :::\nkind: nope",
        )
        cycle = _make_cycle(execution_overrides={"plan_artifact_refs": ["art_iface"]})
        assert await executor._load_interface_manifest_for_run(cycle, _make_run()) is None

    async def test_framing_run_never_loads_a_seeded_manifest(self):
        # #496: an operator-seeded manifest is in plan_artifact_refs from cycle
        # creation, visible to every workload — but the skeleton is the
        # implementation substrate. Bug caught: a framing run expanding skeleton
        # files into its own artifact list (pre-#496 unreachable, so untested).
        executor = _make_executor()
        executor._artifact_vault.retrieve.return_value = (
            _FakeManifestRef(),
            _GROUP_RUN_MANIFEST.encode(),
        )
        cycle = _make_cycle(execution_overrides={"plan_artifact_refs": ["art_iface"]})
        run = _make_run()
        run.workload_type = "framing"

        assert await executor._load_interface_manifest_for_run(cycle, run) is None
        executor._artifact_vault.retrieve.assert_not_awaited()


class TestSeedSkeletonArtifacts:
    async def test_seeds_full_skeleton_set_as_source_artifacts(self):
        from squadops.capabilities.handlers.build_profiles import get_profile
        from squadops.capabilities.scaffold import InterfaceManifest

        manifest = InterfaceManifest.from_yaml(_GROUP_RUN_MANIFEST)
        expected_files = get_profile("fullstack_fastapi_react").expand(manifest)

        executor = _make_executor()
        ids = await executor._seed_skeleton_artifacts(manifest, _make_cycle(), "run_x")

        # one seeded artifact per expanded skeleton file, and the returned ids are exactly
        # the artifact_ids of the refs handed to the vault (so _seed_prior_artifacts can
        # retrieve them into the workspace)
        assert len(ids) == len(expected_files)
        assert executor._artifact_vault.store.await_count == len(expected_files)
        stored_refs = [call.args[0] for call in executor._artifact_vault.store.await_args_list]
        assert [r.artifact_id for r in stored_refs] == ids
        # every skeleton file is a source artifact with a workspace-relative name
        assert {r.artifact_type for r in stored_refs} == {"source"}
        assert {r.filename for r in stored_refs} == {f["name"] for f in expected_files}
        assert all(not Path(r.filename).is_absolute() for r in stored_refs)

    async def test_unscaffoldable_stack_seeds_nothing(self):
        from squadops.capabilities.scaffold import InterfaceManifest

        manifest = InterfaceManifest.from_dict(
            {"version": 1, "kind": "interface_manifest", "project_id": "x", "stack": "django_htmx"}
        )
        executor = _make_executor()

        ids = await executor._seed_skeleton_artifacts(manifest, _make_cycle(), "run_x")

        assert ids == []
        executor._artifact_vault.store.assert_not_awaited()

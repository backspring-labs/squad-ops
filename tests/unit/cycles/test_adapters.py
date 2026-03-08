"""
Tests for SIP-0064 adapter implementations.
"""

import dataclasses
from datetime import UTC, datetime

import pytest
import yaml

from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    CycleError,
    CycleNotFoundError,
    CycleStatus,
    Gate,
    GateAlreadyDecidedError,
    GateDecision,
    IllegalStateTransitionError,
    Project,
    ProjectNotFoundError,
    Run,
    RunNotFoundError,
    RunStatus,
    RunTerminalError,
    SquadProfile,
    TaskFlowPolicy,
    ValidationError,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


# =============================================================================
# ConfigProjectRegistry tests
# =============================================================================


class TestConfigProjectRegistry:
    @pytest.fixture
    def yaml_dir(self, tmp_path):
        yaml_path = tmp_path / "projects.yaml"
        yaml_path.write_text(
            yaml.dump(
                {
                    "projects": [
                        {
                            "project_id": "hello_squad",
                            "name": "Hello Squad",
                            "description": "Test project",
                            "tags": ["example"],
                        },
                        {
                            "project_id": "run_crysis",
                            "name": "Run Crysis",
                            "description": "Benchmark",
                            "tags": ["benchmark"],
                        },
                    ]
                }
            )
        )
        return yaml_path

    @pytest.fixture
    def registry(self, yaml_dir):
        from adapters.cycles.config_project_registry import ConfigProjectRegistry

        return ConfigProjectRegistry(yaml_path=yaml_dir)

    async def test_list_projects(self, registry):
        projects = await registry.list_projects()
        assert len(projects) == 2
        assert all(isinstance(p, Project) for p in projects)

    async def test_get_project(self, registry):
        p = await registry.get_project("hello_squad")
        assert p.project_id == "hello_squad"
        assert p.name == "Hello Squad"
        assert p.tags == ("example",)

    async def test_get_project_not_found(self, registry):
        with pytest.raises(ProjectNotFoundError):
            await registry.get_project("unknown")

    async def test_empty_yaml(self, tmp_path):
        from adapters.cycles.config_project_registry import ConfigProjectRegistry

        yaml_path = tmp_path / "empty.yaml"
        yaml_path.write_text("")
        reg = ConfigProjectRegistry(yaml_path=yaml_path)
        projects = await reg.list_projects()
        assert projects == []


# =============================================================================
# MemoryCycleRegistry tests
# =============================================================================


class TestMemoryCycleRegistry:
    @pytest.fixture
    def registry(self):
        from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry

        return MemoryCycleRegistry()

    @pytest.fixture
    def cycle(self):
        return Cycle(
            cycle_id="cyc_001",
            project_id="hello_squad",
            created_at=NOW,
            created_by="system",
            prd_ref=None,
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(
                mode="fan_out_soft_gates",
                gates=(
                    Gate(
                        name="qa_review",
                        description="QA gate",
                        after_task_types=("code_generate",),
                    ),
                ),
            ),
            build_strategy="fresh",
        )

    @pytest.fixture
    def run(self):
        return Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )

    # --- Cycle tests ---

    async def test_create_and_get_cycle(self, registry, cycle):
        created = await registry.create_cycle(cycle)
        assert created.cycle_id == "cyc_001"
        fetched = await registry.get_cycle("cyc_001")
        assert fetched.cycle_id == "cyc_001"
        assert fetched.project_id == "hello_squad"

    async def test_get_cycle_not_found(self, registry):
        with pytest.raises(CycleNotFoundError):
            await registry.get_cycle("nonexistent")

    async def test_list_cycles_by_project(self, registry, cycle):
        await registry.create_cycle(cycle)
        cycles = await registry.list_cycles("hello_squad")
        assert len(cycles) == 1
        assert cycles[0].cycle_id == "cyc_001"

    async def test_list_cycles_empty_project(self, registry):
        cycles = await registry.list_cycles("unknown")
        assert cycles == []

    async def test_list_cycles_filtered_by_status(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        # With queued run, derived status is ACTIVE
        active = await registry.list_cycles("hello_squad", status=CycleStatus.ACTIVE)
        assert len(active) == 1
        completed = await registry.list_cycles("hello_squad", status=CycleStatus.COMPLETED)
        assert len(completed) == 0

    async def test_cancel_cycle(self, registry, cycle):
        await registry.create_cycle(cycle)
        await registry.cancel_cycle("cyc_001")
        # Cancelling again is idempotent
        await registry.cancel_cycle("cyc_001")

    async def test_cancel_cycle_not_found(self, registry):
        with pytest.raises(CycleNotFoundError):
            await registry.cancel_cycle("nonexistent")

    # --- Run tests ---

    async def test_create_and_get_run(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        created = await registry.create_run(run)
        assert created.run_id == "run_001"
        fetched = await registry.get_run("run_001")
        assert fetched.run_id == "run_001"
        assert fetched.status == "queued"

    async def test_get_run_not_found(self, registry):
        with pytest.raises(RunNotFoundError):
            await registry.get_run("nonexistent")

    async def test_list_runs(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        runs = await registry.list_runs("cyc_001")
        assert len(runs) == 1

    async def test_update_run_status_legal(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        updated = await registry.update_run_status("run_001", RunStatus.RUNNING)
        assert updated.status == "running"

    async def test_update_run_status_illegal(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        with pytest.raises(IllegalStateTransitionError):
            await registry.update_run_status("run_001", RunStatus.COMPLETED)

    async def test_update_run_not_found(self, registry):
        with pytest.raises(RunNotFoundError):
            await registry.update_run_status("nonexistent", RunStatus.RUNNING)

    async def test_cancel_run_from_queued(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.cancel_run("run_001")
        fetched = await registry.get_run("run_001")
        assert fetched.status == "cancelled"

    async def test_cancel_run_from_running(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.update_run_status("run_001", RunStatus.RUNNING)
        await registry.cancel_run("run_001")
        fetched = await registry.get_run("run_001")
        assert fetched.status == "cancelled"

    async def test_cancel_run_from_paused(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.update_run_status("run_001", RunStatus.RUNNING)
        await registry.update_run_status("run_001", RunStatus.PAUSED)
        await registry.cancel_run("run_001")
        fetched = await registry.get_run("run_001")
        assert fetched.status == "cancelled"

    async def test_create_run_on_cancelled_cycle_rejected(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.cancel_cycle("cyc_001")
        with pytest.raises(IllegalStateTransitionError, match="cancelled cycle"):
            await registry.create_run(run)

    # --- append_artifact_refs tests (SIP-0066) ---

    async def test_append_artifact_refs(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        updated = await registry.append_artifact_refs("run_001", ("art_001", "art_002"))
        assert "art_001" in updated.artifact_refs
        assert "art_002" in updated.artifact_refs

    async def test_append_artifact_refs_deduplicates(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.append_artifact_refs("run_001", ("art_001",))
        updated = await registry.append_artifact_refs("run_001", ("art_001", "art_002"))
        assert updated.artifact_refs.count("art_001") == 1
        assert "art_002" in updated.artifact_refs

    async def test_append_artifact_refs_not_found(self, registry):
        with pytest.raises(RunNotFoundError):
            await registry.append_artifact_refs("nonexistent", ("art_001",))

    async def test_append_artifact_refs_returns_updated_run(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        updated = await registry.append_artifact_refs("run_001", ("art_x",))
        assert isinstance(updated, Run)
        assert updated.run_id == "run_001"

    # --- Gate decision tests (T11) ---

    async def test_record_gate_decision(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.update_run_status("run_001", RunStatus.RUNNING)
        await registry.update_run_status("run_001", RunStatus.PAUSED)

        decision = GateDecision(
            gate_name="qa_review",
            decision="approved",
            decided_by="operator",
            decided_at=NOW,
        )
        updated = await registry.record_gate_decision("run_001", decision)
        assert len(updated.gate_decisions) == 1
        assert updated.gate_decisions[0].decision == "approved"

    async def test_gate_decision_idempotent(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.update_run_status("run_001", RunStatus.RUNNING)
        await registry.update_run_status("run_001", RunStatus.PAUSED)

        decision = GateDecision(
            gate_name="qa_review",
            decision="approved",
            decided_by="operator",
            decided_at=NOW,
        )
        await registry.record_gate_decision("run_001", decision)
        # Same decision again — idempotent
        updated = await registry.record_gate_decision("run_001", decision)
        assert len(updated.gate_decisions) == 1

    async def test_gate_decision_conflicting(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.update_run_status("run_001", RunStatus.RUNNING)
        await registry.update_run_status("run_001", RunStatus.PAUSED)

        approved = GateDecision(
            gate_name="qa_review",
            decision="approved",
            decided_by="op",
            decided_at=NOW,
        )
        rejected = GateDecision(
            gate_name="qa_review",
            decision="rejected",
            decided_by="op",
            decided_at=NOW,
        )
        await registry.record_gate_decision("run_001", approved)
        with pytest.raises(GateAlreadyDecidedError):
            await registry.record_gate_decision("run_001", rejected)

    @pytest.mark.parametrize("terminal_status", [RunStatus.FAILED, RunStatus.CANCELLED])
    async def test_gate_decision_gate_rejected_run(self, registry, cycle, run, terminal_status):
        """GATE_REJECTED_STATES (failed/cancelled) reject gate decisions."""
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.update_run_status("run_001", RunStatus.RUNNING)
        await registry.update_run_status("run_001", terminal_status)

        decision = GateDecision(
            gate_name="qa_review",
            decision="approved",
            decided_by="op",
            decided_at=NOW,
        )
        with pytest.raises(RunTerminalError):
            await registry.record_gate_decision("run_001", decision)

    async def test_gate_decision_completed_run_accepted(self, registry, cycle, run):
        """SIP-0083 D15: COMPLETED runs accept gate decisions."""
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.update_run_status("run_001", RunStatus.RUNNING)
        await registry.update_run_status("run_001", RunStatus.COMPLETED)

        decision = GateDecision(
            gate_name="qa_review",
            decision="approved",
            decided_by="op",
            decided_at=NOW,
        )
        updated = await registry.record_gate_decision("run_001", decision)
        assert len(updated.gate_decisions) == 1

    async def test_gate_decision_unknown_gate(self, registry, cycle, run):
        await registry.create_cycle(cycle)
        await registry.create_run(run)
        await registry.update_run_status("run_001", RunStatus.RUNNING)

        decision = GateDecision(
            gate_name="nonexistent_gate",
            decision="approved",
            decided_by="op",
            decided_at=NOW,
        )
        with pytest.raises(ValidationError):
            await registry.record_gate_decision("run_001", decision)


# =============================================================================
# ConfigSquadProfile tests
# =============================================================================


class TestConfigSquadProfile:
    @pytest.fixture
    def yaml_dir(self, tmp_path):
        yaml_path = tmp_path / "squad-profiles.yaml"
        yaml_path.write_text(
            yaml.dump(
                {
                    "profiles": [
                        {
                            "profile_id": "full-squad",
                            "name": "Full Squad",
                            "description": "All agents",
                            "version": 1,
                            "agents": [
                                {
                                    "agent_id": "max",
                                    "role": "lead",
                                    "model": "gpt-4",
                                    "enabled": True,
                                },
                            ],
                        },
                        {
                            "profile_id": "minimal",
                            "name": "Minimal",
                            "description": "One agent",
                            "version": 1,
                            "agents": [
                                {
                                    "agent_id": "neo",
                                    "role": "dev",
                                    "model": "gpt-4",
                                    "enabled": True,
                                },
                            ],
                        },
                    ],
                    "active_profile": "full-squad",
                }
            )
        )
        return yaml_path

    @pytest.fixture
    def provider(self, yaml_dir):
        from adapters.cycles.config_squad_profile import ConfigSquadProfile

        return ConfigSquadProfile(yaml_path=yaml_dir)

    async def test_list_profiles(self, provider):
        profiles = await provider.list_profiles()
        assert len(profiles) == 2
        assert all(isinstance(p, SquadProfile) for p in profiles)

    async def test_get_profile(self, provider):
        p = await provider.get_profile("full-squad")
        assert p.profile_id == "full-squad"
        assert len(p.agents) == 1

    async def test_get_profile_not_found(self, provider):
        with pytest.raises(CycleError):
            await provider.get_profile("unknown")

    async def test_get_active_profile(self, provider):
        active = await provider.get_active_profile()
        assert active.profile_id == "full-squad"

    async def test_set_active_profile(self, provider):
        await provider.set_active_profile("minimal")
        active = await provider.get_active_profile()
        assert active.profile_id == "minimal"

    async def test_set_active_profile_not_found(self, provider):
        with pytest.raises(CycleError):
            await provider.set_active_profile("unknown")

    async def test_resolve_snapshot(self, provider):
        profile, snapshot_hash = await provider.resolve_snapshot("full-squad")
        assert profile.profile_id == "full-squad"
        assert isinstance(snapshot_hash, str)
        assert len(snapshot_hash) == 64  # SHA-256 hex

    async def test_resolve_snapshot_deterministic(self, provider):
        _, h1 = await provider.resolve_snapshot("full-squad")
        _, h2 = await provider.resolve_snapshot("full-squad")
        assert h1 == h2


# =============================================================================
# FilesystemArtifactVault tests
# =============================================================================


class TestFilesystemArtifactVault:
    @pytest.fixture
    def vault(self, tmp_path):
        from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault

        return FilesystemArtifactVault(base_dir=tmp_path / "artifacts")

    @pytest.fixture
    def base_dir(self, vault):
        return vault._base_dir

    @pytest.fixture
    def artifact_ref(self):
        return ArtifactRef(
            artifact_id="art_001",
            project_id="hello_squad",
            artifact_type="prd",
            filename="prd-v1.md",
            content_hash="placeholder",
            size_bytes=0,
            media_type="text/markdown",
            created_at=NOW,
            cycle_id="cyc_abc",
            run_id="run_xyz",
        )

    @pytest.fixture
    def unattached_ref(self):
        return ArtifactRef(
            artifact_id="art_bare",
            project_id="hello_squad",
            artifact_type="prd",
            filename="prd-v0.md",
            content_hash="placeholder",
            size_bytes=0,
            media_type="text/markdown",
            created_at=NOW,
        )

    async def test_store_returns_ref_with_vault_uri(self, vault, artifact_ref):
        content = b"# PRD v1\nThis is a test."
        stored = await vault.store(artifact_ref, content)
        assert stored.vault_uri is not None
        assert stored.size_bytes == len(content)
        assert len(stored.content_hash) == 64

    async def test_retrieve_roundtrip(self, vault, artifact_ref):
        content = b"Hello World"
        await vault.store(artifact_ref, content)
        ref, data = await vault.retrieve("art_001")
        assert data == content
        assert ref.artifact_id == "art_001"

    async def test_retrieve_not_found(self, vault):
        from squadops.cycles.models import ArtifactNotFoundError

        with pytest.raises(ArtifactNotFoundError):
            await vault.retrieve("nonexistent")

    async def test_get_metadata(self, vault, artifact_ref):
        await vault.store(artifact_ref, b"data")
        meta = await vault.get_metadata("art_001")
        assert meta.artifact_id == "art_001"
        assert meta.vault_uri is not None

    async def test_list_artifacts_by_project(self, vault, artifact_ref):
        await vault.store(artifact_ref, b"data")
        results = await vault.list_artifacts(project_id="hello_squad")
        assert len(results) == 1
        assert results[0].artifact_id == "art_001"

    async def test_list_artifacts_by_type(self, vault, artifact_ref):
        await vault.store(artifact_ref, b"data")
        results = await vault.list_artifacts(artifact_type="prd")
        assert len(results) == 1
        results_empty = await vault.list_artifacts(artifact_type="code")
        assert len(results_empty) == 0

    async def test_set_and_get_baseline(self, vault, artifact_ref):
        await vault.store(artifact_ref, b"data")
        await vault.set_baseline("hello_squad", "prd", "art_001")
        baseline = await vault.get_baseline("hello_squad", "prd")
        assert baseline is not None
        assert baseline.artifact_id == "art_001"

    async def test_get_baseline_none(self, vault):
        baseline = await vault.get_baseline("hello_squad", "prd")
        assert baseline is None

    async def test_list_baselines(self, vault, artifact_ref):
        await vault.store(artifact_ref, b"data")
        await vault.set_baseline("hello_squad", "prd", "art_001")
        baselines = await vault.list_baselines("hello_squad")
        assert "prd" in baselines
        assert baselines["prd"].artifact_id == "art_001"

    async def test_set_baseline_not_found(self, vault):
        from squadops.cycles.models import ArtifactNotFoundError

        with pytest.raises(ArtifactNotFoundError):
            await vault.set_baseline("hello_squad", "prd", "nonexistent")

    # --- Hierarchical layout tests ---

    async def test_store_creates_hierarchical_directory(self, vault, artifact_ref, base_dir):
        await vault.store(artifact_ref, b"code")
        expected = base_dir / "hello_squad" / "cyc_abc" / "run_xyz" / "art_001"
        assert expected.is_dir()
        assert (expected / "metadata.json").exists()
        assert (expected / "prd-v1.md").exists()

    async def test_index_updated_on_store(self, vault, artifact_ref, base_dir):
        import json

        await vault.store(artifact_ref, b"data")
        index = json.loads((base_dir / "_index.json").read_text())
        assert "art_001" in index
        assert index["art_001"] == "hello_squad/cyc_abc/run_xyz/art_001"

    async def test_retrieve_via_index(self, vault, artifact_ref):
        await vault.store(artifact_ref, b"payload")
        ref, data = await vault.retrieve("art_001")
        assert data == b"payload"
        assert ref.project_id == "hello_squad"
        assert ref.cycle_id == "cyc_abc"
        assert ref.run_id == "run_xyz"

    async def test_list_artifacts_scoped_to_run(self, vault, artifact_ref):
        await vault.store(artifact_ref, b"data")
        # Different run — should not appear
        other = dataclasses.replace(artifact_ref, artifact_id="art_002", run_id="run_other")
        await vault.store(other, b"data2")
        results = await vault.list_artifacts(
            project_id="hello_squad", cycle_id="cyc_abc", run_id="run_xyz"
        )
        assert len(results) == 1
        assert results[0].artifact_id == "art_001"

    async def test_list_artifacts_scoped_to_cycle(self, vault, artifact_ref):
        await vault.store(artifact_ref, b"data")
        other = dataclasses.replace(
            artifact_ref, artifact_id="art_002", cycle_id="cyc_other", run_id="run_other"
        )
        await vault.store(other, b"data2")
        results = await vault.list_artifacts(project_id="hello_squad", cycle_id="cyc_abc")
        assert len(results) == 1
        assert results[0].artifact_id == "art_001"

    async def test_unattached_artifact_stored_correctly(self, vault, unattached_ref, base_dir):
        await vault.store(unattached_ref, b"bare")
        expected = base_dir / "_unattached" / "art_bare"
        assert expected.is_dir()
        assert (expected / "metadata.json").exists()
        # Unattached should appear in full scan
        results = await vault.list_artifacts()
        ids = [r.artifact_id for r in results]
        assert "art_bare" in ids

    async def test_unattached_in_project_scoped_list(self, vault, unattached_ref):
        await vault.store(unattached_ref, b"bare")
        results = await vault.list_artifacts(project_id="hello_squad")
        assert len(results) == 1
        assert results[0].artifact_id == "art_bare"

    async def test_baselines_per_project(self, vault, artifact_ref, base_dir):
        import json

        await vault.store(artifact_ref, b"data")
        await vault.set_baseline("hello_squad", "prd", "art_001")
        bl_path = base_dir / "hello_squad" / ".baselines.json"
        assert bl_path.exists()
        data = json.loads(bl_path.read_text())
        assert data["prd"] == "art_001"

    async def test_index_rebuild_from_filesystem(self, vault, artifact_ref, base_dir):
        import json

        await vault.store(artifact_ref, b"data")
        # Delete the index
        (base_dir / "_index.json").unlink()
        # Rebuild by re-instantiating
        from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault

        vault2 = FilesystemArtifactVault(base_dir=base_dir)
        index = json.loads((base_dir / "_index.json").read_text())
        assert "art_001" in index
        # Retrieval still works
        ref, data = await vault2.retrieve("art_001")
        assert data == b"data"

"""
Integration tests for SIP-0064 — end-to-end flows with real adapters (no mocks).
"""

from datetime import UTC, datetime

import pytest
import yaml

from squadops.cycles.lifecycle import compute_config_hash, derive_cycle_status
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    CycleStatus,
    Gate,
    GateDecision,
    IllegalStateTransitionError,
    Run,
    RunStatus,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def project_registry(tmp_path):
    from adapters.cycles.config_project_registry import ConfigProjectRegistry

    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(
        yaml.dump(
            {
                "projects": [
                    {
                        "project_id": "hello_squad",
                        "name": "Hello Squad",
                        "description": "Test",
                        "tags": ["example"],
                    }
                ]
            }
        )
    )
    return ConfigProjectRegistry(yaml_path=yaml_path)


@pytest.fixture
def cycle_registry():
    from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry

    return MemoryCycleRegistry()


@pytest.fixture
def profile_provider(tmp_path):
    from adapters.cycles.config_squad_profile import ConfigSquadProfile

    yaml_path = tmp_path / "profiles.yaml"
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
                            }
                        ],
                    }
                ],
                "active_profile": "full-squad",
            }
        )
    )
    return ConfigSquadProfile(yaml_path=yaml_path)


@pytest.fixture
def vault(tmp_path):
    from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault

    return FilesystemArtifactVault(base_dir=tmp_path / "artifacts")


def _make_cycle(policy=None, build_strategy="fresh", **kwargs):
    return Cycle(
        cycle_id=kwargs.get("cycle_id", "cyc_001"),
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref=kwargs.get("prd_ref"),
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=policy or TaskFlowPolicy(mode="sequential"),
        build_strategy=build_strategy,
        applied_defaults=kwargs.get("applied_defaults", {"timeout": 300}),
        execution_overrides=kwargs.get("execution_overrides", {}),
        experiment_context=kwargs.get("experiment_context", {}),
    )


def _make_run(cycle_id="cyc_001", run_number=1, run_id=None, **kwargs):
    defaults = kwargs.get("applied_defaults", {"timeout": 300})
    overrides = kwargs.get("execution_overrides", {})
    return Run(
        run_id=run_id or f"run_{run_number:03d}",
        cycle_id=cycle_id,
        run_number=run_number,
        status=kwargs.get("status", "queued"),
        initiated_by="api",
        resolved_config_hash=compute_config_hash(defaults, overrides),
    )


class TestCycleLifecycleFlow:
    """Full lifecycle: create → start → complete."""

    async def test_create_start_complete(self, cycle_registry):
        cycle = _make_cycle()
        await cycle_registry.create_cycle(cycle)

        run = _make_run()
        await cycle_registry.create_run(run)

        # Start run
        await cycle_registry.update_run_status("run_001", RunStatus.RUNNING)

        # Complete run
        updated = await cycle_registry.update_run_status("run_001", RunStatus.COMPLETED)
        assert updated.status == "completed"

        # Verify cycle status
        runs = await cycle_registry.list_runs("cyc_001")
        status = derive_cycle_status(runs, cycle_cancelled=False)
        assert status == CycleStatus.COMPLETED

    async def test_create_start_fail(self, cycle_registry):
        cycle = _make_cycle()
        await cycle_registry.create_cycle(cycle)

        run = _make_run()
        await cycle_registry.create_run(run)
        await cycle_registry.update_run_status("run_001", RunStatus.RUNNING)
        await cycle_registry.update_run_status("run_001", RunStatus.FAILED)

        runs = await cycle_registry.list_runs("cyc_001")
        status = derive_cycle_status(runs, cycle_cancelled=False)
        assert status == CycleStatus.FAILED

    async def test_gate_approve_then_complete(self, cycle_registry):
        policy = TaskFlowPolicy(
            mode="fan_out_soft_gates",
            gates=(
                Gate(
                    name="qa_gate",
                    description="QA review",
                    after_task_types=("code_generate",),
                ),
            ),
        )
        cycle = _make_cycle(policy=policy)
        await cycle_registry.create_cycle(cycle)

        run = _make_run()
        await cycle_registry.create_run(run)
        await cycle_registry.update_run_status("run_001", RunStatus.RUNNING)
        await cycle_registry.update_run_status("run_001", RunStatus.PAUSED)

        decision = GateDecision(
            gate_name="qa_gate",
            decision="approved",
            decided_by="operator",
            decided_at=NOW,
        )
        updated = await cycle_registry.record_gate_decision("run_001", decision)
        assert len(updated.gate_decisions) == 1

        # Resume and complete
        await cycle_registry.update_run_status("run_001", RunStatus.RUNNING)
        await cycle_registry.update_run_status("run_001", RunStatus.COMPLETED)

        runs = await cycle_registry.list_runs("cyc_001")
        status = derive_cycle_status(runs, cycle_cancelled=False)
        assert status == CycleStatus.COMPLETED

    async def test_gate_reject_then_cancel_run(self, cycle_registry):
        """Scenario 4: pause at gate → reject → RunStatus = cancelled."""
        policy = TaskFlowPolicy(
            mode="fan_out_soft_gates",
            gates=(
                Gate(
                    name="qa_gate",
                    description="QA review",
                    after_task_types=("code_generate",),
                ),
            ),
        )
        cycle = _make_cycle(policy=policy)
        await cycle_registry.create_cycle(cycle)

        run = _make_run()
        await cycle_registry.create_run(run)
        await cycle_registry.update_run_status("run_001", RunStatus.RUNNING)
        await cycle_registry.update_run_status("run_001", RunStatus.PAUSED)

        decision = GateDecision(
            gate_name="qa_gate",
            decision="rejected",
            decided_by="operator",
            decided_at=NOW,
        )
        updated = await cycle_registry.record_gate_decision("run_001", decision)
        assert len(updated.gate_decisions) == 1
        assert updated.gate_decisions[0].decision == "rejected"

        # Rejected gate → cancel the run
        await cycle_registry.cancel_run("run_001")
        final = await cycle_registry.get_run("run_001")
        assert final.status == "cancelled"

    async def test_cancel_cycle_rejects_new_run(self, cycle_registry):
        """Scenario 5: cancel cycle → attempt new run → rejected."""
        cycle = _make_cycle()
        await cycle_registry.create_cycle(cycle)

        await cycle_registry.cancel_cycle("cyc_001")

        # Attempting to create a new run on a cancelled cycle must fail
        run = _make_run()
        with pytest.raises(IllegalStateTransitionError, match="cancelled cycle"):
            await cycle_registry.create_run(run)

        # Verify cycle status is cancelled
        runs = await cycle_registry.list_runs("cyc_001")
        status = derive_cycle_status(runs, cycle_cancelled=True)
        assert status == CycleStatus.CANCELLED

    async def test_cancel_run_then_retry(self, cycle_registry):
        cycle = _make_cycle()
        await cycle_registry.create_cycle(cycle)

        run1 = _make_run(run_number=1)
        await cycle_registry.create_run(run1)
        await cycle_registry.update_run_status("run_001", RunStatus.RUNNING)
        await cycle_registry.cancel_run("run_001")

        # Retry
        run2 = _make_run(run_number=2, run_id="run_002")
        await cycle_registry.create_run(run2)
        await cycle_registry.update_run_status("run_002", RunStatus.RUNNING)
        await cycle_registry.update_run_status("run_002", RunStatus.COMPLETED)

        runs = await cycle_registry.list_runs("cyc_001")
        status = derive_cycle_status(runs, cycle_cancelled=False)
        assert status == CycleStatus.COMPLETED


class TestArtifactFlow:
    async def test_ingest_and_retrieve(self, vault):
        ref = ArtifactRef(
            artifact_id="art_001",
            project_id="hello_squad",
            artifact_type="prd",
            filename="prd-v1.md",
            content_hash="placeholder",
            size_bytes=0,
            media_type="text/markdown",
            created_at=NOW,
        )
        stored = await vault.store(ref, b"# PRD v1")
        assert stored.vault_uri is not None

        retrieved_ref, content = await vault.retrieve("art_001")
        assert content == b"# PRD v1"

    async def test_ingest_and_promote_baseline(self, vault):
        ref = ArtifactRef(
            artifact_id="art_002",
            project_id="hello_squad",
            artifact_type="code",
            filename="main.py",
            content_hash="placeholder",
            size_bytes=0,
            media_type="text/x-python",
            created_at=NOW,
        )
        await vault.store(ref, b"print('hello')")
        await vault.set_baseline("hello_squad", "code", "art_002")

        baseline = await vault.get_baseline("hello_squad", "code")
        assert baseline is not None
        assert baseline.artifact_id == "art_002"


class TestArtifactCycleLinkage:
    async def test_ingest_prd_and_create_cycle_with_ref(self, vault, cycle_registry):
        """Scenario 7: ingest PRD artifact → create cycle with prd_ref → verify linkage."""
        ref = ArtifactRef(
            artifact_id="art_prd_001",
            project_id="hello_squad",
            artifact_type="prd",
            filename="prd-v2.md",
            content_hash="placeholder",
            size_bytes=0,
            media_type="text/markdown",
            created_at=NOW,
        )
        stored = await vault.store(ref, b"# PRD v2\nRequirements here.")
        assert stored.vault_uri is not None

        # Create a cycle that references the ingested artifact
        cycle = _make_cycle(prd_ref=stored.artifact_id)
        await cycle_registry.create_cycle(cycle)

        fetched = await cycle_registry.get_cycle("cyc_001")
        assert fetched.prd_ref == "art_prd_001"

        # Verify the artifact is retrievable via vault
        retrieved_ref, content = await vault.retrieve("art_prd_001")
        assert retrieved_ref.artifact_id == fetched.prd_ref
        assert b"PRD v2" in content


class TestExperimentContext:
    async def test_context_preserved(self, cycle_registry):
        cycle = _make_cycle(
            experiment_context={"infra_profile": "gpu-a100-4x", "region": "us-east-1"}
        )
        await cycle_registry.create_cycle(cycle)
        fetched = await cycle_registry.get_cycle("cyc_001")
        assert fetched.experiment_context["infra_profile"] == "gpu-a100-4x"
        assert fetched.experiment_context["region"] == "us-east-1"

    async def test_applied_defaults_vs_overrides(self, cycle_registry):
        cycle = _make_cycle(
            applied_defaults={"timeout": 300, "retries": 3},
            execution_overrides={"timeout": 600},
        )
        await cycle_registry.create_cycle(cycle)
        fetched = await cycle_registry.get_cycle("cyc_001")
        assert fetched.applied_defaults == {"timeout": 300, "retries": 3}
        assert fetched.execution_overrides == {"timeout": 600}


class TestMultipleCycles:
    async def test_list_and_filter(self, cycle_registry):
        c1 = _make_cycle(cycle_id="cyc_001")
        c2 = _make_cycle(cycle_id="cyc_002")
        await cycle_registry.create_cycle(c1)
        await cycle_registry.create_cycle(c2)

        # Create a completed run for c1
        r1 = Run(
            run_id="run_c1",
            cycle_id="cyc_001",
            run_number=1,
            status="completed",
            initiated_by="api",
            resolved_config_hash="h1",
        )
        await cycle_registry.create_run(r1)

        all_cycles = await cycle_registry.list_cycles("hello_squad")
        assert len(all_cycles) == 2

        completed = await cycle_registry.list_cycles("hello_squad", status=CycleStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].cycle_id == "cyc_001"

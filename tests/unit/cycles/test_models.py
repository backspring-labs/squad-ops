"""
Tests for SIP-0064 domain models, enums, and constants.
"""

import dataclasses
from datetime import datetime, timezone

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    ArtifactType,
    BuildStrategy,
    Cycle,
    CycleStatus,
    FlowMode,
    GateDecision,
    GateDecisionValue,
    Project,
    Run,
    RunInitiator,
    RunStatus,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# =============================================================================
# Enum membership tests
# =============================================================================


class TestCycleStatus:
    def test_members(self):
        assert set(CycleStatus) == {
            CycleStatus.CREATED,
            CycleStatus.ACTIVE,
            CycleStatus.COMPLETED,
            CycleStatus.FAILED,
            CycleStatus.CANCELLED,
        }

    def test_values_are_strings(self):
        for member in CycleStatus:
            assert isinstance(member.value, str)
            assert member == member.value


class TestRunStatus:
    def test_members(self):
        assert set(RunStatus) == {
            RunStatus.QUEUED,
            RunStatus.RUNNING,
            RunStatus.PAUSED,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }

    def test_values_are_strings(self):
        for member in RunStatus:
            assert isinstance(member.value, str)
            assert member == member.value


class TestFlowMode:
    def test_members(self):
        assert set(FlowMode) == {
            FlowMode.SEQUENTIAL,
            FlowMode.FAN_OUT_FAN_IN,
            FlowMode.FAN_OUT_SOFT_GATES,
        }

    def test_sequential_value(self):
        assert FlowMode.SEQUENTIAL == "sequential"

    def test_fan_out_fan_in_value(self):
        assert FlowMode.FAN_OUT_FAN_IN == "fan_out_fan_in"

    def test_fan_out_soft_gates_value(self):
        assert FlowMode.FAN_OUT_SOFT_GATES == "fan_out_soft_gates"


class TestBuildStrategy:
    def test_members(self):
        assert set(BuildStrategy) == {BuildStrategy.FRESH, BuildStrategy.INCREMENTAL}

    def test_values(self):
        assert BuildStrategy.FRESH == "fresh"
        assert BuildStrategy.INCREMENTAL == "incremental"


class TestGateDecisionValue:
    def test_members(self):
        assert set(GateDecisionValue) == {
            GateDecisionValue.APPROVED,
            GateDecisionValue.REJECTED,
        }

    def test_values(self):
        assert GateDecisionValue.APPROVED == "approved"
        assert GateDecisionValue.REJECTED == "rejected"


# =============================================================================
# Constants tests
# =============================================================================


class TestArtifactType:
    def test_prd(self):
        assert ArtifactType.PRD == "prd"

    def test_code(self):
        assert ArtifactType.CODE == "code"

    def test_test_report(self):
        assert ArtifactType.TEST_REPORT == "test_report"

    def test_build_plan(self):
        assert ArtifactType.BUILD_PLAN == "build_plan"

    def test_config_snapshot(self):
        assert ArtifactType.CONFIG_SNAPSHOT == "config_snapshot"


class TestRunInitiator:
    def test_api(self):
        assert RunInitiator.API == "api"

    def test_cli(self):
        assert RunInitiator.CLI == "cli"

    def test_retry(self):
        assert RunInitiator.RETRY == "retry"

    def test_system(self):
        assert RunInitiator.SYSTEM == "system"


# =============================================================================
# Frozen dataclass tests
# =============================================================================


class TestProject:
    def test_construction(self, sample_project):
        assert sample_project.project_id == "hello_squad"
        assert sample_project.name == "Hello Squad"
        assert sample_project.description == "Simple single-agent greeting"
        assert sample_project.tags == ("example", "selftest")

    def test_default_tags(self):
        p = Project(project_id="x", name="X", description="", created_at=NOW)
        assert p.tags == ()

    def test_immutability(self, sample_project):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_project.name = "changed"


class TestGate:
    def test_construction(self, sample_gate):
        assert sample_gate.name == "qa_review"
        assert sample_gate.after_task_types == ("code_generate",)

    def test_immutability(self, sample_gate):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_gate.name = "changed"


class TestTaskFlowPolicy:
    def test_construction_with_gates(self, sample_flow_policy, sample_gate):
        assert sample_flow_policy.mode == "sequential"
        assert sample_flow_policy.gates == (sample_gate,)

    def test_default_gates(self):
        policy = TaskFlowPolicy(mode="sequential")
        assert policy.gates == ()

    def test_immutability(self, sample_flow_policy):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_flow_policy.mode = "changed"


class TestGateDecision:
    def test_construction(self, sample_gate_decision):
        assert sample_gate_decision.gate_name == "qa_review"
        assert sample_gate_decision.decision == "approved"
        assert sample_gate_decision.decided_by == "operator-1"
        assert sample_gate_decision.notes == "Looks good"

    def test_default_notes(self):
        gd = GateDecision(
            gate_name="g", decision="approved", decided_by="u", decided_at=NOW
        )
        assert gd.notes is None

    def test_immutability(self, sample_gate_decision):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_gate_decision.decision = "rejected"


class TestCycle:
    def test_full_construction(self, sample_cycle):
        assert sample_cycle.cycle_id == "cyc_001"
        assert sample_cycle.project_id == "hello_squad"
        assert sample_cycle.prd_ref == "art_prd_v1"
        assert sample_cycle.squad_profile_id == "full-squad"
        assert sample_cycle.build_strategy == "fresh"
        assert sample_cycle.applied_defaults == {"timeout": 300}
        assert sample_cycle.execution_overrides == {"parallel": False}
        assert sample_cycle.expected_artifact_types == ("code", "test_report")
        assert sample_cycle.experiment_context == {"infra_profile": "gpu-a100-4x"}
        assert sample_cycle.notes == "Test cycle"

    def test_prd_ref_none_for_example_project(self, now, sample_flow_policy):
        cycle = Cycle(
            cycle_id="cyc_002",
            project_id="hello_squad",
            created_at=now,
            created_by="system",
            prd_ref=None,
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=sample_flow_policy,
            build_strategy="fresh",
        )
        assert cycle.prd_ref is None

    def test_defaults(self, now, sample_flow_policy):
        cycle = Cycle(
            cycle_id="cyc_003",
            project_id="p",
            created_at=now,
            created_by="system",
            prd_ref=None,
            squad_profile_id="sp",
            squad_profile_snapshot_ref="hash",
            task_flow_policy=sample_flow_policy,
            build_strategy="fresh",
        )
        assert cycle.applied_defaults == {}
        assert cycle.execution_overrides == {}
        assert cycle.expected_artifact_types == ()
        assert cycle.experiment_context == {}
        assert cycle.notes is None

    def test_experiment_context_arbitrary_keys(self, now, sample_flow_policy):
        cycle = Cycle(
            cycle_id="cyc_004",
            project_id="p",
            created_at=now,
            created_by="system",
            prd_ref=None,
            squad_profile_id="sp",
            squad_profile_snapshot_ref="hash",
            task_flow_policy=sample_flow_policy,
            build_strategy="fresh",
            experiment_context={"custom_key": 42, "nested": {"a": 1}},
        )
        assert cycle.experiment_context["custom_key"] == 42
        assert cycle.experiment_context["nested"]["a"] == 1

    def test_immutability(self, sample_cycle):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_cycle.cycle_id = "changed"


class TestRun:
    def test_construction(self, sample_run):
        assert sample_run.run_id == "run_001"
        assert sample_run.cycle_id == "cyc_001"
        assert sample_run.run_number == 1
        assert sample_run.status == "queued"
        assert sample_run.initiated_by == "api"

    def test_defaults(self):
        run = Run(
            run_id="r",
            cycle_id="c",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )
        assert run.resolved_config_ref is None
        assert run.started_at is None
        assert run.finished_at is None
        assert run.gate_decisions == ()
        assert run.artifact_refs == ()

    def test_with_gate_decisions(self, sample_gate_decision):
        run = Run(
            run_id="r",
            cycle_id="c",
            run_number=1,
            status="paused",
            initiated_by="api",
            resolved_config_hash="hash",
            gate_decisions=(sample_gate_decision,),
        )
        assert len(run.gate_decisions) == 1
        assert run.gate_decisions[0].gate_name == "qa_review"

    def test_immutability(self, sample_run):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_run.status = "running"


class TestArtifactRef:
    def test_construction(self, sample_artifact_ref):
        assert sample_artifact_ref.artifact_id == "art_001"
        assert sample_artifact_ref.project_id == "hello_squad"
        assert sample_artifact_ref.artifact_type == "prd"
        assert sample_artifact_ref.size_bytes == 1024

    def test_vault_uri_none_during_ingestion(self):
        ref = ArtifactRef(
            artifact_id="a",
            project_id="p",
            artifact_type="code",
            filename="f.py",
            content_hash="h",
            size_bytes=0,
            media_type="text/plain",
            created_at=NOW,
        )
        assert ref.vault_uri is None
        assert ref.cycle_id is None
        assert ref.run_id is None

    def test_defaults(self):
        ref = ArtifactRef(
            artifact_id="a",
            project_id="p",
            artifact_type="code",
            filename="f.py",
            content_hash="h",
            size_bytes=0,
            media_type="text/plain",
            created_at=NOW,
        )
        assert ref.metadata == {}

    def test_immutability(self, sample_artifact_ref):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_artifact_ref.vault_uri = "new"


class TestAgentProfileEntry:
    def test_construction(self, sample_agent_entry):
        assert sample_agent_entry.agent_id == "max"
        assert sample_agent_entry.role == "lead"
        assert sample_agent_entry.model == "gpt-4"
        assert sample_agent_entry.enabled is True

    def test_default_config_overrides(self):
        entry = AgentProfileEntry(agent_id="a", role="r", model="m", enabled=True)
        assert entry.config_overrides == {}

    def test_immutability(self, sample_agent_entry):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_agent_entry.model = "gpt-5"


class TestSquadProfile:
    def test_construction(self, sample_profile):
        assert sample_profile.profile_id == "full-squad"
        assert sample_profile.name == "Full Squad"
        assert sample_profile.version == 1
        assert len(sample_profile.agents) == 5

    def test_immutability(self, sample_profile):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_profile.name = "changed"

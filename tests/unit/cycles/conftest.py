"""
Shared fixtures for SIP-0064 cycle domain tests.
"""

from datetime import datetime, timezone

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Gate,
    GateDecision,
    Project,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)

_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def now():
    return _NOW


@pytest.fixture
def sample_project(now):
    return Project(
        project_id="hello_squad",
        name="Hello Squad",
        description="Simple single-agent greeting",
        created_at=now,
        tags=("example", "selftest"),
    )


@pytest.fixture
def sample_gate():
    return Gate(
        name="qa_review",
        description="QA review gate after code generation",
        after_task_types=("code_generate",),
    )


@pytest.fixture
def sample_flow_policy(sample_gate):
    return TaskFlowPolicy(mode="sequential", gates=(sample_gate,))


@pytest.fixture
def sample_flow_policy_no_gates():
    return TaskFlowPolicy(mode="sequential")


@pytest.fixture
def sample_cycle(now, sample_flow_policy):
    return Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=now,
        created_by="system",
        prd_ref="art_prd_v1",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc123",
        task_flow_policy=sample_flow_policy,
        build_strategy="fresh",
        applied_defaults={"timeout": 300},
        execution_overrides={"parallel": False},
        expected_artifact_types=("code", "test_report"),
        experiment_context={"infra_profile": "gpu-a100-4x"},
        notes="Test cycle",
    )


@pytest.fixture
def sample_run():
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="sha256:def456",
    )


@pytest.fixture
def sample_gate_decision(now):
    return GateDecision(
        gate_name="qa_review",
        decision="approved",
        decided_by="operator-1",
        decided_at=now,
        notes="Looks good",
    )


@pytest.fixture
def sample_artifact_ref(now):
    return ArtifactRef(
        artifact_id="art_001",
        project_id="hello_squad",
        artifact_type="prd",
        filename="prd-v1.md",
        content_hash="sha256:abc",
        size_bytes=1024,
        media_type="text/markdown",
        created_at=now,
    )


@pytest.fixture
def sample_agent_entry():
    return AgentProfileEntry(
        agent_id="max",
        role="lead",
        model="gpt-4",
        enabled=True,
    )


@pytest.fixture
def sample_profile(now, sample_agent_entry):
    return SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="All agents with default models",
        version=1,
        agents=(
            sample_agent_entry,
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="nat", role="strategy", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="data", role="analytics", model="gpt-4", enabled=True),
        ),
        created_at=now,
    )

"""Unit tests for cycle DTO mapping — profile_to_response and cycle_to_response."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.api.routes.cycles.mapping import cycle_to_response, profile_to_response
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    GateDecision,
    GateDecisionValue,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_api]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


class TestProfileToResponse:
    def _make_profile(self, agents: tuple) -> SquadProfile:
        return SquadProfile(
            profile_id="full-squad",
            name="Full Squad",
            description="All agents",
            version=1,
            agents=agents,
            created_at=datetime(2025, 6, 1, tzinfo=UTC),
        )

    def test_role_label_populated(self):
        profile = self._make_profile((
            AgentProfileEntry(
                agent_id="neo", role="dev", model="qwen2.5:7b", enabled=True
            ),
        ))
        resp = profile_to_response(profile)
        agent = resp.agents[0]
        assert agent.role_label == "Developer"

    def test_display_name_from_agent_id(self):
        profile = self._make_profile((
            AgentProfileEntry(
                agent_id="max", role="lead", model="qwen2.5:7b", enabled=True
            ),
        ))
        resp = profile_to_response(profile)
        agent = resp.agents[0]
        assert agent.display_name == "Max"

    def test_unknown_role_gets_title_label(self):
        profile = self._make_profile((
            AgentProfileEntry(
                agent_id="zara", role="custom_role", model="qwen2.5:7b", enabled=True
            ),
        ))
        resp = profile_to_response(profile)
        agent = resp.agents[0]
        assert agent.role_label == "Custom_Role"
        assert agent.display_name == "Zara"

    def test_all_agents_get_labels(self):
        agents = (
            AgentProfileEntry(agent_id="max", role="lead", model="m", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
            AgentProfileEntry(agent_id="nat", role="strat", model="m", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
            AgentProfileEntry(agent_id="data", role="data", model="m", enabled=True),
            AgentProfileEntry(agent_id="bob", role="builder", model="m", enabled=True),
        )
        profile = self._make_profile(agents)
        resp = profile_to_response(profile)

        for agent in resp.agents:
            assert agent.role_label is not None
            assert agent.display_name is not None


def _make_cycle(workload_sequence: list[dict] | None = None) -> Cycle:
    defaults = {}
    if workload_sequence is not None:
        defaults["workload_sequence"] = workload_sequence
    return Cycle(
        cycle_id="cyc_001",
        project_id="proj_001",
        created_at=NOW,
        created_by="system",
        prd_ref=None,
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=defaults,
    )


def _make_run(
    run_id: str = "run_001",
    run_number: int = 1,
    status: str = "completed",
    workload_type: str | None = None,
    gate_decisions: tuple = (),
) -> Run:
    return Run(
        run_id=run_id,
        cycle_id="cyc_001",
        run_number=run_number,
        status=status,
        initiated_by="api",
        resolved_config_hash="hash_abc",
        workload_type=workload_type,
        gate_decisions=gate_decisions,
    )


class TestCycleToResponseStatus:
    """SIP-0083 D5: cycle_to_response uses resolve_cycle_status, not derive."""

    def test_completed_run_with_pending_workloads_shows_active(self):
        """Bug that motivated SIP-0083 D5: derive returns COMPLETED but
        pending workloads remain — resolve_cycle_status returns ACTIVE."""
        ws = [
            {"type": "planning"},
            {"type": "implementation"},
            {"type": "wrapup"},
        ]
        cycle = _make_cycle(workload_sequence=ws)
        runs = [_make_run("run_001", 1, "completed", "planning")]

        resp = cycle_to_response(cycle, runs)

        assert resp.status == "active"
        assert resp.workload_progress[0].status == "completed"
        assert resp.workload_progress[1].status == "pending"
        assert resp.workload_progress[2].status == "pending"

    def test_gate_awaiting_shows_paused(self):
        """Paused run at inter-workload gate → cycle status is PAUSED."""
        ws = [
            {"type": "planning", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ]
        cycle = _make_cycle(workload_sequence=ws)
        runs = [_make_run("run_001", 1, "paused", "planning")]

        resp = cycle_to_response(cycle, runs)

        assert resp.status == "paused"
        assert resp.workload_progress[0].status == "gate_awaiting"

    def test_rejected_gate_shows_failed(self):
        """Rejected gate decision → cycle status is FAILED."""
        ws = [
            {"type": "planning", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ]
        decision = GateDecision(
            gate_name="progress_plan_review",
            decision=GateDecisionValue.REJECTED,
            decided_by="user",
            decided_at=NOW,
        )
        cycle = _make_cycle(workload_sequence=ws)
        runs = [_make_run("run_001", 1, "completed", "planning",
                          gate_decisions=(decision,))]

        resp = cycle_to_response(cycle, runs)

        assert resp.status == "failed"

    def test_all_workloads_completed_shows_completed(self):
        """All workloads done → COMPLETED (no pending guard fires)."""
        ws = [
            {"type": "planning"},
            {"type": "implementation"},
        ]
        cycle = _make_cycle(workload_sequence=ws)
        runs = [
            _make_run("run_001", 1, "completed", "planning"),
            _make_run("run_002", 2, "completed", "implementation"),
        ]

        resp = cycle_to_response(cycle, runs)

        assert resp.status == "completed"

    def test_no_workload_sequence_uses_derive(self):
        """Without workload_sequence, backward compat — derive_cycle_status."""
        cycle = _make_cycle()  # no workload_sequence
        runs = [_make_run("run_001", 1, "completed")]

        resp = cycle_to_response(cycle, runs)

        assert resp.status == "completed"
        assert resp.workload_progress == []

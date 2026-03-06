"""Tests for agent_model + agent_config_overrides in task plan (SIP-0075 §3.1)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    CycleError,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import generate_task_plan

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_FULL_AGENTS = (
    AgentProfileEntry(
        agent_id="nat",
        role="strat",
        model="qwen2.5:7b",
        enabled=True,
        config_overrides={"temperature": 0.3},
    ),
    AgentProfileEntry(
        agent_id="neo",
        role="dev",
        model="deepseek-coder:6.7b",
        enabled=True,
        config_overrides={"max_completion_tokens": 4096, "temperature": 0.1},
    ),
    AgentProfileEntry(
        agent_id="eve",
        role="qa",
        model="qwen2.5:7b",
        enabled=True,
    ),
    AgentProfileEntry(
        agent_id="data",
        role="data",
        model="qwen2.5:7b",
        enabled=True,
    ),
    AgentProfileEntry(
        agent_id="max",
        role="lead",
        model="gpt-4",
        enabled=True,
        config_overrides={"timeout_seconds": 600},
    ),
)


def _make_profile(agents=_FULL_AGENTS, profile_id="test-squad"):
    return SquadProfile(
        profile_id=profile_id,
        name="Test Squad",
        description="Test",
        version=1,
        agents=agents,
        created_at=NOW,
    )


def _make_cycle(**overrides):
    defaults = {
        "cycle_id": "cycle-1",
        "project_id": "proj-1",
        "created_at": NOW,
        "created_by": "test",
        "prd_ref": "prd_ref_123",
        "squad_profile_id": "test-squad",
        "squad_profile_snapshot_ref": "abc123",
        "task_flow_policy": TaskFlowPolicy(mode="sequential"),
        "build_strategy": "fresh",
        "applied_defaults": {},
        "execution_overrides": {},
    }
    defaults.update(overrides)
    return Cycle(**defaults)


def _make_run():
    return Run(
        run_id="run-1",
        cycle_id="cycle-1",
        run_number=1,
        status="queued",
        initiated_by="test",
        resolved_config_hash="hash123",
    )


class TestAgentModelInjection:
    def test_envelopes_contain_agent_model(self):
        plan = generate_task_plan(_make_cycle(), _make_run(), _make_profile())
        # First envelope is strategy (nat, qwen2.5:7b)
        assert plan[0].inputs["agent_model"] == "qwen2.5:7b"
        # Second envelope is dev (neo, deepseek-coder:6.7b)
        assert plan[1].inputs["agent_model"] == "deepseek-coder:6.7b"

    def test_envelopes_contain_agent_config_overrides(self):
        plan = generate_task_plan(_make_cycle(), _make_run(), _make_profile())
        # strat has temperature override
        assert plan[0].inputs["agent_config_overrides"] == {"temperature": 0.3}
        # dev has max_completion_tokens + temperature
        assert plan[1].inputs["agent_config_overrides"] == {
            "max_completion_tokens": 4096,
            "temperature": 0.1,
        }

    def test_empty_overrides_default_to_empty_dict(self):
        plan = generate_task_plan(_make_cycle(), _make_run(), _make_profile())
        # qa (eve) has no config_overrides
        assert plan[2].inputs["agent_config_overrides"] == {}

    def test_agent_model_none_when_empty_string(self):
        agents = (
            *_FULL_AGENTS[:4],
            AgentProfileEntry(agent_id="max", role="lead", model="", enabled=True),
        )
        plan = generate_task_plan(_make_cycle(), _make_run(), _make_profile(agents))
        lead_envelope = plan[4]
        assert lead_envelope.inputs["agent_model"] is None


class TestRequiredRolesValidation:
    def test_missing_required_role_raises(self):
        # Profile missing 'lead' role
        agents = _FULL_AGENTS[:4]  # strat, dev, qa, data — no lead
        with pytest.raises(CycleError, match="missing required roles.*lead"):
            generate_task_plan(_make_cycle(), _make_run(), _make_profile(agents))

    def test_missing_multiple_roles_raises(self):
        agents = _FULL_AGENTS[:2]  # strat, dev only
        with pytest.raises(CycleError, match="missing required roles"):
            generate_task_plan(_make_cycle(), _make_run(), _make_profile(agents))

    def test_disabled_agent_counts_as_missing(self):
        agents = (
            *_FULL_AGENTS[:4],
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=False),
        )
        with pytest.raises(CycleError, match="missing required roles.*lead"):
            generate_task_plan(_make_cycle(), _make_run(), _make_profile(agents))

    def test_all_required_roles_present_succeeds(self):
        plan = generate_task_plan(_make_cycle(), _make_run(), _make_profile())
        assert len(plan) == 5  # 5 standard steps

    def test_builder_role_not_required(self):
        # Full profile without builder should still work
        plan = generate_task_plan(_make_cycle(), _make_run(), _make_profile())
        assert len(plan) == 5

    def test_build_only_skips_required_role_validation(self):
        # Build-only cycles (plan_tasks=False) only need dev+qa, not all 5 roles
        agents = (
            AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
        )
        cycle = _make_cycle(
            applied_defaults={
                "plan_tasks": False,
                "build_tasks": ["development.develop", "qa.test"],
            },
        )
        plan = generate_task_plan(cycle, _make_run(), _make_profile(agents))
        assert len(plan) == 2  # dev + qa build steps only


class TestBackwardCompatibility:
    def test_existing_inputs_preserved(self):
        plan = generate_task_plan(_make_cycle(), _make_run(), _make_profile())
        for env in plan:
            assert "prd" in env.inputs
            assert "resolved_config" in env.inputs
            assert "config_hash" in env.inputs

"""#927's fourth rung: a cycle-level reasoning override.

The chain the issue specified is model dial -> capability declaration -> agent
override -> cycle/CRP override, precedence increasing left to right. The first three
were implemented; this file covers the fourth, which is what lets an experiment say
"run this cycle at this level" without editing the squad profile every arm.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.capabilities.reasoning_policy import REASONING_OVERRIDE_KEY
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.profile_utils import validate_reasoning_override
from squadops.cycles.task_plan import generate_task_plan

pytestmark = [pytest.mark.unit, pytest.mark.domain_orchestration]


class TestCycleLevelOverrideValidation:
    """A misspelt level must not reach the adapter and be sent as a real one — the
    failure validate_reasoning_override already prevents for the profile knob."""

    def test_a_valid_level_passes(self):
        assert validate_reasoning_override({REASONING_OVERRIDE_KEY: "high"}) == []

    def test_a_misspelt_level_is_rejected_with_the_allowed_set(self):
        errors = validate_reasoning_override({REASONING_OVERRIDE_KEY: "hihg"})
        assert errors, "a misspelt level must not pass validation"
        assert "hihg" in errors[0]
        # The operator needs to be told what IS allowed, not merely that they were wrong.
        assert "high" in errors[0]

    def test_absent_key_is_not_an_error(self):
        """Most cycles set nothing; absence must not be a validation failure."""
        assert validate_reasoning_override({}) == []


# ---- The behaviour, not just the validation ----

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _profile(config_overrides=None):
    return SquadProfile(
        profile_id="full",
        name="Full",
        description="",
        version=1,
        agents=(
            AgentProfileEntry(
                agent_id="nat",
                role="strat",
                model="qwen3.8:27b",
                enabled=True,
                config_overrides=config_overrides or {},
            ),
            AgentProfileEntry(agent_id="neo", role="dev", model="qwen3.8:27b", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="qwen3.8:27b", enabled=True),
            AgentProfileEntry(
                agent_id="data-agent", role="data", model="qwen3.8:27b", enabled=True
            ),
            AgentProfileEntry(agent_id="max", role="lead", model="qwen3.8:27b", enabled=True),
            AgentProfileEntry(agent_id="bob", role="builder", model="qwen3.8:27b", enabled=True),
        ),
        created_at=NOW,
    )


def _cycle(applied_defaults=None, execution_overrides=None):
    return Cycle(
        cycle_id="cyc_001",
        project_id="p",
        created_at=NOW,
        created_by="system",
        prd_ref="prd",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=applied_defaults or {},
        execution_overrides=execution_overrides or {},
    )


def _run():
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="h",
        workload_type="framing",
    )


def _reasoning_in(envelopes):
    return {
        e.inputs.get("agent_config_overrides", {}).get(REASONING_OVERRIDE_KEY) for e in envelopes
    }


class TestCycleLevelOverrideReachesEveryTask:
    def test_absent_by_default_so_nothing_changes(self):
        """A cycle that sets nothing must send nothing — the wire stays what it was."""
        envelopes = generate_task_plan(_cycle(), _run(), _profile())
        assert _reasoning_in(envelopes) == {None}

    def test_a_crp_default_reaches_every_task(self):
        envelopes = generate_task_plan(
            _cycle(applied_defaults={REASONING_OVERRIDE_KEY: "high"}), _run(), _profile()
        )
        assert _reasoning_in(envelopes) == {"high"}

    def test_the_cycle_level_value_beats_the_profile(self):
        """The point of the rung: an experiment says "run this cycle at this level" and
        is not silently overruled by a profile written for ordinary use."""
        envelopes = generate_task_plan(
            _cycle(applied_defaults={REASONING_OVERRIDE_KEY: "high"}),
            _run(),
            _profile(config_overrides={REASONING_OVERRIDE_KEY: "none"}),
        )
        assert _reasoning_in(envelopes) == {"high"}

    def test_the_profile_still_applies_when_the_cycle_says_nothing(self):
        envelopes = generate_task_plan(
            _cycle(), _run(), _profile(config_overrides={REASONING_OVERRIDE_KEY: "low"})
        )
        assert "low" in _reasoning_in(envelopes)

    def test_a_misspelt_cycle_level_value_fails_the_plan_not_the_generation(self):
        """Loudly at plan time, where it is one error, rather than silently on every
        generation as a level the adapter does not recognise."""
        with pytest.raises(ValueError, match="cycle-level reasoning override is invalid"):
            generate_task_plan(
                _cycle(applied_defaults={REASONING_OVERRIDE_KEY: "hihg"}), _run(), _profile()
            )

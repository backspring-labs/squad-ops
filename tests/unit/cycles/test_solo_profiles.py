"""The Solo arm's two declarations (SIP-0108 §10i, 1.8.1 plan §3.5), held equal to the squad's.

The comparison window may differ between its arms by the reasoning organization and nothing
else (§4.4). The driver's arm preflight refuses a drifted pair at launch; these tests refuse
it at commit, and each names the drift it would catch.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from squadops.cycles.agent_config import served_roles
from squadops.cycles.task_plan import decision_is_declared, declared_correction_steps

REPO = Path(__file__).resolve().parents[3]
SQUAD_PROFILES = REPO / "config" / "squad-profiles.yaml"
REQUEST_PROFILES = REPO / "src" / "squadops" / "contracts" / "cycle_request_profiles" / "profiles"


async def test_solo_serves_exactly_the_roles_full_38_serves_with_the_same_substrate():
    """Bug this catches: a role the squad serves that Han does not (a dispatch to a queue
    nobody consumes), a model or cap that differs between the arms (the #1619 shape, which
    the preflight would refuse hours later), or the flat cap moving on one side only."""
    provider = ConfigSquadProfile(yaml_path=SQUAD_PROFILES)
    solo = await provider.get_profile("solo")
    squad = await provider.get_profile("full-38")

    assert [a.agent_id for a in solo.agents] == ["han"]
    han = solo.agents[0]
    assert han.role == "generalist" and han.enabled
    assert served_roles(solo) == served_roles(squad)
    assert {a.model for a in squad.agents} == {han.model}
    for member in squad.agents:
        assert member.config_overrides == han.config_overrides, (
            f"{member.agent_id}'s overrides differ from han's — the arms are no longer held "
            "equal by the flat cap (SIP-0108 §10l)"
        )


def test_the_solo_request_profile_is_validated_fullstack_with_one_difference():
    """Bug this catches: any constant of the Solo request profile drifting from the squad's
    (a budget, a required check, the task plan, self-eval depth) — every one would make the
    window a comparison of two profiles rather than of two organizations."""
    squad = yaml.safe_load((REQUEST_PROFILES / "validated-fullstack.yaml").read_text())
    solo = yaml.safe_load((REQUEST_PROFILES / "validated-fullstack-solo.yaml").read_text())

    assert solo["name"] == "validated-fullstack-solo"
    differing = {
        key
        for key in set(squad["defaults"]) | set(solo["defaults"])
        if squad["defaults"].get(key) != solo["defaults"].get(key)
    }
    assert differing == {"correction_steps", "notes"}, differing
    assert solo["defaults"]["correction_steps"] == ["repair"]
    assert squad["defaults"]["correction_steps"] == ["analyze", "decide", "repair"]


def test_the_solo_correction_protocol_is_repair_alone_and_decides_nothing():
    """Wiring into the runner's declaration reader (§10i item 3). Bug this catches: the
    reader rejecting a repair-only declaration, or reporting a decision step the Solo arm
    does not declare — either would run the squad's protocol on the Solo arm."""
    solo = yaml.safe_load((REQUEST_PROFILES / "validated-fullstack-solo.yaml").read_text())
    resolved = dict(solo["defaults"])
    assert declared_correction_steps(resolved) == ("repair",)
    assert decision_is_declared(resolved) is False

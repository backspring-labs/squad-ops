"""A Campaign names the development profile its product is developed under (SIP-0109 §24ed, #3157).

Entered at ``POST /api/v1/campaigns``, the route ``squadops campaigns create`` calls, over the
repository-creation tests' world, with the squads the deploy seeds (``config/squad-profiles.yaml``).
The wiring test follows the stored Campaign to the launch its deciding row writes
(``increment_launch``, ``bound_launch``) and to what a cycle's creation reads of that request: its
pin (``development_profile_pin``) and its squad's coverage (``cycle_coverage``).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from squadops.campaigns.launch_requests import bound_launch, increment_launch
from squadops.campaigns.lifecycle import creation_request_hash
from squadops.campaigns.models import AcceptedTree, CampaignPolicy, CycleKind
from squadops.capabilities.skillsets import load_skillsets
from squadops.cycles.development_pin import development_profile_pin
from squadops.cycles.preflight import seeds_skeleton
from squadops.cycles.skillset_coverage import cycle_coverage
from tests.unit.api.test_campaign_repository_creation import _GoalSets, _on, _Projects
from tests.unit.api.test_campaign_routes import _World
from tests.unit.campaigns.builders import campaign, policy
from tests.unit.projects.test_profile_derivation_luau import _SCRIPT_SYNC, _derive

pytestmark = pytest.mark.auth

SQUAD_PROFILES = Path(__file__).resolve().parents[3] / "config" / "squad-profiles.yaml"
PROFILE = "game_dev_roblox"
SQUAD = "game-dev-roblox"
CID = "cmp_api000000001"


@pytest.fixture
def world() -> _World:
    world = _World()
    world.client.app.state.project_registry = _Projects()
    world.client.app.state.goal_set_registry = _GoalSets()
    world.client.app.state.squad_profile = ConfigSquadProfile(yaml_path=SQUAD_PROFILES)
    return world


def _config(launch) -> dict:
    """The configuration a cycle created from ``launch`` resolves, as cycle create reads it."""
    body = launch.cycle_request["body"]
    return {**body["applied_defaults"], **body["execution_overrides"]}


async def test_a_campaigns_development_profile_reaches_every_launchs_pin_and_coverage(world):
    """Bugs caught: the profile stored on the Campaign and dropped from its launches, so every
    cycle derives ``product_neutral`` and is handed no skill (#3157); a launch carrying it as a
    ``build_profile`` too, which pins nothing and seeds a skeleton beside the product."""
    resp = _on(world, "prj-tally", development_profile=PROFILE, squad_profile=SQUAD)
    assert resp.status_code == 201, resp.json()
    assert world.client.get(f"/api/v1/campaigns/{CID}").json()["policy"]["development_profile"] == (
        PROFILE
    )
    stored = await world.campaigns.get_campaign(CID)
    on_branch = dataclasses.replace(
        stored,
        accepted=AcceptedTree(
            "sha-cal", calibration_record_id="calrec_0123456789ab", commit="a" * 40
        ),
    )
    squad = await world.client.app.state.squad_profile.get_profile(SQUAD)

    increment = increment_launch(on_branch, baseline_manifest=None)
    proposal = increment.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    launches = [
        increment,
        bound_launch(
            on_branch, CycleKind.REPAIR, proposal, plan_artifact_refs=[], contract_ref=None
        ),
    ]

    for launch in launches:
        config = _config(launch)
        assert config["development_profile"] == PROFILE
        assert "build_profile" not in config
        assert seeds_skeleton(config) is False
        pin = development_profile_pin(config, _derive(_SCRIPT_SYNC))
        assert (pin.name, pin.origin) == (PROFILE, "operator")
        coverage = cycle_coverage(squad, config, load_skillsets())
        assert coverage.findings == ()
        assert [(a.role, a.skillset) for a in coverage.assignments] == [
            ("strat", "roblox-increment-design"),
            ("dev", "roblox-luau-dev"),
            ("qa", "roblox-studio-qa"),
        ]


async def test_a_campaign_naming_no_development_profile_launches_as_before(world):
    """The edge the field must leave alone. Bug caught: an undeclared profile written to a launch
    as an empty key, or a product's cycle no longer deriving its own profile."""
    assert _on(world, "prj-tally").status_code == 201
    stored = await world.campaigns.get_campaign(CID)
    on_branch = dataclasses.replace(
        stored,
        accepted=AcceptedTree(
            "sha-cal", calibration_record_id="calrec_0123456789ab", commit="a" * 40
        ),
    )

    config = _config(increment_launch(on_branch, baseline_manifest=None))

    assert "development_profile" not in config
    assert "build_profile" not in config
    pin = development_profile_pin({**config, "implementation_plan": True}, _derive(_SCRIPT_SYNC))
    assert (pin.name, pin.origin) == ("product_neutral", "derived")


@pytest.mark.parametrize(
    ("project_id", "policy", "named"),
    [
        (
            "prj-tally",
            {"development_profile": PROFILE, "squad_profile": "full-38-tf"},
            "policy.development_profile 'game_dev_roblox': Squad skillset requirements not met. "
            "Selected squad: `full-38-tf`. Missing: `roblox-increment-design` for `strat`",
        ),
        (
            "prj-tally",
            {"development_profile": PROFILE, "squad_profile": "no-such-squad"},
            "policy.squad_profile: ",
        ),
        (
            "prj-tally",
            {"development_profile": "game_dev_unheld", "squad_profile": SQUAD},
            "CampaignPolicy.development_profile 'game_dev_unheld' is not a development profile "
            "this deployment holds; the profiles are [",
        ),
        (
            "prj-tally",
            {"development_profile": "", "squad_profile": SQUAD},
            "CampaignPolicy.development_profile '' is not a development profile",
        ),
        (
            "prj-tally",
            {
                "development_profile": PROFILE,
                "stack": "fullstack_fastapi_react",
                "squad_profile": SQUAD,
            },
            "declares both stack 'fullstack_fastapi_react' and development_profile "
            "'game_dev_roblox'",
        ),
        (
            "group_run",
            {
                "development_profile": PROFILE,
                "squad_profile": SQUAD,
                "proposal_profile": "campaign-increment",
            },
            "policy.development_profile names the profile a repository-backed Project's product",
        ),
    ],
    ids=[
        "a squad lacking the skillsets",
        "a squad the deploy doesn't hold",
        "a profile the deploy doesn't hold",
        "an empty name",
        "with a stack",
        "a sample application",
    ],
)
def test_a_development_profile_a_campaign_cant_run_under_is_refused_at_creation(
    world, project_id, policy, named
):
    """Bugs caught: a Campaign whose every launch the cycle's preflight would refuse (a squad
    without the skillsets, a profile no deploy holds) created and discovered at its first launch;
    a stack and a profile both declared, where the stack's would silently win; a sample
    application's Campaign carrying a profile its scaffold stack contradicts."""
    resp = _on(
        world, project_id, objective=None if project_id == "prj-tally" else _sample(), **policy
    )

    assert resp.status_code == 422, resp.json()
    assert named in resp.json()["detail"]["error"]["message"]
    assert world.client.get(f"/api/v1/campaigns/{CID}").status_code == 404


def _sample() -> dict:
    """A sample application's objective: it names no requirements source."""
    return {
        "statement": "evolve group_run",
        "allowed_scope": ["backend"],
        "measurement": "one accepted increment",
        "target_accepted_increments": 1,
        "work_class": {"prd_tier": "tier-1", "attendance": "attended"},
    }


def test_the_profile_is_part_of_the_creation_hash_only_when_declared_and_is_read_back():
    """Bugs caught: every stored Campaign's creation hash moved by the new field, so its
    creation's retry conflicts; two Campaigns differing only in their profile hashing alike, so
    the second creation replays the first; or the profile lost when a stored policy is read."""

    def h(c):
        return creation_request_hash(c, actor="owner", actor_role="admin", reason="r")

    plain = campaign(policy=policy())
    named = policy(development_profile=PROFILE)
    stored = json.loads(json.dumps(dataclasses.asdict(named), default=str))

    # The hash this definition's creation had before the field existed (main's code, as
    # test_scripted_campaign_policy pins it).
    assert h(plain) == "fba6b2919996fdecb76cf9b83d04fae9dcd99eda7e2104d3170f3b4acfd1fcfd"
    assert (
        len(
            {
                h(plain),
                h(campaign(policy=named)),
                h(campaign(policy=policy(development_profile="product_neutral"))),
            }
        )
        == 3
    )
    assert CampaignPolicy.from_stored(stored).development_profile == PROFILE

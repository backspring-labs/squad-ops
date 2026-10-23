"""The request-profile taxonomy (#316, R2.4): seven operator names, the campaign's own profiles,
and every released profile frozen under its old name, so a pinned config resolves to what it ran.

The stack's request defaults (R2.3, ``squadops.stacks.request_defaults``) sit beneath a profile's
own keys. A profile that sets one keeps it, so every frozen profile that declares them resolves as
it did, and ``validate`` on a stack asks for what ``validated-fullstack`` asked for.
"""

from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path

import pytest
import yaml

from squadops.contracts.cycle_request_profiles import (
    CAMPAIGN_PROFILES,
    OPERATOR_PROFILES,
    cycle_request_body,
    list_profiles,
    load_profile,
)
from squadops.cycles.lifecycle import compute_config_hash
from squadops.stacks.request_defaults import STACK_REQUEST_DEFAULTS

pytestmark = [pytest.mark.domain_contracts]

ROOT = Path(__file__).resolve().parents[3]

#: Every profile as v2.3.1 released it, the last release before the taxonomy: its sha256. A
#: pinned config names one of these, so each stays byte for byte (R2.4, revision 4 (a)).
RELEASED = {
    "benchmark": "dc43069fe06599752802c55384f511fdcb9cfd58465d93cc3566c28cfa0a9f23",
    "build-only": "be21981370e66d9e3b6cc35b801777e04273eec5068c5ed4df47e07a7d3f236f",
    "build": "efdcc688319802e9bcd8f4932ff19dd526a03ae9e11d776407b28fe7c7ad1db2",
    "builder-assemble": "da2b49b1fd5462a6ea294a8b23e8ba772faf8b4223d1161b70db5b46a35acaa0",
    "campaign-increment-asks": "1f52cd930e51be946eddf051cc15c84a4bc84b2b1fa5b364c15e32cdc4031087",
    "campaign-increment": "cc6f29472026243acb1185355af8b31af3ea1d46f5ec9dc52c0cc23a4bfb0dd8",
    "campaign-proposal": "f303fc7c13b2cb9a783f4e59bf0cc988503da45bc0f3463f7a5ed97d5f2e9624",
    "campaign-reference": "25a2edd14bc79ecb8484edcd1d23c0324ce63737d75eed8f6bc5e2395c085758",
    "default": "5d157a25af8f1cd3e7bfd9c08f70d6d0405c783d6709ab31fd1ef3ec337b4590",
    "framing": "39a5c18c890a4662142fd067c04aafec117ac1d1485075b50d7637c15decdd6d",
    "fullstack-fastapi-react": "e250007458252f5ab63143e9e27b9424842140143967b9cd1ead9c99c42bfb3f",
    "implementation": "654b4dc33d7343c1b443da02b96f203da08456ae4b318975520bef2470f9c0ce",
    "multi-phase": "4dea3f2b6d10d2bbb9915e6773b973108b83508fc790b0ae7977ad6c9801668e",
    "pulse-check-build": "07f546c0924f00c4fd067b90f405263ae47af8f4cb311a9824522ecaf45f6b33",
    "pulse-check": "3ef7683b218468aa05313304459a36519a2b36bbb01aafaee184cf15d5dd8f63",
    "selftest": "c27c916a82fb08eba22315e8475f587da898892632a982a831a6af774e4a75d6",
    "validated-fullstack-solo": "d17115951d5f7e062d9a64360c917f707273bc70187f08e17fab354182bc1886",
    "validated-fullstack": "b49e35a8739bbc23dd3388459dcdd5ccbb1b158c21194bb474dd571cd3864af9",
    "validation-multirole": "2bb401aa1162f2b04db10ef7a73d5c2e96889adeea04e7f223317fe13b927924",
    "validation": "0dc01de4a8538f1500909f283fbe3b445322e61203371d8d01f729ca24028111",
    "wrapup": "16e84117a74ce0f71f355ccf0622ab068a0c585c627948206edee8761b59e74c",
}

_PROFILES = resources.files("squadops.contracts.cycle_request_profiles.profiles")


def _stack(stack: str) -> dict:
    """A cycle's two stack keys, as a campaign's launches and the verification sets pass them."""
    return {"build_profile": stack, "development_profile": stack}


def _resolved(profile: str, user_values: dict) -> dict:
    body = cycle_request_body(profile, squad_profile_id="full-38-tf", user_values=user_values)
    return {**body["applied_defaults"], **body["execution_overrides"]}


def _pinned() -> list[tuple[str, str, dict]]:
    """Every pinned config's request: the verification sets' ``request_profile`` and
    ``overrides``, and each campaign definition's profiles with its stack."""
    pinned = []
    for path in sorted((ROOT / "docs" / "plans" / "verification-sets").glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        if isinstance(doc, dict) and doc.get("request_profile"):
            pinned.append((path.name, doc["request_profile"], dict(doc.get("overrides") or {})))
    for path in sorted(ROOT.glob("examples/*/campaigns/*.yaml")):
        policy = (yaml.safe_load(path.read_text()) or {}).get("policy") or {}
        stack = _stack(policy["stack"]) if policy.get("stack") else {}
        for field in ("calibration_profile", "proposal_profile"):
            if policy.get(field):
                pinned.append((f"{path.name}:{field}", policy[field], stack))
    return pinned


@pytest.mark.parametrize("name", sorted(RELEASED))
def test_every_released_profile_is_frozen_byte_for_byte(name):
    """Bug caught: an edit to a released profile, so a pinned config that names it, a verification
    set or a campaign definition, resolves to something it never ran."""
    content = (_PROFILES / f"{name}.yaml").read_bytes()
    assert hashlib.sha256(content).hexdigest() == RELEASED[name]


def test_every_profile_is_the_operators_the_campaigns_or_a_released_one():
    """Bug caught: a new profile minted outside the taxonomy, a name per stack or per pulse
    setting, the combinatorial trap the taxonomy closes (§2)."""
    assert set(list_profiles()) == set(OPERATOR_PROFILES) | set(CAMPAIGN_PROFILES) | set(RELEASED)
    assert set(CAMPAIGN_PROFILES) <= set(RELEASED)


async def test_the_operators_listing_is_the_seven_names():
    """Bug caught: the listing an operator picks from showing every frozen and campaign profile
    again, so the old names stay the ones chosen."""
    from fastapi import Response

    from squadops.api.routes.cycles.cycle_request_profiles import list_cycle_request_profiles

    listed = await list_cycle_request_profiles(Response())

    assert [p.name for p in listed] == list(OPERATOR_PROFILES)


@pytest.mark.parametrize("stack", sorted(STACK_REQUEST_DEFAULTS))
def test_validate_on_a_stack_asks_what_validated_fullstack_asked(stack):
    """R2.3's equivalence. Bug caught: ``validate --set build_profile=<stack>`` silently dropping
    a requirement ``validated-fullstack`` carried (its required checks, its three-hour budget, its
    four manifest attempts), so the operator's name for a validating cycle checks less."""
    new = _resolved("validate", _stack(stack))
    old = _resolved("validated-fullstack", _stack(stack))

    differing = {k for k in new.keys() | old.keys() if new.get(k) != old.get(k)}
    assert differing == {"notes"}


@pytest.mark.parametrize(("where", "profile", "user_values"), _pinned(), ids=lambda v: str(v)[:60])
def test_a_pinned_config_resolves_as_it_did(where, profile, user_values):
    """Revision 4 (a)'s test. Bug caught: the stack's defaults reaching a frozen profile a pinned
    config names, so a verification set or a campaign definition resolves to new defaults and a
    new config hash under the name it was recorded with."""
    body = cycle_request_body(profile, squad_profile_id="full-38-tf", user_values=user_values)
    defaults = load_profile(profile).defaults

    assert body["applied_defaults"] == defaults
    assert compute_config_hash(body["applied_defaults"], body["execution_overrides"]) == (
        compute_config_hash(defaults, body["execution_overrides"])
    )


def test_the_pinned_configs_are_read():
    """Bug caught: the test above reading no verification set or no campaign definition (a moved
    directory, a renamed key) and passing on nothing."""
    pinned = _pinned()
    assert sum(":" not in where for where, _, _ in pinned) >= 100
    assert sum(":" in where for where, _, _ in pinned) >= 30


def test_the_callers_own_value_sits_above_the_stacks():
    """R2.3's order. Bug caught: an operator's ``--set time_budget_seconds=3600`` losing to the
    stack's three hours, so a value set at create time is silently ignored."""
    stack = _stack("fullstack_fastapi_react")

    assert _resolved("validate", stack)["time_budget_seconds"] == 10800
    assert _resolved("validate", {**stack, "time_budget_seconds": 3600})["time_budget_seconds"] == (
        3600
    )


@pytest.mark.parametrize("stack", sorted(STACK_REQUEST_DEFAULTS))
@pytest.mark.parametrize("profile", sorted(set(RELEASED) - set(OPERATOR_PROFILES)))
def test_an_old_or_campaign_profile_gets_nothing_from_a_stack(profile, stack):
    """R2.4's guarantee, by construction rather than by the record. Bug caught: a stack's
    requirements reaching an old name that lacks the stack's keys (``validation``, or
    ``campaign-proposal``, which pins its stack and sets none of them), so a config naming it
    resolves to new defaults under the old name, whatever stack the caller passes."""
    body = cycle_request_body(profile, squad_profile_id="full-38-tf", user_values=_stack(stack))

    assert body["applied_defaults"] == load_profile(profile).defaults


@pytest.mark.parametrize(
    "user_values", [{}, _stack("python_cli_builder")], ids=["none", "unlisted"]
)
def test_a_cycle_on_no_stack_or_an_unlisted_one_gets_nothing_from_it(user_values):
    """Bug caught: a stack's requirements reaching a cycle that doesn't build on it, such as a
    frontend build required of a Python CLI."""
    body = cycle_request_body("validate", squad_profile_id="full-38-tf", user_values=user_values)

    assert body["applied_defaults"] == load_profile("validate").defaults
    assert "required_checks" not in _resolved("validate", user_values)


def test_a_campaigns_launches_on_a_stack_resolve_as_their_profiles_do():
    """Wiring, entered at the launches a campaign makes (SIP-0109 §12b), the path the window's
    campaigns take. Bug caught: a Next.js campaign's calibration or bound cycle picking up the
    stack's defaults under its frozen profile's name, so the window resolves differently from the
    profiles it records."""
    from squadops.campaigns.launch_requests import bound_launch, calibration_launch
    from squadops.campaigns.models import AcceptedTree, CycleKind
    from tests.unit.campaigns.builders import campaign, policy

    c = campaign(
        policy=policy(proposal_profile="campaign-increment", stack="nextjs_ts"),
        accepted=AcceptedTree("sha-1", "cyc_cal"),
    )
    launched = {
        c.policy.calibration_profile: calibration_launch(c).cycle_request["body"],
        "campaign-increment": bound_launch(
            c, CycleKind.REPAIR, {"proposal_id": "p"}, ["art_1"], None
        ).cycle_request["body"],
    }

    for profile, body in launched.items():
        assert body["applied_defaults"] == load_profile(profile).defaults, profile
        assert body["execution_overrides"]["build_profile"] == "nextjs_ts", profile


#: The 2.4 window's launches as main resolved them before #316 (read on c6e10001, and again on this
#: branch, by the second read's method): a calibration and a repair cycle per stack, by config
#: hash. Frozen, so any change on the path a window launch takes (a profile, the stack's defaults,
#: the overrides, the hash) fails here, not only one that changes a profile's own defaults.
_WINDOW_LAUNCH_HASHES = {
    "fullstack_fastapi_react": (
        "a79f58658cd8b37e1a65db41ec343a83a0528d45dd6ccd30964bc611425ece91",
        "00127ca7131c4f38448b7b517cd63ab8e3925e3af31fbfca86ecd8eb84a2ad11",
    ),
    "nextjs_ts": (
        "8e730c8ea1690bdeed5c5eb41277df2cdc0ae402b75ba2c375f331810c9b2c65",
        "6001f3f91be715933c9376bb70fe029cc0080e4608cd953ec6591b1cd38f9189",
    ),
}
_WINDOW_DEFINITIONS = sorted(ROOT.glob("examples/03_group_run/campaigns/2-4-0-*.yaml"))


@pytest.mark.parametrize("path", _WINDOW_DEFINITIONS, ids=lambda p: p.name)
def test_the_windows_launches_resolve_to_the_hashes_main_recorded(path):
    """The second read of PR #2500. Bug caught: anything on a window campaign's launch path moving
    the config its cycles record (an override computed differently, a profile file edited, the hash
    changed), which comparing a profile's defaults against themselves misses. The window's two
    profiles already set the stack's three keys, so a stack's defaults leaking past the operator
    rule doesn't move these hashes: ``test_an_old_or_campaign_profile_gets_nothing_from_a_stack``
    catches that."""
    from squadops.campaigns.launch_requests import bound_launch, calibration_launch
    from squadops.campaigns.models import AcceptedTree, CycleKind
    from tests.unit.campaigns.builders import campaign, policy

    raw = yaml.safe_load(path.read_text())
    c = campaign(policy=policy(**raw["policy"]), accepted=AcceptedTree("sha-1", "cyc_cal"))
    launches = (
        calibration_launch(c).cycle_request["body"],
        bound_launch(c, CycleKind.REPAIR, {"proposal_id": "p"}, ["art_1"], None).cycle_request[
            "body"
        ],
    )

    assert (
        tuple(
            compute_config_hash(b["applied_defaults"], b["execution_overrides"]) for b in launches
        )
        == _WINDOW_LAUNCH_HASHES[raw["policy"]["stack"]]
    )


def test_the_window_definitions_are_read():
    """Bug caught: the frozen-hash test above passing on no definition (a moved directory). Seven:
    the window's four, its two shakeouts, and SIP-0113 §4.5's reading, whose launches the window's
    hashes pin too."""
    assert len(_WINDOW_DEFINITIONS) == 7

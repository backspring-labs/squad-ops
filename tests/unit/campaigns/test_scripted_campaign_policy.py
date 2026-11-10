"""A scripted Campaign's ``llm_scripts`` as the policy holds it (SIP-0109 §24dt, #2892): what the
declaration accepts, how a stored policy reads it back, and its place in the creation hash. The
launch's choice of script is ``tests/unit/api/test_campaign_scripted_launch.py``'s.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from squadops.campaigns.launch_requests import scripted_launch
from squadops.campaigns.lifecycle import creation_request_hash
from squadops.campaigns.models import CampaignPolicy
from tests.unit.campaigns.builders import campaign, policy

PINNED = ["shelf-c1@0123456789ab", "shelf-c2@ba9876543210"]


@pytest.mark.parametrize(
    ("declared", "message"),
    [
        (["shelf-c1"], "entry 1: llm_script must be '<name>@<version>'"),
        ([PINNED[0], "shelf-c2@"], "entry 2: llm_script must be '<name>@<version>'"),
        ([PINNED[0], 7], "entry 2: llm_script must be '<name>@<version>', not 7"),
        ("shelf-c1@0123456789ab", "is a list of pinned scripts"),
    ],
)
def test_a_policy_refuses_a_script_it_could_not_pin(declared, message):
    """Bug caught: an unpinned name accepted, so a cycle's record couldn't say which answers it
    ran on, or a bare string read as a list of its characters, one 'script' per launch."""
    with pytest.raises(ValueError, match=message):
        policy(llm_scripts=declared)


def test_a_stored_policy_reads_its_scripts_back_in_their_order():
    """Bug caught: the JSON list a registry stores read back as a list, so a stored campaign's
    policy no longer equals the one it was created with and its creation's retry conflicts; or
    the order lost, so launch 2 takes another launch's script."""
    created = policy(llm_scripts=list(reversed(PINNED)))
    stored = json.loads(json.dumps(dataclasses.asdict(created), default=str))

    read = CampaignPolicy.from_stored(stored)

    assert read == created
    assert read.llm_scripts == (PINNED[1], PINNED[0])


def test_the_scripts_are_part_of_the_creation_hash_only_when_set():
    """Bugs caught: every stored campaign's creation hash moved by the new field, so its
    creation's retry conflicts; or the scripts left out of the hash, so two definitions that
    replay different answers read as the same one."""

    def h(c):
        return creation_request_hash(c, actor="owner", actor_role="admin", reason="r")

    plain = campaign(policy=policy())
    # The hash this definition's creation had before the field existed (main's code, as
    # test_unattended_resume pins it).
    assert h(plain) == "fba6b2919996fdecb76cf9b83d04fae9dcd99eda7e2104d3170f3b4acfd1fcfd"
    assert h(campaign(policy=policy(llm_scripts=[]))) == h(plain)
    hashes = {
        h(plain),
        h(campaign(policy=policy(llm_scripts=PINNED))),
        h(campaign(policy=policy(llm_scripts=list(reversed(PINNED))))),
    }
    assert len(hashes) == 3


def test_a_campaign_with_no_scripts_launches_its_request_as_written():
    """Bug caught: every campaign's launch rewritten, so a model campaign's cycle is named a
    script, and the cycle-create preflight refuses it as a script nobody reads."""
    request = {"body": {"execution_overrides": {"campaign_proposal": {"proposal_id": "p"}}}}

    assert scripted_launch(campaign(policy=policy()), request, launched_before=3) is request

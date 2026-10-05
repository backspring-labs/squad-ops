"""A tracked campaign definition is called a campaign's record only when it reconciles (#1941).

What bugs would these catch? A recovered file called the record of a campaign it did not produce, a
changed limit missed by the comparison, or a definition from before §24al's one supervisor bound
failing to reconcile with the campaign it ran (the registry maps its two seat bounds to one).
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "campaign_definition_provenance",
    Path(__file__).resolve().parents[3] / "scripts" / "dev" / "campaign_definition_provenance.py",
)
prov = importlib.util.module_from_spec(_SPEC)
sys.modules["campaign_definition_provenance"] = prov
_SPEC.loader.exec_module(prov)

_REPO = Path(__file__).resolve().parents[3]
_POLICY = {
    "max_cycles": 9,
    "max_elapsed_s": 43200,
    "budget_tokens": 4000000,
    "max_repair_cycles_per_increment": 1,
    "max_retry_cycles_per_increment": 1,
    "max_proposal_run_retries": 1,
    "max_proposal_revisions": 2,
    "max_rejected_proposals_in_row": 2,
    "max_unaccepted_increments": 2,
    "ruling_bound_s": 1800,
    "lease_expiry_s": 3600,
    "launch_blocked_interval_s": 300,
    "launch_blocked_attempts": 6,
    "calibration_profile": "validated-fullstack",
    "proposal_profile": "campaign-increment",
    "squad_profile": "full-38",
}
_OBJECTIVE = {
    "statement": "evolve group_run",
    "allowed_scope": ["backend/**", "frontend/**"],
    "measurement": "three accepted increments",
    "target_accepted_increments": 3,
}


def _stored(policy=None, objective=None, cid="cmp_a"):
    return prov.StoredCampaign(
        cid,
        "group_run",
        objective or _OBJECTIVE,
        policy or _POLICY,
        "t",
        "completed",
        "success",
        "r",
    )


def _spec(**policy_changes):
    return {
        "project_id": "group_run",
        "objective": _OBJECTIVE,
        "policy": {**_POLICY, **policy_changes},
    }


def test_a_definition_reconciles_and_a_changed_limit_is_named():
    assert prov.differences(_spec(), _stored()) == []
    assert prov.differences(_spec(max_cycles=6, ruling_bound_s=900), _stored()) == [
        "policy.max_cycles",
        "policy.ruling_bound_s",
    ]


def test_a_definition_from_before_one_supervisor_bound_reconciles_as_the_registry_maps_it():
    """§24al: a stored policy with a crew's and an owner's bound runs under the crew's."""
    legacy = {k: v for k, v in _POLICY.items() if k != "ruling_bound_s"}
    legacy |= {"crew_ruling_bound_s": 1800, "owner_ruling_bound_s": 600}

    assert prov.differences({**_spec(), "policy": legacy}, _stored()) == []
    assert prov.differences({**_spec(), "policy": legacy}, _stored(policy=legacy)) == []


def test_a_file_that_matches_no_campaign_is_an_example_not_a_record():
    record = prov.Definition("a.yaml", "sha-a", _spec())
    example = prov.Definition("b.yaml", "sha-b", _spec(max_cycles=3))
    unreadable = prov.Definition("c.yaml", "sha-c", {"project_id": "group_run"})

    doc = prov.reconcile(
        [record, example, unreadable],
        [_stored()],
        {"cmp_a": {"identity": "pkg", "artifact_id": "x"}},
    )

    [campaign] = doc["campaigns"]
    assert campaign["definitions"] == [{"path": "a.yaml", "sha256": "sha-a"}]
    assert campaign["package_identity"] == "pkg"
    assert doc["examples_only"] == ["b.yaml", "c.yaml"]


def test_the_set_files_carry_exactly_the_exit_shakeouts_content():
    """The 2.0 set runs what the exit shakeout ran (#1908 §5): its two files reconcile with each
    other and with shakeout 7's, so a drift in either is caught before registration."""
    folder = _REPO / "examples" / "03_group_run" / "campaigns"
    exit_run = prov.load_definitions(folder, _REPO)
    by_name = {Path(d.path).name: d for d in exit_run}
    shakeout = by_name["shakeout-7.yaml"].spec
    as_stored = _stored(policy=shakeout["policy"], objective=shakeout["objective"])

    assert prov.differences(by_name["2-0-0-set-1.yaml"].spec, as_stored) == []
    assert prov.differences(by_name["2-0-0-set-2.yaml"].spec, as_stored) == []


@pytest.mark.parametrize(
    ("recorded", "reconciles"),
    [
        ({"path": "set-1.yaml", "sha256": "sha-set-1"}, True),
        ({"path": "edited.yaml", "sha256": "sha-edited"}, False),
        (None, None),
    ],
    ids=["names-a-file-that-reconciles", "names-a-file-that-does-not", "created-before-1954"],
)
def test_a_recorded_definition_is_the_lookup_and_the_reconciliation_its_check(recorded, reconciles):
    """#1954: two files with the same content both reconcile, and only the record says which one
    made the campaign. Bugs caught: the record dropped from the document, or a recorded file that
    no longer reconciles (edited since, or untracked) reported as if it did."""
    twins = [
        prov.Definition("set-1.yaml", "sha-set-1", _spec()),
        prov.Definition("shakeout-7.yaml", "sha-shakeout-7", _spec()),
    ]
    stored = dataclasses.replace(_stored(), recorded=recorded)

    [campaign] = prov.reconcile(twins, [stored], {})["campaigns"]

    assert len(campaign["definitions"]) == 2
    assert campaign["recorded_definition"] == recorded
    assert campaign["recorded_reconciles"] is reconciles

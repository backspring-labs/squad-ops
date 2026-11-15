"""A Campaign's pinned equipment (SIP-0116 §10, phase 5, #3037): §14's proof.

Entered where the runtime enters a Campaign, through the machinery harness (#3050): its
calibration record heard, each launch built by ``CampaignLaunchService`` through the cycle-create
path, and every later launch decided by the Campaign. The catalog is "redeployed" mid-Campaign by
patching what each seam reads, as a redeploy changes what the runtime's ``packaged_skillsets``
returns.
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.api.routes.cycles import cycles as create_route
from squadops.campaigns.equipment import equipment_transition
from squadops.campaigns.models import CampaignState, CampaignTransition, ControlOperation
from squadops.capabilities import skillsets
from squadops.capabilities.handlers.cycle import run_remote_operation
from squadops.capabilities.skillsets import skill_files_digest
from squadops.execution import dispatched_flow_executor, product_acceptance
from tests.unit.campaigns.machinery import compose
from tests.unit.campaigns.test_machinery_campaign import CID, PROJECT, _rows, _start, _until_settled
from tests.unit.campaigns.test_product_runner_acceptance_wiring import _scenario_catalog
from tests.unit.cycles.skillset_fixture import skillset

pytestmark = [pytest.mark.domain_orchestration]

EQUIPMENT_ROWS = (
    ControlOperation.EQUIPMENT_PINNED,
    ControlOperation.EQUIPMENT_CHANGED,
    ControlOperation.EQUIPMENT_TRANSITION,
)


@pytest.fixture
async def machinery(tmp_path, monkeypatch):
    world = await compose(tmp_path, monkeypatch, campaign=True)
    yield world
    await world.broker.drained()


def _deploy(monkeypatch, catalog: dict) -> None:
    """The runtime redeployed with ``catalog``: every seam that reads the packaged skillsets."""
    for module in (
        skillsets, product_acceptance, run_remote_operation, dispatched_flow_executor,
        create_route,
    ):  # fmt: skip
        monkeypatch.setattr(module, "packaged_skillsets", lambda: catalog)


def _with_an_unrelated_skillset() -> dict:
    catalog = _scenario_catalog()
    catalog["fixture-extra"] = skillset(
        "fixture-extra", "qa", (), {"extra": {"SKILL.md": "---\nname: extra\n---\nUnused.\n"}}
    )
    return catalog


def _with_the_play_skill_revised() -> dict:
    """The qa skillset's play skill, revised: its text changes, and so its digest."""
    catalog = _scenario_catalog()
    qa = catalog["fixture-qa"]
    files = {name: dict(skill) for name, skill in qa.skill_files.items()}
    files["play-scenario"]["SKILL.md"] += "\nRead the console after every step.\n"
    catalog["fixture-qa"] = dataclasses.replace(
        qa,
        skill_files=files,
        skill_digests={name: skill_files_digest(f) for name, f in files.items()},
    )
    return catalog


def _equipment(log) -> list[ControlOperation]:
    return [e.operation for e in log if e.operation in EQUIPMENT_ROWS]


async def test_a_catalog_change_its_work_doesnt_use_has_no_effect_on_the_campaign(
    machinery, monkeypatch
):
    """§14: an unrelated addition to the skillset catalog has no effect. Bug caught: the pin
    compared on the whole catalog, so any redeploy stops every running Campaign."""
    async with machinery.worker():
        await _start(machinery)
        _deploy(monkeypatch, _with_an_unrelated_skillset())
        await _until_settled(machinery)

    log = await machinery.campaigns.control_log(CID)
    assert (await machinery.campaigns.get_campaign(CID)).state is CampaignState.COMPLETED
    assert _rows(log) == ["row 5", "row 7", "row 12", "row 3"]
    assert _equipment(log) == [ControlOperation.EQUIPMENT_PINNED]


async def test_a_changed_assigned_skill_stops_the_next_launch_until_the_owners_transition(
    machinery, monkeypatch
):
    """§14: a change to assigned equipment stops the next launch with the parts named; after a
    recorded transition, earlier evidence and verifier content are unchanged. Bugs caught: a
    redeploy that revises a required skill reaching the next increment silently; the refusal
    naming nothing the owner can act on; or the transition rewriting what earlier increments ran
    with or froze."""
    async with machinery.worker():
        await _start(machinery)
        _deploy(monkeypatch, _with_the_play_skill_revised())
        await _until_settled(machinery)

        stopped = await machinery.campaigns.get_campaign(CID)
        log = await machinery.campaigns.control_log(CID)
        [changed] = [e for e in log if e.operation is ControlOperation.EQUIPMENT_CHANGED]
        [refused] = [e for e in log if e.operation is ControlOperation.LAUNCH_REFUSED]
        [first] = await machinery.registry.list_cycles(PROJECT)
        promoted = [e.binding for e in log if e.operation is ControlOperation.PROMOTE]
        assert stopped.state is CampaignState.ESCALATED
        assert len(changed.binding["parts"]) == 1
        assert changed.binding["parts"][0].startswith("skill fixture-qa/play-scenario: digest ")
        assert "SKILLSET_EQUIPMENT_CHANGED" in refused.reason
        assert "skill fixture-qa/play-scenario" in refused.reason

        await machinery.campaigns.transition(
            CID,
            equipment_transition(
                stopped, log, changed.binding["found_digest"], actor="owner",
                actor_role="admin", reason="the play skill's revision is approved",
                idempotency_key="equipment-1",
            ),
        )  # fmt: skip
        await machinery.campaigns.transition(
            CID,
            CampaignTransition(
                operation=ControlOperation.RESUME, actor="owner", actor_role="admin",
                reason="retry the launch", idempotency_key="resume-1",
                next_state=CampaignState(refused.binding["refused_from"]),
                expected_state=CampaignState.ESCALATED,
            ),
        )  # fmt: skip
        await machinery.launch.drain()
        await _until_settled(machinery)

    log = await machinery.campaigns.control_log(CID)
    cycles = sorted(await machinery.registry.list_cycles(PROJECT), key=lambda c: c.created_at)
    assert (await machinery.campaigns.get_campaign(CID)).state is CampaignState.COMPLETED
    assert _equipment(log) == list(EQUIPMENT_ROWS)
    # Earlier evidence: the first increment's record, and what it froze, as they were.
    assert cycles[0].skillset_record == first.skillset_record
    assert [e.binding for e in log if e.operation is ControlOperation.PROMOTE][
        : len(promoted)
    ] == promoted
    # The retried launch ran with the equipment the owner accepted.
    play = [
        c["digest"] for c in cycles[1].skillset_record["content"] if c["skill"] == "play-scenario"
    ]
    old = [c["digest"] for c in first.skillset_record["content"] if c["skill"] == "play-scenario"]
    assert play != old


ASSIGNED = {"role": "qa", "agent_id": "eve", "skillset": "fixture-qa", "version": 2,
            "digest": "a" * 64}  # fmt: skip


@pytest.mark.parametrize(
    ("change", "named"),
    [
        (
            {"assignment": [{**ASSIGNED, "version": 3, "digest": "b" * 64}]},
            "assignment qa: fixture-qa 2 (digest aaaaaaaaaaaa…) from eve is now fixture-qa 3 "
            "(digest bbbbbbbbbbbb…) from eve",
        ),
        (
            {"assignment": [{**ASSIGNED, "agent_id": "zed"}]},
            "assignment qa: fixture-qa 2 (digest aaaaaaaaaaaa…) from eve is now fixture-qa 2 "
            "(digest aaaaaaaaaaaa…) from zed",
        ),
        ({"base_set": "base@2"}, "the base set was base@1 and is base@2"),
        ({"requirements": [{"role": "qa"}]}, "the requirements differ from the pinned ones"),
    ],
    ids=["skillset revised", "supplying agent changed", "base set", "requirements"],
)
def test_each_changed_part_of_the_equipment_is_named(change, named):
    """Bug caught: a refusal that says the equipment changed and not where, so the owner can't
    tell a revised skillset from a reassigned agent before accepting it."""
    from squadops.campaigns.equipment import changed_parts, equipment, equipment_digest

    record = {"base_set": {"version": "base@1"}, "requirements": [], "assignment": [ASSIGNED],
              "offered": [], "content": []}  # fmt: skip
    pinned = equipment(record)
    found = {**pinned, **change}

    assert changed_parts(pinned, found) == [named]
    assert equipment_digest(found) != equipment_digest(pinned)
    # The squad's roster hash and the development profile's fingerprint aren't equipment.
    other = {**record, "squad": {"roster_hash": "x"}, "development_profile": {"fingerprint": "y"}}
    assert equipment_digest(equipment(other)) == equipment_digest(pinned)


def test_a_cycle_with_no_record_is_never_pinned_as_having_no_equipment():
    """Bug caught: a missing record read as empty equipment, so a Campaign pins nothing and every
    later launch matches it."""
    from squadops.campaigns.equipment import EquipmentUnreadable, equipment

    with pytest.raises(EquipmentUnreadable, match="no skillset record"):
        equipment(None)
    with pytest.raises(EquipmentUnreadable, match="has no assignment"):
        equipment({"base_set": {}, "requirements": [], "offered": [], "content": []})

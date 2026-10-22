"""Re-binding a reference's bound revision (SIP-0110 Appendix A §3.7; #2179).

Entered where the operator re-binds (``POST /api/v1/projects/{p}/memory-snapshots/{kind}/{id}/rebindings``)
and where the live composer supplies (``supply_lessons`` through ``SnapshotRecall``), over one store,
with a resolver standing in for a family's.
"""

from __future__ import annotations

import pytest

from adapters.memory.recall import SnapshotRecall
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.memory.pinning import pin_campaign, pin_standalone_cycle
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.memory.task_instructions import TaskInstructionsUnavailable
from tests.unit.api.test_rebinding import DESIGN, NOW, RECORDS, WHERE, _World
from tests.unit.campaigns.builders import campaign
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan
from tests.unit.memory.test_reference_binding import _Resolver

pytestmark = [pytest.mark.auth, pytest.mark.domain_memory]


def _instructed(world: _World, resolver: _Resolver) -> str:
    """A project instruction naming a required reference written ``@current``."""
    world.client.app.state.reference_resolvers = {"fake": resolver}
    response = world.client.post(
        RECORDS,
        json={"kind": "instruction", "scope": "project", "project_id": "group_run",
              "body": "Read the spec.", "applicability": WHERE,
              "references": [{"ref": "fake:doc:spec@current", "required": True}]},
    )  # fmt: skip
    assert response.status_code == 201, response.text
    return response.json()["record_id"]


async def _handed(world: _World, cycle, run_id: str):
    envelopes = await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(world.store, records=world.records),
        unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id=run_id, now=NOW,
    )  # fmt: skip
    [design] = [e for e in envelopes if str(e.task_type) == DESIGN]
    return design.inputs[PROJECT_INSTRUCTIONS_INPUT]["instructions"]


async def test_a_task_held_on_a_reference_admission_couldnt_bind_is_released_by_rebinding_it():
    """T8's release for a pinned project instruction: a re-binding, not a revision alone (§3.6,
    §3.7). Bugs caught: the re-binding refused because the record's revision is unchanged, so the
    task stays held until someone revises an instruction nothing was wrong with; the reference left
    unbound after it; the held dispatch read as having been handed the instruction, which sends the
    re-binding down the restart path."""
    world, resolver = _World(), _Resolver()
    record_id = _instructed(world, resolver)
    cycle = _framing_cycle()
    await world.cycles.create_cycle(cycle)
    resolver.refuse = "the spec service didn't answer"
    await pin_standalone_cycle(
        world.store, cycle, now=NOW, records=world.records, resolvers={"fake": resolver}
    )
    with pytest.raises(TaskInstructionsUnavailable, match="fake:doc:spec@current unbound"):
        await _handed(world, cycle, "run_held0001")
    resolver.refuse = None

    response = world.rebind(record_id, why="the spec service answers again")

    assert response.status_code == 201, response.text
    rebinding = response.json()["rebinding"]
    assert rebinding["replaced"]["revision"] == rebinding["replacement"]["revision"] == 1
    stored = await world.store.get_snapshot(*unit_of(cycle))
    [instruction] = stored.instructions
    assert ([(r.ref, r.digest) for r in instruction.references], instruction.unbound) == (
        [("fake:doc:spec@r1", "sha256:r1")],
        (),
    )
    [handed] = await _handed(world, cycle, "run_after0001")
    assert [r["ref"] for r in handed["references"]] == ["fake:doc:spec@r1"]


async def test_a_rebinding_that_would_change_nothing_is_refused():
    """Bug caught: a re-binding recorded as an intervention when the unit already binds the
    revision and every reference as they bind now, which sets the unit's measurements apart for
    nothing."""
    world, resolver = _World(), _Resolver()
    record_id = _instructed(world, resolver)
    cycle = _framing_cycle()
    await world.cycles.create_cycle(cycle)
    await pin_standalone_cycle(
        world.store, cycle, now=NOW, records=world.records, resolvers={"fake": resolver}
    )
    before = await world.store.get_snapshot(*unit_of(cycle))

    response = world.rebind(record_id, why="nothing moved")

    assert response.status_code == 422, response.text
    assert "as they bind now" in response.json()["detail"]["error"]["message"]
    assert await world.store.get_snapshot(*unit_of(cycle)) == before


async def test_a_campaigns_reference_is_rebound_by_a_revision_not_in_place():
    """§5ad: each of a campaign's cycles binds its references at its own commit, for its life.
    Bug caught: a campaign's snapshot re-bound to a new reference revision that none of its cycles
    reads, recorded as an intervention that changed nothing they were handed."""
    world, resolver = _World(), _Resolver()
    record_id = _instructed(world, resolver)
    cmp = campaign("cmp_refs")
    await world.campaigns.create_campaign(
        cmp, actor="ada", actor_role="admin", reason="test", idempotency_key="create"
    )
    await pin_campaign(
        world.store, cmp, now=NOW, records=world.records, resolvers={"fake": resolver}
    )
    resolver.revision = "r2"

    response = world.rebind(record_id, kind="campaign", unit_id="cmp_refs", why="the spec moved")

    assert response.status_code == 422, response.text
    assert "each of its cycles" in response.json()["detail"]["error"]["message"]

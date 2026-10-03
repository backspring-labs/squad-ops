"""The box lease's changes (SIP-0109 §9.3; #1802), entering at the registry the lease routes and
the executor read: the lease and its control-log row commit together, or the refusal is recorded
and the lease is unchanged."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.campaigns.box import LeaseHolder
from squadops.campaigns.models import (
    CampaignState,
    CampaignTransition,
    ControlOperation,
    ControlOperationRefused,
    ControlOutcome,
    RefusalReason,
)
from tests.unit.campaigns.builders import campaign, move

S = CampaignState
OP = ControlOperation


async def _registry(*campaign_ids: str, at: CampaignState = S.AWAITING_RULING):
    reg = MemoryCampaignRegistry()
    for cid in campaign_ids:
        await reg.create_campaign(
            campaign(cid), actor="owner", actor_role="owner", reason="r", idempotency_key=cid
        )
        for i, state in enumerate((S.CALIBRATING, S.AT_PROPOSAL, S.AWAITING_RULING)):
            await reg.transition(cid, move(state, f"{cid}-{i}"))
        if at is not S.AWAITING_RULING:
            await reg.transition(cid, move(at, f"{cid}-at"))
    return reg


def _lease(op: ControlOperation, held_by: str, key: str, expires_in_s: int = 600):
    binding = {"held_by": held_by}
    if op is OP.LEASE_ACQUIRE:
        binding["expires_in_s"] = expires_in_s
    return CampaignTransition(
        operation=op,
        actor=held_by,
        actor_role="campaign-supervisor",
        reason="the increment gate",
        idempotency_key=key,
        next_state=None,
        binding=binding,
    )


async def test_the_supervisor_holds_the_box_from_its_gate_until_it_gives_it_back():
    """Bug caught: the lease and its row not committing together, or the acquire moving the
    campaign's state, or a release leaving the supervisor holding the box."""
    reg = await _registry("cmp_a")
    acquired = await reg.change_box_lease(
        "cmp_a", _lease(OP.LEASE_ACQUIRE, "crew", "k1"), runs_in_flight=()
    )
    lease = await reg.box_lease()
    assert (lease.holder, lease.held_by, lease.campaign_id) == (
        LeaseHolder.SUPERVISOR,
        "crew",
        "cmp_a",
    )
    assert 590 <= (lease.expires_at - datetime.now(UTC)).total_seconds() <= 600
    assert (acquired.entry.outcome, acquired.entry.next_state) == (
        ControlOutcome.APPLIED,
        S.AWAITING_RULING,
    )

    await reg.change_box_lease("cmp_a", _lease(OP.LEASE_RELEASE, "crew", "k2"), runs_in_flight=())
    released = await reg.box_lease()
    assert (released.holder, released.supervisor_holds(datetime.now(UTC))) == (
        LeaseHolder.SQUAD,
        False,
    )


@pytest.mark.parametrize(
    ("case", "refusal"),
    [
        ("outside the gate", RefusalReason.GATE_NOT_OPEN),
        ("a run in flight", RefusalReason.RUN_IN_FLIGHT),
        ("another supervisor holds it", RefusalReason.BOX_HELD),
        ("released by someone who does not hold it", RefusalReason.NOT_LEASE_HOLDER),
    ],
)
async def test_a_refused_change_is_recorded_and_leaves_the_lease_as_it_was(case, refusal):
    """Bug caught: a supervisor taking the box beside a running cycle, or from another holder,
    or a release by someone else freeing a box its holder still uses; and a refusal that leaves
    no row, so the control log cannot show the guarantee was held."""
    reg = await _registry(
        "cmp_a", "cmp_b", at=S.BUILDING if case == "outside the gate" else S.AWAITING_RULING
    )
    if case in ("another supervisor holds it", "released by someone who does not hold it"):
        await reg.change_box_lease(
            "cmp_a", _lease(OP.LEASE_ACQUIRE, "crew-a", "hold"), runs_in_flight=()
        )
    before = await reg.box_lease()
    attempt = {
        "outside the gate": ("cmp_a", _lease(OP.LEASE_ACQUIRE, "crew", "x"), ()),
        "a run in flight": ("cmp_a", _lease(OP.LEASE_ACQUIRE, "crew", "x"), ("run_1",)),
        "another supervisor holds it": ("cmp_b", _lease(OP.LEASE_ACQUIRE, "crew-b", "x"), ()),
        "released by someone who does not hold it": (
            "cmp_a",
            _lease(OP.LEASE_RELEASE, "crew-b", "x"),
            (),
        ),
    }[case]

    with pytest.raises(ControlOperationRefused) as refused:
        await reg.change_box_lease(attempt[0], attempt[1], runs_in_flight=attempt[2])

    assert refused.value.entry.refusal is refusal
    assert (await reg.box_lease()) == before
    assert (await reg.control_log(attempt[0]))[-1].refusal is refusal


async def test_an_expired_lease_holds_nothing_and_the_same_holder_renews():
    """Bug caught: a crashed supervisor's lease holding the box forever; and a renewal by the
    holder being refused as if another supervisor held it."""
    reg = await _registry("cmp_a", "cmp_b")
    await reg.change_box_lease(
        "cmp_a", _lease(OP.LEASE_ACQUIRE, "crew-a", "k1", expires_in_s=0), runs_in_flight=()
    )
    await reg.change_box_lease("cmp_b", _lease(OP.LEASE_ACQUIRE, "crew-b", "k2"), runs_in_flight=())
    first = await reg.box_lease()
    await reg.change_box_lease(
        "cmp_b", _lease(OP.LEASE_ACQUIRE, "crew-b", "k3", expires_in_s=900), runs_in_flight=()
    )
    renewed = await reg.box_lease()
    assert (first.held_by, renewed.held_by, renewed.acquired_at) == (
        "crew-b",
        "crew-b",
        first.acquired_at,
    )
    assert renewed.expires_at > first.expires_at


async def test_a_lease_operation_never_commits_without_its_lease():
    """Bug caught: a lease row written through the generic transition, recording a change the
    lease never made."""
    reg = await _registry("cmp_a")
    with pytest.raises(ValueError, match="change_box_lease"):
        await reg.transition("cmp_a", _lease(OP.LEASE_ACQUIRE, "crew", "k"))
    with pytest.raises(ValueError, match="does not change the box lease"):
        await reg.change_box_lease("cmp_a", move(S.BUILDING, "k2"), runs_in_flight=())
    assert await reg.box_lease() is None

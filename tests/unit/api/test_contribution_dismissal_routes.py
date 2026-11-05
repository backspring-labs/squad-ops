"""``POST /api/v1/campaigns/{id}/contribution-dismissal`` (SIP-0109 §24dg, #2926), entered at the
route with the real authorization adapter, over ``test_close_contribution``'s world: Tally, a real
managed clone, a Campaign closed by its accepted increment and its contribution opened through the
route. A closed request is what a sync records, set here on the record."""

from __future__ import annotations

import dataclasses

import pytest

from squadops.auth.models import Role
from squadops.campaigns.models import ControlOperation, ControlOutcome
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.campaigns.test_close_contribution import CID, URL, _World

UNINTEGRATED = f"/api/v1/projects/{PROJECT}/unintegrated-increments"
CONTRIBUTIONS = f"/api/v1/projects/{PROJECT}/contributions"
DISMISS = f"/api/v1/campaigns/{CID}/contribution-dismissal"
LOG = f"/api/v1/campaigns/{CID}/control-log"
BODY = {"reason": "the owner refused this work", "idempotency_key": "d-1"}


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


async def _contributed(tmp_path, state: str = "closed", **fields) -> _World:
    """The Campaign closed, its contribution opened by the supervisor, standing at ``state``."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion()
    opened = world.client().post(f"/api/v1/campaigns/{CID}/contributions", json={"token": "t"})
    assert opened.status_code == 201, opened.text
    world.book.recorded[0] = dataclasses.replace(world.book.recorded[0], state=state, **fields)
    return world


async def _dismissals(world: _World) -> list:
    return [
        e
        for e in await world.campaigns.control_log(CID)
        if e.operation is ControlOperation.CONTRIBUTION_DISMISSED
    ]


def _code(resp) -> tuple[int, str]:
    return resp.status_code, resp.json()["detail"]["error"]["code"]


async def test_the_owner_clears_the_gate_and_the_record_says_who_and_why(tmp_path):
    """The issue, end to end at the routes (anti-pattern 6a). Bugs caught: the row written and the
    unintegrated set not reading it, so the gate stays shut; the contribution deleted or rewritten,
    so the history loses what was opened; who dismissed it and why not reaching the control log."""
    world = await _contributed(tmp_path)
    owner = world.client(Role.ADMIN)
    assert [i["standing"] for i in owner.get(UNINTEGRATED).json()] == ["contribution_closed"]

    resp = owner.post(DISMISS, json={**BODY, "source_ref": "https://chat.example.invalid/t/9"})

    assert resp.status_code == 201, resp.text
    entry = resp.json()["entry"]
    assert (entry["operation"], entry["outcome"]) == ("contribution_dismissed", "applied")
    assert owner.get(UNINTEGRATED).json() == []
    [held] = owner.get(CONTRIBUTIONS).json()
    assert (held["contribution"]["state"], held["contribution"]["review_url"]) == ("closed", URL)
    row = owner.get(LOG).json()[-1]
    commit = world.book.recorded[0].commit
    assert (row["actor"], row["reason"]) == (entry["actor"], "the owner refused this work")
    assert row["binding"] == {
        "commit": commit,
        "review_url": URL,
        "source_ref": "https://chat.example.invalid/t/9",
    }
    assert resp.json()["campaign"]["state"] == "completed"


@pytest.mark.parametrize(
    ("role", "status"),
    [
        (Role.ADMIN, 201),
        (Role.CAMPAIGN_SUPERVISOR, 403),
        (Role.CAMPAIGN_TRIAGE, 403),
        (Role.OPERATOR, 403),
    ],
)
async def test_only_the_owner_may_dismiss(tmp_path, role, status):
    """Bug caught: the route on ``campaigns:manage``, where the contribution's own write is, so the
    crew writes off the work blocking its gate and opens the gate for itself."""
    world = await _contributed(tmp_path)

    resp = world.client(role).post(DISMISS, json=BODY)

    assert resp.status_code == status, resp.text
    assert len(await _dismissals(world)) == (1 if status == 201 else 0)


@pytest.mark.parametrize(
    ("state", "fields"),
    [
        ("pending", {}),
        ("integrated", {"integrated_commit": "m" * 40}),
        ("closed", {"integrated_commit": "m" * 40}),
    ],
    ids=["pending", "integrated", "closed yet merged"],
)
async def test_anything_but_closed_and_unmerged_is_refused_and_writes_nothing(
    tmp_path, state, fields
):
    """Bugs caught: work that may still land written off, or work that landed; a refusal that
    leaves a row the unintegrated set then reads as a dismissal."""
    world = await _contributed(tmp_path, state, **fields)

    resp = world.client(Role.ADMIN).post(DISMISS, json=BODY)

    assert _code(resp) == (409, "CONTRIBUTION_NOT_DISMISSABLE")
    assert await _dismissals(world) == []


async def test_another_campaigns_closed_contribution_is_not_this_ones(tmp_path):
    """Bug caught: the Project's first contribution read as the Campaign's, so a closed one of
    another Campaign lets the owner dismiss this one's pending work."""
    world = await _contributed(tmp_path, "pending")
    ours = world.book.recorded[0]
    world.book.recorded.insert(0, dataclasses.replace(ours, cycle_id="cmp_other", state="closed"))

    resp = world.client(Role.ADMIN).post(DISMISS, json=BODY)

    assert _code(resp) == (409, "CONTRIBUTION_NOT_DISMISSABLE")
    assert await _dismissals(world) == []


async def test_a_campaign_with_no_contribution_and_an_unknown_one_are_refused(tmp_path):
    """Bugs caught: a dismissal of nothing recorded, which would clear a later contribution's row
    before it existed; a 500 for an unknown id."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion()
    owner = world.client(Role.ADMIN)

    assert _code(owner.post(DISMISS, json=BODY)) == (409, "CONTRIBUTION_NOT_DISMISSABLE")
    assert await _dismissals(world) == []
    assert _code(owner.post("/api/v1/campaigns/cmp_nobody/contribution-dismissal", json=BODY)) == (
        404,
        "CAMPAIGN_NOT_FOUND",
    )


async def test_a_reason_is_required(tmp_path):
    """Bug caught: the record of why, which is all that's left of the work, written blank."""
    world = await _contributed(tmp_path)
    owner = world.client(Role.ADMIN)

    assert owner.post(DISMISS, json={"idempotency_key": "d-1"}).status_code == 422
    assert owner.post(DISMISS, json={**BODY, "reason": "  "}).status_code == 422
    assert await _dismissals(world) == []


async def test_a_retry_replays_whatever_became_of_the_record_and_a_new_key_is_refused(tmp_path):
    """Bugs caught: a retry writing a second row, or refused because the record moved since; a
    second dismissal under a new key piling rows onto one decision; a key reused for another
    source read as the same act."""
    world = await _contributed(tmp_path)
    owner = world.client(Role.ADMIN)
    first = owner.post(DISMISS, json=BODY)
    assert first.status_code == 201, first.text

    twice = owner.post(DISMISS, json={**BODY, "idempotency_key": "d-2"})
    assert _code(twice) == (409, "CONTRIBUTION_NOT_DISMISSABLE")

    world.book.recorded[0] = dataclasses.replace(
        world.book.recorded[0], state="integrated", integrated_commit="m" * 40
    )
    again = owner.post(DISMISS, json=BODY)

    assert again.status_code == 201, again.text
    assert again.json()["replayed"] is True
    assert again.json()["entry"]["entry_id"] == first.json()["entry"]["entry_id"]
    rows = await _dismissals(world)
    assert [e.outcome for e in rows] == [ControlOutcome.APPLIED]

    other = owner.post(DISMISS, json={**BODY, "source_ref": "https://chat.example.invalid/t/2"})
    assert other.status_code == 409, other.text

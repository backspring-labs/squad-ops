"""A task instruction captured from chat (SIP-0110 Appendix A §3.5, §3.7; #2180 stage B's task half),
entered at the chat routes with the agent's proposal, confirmed on the card, and its dispatch composed
by the live composer (``supply_lessons`` through ``SnapshotRecall``).

What bugs would these catch? A capture that bypasses the records API's rules for an intervention, so
an instruction lands on a task that already dispatched; that refusal swallowed into a 503 "not
saved"; a lesson reaching the lessons-disabled control through "apply lesson X to this task"; an
operator capturing for a campaign's cycle, which needs ``campaigns:supervise``; a campaign cycle's
capture the intervention ledger never sees; the card offered nothing to fill its target from.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from datetime import UTC, datetime

import httpx
import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.memory.recall import SnapshotRecall
from squadops.auth.models import Role
from squadops.campaigns.models import ControlOperation
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import pin_unit
from squadops.memory.recall import RecallQuery
from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT
from tests.unit.api.test_chat_memory_routes import world  # noqa: F401 — the chat world fixture
from tests.unit.api.test_dispatch_turns import _dispatching, _still_waiting
from tests.unit.campaigns.builders import campaign
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan

pytestmark = [pytest.mark.auth, pytest.mark.domain_memory]

DESIGN = "development.design_plan"
NOW = datetime(2026, 10, 20, tzinfo=UTC)
LESSON = "pat_0123456789abcdef@2"
#: Cycle ids as the registry mints them: a card keeps only a well-formed one.
CYCLE, CAMP_CYCLE = "cyc_0123456789ab", "cyc_ba9876543210"


def _cycle(**change):
    return dataclasses.replace(_framing_cycle(), **{"cycle_id": CYCLE, **change})


def _registries(chat):
    cycles, campaigns = MemoryCycleRegistry(), MemoryCampaignRegistry()
    chat.client.app.state.cycle_registry = cycles
    chat.client.app.state.campaign_registry = campaigns
    return cycles, campaigns


def _proposed(chat, cycle_id: str, role: str = Role.ADMIN, said: str | None = None, **extra):
    """The agent proposes a task instruction for ``cycle_id``, which the person named unless
    ``said`` says otherwise; the card shows it."""
    chat.agent.reply = (
        "I'll pass it on.\n<memory-capture>"
        + json.dumps(
            {"text": "Cover the empty list.", "kind": "instruction", "scope": "task",
             "target": {"cycle_id": cycle_id, "task_types": [DESIGN]}, **extra}
        )
        + "</memory-capture>"
    )  # fmt: skip
    said = f"tell design in {cycle_id} to cover it" if said is None else said
    response, events = chat.as_("ada", role).say(said, project_id="group_run")
    [card] = [e["capture"] for e in events if e.get("capture")]
    return response.headers["X-Session-Id"], card


def _confirm(chat, session_id: str, card: dict, **change):
    body = {
        "message_id": card["source_message_id"], "text": card["text"], "kind": "instruction",
        "scope": "task", "target": card["target"], **change,
    }  # fmt: skip
    return chat.client.post(f"/api/v1/chat/sessions/{session_id}/captures", json=body)


async def _dispatch(chat, cycle, run_id: str = "run_recall0001"):
    envelopes = await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(chat.store, records=chat.records),
        unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id=run_id, now=NOW,
    )  # fmt: skip
    [design] = [e for e in envelopes if str(e.task_type) == DESIGN]
    return (design.inputs.get(TASK_INSTRUCTIONS_INPUT) or {}).get("instructions", [])


async def test_a_captured_task_instruction_reaches_its_task_as_an_intervention(world):  # noqa: F811
    """Wired from the agent's proposal to the dispatch. Bugs caught: a card with no target to
    confirm; a captured instruction never reaching its task, or reaching it unmarked."""
    cycles, _ = _registries(world)
    cycle = _cycle()
    await cycles.create_cycle(cycle)
    session_id, card = _proposed(world, cycle.cycle_id)

    response = _confirm(world, session_id, card)
    handed = await _dispatch(world, cycle)

    assert card["target"] == {"cycle_id": cycle.cycle_id, "task_types": [DESIGN]}
    assert response.status_code == 201, response.text
    record_id = response.json()["record_id"]
    assert [(i["record_id"], i.get("intervention")) for i in handed] == [(record_id, True)]
    assert f"{cycle.cycle_id}'s {DESIGN}" in response.json()["reply"]["content"]


@pytest.mark.parametrize(("carries", "status"), [("continuations", 201), ("forks", 422)])
async def test_a_capture_given_to_carry_is_stored_to_carry(world, carries, status):  # noqa: F811
    """SIP-0110 §3.7 (#2178), the second read of PR #2556. Bugs caught: the card's target taking
    ``carries_into`` and the record dropping it, so the person is told it carries and a repair of
    the cycle runs without it; a value the records refuse answered as a failure to save."""
    cycles, _ = _registries(world)
    cycle = _cycle()
    await cycles.create_cycle(cycle)
    session_id, card = _proposed(world, cycle.cycle_id)

    response = _confirm(world, session_id, card, target={**card["target"], "carries_into": carries})

    assert response.status_code == status, response.text
    stored = [r.current.target.carries_into for r in await world.records.list_project("group_run")]
    assert stored == ([carries] if status == 201 else [])


async def test_a_capture_for_a_task_that_already_dispatched_is_refused_as_such(world):  # noqa: F811
    """Bugs caught: chat landing an instruction the records API refuses; the refusal caught by the
    capture's catch-all and answered as a 503 "not saved", with that reply added to the chat."""
    cycles, _ = _registries(world)
    cycle = _cycle()
    await cycles.create_cycle(cycle)
    await _dispatch(world, cycle)
    session_id, card = _proposed(world, cycle.cycle_id)
    replies_before = len(world.chats.messages)

    response = _confirm(world, session_id, card)

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "TASK_DISPATCHED"
    assert await world.records.list_project("group_run") == []
    assert len(world.chats.messages) == replies_before


async def test_a_capture_waits_for_a_dispatch_being_composed(world):  # noqa: F811
    """#2545. Bug caught: the capture's dispatched check run while the task's dispatch is between
    reading its instructions and disclosing them, so the capture lands for a task that dispatched
    without it."""
    cycles, _ = _registries(world)
    cycle = _cycle()
    await cycles.create_cycle(cycle)
    session_id, card = _proposed(world, cycle.cycle_id)
    entered, release = asyncio.Event(), asyncio.Event()
    exposure = Exposure(
        run_id="run_recall0001", task_id="t_design", cycle_id=cycle.cycle_id, agent_id="nat",
        seam="plan_authoring", query=RecallQuery(project_id="group_run", task_type=DESIGN),
        recalled={}, recorded_at=NOW,
    )  # fmt: skip
    dispatching = asyncio.create_task(
        _dispatching(world.store, unit_of(cycle), exposure, entered, release)
    )
    await entered.wait()
    body = {"message_id": card["source_message_id"], "text": card["text"], "kind": "instruction",
            "scope": "task", "target": card["target"]}  # fmt: skip
    transport = httpx.ASGITransport(app=world.client.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        capture = asyncio.create_task(
            client.post(f"/api/v1/chat/sessions/{session_id}/captures", json=body)
        )
        waited = await _still_waiting(capture)
        release.set()
        await dispatching
        response = await capture

    assert waited
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "TASK_DISPATCHED"
    assert await world.records.list_project("group_run") == []


@pytest.mark.parametrize(("disabled", "status"), [(True, 422), (False, 201)])
async def test_a_task_instruction_applying_a_lesson_never_reaches_the_lessons_disabled_control(
    world,  # noqa: F811
    disabled,
    status,
):
    """§3.7's guarantee (T9). Bug caught: "apply lesson X to this task" reaching a unit that
    declares lessons disabled, so the control arm is handed the lesson after all; and the lesson
    left off the provenance of one that may have it."""
    cycles, _ = _registries(world)
    cycle = _cycle()
    await cycles.create_cycle(cycle)
    await pin_unit(
        world.store, unit_kind=UnitKind.CYCLE, unit_id=cycle.cycle_id, project_id="group_run",
        pinned_at=NOW, disabled=disabled, records=world.records,
    )  # fmt: skip
    session_id, card = _proposed(world, cycle.cycle_id, lesson=LESSON)

    response = _confirm(world, session_id, card, lesson_revision=card["lesson_revision"])

    assert card["lesson_revision"] == LESSON
    assert response.status_code == status, response.text
    stored = await world.records.list_project("group_run")
    if disabled:
        assert "lessons disabled" in response.json()["detail"]["error"]["message"]
        assert stored == []
    else:
        assert stored[0].current.source.ids["lesson_revision"] == LESSON


async def test_a_campaign_cycles_capture_needs_the_supervisor_and_is_a_control_log_row(world):  # noqa: F811
    """§3.3, §3.5. Bugs caught: an operator directing a campaign's cycle from chat; the
    supervisor's capture invisible to the intervention ledger."""
    cycles, campaigns = _registries(world)
    cmp = campaign("cmp_chat")
    await campaigns.create_campaign(
        cmp, actor="ada", actor_role="admin", reason="test", idempotency_key="create"
    )
    camp_cycle = _cycle(cycle_id=CAMP_CYCLE, campaign_id="cmp_chat")
    await cycles.create_cycle(camp_cycle)

    session_id, card = _proposed(world, CAMP_CYCLE, role=Role.OPERATOR)
    refused = _confirm(world, session_id, card)
    session_id, card = _proposed(world, CAMP_CYCLE, role=Role.ADMIN)
    saved = _confirm(world, session_id, card)

    assert refused.status_code == 403
    assert saved.status_code == 201, saved.text
    [row] = [
        e for e in await campaigns.control_log("cmp_chat")
        if e.operation is ControlOperation.INSTRUCT
    ]  # fmt: skip
    assert (row.binding["action"], row.binding["record_id"]) == ("add", saved.json()["record_id"])
    assert saved.json()["control_log_entry_id"] == row.entry_id


@pytest.mark.parametrize(
    ("target", "says"),
    [
        (None, "names its cycle and its task types"),
        ({"cycle_id": "", "task_types": [DESIGN]}, "names its target cycle"),
    ],
    ids=["no-target", "a-cycle-the-card-left-blank"],
)
async def test_a_task_instruction_without_its_target_is_refused(world, target, says):  # noqa: F811
    """Bug caught: a cycle the card left blank (the agent named none, or a malformed one) answered
    as a 500 when the person confirmed without filling it."""
    cycles, _ = _registries(world)
    await cycles.create_cycle(_cycle())
    session_id, card = _proposed(world, CYCLE)

    response = _confirm(world, session_id, card, target=target)

    assert response.status_code == 422
    assert says in response.json()["detail"]["error"]["message"]


async def test_the_card_keeps_a_cycle_only_when_the_person_named_it(world):  # noqa: F811
    """The second reader's finding. Bug caught: the agent choosing the cycle, a real one the person
    never named, pre-filled on the card for a confirmation that reads as theirs."""
    cycles, _ = _registries(world)
    await cycles.create_cycle(_cycle())

    _, named = _proposed(world, CYCLE)
    _, unnamed = _proposed(world, CYCLE, said="tell design to cover the empty list")

    assert named["target"]["cycle_id"] == CYCLE
    assert unnamed["target"] == {"cycle_id": "", "task_types": [DESIGN]}


async def test_a_malformed_lesson_citation_is_refused_never_dropped(world):  # noqa: F811
    """The second reader's finding. Bug caught: a lesson named without its revision dropped by the
    parser, so the instruction is stored with no citation and reaches the lessons-disabled
    control unchecked."""
    cycles, _ = _registries(world)
    await cycles.create_cycle(_cycle())
    session_id, card = _proposed(world, CYCLE, lesson="pat_0123456789abcdef")

    response = _confirm(world, session_id, card, lesson_revision=card["lesson_revision"])

    assert card["lesson_revision"] == "pat_0123456789abcdef"
    assert response.status_code == 422
    assert await world.records.list_project("group_run") == []

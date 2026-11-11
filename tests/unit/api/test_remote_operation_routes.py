"""``/api/v1/remote-operations`` as a requester calls it (SIP-0117 R3.3, R5.6).

Entered at the routes with the agent's identity, over the real registry and the memory store.
The worker's side is the real worker routes in the same app.
"""

from __future__ import annotations

import pytest

from squadops.auth.models import Role
from squadops.remote_execution import leasing
from squadops.remote_execution.wire import request_to_wire, result_to_wire
from tests.unit.api.worker_world import World
from tests.unit.remote_execution.registry_contract import passing, request

pytestmark = pytest.mark.auth

OPERATIONS = "/api/v1/remote-operations"
ORIGIN = {"task_id": "task-7", "agent_id": "eve"}


def _body(**over) -> dict:
    return {"request": request_to_wire(request()), "origin": ORIGIN, "max_attempts": 2, **over}


def _served_world() -> tuple[World, str]:
    """A world with one worker registered, called from here on as the agent."""
    w = World()
    session = w.register()
    w.as_(Role.AGENT)
    return w, session


def _error(reply) -> dict:
    return reply.json()["detail"]["error"]


def test_an_operation_is_queued_claimed_and_read_with_its_result():
    """The requester's whole exchange. Bug caught: a field lost between the registry and the
    body (the state, the result, the lease's length), or an origin that doesn't say who
    asked."""
    w, session = _served_world()

    created = w.client.post(OPERATIONS, json=_body(origin={**ORIGIN, "requested_by": "forged"}))
    operation_id = created.json()["operation_id"]
    claim = w.as_(Role.WORKER).post(f"/api/v1/workers/sessions/{session}/claims").json()["claim"]
    held = w.as_(Role.AGENT).get(f"{OPERATIONS}/{operation_id}")
    w.as_(Role.WORKER).post(
        f"/api/v1/workers/sessions/{session}/results",
        json={
            "fence": {k: claim[k] for k in ("operation_id", "attempt", "lease_id")},
            "result": result_to_wire(passing()),
        },
    )
    settled = w.as_(Role.AGENT).get(f"{OPERATIONS}/{operation_id}")

    assert created.status_code == 201
    assert created.json() == {
        "operation_id": operation_id,
        "state": "queued",
        "attempt": 0,
        "max_attempts": 2,
        "cancel_requested": False,
        "created_at": "2026-11-10T15:00:00Z",
        "settled_at": None,
        "result": None,
        "lease_seconds": leasing.LEASE_SECONDS,
    }
    assert claim["operation_id"] == operation_id
    assert (held.json()["state"], held.json()["attempt"], held.json()["result"]) == (
        "claimed",
        1,
        None,
    )
    assert settled.json() == {
        **created.json(),
        "state": "settled",
        "attempt": 1,
        "settled_at": "2026-11-10T15:00:00Z",
        "result": result_to_wire(passing()),
    }
    # The route's own word on who asked replaces what the body said under that key.
    assert w.operation(operation_id).origin == {**ORIGIN, "requested_by": Role.AGENT}


def test_with_no_worker_being_heard_from_nothing_is_queued_and_the_answer_says_which():
    """Bug caught: an operation queued for nobody, which its requester waits on for the whole
    of its wait; or "offline" told as "nobody serves it"."""
    w = World()
    unserved = w.as_(Role.AGENT).post(OPERATIONS, json=_body())
    session = w.as_(Role.WORKER) and w.register()
    w.clock.advance(leasing.SESSION_SILENT_SECONDS + 1)
    offline = w.as_(Role.AGENT).post(OPERATIONS, json=_body())
    w.as_(Role.WORKER).post(
        f"/api/v1/workers/sessions/{session}/heartbeats", json={"runtime_status": "online"}
    )
    nothing = w.client.post(f"/api/v1/workers/sessions/{session}/claims")

    assert (unserved.status_code, _error(unserved)["code"]) == (409, "NO_WORKER_FOR_OPERATION")
    assert _error(unserved)["details"] == {
        "reason": "no registered worker serves fixture-editor/play_scenario",
        "unreachable": [],
    }
    assert offline.status_code == 409
    assert _error(offline)["details"] == {
        "reason": "macbook serves fixture-editor/play_scenario and is offline "
        "(last heard from at 2026-11-10T15:00:00+00:00)",
        "unreachable": ["macbook"],
    }
    assert nothing.json() == {"claim": None}


@pytest.mark.parametrize(
    ("over", "code", "details"),
    [
        (
            {"request": {**request_to_wire(request()), "mode": 7}},
            "OPERATION_REQUEST_INVALID",
            {"defect": "request.mode is int, and text is needed"},
        ),
        (
            {"request": {"contract": "game.playtest"}},
            "OPERATION_REQUEST_INVALID",
            {
                "defect": "request lacks dispatch_id, location, mode, operation, provider, "
                "scenario, source_files, source_revision"
            },
        ),
        ({"origin": {}}, "OPERATION_ORIGIN_INVALID", {"blank": []}),
        (
            {"origin": {"task_id": " ", "agent_id": "eve"}},
            "OPERATION_ORIGIN_INVALID",
            {"blank": ["task_id"]},
        ),
    ],
    ids=["a-value-of-the-wrong-kind", "keys-missing", "no-origin", "a-blank-origin-value"],
)
def test_a_request_that_cant_be_read_is_refused_with_its_defect_and_queues_nothing(
    over, code, details
):
    """Bug caught: a request with a key missing queued with that key filled in, and run by a
    worker as something its requester never asked for."""
    w, session = _served_world()

    reply = w.client.post(OPERATIONS, json=_body(**over))
    nothing = w.as_(Role.WORKER).post(f"/api/v1/workers/sessions/{session}/claims")

    assert (reply.status_code, _error(reply)["code"]) == (422, code)
    assert _error(reply)["details"] == details
    assert nothing.json() == {"claim": None}


@pytest.mark.parametrize("over", [{"max_attempts": 0}, {"surprise": 1}], ids=["zero", "unknown"])
def test_a_body_outside_the_schema_is_refused(over):
    w, _ = _served_world()
    assert w.client.post(OPERATIONS, json=_body(**over)).status_code == 422


def test_a_cancel_settles_a_queued_operation_and_marks_a_claimed_one():
    """Bug caught: a cancel that reads as done while a worker can still claim the operation;
    or a claimed one settled by the route, under its worker, as if it had not started."""
    w, session = _served_world()
    first = w.client.post(OPERATIONS, json=_body()).json()["operation_id"]
    w.clock.advance(1)  # the claim takes the oldest
    second = w.client.post(OPERATIONS, json=_body()).json()["operation_id"]
    w.as_(Role.WORKER).post(f"/api/v1/workers/sessions/{session}/claims")

    marked = w.as_(Role.AGENT).post(f"{OPERATIONS}/{first}/cancel")
    stopped = w.client.post(f"{OPERATIONS}/{second}/cancel")
    again = w.client.post(f"{OPERATIONS}/{second}/cancel")

    assert (marked.status_code, marked.json()["state"], marked.json()["cancel_requested"]) == (
        200,
        "claimed",
        True,
    )
    assert marked.json()["result"] is None
    assert (stopped.json()["state"], stopped.json()["result"]["status"]) == (
        "settled",
        "not_executed",
    )
    assert stopped.json()["result"]["reason"] == leasing.REASON_CANCELLED_UNCLAIMED
    assert again.json() == stopped.json()


def test_an_id_no_operation_has_is_a_404_with_the_routes_own_code():
    w, _ = _served_world()

    replies = [
        w.client.get(f"{OPERATIONS}/rop-never-queued"),
        w.client.post(f"{OPERATIONS}/rop-never-queued/cancel"),
    ]

    assert [reply.status_code for reply in replies] == [404, 404]
    assert [_error(reply)["code"] for reply in replies] == ["REMOTE_OPERATION_NOT_FOUND"] * 2
    assert _error(replies[0])["details"] == {"operation_id": "rop-never-queued"}


@pytest.mark.parametrize("role", [Role.WORKER, Role.ADMIN, Role.OPERATOR, Role.VIEWER])
def test_no_role_but_the_agents_may_ask_for_read_or_cancel_an_operation(role):
    """Bug caught: a worker queueing work for itself to run on the machine that hosts a tool,
    or a person's token doing so (R5.6: the agent role alone)."""
    w, _ = _served_world()
    operation_id = w.client.post(OPERATIONS, json=_body()).json()["operation_id"]

    client = w.as_(role)
    replies = [
        client.post(OPERATIONS, json=_body()),
        client.get(f"{OPERATIONS}/{operation_id}"),
        client.post(f"{OPERATIONS}/{operation_id}/cancel"),
    ]

    assert [reply.status_code for reply in replies] == [403, 403, 403]
    assert w.operation(operation_id).cancel_requested is False


def test_a_runtime_with_no_registry_says_so():
    w = World(registry=False)

    reply = w.as_(Role.AGENT).post(OPERATIONS, json=_body())

    assert (reply.status_code, _error(reply)["code"]) == (503, "WORKER_REGISTRY_UNAVAILABLE")

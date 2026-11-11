"""``GET /api/v1/workers`` and ``squadops workers`` (#3047): an operator reads the registry.

Entered where the issue's "done when" says: a worker registers, claims and is refused through
the real routes, and the operator's CLI reads it through the real read route, over the real
registry and the memory store. The clock is the test's, so a worker goes silent when the test
says so.

What bugs would these catch?
- A silent session read as online by an operator during an overnight Campaign.
- The read route open to a worker's role, or closed to an operator's.
- A lease id, which a worker presents with its result, shown to a person.
- ``show`` answering for a worker with no live session as if it had one.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.auth.models import Role
from squadops.cli.client import CLIError
from squadops.cli.main import app
from squadops.remote_execution import leasing
from squadops.remote_execution.wire import result_to_wire
from tests.unit.api.worker_world import World, identity
from tests.unit.remote_execution.registry_contract import passing

pytestmark = [pytest.mark.auth, pytest.mark.domain_cli]

runner = CliRunner()


def _world_with_a_held_operation_and_a_refusal() -> tuple[World, str, dict]:
    w = World()
    w.tokens["operator"] = identity(Role.OPERATOR)
    queued = w.enqueue()
    session = w.register("macbook")
    claim = w.client.post(f"/api/v1/workers/sessions/{session}/claims").json()["claim"]
    refused = w.client.post(
        f"/api/v1/workers/sessions/{session}/results",
        json={
            "fence": {"operation_id": claim["operation_id"], "attempt": 1, "lease_id": "lease-x"},
            "result": result_to_wire(passing()),
        },
    )
    assert refused.status_code == 409, refused.text
    return w, session, {"operation_id": queued.operation_id, "lease_id": claim["lease_id"]}


def _cli(w: World, *args: str):
    """The CLI, reading the routes in ``w`` as the operator."""

    def get(path: str):
        reply = w.client.get(path, headers={"Authorization": "Bearer operator"})
        if reply.status_code >= 400:
            body = reply.json()  # the standard envelope, under ``detail`` in this bare app
            raise CLIError(body.get("detail", body)["error"]["message"], exit_code=1)
        return reply.json()

    client = MagicMock()
    client.get.side_effect = get
    with patch("squadops.cli.commands.workers._get_client", return_value=client):
        return runner.invoke(app, list(args))


def test_an_operator_reads_what_the_worker_registered_holds_and_had_refused():
    w, session, held = _world_with_a_held_operation_and_a_refusal()

    reply = w.client.get("/api/v1/workers/macbook", headers={"Authorization": "Bearer operator"})

    assert reply.status_code == 200
    body = reply.json()
    assert (body["worker_id"], body["session_id"], body["health"]) == ("macbook", session, "online")
    assert body["operations"] == [{"provider": "fixture-editor", "operation": "play_scenario"}]
    assert [(h["operation_id"], h["attempt"]) for h in body["held"]] == [(held["operation_id"], 1)]
    assert [(r["operation_id"], r["refusal"]) for r in body["recent_refusals"]] == [
        (held["operation_id"], "stale_lease")
    ]
    assert held["lease_id"] not in reply.text and "lease-x" not in reply.text


def test_a_session_silent_for_45_seconds_reads_offline_in_the_cli():
    w, _, held = _world_with_a_held_operation_and_a_refusal()

    heard = _cli(w, "-q", "workers", "list")  # tab-separated: a table wraps long ids
    w.clock.advance(leasing.SESSION_SILENT_SECONDS + 1)
    silent = _cli(w, "workers", "show", "macbook")

    assert heard.exit_code == 0, heard.output
    [row] = [line.split("\t") for line in heard.output.splitlines()]
    assert row[:2] == ["macbook", "online"]
    assert row[4] == f"{held['operation_id']} (attempt 1 of 2)"
    assert row[5] == "1"
    assert silent.exit_code == 0, silent.output
    said = " ".join(silent.output.split())
    assert "offline (last reported online)" in said
    assert "stale_lease" in said


@pytest.mark.parametrize(
    ("role", "status"),
    [(Role.WORKER, 403), (Role.AGENT, 403), (Role.VIEWER, 200), (Role.CAMPAIGN_TRIAGE, 200)],
)
def test_only_a_persons_role_reads_the_registry(role, status):
    w = World()
    w.register("macbook")
    w.tokens["reader"] = identity(role)

    reply = w.client.get("/api/v1/workers", headers={"Authorization": "Bearer reader"})

    assert reply.status_code == status, reply.text


def test_show_for_a_worker_with_no_live_session_is_not_found_and_the_cli_says_why():
    w = World()
    w.tokens["operator"] = identity(Role.OPERATOR)
    w.register("macbook")

    shown = _cli(w, "workers", "show", "mac-mini")

    assert shown.exit_code == 1
    assert "no live session for this worker" in " ".join(shown.output.split())

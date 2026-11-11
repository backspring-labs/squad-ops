"""``/api/v1/workers`` as a worker calls it (SIP-0117 R3.3, R5.3, R5.4).

Entered at the routes with the worker's identity, over the real registry and the memory store.
The clock is the test's, so a lease runs out when the test says so.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.workers import router
from squadops.auth.models import ROLE_SCOPES, Identity, IdentityType, Role, scopes_for_roles
from squadops.remote_execution import leasing
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.wire import request_to_wire, result_to_wire
from squadops.remote_execution.workers import OperationState
from tests.unit.remote_execution.registry_contract import ORIGIN, Clock, passing, request

pytestmark = pytest.mark.auth

REGISTRATION = {
    "worker_id": "macbook",
    "platform": "macos-arm64",
    "tool_versions": {"fixture-editor": "1.0"},
    "operations": [{"provider": "fixture-editor", "operation": "play_scenario"}],
}


def _identity(role: str) -> Identity:
    return Identity(
        user_id=role,
        display_name=role,
        roles=(role,),
        scopes=tuple(sorted(scopes_for_roles((role,)))),
        identity_type=IdentityType.SERVICE,
    )


class _World:
    def __init__(self, *, registry: bool = True) -> None:
        self.clock = Clock()
        self.registry = WorkerRegistry(MemoryWorkerRegistryStore(), clock=self.clock)
        self.identity = _identity(Role.WORKER)
        world = self
        app = FastAPI()

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = world.identity
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(router)
        register_domain_error_handlers(app)
        app.state.worker_registry = self.registry if registry else None
        # Without an authorization backend, require_scopes is a no-op: the scopes go unread.
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def as_(self, role: str) -> TestClient:
        self.identity = _identity(role)
        return self.client

    def enqueue(self, *, max_attempts: int = 2):
        return asyncio.run(self.registry.enqueue(request(), ORIGIN, max_attempts=max_attempts))

    def operation(self, operation_id: str):
        return asyncio.run(self.registry.operation(operation_id))

    def register(self, worker_id: str = "macbook") -> str:
        reply = self.client.post(
            "/api/v1/workers/sessions", json={**REGISTRATION, "worker_id": worker_id}
        )
        assert reply.status_code == 201, reply.text
        return reply.json()["session_id"]


def _fence(claim: dict) -> dict:
    return {key: claim[key] for key in ("operation_id", "attempt", "lease_id")}


def test_a_worker_registers_claims_renews_and_submits_and_the_operation_has_its_result():
    """The whole exchange, as R3.3's table lists it. Bug caught: any step's body losing a field
    on the way through the route: the lease's expiry, the request's scenario, the cancel."""
    w = _World()
    queued = w.enqueue()

    registered = w.client.post("/api/v1/workers/sessions", json=REGISTRATION)
    session = registered.json()["session_id"]
    claimed = w.client.post(f"/api/v1/workers/sessions/{session}/claims")
    claim = claimed.json()["claim"]
    idle = w.client.post(f"/api/v1/workers/sessions/{session}/claims")
    w.clock.advance(40)
    renewed = w.client.post(
        f"/api/v1/workers/sessions/{session}/heartbeats",
        json={"runtime_status": "online", "fence": _fence(claim)},
    )
    plain = w.client.post(
        f"/api/v1/workers/sessions/{session}/heartbeats", json={"runtime_status": "degraded"}
    )
    submitted = w.client.post(
        f"/api/v1/workers/sessions/{session}/results",
        json={"fence": _fence(claim), "result": result_to_wire(passing())},
    )

    assert registered.status_code == 201
    assert registered.json() == {
        "session_id": session,
        "worker_id": "macbook",
        "registered_at": "2026-11-10T15:00:00Z",
        "heartbeat_seconds": leasing.HEARTBEAT_SECONDS,
        "lease_seconds": leasing.LEASE_SECONDS,
    }
    assert claimed.status_code == 200
    assert claim == {
        "operation_id": queued.operation_id,
        "attempt": 1,
        "lease_id": claim["lease_id"],
        "lease_expires_at": "2026-11-10T15:01:00Z",
        "reconcile_first": False,
        "request": request_to_wire(request()),
    }
    assert idle.json() == {"claim": None}
    assert renewed.json() == {
        "lease": {
            "held": True,
            "refusal": None,
            "expires_at": "2026-11-10T15:01:40Z",
            "cancel_requested": False,
        }
    }
    assert plain.json() == {"lease": None}
    assert (submitted.status_code, submitted.json()) == (200, {"accepted": True, "replayed": False})
    settled = w.operation(queued.operation_id)
    assert (settled.state, settled.result) == (OperationState.SETTLED, passing())


def test_a_late_result_is_a_409_with_its_reason_and_the_newer_attempt_keeps_the_operation():
    """R3.3's fence at the route. Bug caught: a refusal answered 200, which a worker reads as
    done; or one that says only "conflict", so nobody can tell a sleeping worker from a bug."""
    w = _World()
    queued = w.enqueue(max_attempts=3)
    first, second = w.register("macbook"), w.register("mac-mini")
    early = w.client.post(f"/api/v1/workers/sessions/{first}/claims").json()["claim"]
    w.clock.advance(leasing.LEASE_SECONDS + 1)
    newer = w.client.post(f"/api/v1/workers/sessions/{second}/claims").json()["claim"]

    late = w.client.post(
        f"/api/v1/workers/sessions/{first}/results",
        json={"fence": _fence(early), "result": result_to_wire(passing())},
    )
    lost = w.client.post(
        f"/api/v1/workers/sessions/{first}/heartbeats",
        json={"runtime_status": "online", "fence": _fence(early)},
    )

    assert late.status_code == 409
    assert late.json()["detail"] == {
        "error": {
            "code": "RESULT_REFUSED",
            "message": "the result's ids are not the current ones for this operation; it was "
            "recorded and not accepted",
            "details": {
                "refusal": "stale_attempt",
                "operation_id": queued.operation_id,
                "attempt": 1,
            },
        }
    }
    assert lost.json()["lease"] == {
        "held": False,
        "refusal": "stale_attempt",
        "expires_at": None,
        "cancel_requested": False,
    }
    held = w.operation(queued.operation_id)
    assert (held.state, held.attempt, held.lease_id) == (
        OperationState.CLAIMED,
        2,
        newer["lease_id"],
    )
    recorded = asyncio.run(w.registry.refusals(queued.operation_id))
    assert [(r.fence.session_id, r.refusal.value) for r in recorded] == [(first, "stale_attempt")]


@pytest.mark.parametrize("role", sorted(set(ROLE_SCOPES) - {Role.WORKER}))
def test_no_role_but_the_workers_reaches_any_route(role):
    """R5.3: one scope, held by the worker's role alone. Bug caught: a squad agent's token, or
    an operator's, claiming an operation and submitting a result for it."""
    w = _World()
    queued = w.enqueue()
    session = w.register()
    client = w.as_(role)

    replies = [
        client.post("/api/v1/workers/sessions", json=REGISTRATION),
        client.post(
            f"/api/v1/workers/sessions/{session}/heartbeats", json={"runtime_status": "online"}
        ),
        client.post(f"/api/v1/workers/sessions/{session}/claims"),
        client.post(
            f"/api/v1/workers/sessions/{session}/results",
            json={
                "fence": {"operation_id": queued.operation_id, "attempt": 1, "lease_id": "x"},
                "result": result_to_wire(passing()),
            },
        ),
    ]

    assert [reply.status_code for reply in replies] == [403, 403, 403, 403]
    assert w.operation(queued.operation_id).state is OperationState.QUEUED


@pytest.mark.parametrize(
    ("path", "body", "status", "code", "details"),
    [
        (
            "/sessions",
            {**REGISTRATION, "operations": []},
            422,
            "WORKER_REGISTRATION_INVALID",
            {"errors": ["the worker names no operation it serves"]},
        ),
        (
            "/sessions/{session}/heartbeats",
            {"runtime_status": "busy"},
            422,
            "RUNTIME_STATUS_INVALID",
            {"runtime_status": "busy", "known": ["online", "degraded", "recovering", "offline"]},
        ),
        (
            "/sessions/wks-never-registered/heartbeats",
            {"runtime_status": "online"},
            404,
            "WORKER_SESSION_NOT_FOUND",
            {"session_id": "wks-never-registered"},
        ),
        (
            "/sessions/wks-never-registered/claims",
            None,
            404,
            "WORKER_SESSION_NOT_FOUND",
            {"session_id": "wks-never-registered"},
        ),
        (
            "/sessions/{session}/results",
            {
                "fence": {"operation_id": "rop-x", "attempt": 1, "lease_id": "lease-x"},
                "result": {"status": "passed"},
            },
            422,
            "RESULT_INVALID",
            {
                "defect": "result lacks dispatch_id, evidence, provider_version, ran_with, "
                "reason, records"
            },
        ),
    ],
    ids=[
        "a registration serving nothing",
        "busy as a health value",
        "a heartbeat for no session",
        "a claim for no session",
        "a result that isn't one",
    ],
)
def test_what_a_route_cannot_act_on_is_refused_in_the_envelope_with_what_was_wrong(
    path, body, status, code, details
):
    """Bug caught: a result with no status stored as the operation's result; a session id the
    registry doesn't hold answered with an empty claim, so a worker polls for ever and never
    registers again."""
    w = _World()
    session = w.register()

    reply = w.client.post(f"/api/v1/workers{path.format(session=session)}", json=body)

    assert reply.status_code == status, reply.text
    error = reply.json()["detail"]["error"]
    assert (error["code"], error["details"]) == (code, details)


def test_a_key_the_route_does_not_know_is_refused_and_never_dropped():
    """Bug caught: a worker on a newer version sending a field this runtime ignores, so what
    the worker believes it reported and what was stored differ."""
    w = _World()

    reply = w.client.post("/api/v1/workers/sessions", json={**REGISTRATION, "capacity": 4})

    assert reply.status_code == 422
    assert "capacity" in reply.text
    assert asyncio.run(w.registry.sessions()) == []


def test_a_runtime_with_no_registry_says_so():
    w = _World(registry=False)

    reply = w.client.post("/api/v1/workers/sessions", json=REGISTRATION)

    assert (reply.status_code, reply.json()["detail"]["error"]["code"]) == (
        503,
        "WORKER_REGISTRY_UNAVAILABLE",
    )

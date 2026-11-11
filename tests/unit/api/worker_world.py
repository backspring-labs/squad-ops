"""The worker's routes and the requester's, with an identity the test chooses, over the real
registry and the memory store (SIP-0117 R3.3, R5.4, R5.6). The route tests and the two HTTP
adapters' tests all enter here, so each proves its side against the same app."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.remote_operations import router as remote_operations_router
from squadops.api.routes.worker_readings import router as readings_router
from squadops.api.routes.workers import router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.remote_execution.registry import WorkerRegistry
from tests.unit.remote_execution.registry_contract import Clock, queue, request

REGISTRATION = {
    "worker_id": "macbook",
    "platform": "macos-arm64",
    "tool_versions": {"fixture-editor": "1.0"},
    "operations": [{"provider": "fixture-editor", "operation": "play_scenario"}],
}


def identity(role: str) -> Identity:
    return Identity(
        user_id=role,
        display_name=role,
        roles=(role,),
        scopes=tuple(sorted(scopes_for_roles((role,)))),
        identity_type=IdentityType.SERVICE,
    )


class CurrentSends:
    """The one thing the requester's routes read from the runtime's reply router: the send of
    a task the runtime is waiting on (#2932, R5.6). A test says which sends are current."""

    def __init__(self) -> None:
        self.waiting: dict[str, str] = {}

    def current_dispatch(self, task_id: str) -> str | None:
        return self.waiting.get(task_id)


class World:
    def __init__(self, *, registry: bool = True, reply_router: object = True) -> None:
        """``reply_router``: ``True`` for the stand-in the test sets sends on (``current``),
        ``False`` for a runtime with none, or a real router."""
        self.clock = Clock()
        self.registry = WorkerRegistry(MemoryWorkerRegistryStore(), clock=self.clock)
        self.identity = identity(Role.WORKER)
        #: An identity per bearer token, for a test where a worker and a requester both call.
        #: A call with any other token, or none, is made as ``identity``.
        self.tokens: dict[str, Identity] = {}
        world = self
        app = self.app = FastAPI()

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                bearer = request.headers.get("Authorization", "").removeprefix("Bearer ")
                request.state.identity = world.tokens.get(bearer, world.identity)
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(router)
        app.include_router(remote_operations_router)
        app.include_router(readings_router)
        register_domain_error_handlers(app)
        app.state.worker_registry = self.registry if registry else None
        self.sends = CurrentSends()
        app.state.reply_router = (
            self.sends if reply_router is True else None if reply_router is False else reply_router
        )
        # Without an authorization backend, require_scopes is a no-op: the scopes go unread.
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def as_(self, role: str) -> TestClient:
        self.identity = identity(role)
        return self.client

    def current(self, asked):
        """Make ``asked``'s send the one the runtime waits on for its task, and return it."""
        self.sends.waiting[asked.task_id] = asked.dispatch_id
        return asked

    def enqueue(self, *, max_attempts: int = 2):
        return asyncio.run(queue(self.registry, request(), max_attempts=max_attempts))

    def operation(self, operation_id: str):
        return asyncio.run(self.registry.operation(operation_id))

    def register(self, worker_id: str = "macbook") -> str:
        reply = self.client.post(
            "/api/v1/workers/sessions", json={**REGISTRATION, "worker_id": worker_id}
        )
        assert reply.status_code == 201, reply.text
        return reply.json()["session_id"]

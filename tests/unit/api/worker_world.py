"""The worker routes with an identity the test chooses, over the real registry and the memory
store (SIP-0117 R3.3, R5.4). The route tests and the worker's HTTP adapter's tests both enter
here, so each proves its side against the same app."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.workers import router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.remote_execution.registry import WorkerRegistry
from tests.unit.remote_execution.registry_contract import ORIGIN, Clock, request

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


class World:
    def __init__(self, *, registry: bool = True) -> None:
        self.clock = Clock()
        self.registry = WorkerRegistry(MemoryWorkerRegistryStore(), clock=self.clock)
        self.identity = identity(Role.WORKER)
        world = self
        app = self.app = FastAPI()

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
        self.identity = identity(role)
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

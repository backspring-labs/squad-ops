"""The runtime root binds the worker registry and serves its routes (SIP-0117 R5.4).

Entered at the root's own functions: the binding ``_init_cycle_subsystem`` calls and the router
list ``create_app`` builds. The route tests prove the routes over a registry they are handed;
only this proves the runtime hands them one, on the cycle registry's selector.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from squadops.api.runtime import main as runtime_main
from tests.unit.remote_execution.registry_contract import ORIGIN, registration, request

pytestmark = [pytest.mark.domain_api]


async def test_the_root_binds_a_registry_that_serves_a_claim_on_the_memory_selector():
    registry = runtime_main._worker_registry("memory", None)
    queued = await registry.enqueue(request(), ORIGIN, max_attempts=1)
    session = await registry.register(registration())

    claim = await registry.claim(session.session_id)

    assert (claim.fence.operation_id, claim.fence.attempt) == (queued.operation_id, 1)


@pytest.mark.parametrize(
    ("provider", "message"),
    [("postgres", "pool is required"), ("sqlite", "Unknown worker registry store provider")],
    ids=["postgres with no pool", "a selector nobody wrote a store for"],
)
def test_the_root_never_falls_back_to_memory(provider, message):
    """Bug caught: a deployed runtime whose pool didn't open keeping its leases in the
    process, so they are gone at the next restart and every worker's result is refused."""
    with pytest.raises(ValueError, match=message):
        runtime_main._worker_registry(provider, None)


def test_the_runtime_serves_the_four_worker_routes():
    app = FastAPI()
    runtime_main._include_routers(app)

    served = {
        (method, route.path)
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/v1/workers")
        for method in route.methods
    }

    assert served == {
        ("POST", "/api/v1/workers/sessions"),
        ("POST", "/api/v1/workers/sessions/{session_id}/heartbeats"),
        ("POST", "/api/v1/workers/sessions/{session_id}/claims"),
        ("POST", "/api/v1/workers/sessions/{session_id}/results"),
    }

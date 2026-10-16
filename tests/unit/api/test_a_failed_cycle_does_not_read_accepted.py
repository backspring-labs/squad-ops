"""A failed cycle's roll-up does not read ``accepted`` (#2384).

The 2.3 cut's set 1 fourth roll (``cyc_ce31b502b82c``) failed on a framework integrity error.
Its implementation run's own verdict was ``blocked_unverified``, from two optional rows that had
executed and passed elsewhere. Reconciliation superseded both, and the cycle detail read
``verdict: accepted`` beside ``status: failed``.

Entered at ``GET /api/v1/projects/{project}/cycles/{cycle}``, the cycle-detail route the CLI,
the console and the release package read, over the memory cycle registry.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles import cycles_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.cycles.models import Cycle, Run, TaskFlowPolicy
from squadops.cycles.verification_integrity import (
    RunVerdict,
    RunVerificationSummary,
    UnverifiedCheck,
)

pytestmark = [pytest.mark.domain_api]

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
COMPILES = "acceptance:frontend_compiles"


def _summary(verdict, *, verified=(), unverified=()) -> RunVerificationSummary:
    return RunVerificationSummary(
        verdict=verdict,
        verified=tuple(verified),
        failed=(),
        unverified=tuple(unverified),
        required_unmet=(),
        executed_count=len(verified),
        passed_count=len(verified),
    )


#: The roll's implementation run: the view compiled where QA ran it, and a patch verification
#: without the toolchain recorded it skipped. Optional, and executed: reconciliation supersedes it.
_FAILED_IMPL = _summary(
    RunVerdict.BLOCKED_UNVERIFIED,
    verified=(COMPILES, "tests_pass"),
    unverified=(UnverifiedCheck(COMPILES, "missing_tooling", required=False),),
)


async def _client(runs: list[tuple[Run, RunVerificationSummary]]) -> TestClient:
    registry = MemoryCycleRegistry()
    await registry.create_cycle(
        Cycle(
            cycle_id="cyc_failed",
            project_id="group_run",
            created_at=NOW,
            created_by="owner",
            prd_ref=None,
            squad_profile_id="full-38",
            squad_profile_snapshot_ref="x",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )
    )
    for run, summary in runs:
        await registry.create_run(run)
        await registry.record_run_verification_summary(run.run_id, summary)
    app = FastAPI()

    class Inject(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.identity = Identity(
                user_id="owner",
                display_name="owner",
                roles=(Role.ADMIN,),
                scopes=tuple(sorted(scopes_for_roles((Role.ADMIN,)))),
                identity_type=IdentityType.HUMAN,
            )
            return await call_next(request)

    app.add_middleware(Inject)
    app.include_router(cycles_router)
    register_domain_error_handlers(app)
    app.state.cycle_registry = registry
    app.state.authz_port = KeycloakAuthzAdapter()
    return TestClient(app)


def _run(run_id: str, n: int, status: str, workload: str) -> Run:
    return Run(run_id, "cyc_failed", n, status, "system", "cfg", workload_type=workload)


_FRAMING = (_run("run_frame", 1, "completed", "framing"), _summary(RunVerdict.ACCEPTED))


@pytest.mark.parametrize(
    ("runs", "verdict"),
    [
        (
            [_FRAMING, (_run("run_impl", 2, "failed", "implementation"), _FAILED_IMPL)],
            "blocked_unverified",
        ),
        (
            [
                _FRAMING,
                (_run("run_impl", 2, "failed", "implementation"), _FAILED_IMPL),
                (
                    _run("run_retry", 3, "completed", "implementation"),
                    _summary(RunVerdict.ACCEPTED, verified=(COMPILES, "tests_pass")),
                ),
            ],
            "accepted",
        ),
        (
            [_FRAMING, (_run("run_impl", 2, "completed", "implementation"), _FAILED_IMPL)],
            "accepted",
        ),
    ],
    ids=[
        "the roll: a failed run's verdict stands",
        "a retry re-executed its work and passed",
        "the same rows on a run that completed reconcile as before",
    ],
)
async def test_the_cycle_detail_reads_a_failed_runs_verdict(runs, verdict):
    """Bugs caught: a failed cycle reported ``accepted`` to every reader of the roll-up, which
    the release package had to work around at the 2.3 cut; and, the other way, a retry that
    re-executed the failed run's work and passed still dragged down by the failure."""
    client = await _client(runs)

    body = client.get("/api/v1/projects/group_run/cycles/cyc_failed").json()

    assert body["cycle_outcome"]["verdict"] == verdict

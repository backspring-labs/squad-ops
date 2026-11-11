"""The worker's HTTP adapter, against the real worker routes (SIP-0117 R3.3, R5.5).

The adapter's requests go through ``httpx``'s ASGI transport into the app the route tests use,
over the real registry, so each side of the wire is proved against the other. The refusals are
the ones a worker meets in a deploy: a wrong address, a wrong secret, a runtime that is down.
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

from adapters.remote_execution.fixture_operation_runner import (
    HOLD_PATH,
    OPERATION,
    PROVIDER,
    FixtureOperationRunner,
)
from adapters.remote_execution.http_worker_api import HttpWorkerApi
from squadops.auth.models import Role
from squadops.remote_execution import leasing
from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    OperationStatus,
    RemoteOperationRequest,
    Scenario,
)
from squadops.remote_execution.serving import Worker
from squadops.remote_execution.wire import request_to_wire
from squadops.remote_execution.workers import (
    Fence,
    FenceRefusal,
    OperationState,
    RuntimeAnswerUnreadable,
    RuntimeUnreachable,
    ServedOperation,
    UnknownSession,
    WorkerRefused,
    WorkerRegistration,
)
from tests.unit.api.worker_world import World, identity
from tests.unit.remote_execution.registry_contract import PLAY, passing, queue, request
from tests.unit.remote_execution.worker_harness import Serving, sleeping_on

pytestmark = pytest.mark.auth

SEEN_TOKENS: list[str] = []


async def _token() -> str:
    return "the-worker-token"


def _api(world: World) -> HttpWorkerApi:
    return HttpWorkerApi(
        "http://runtime.test/", _token, transport=httpx.ASGITransport(app=world.app)
    )


def _answering(status: int, body) -> HttpWorkerApi:
    """An adapter whose every call is answered with ``status`` and ``body``."""

    def handler(http_request: httpx.Request) -> httpx.Response:
        SEEN_TOKENS.append(http_request.headers["Authorization"])
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)

    return HttpWorkerApi("http://runtime.test", _token, transport=httpx.MockTransport(handler))


REGISTRATION = WorkerRegistration(
    worker_id="macbook",
    platform="darwin-arm64",
    tool_versions={"fixture-editor": "1.0"},
    operations=(PLAY,),
)


async def test_a_worker_over_http_serves_a_queued_operation_to_its_accepted_result():
    """The wiring, entered at ``Worker.serve()``: the loop, the HTTP adapter, the routes, the
    registry and the fixture provider. Bug caught: either side of the wire naming a field the
    other doesn't (the claim's request, the fence, the lease's expiry), which each side's own
    tests pass through. The operation holds for 40 seconds, so its lease is renewed over HTTP."""
    world = World()
    asked = RemoteOperationRequest(
        contract="game.playtest",
        mode="simulation",
        provider=PROVIDER,
        operation=OPERATION,
        location="worker",
        source_revision="rev_1",
        source_files={"src/init.luau": "return {}\n", "src/empty.luau": "", HOLD_PATH: "40"},
        scenario=Scenario("scn_1", "sha256:abc", ("src/init.luau", "src/empty.luau", "src/no")),
        task_id="task_1",
        dispatch_id="dispatch-7",
    )
    queued = await queue(world.registry, asked, max_attempts=1)
    worker = Worker(
        _api(world),
        FixtureOperationRunner(sleep=sleeping_on(world.clock)),
        worker_id="macbook",
        platform="darwin-arm64",
        clock=world.clock,
        sleep=sleeping_on(world.clock),
    )

    async def settled() -> bool:
        stored = await world.registry.operation(queued.operation_id)
        return stored.state is OperationState.SETTLED

    async with Serving(worker) as serving:
        await serving.until(settled)

    result = (await world.registry.operation(queued.operation_id)).result
    expected = "a staged file with content"
    assert result.status is OperationStatus.COMPLETED
    assert result.records == (
        AssertionRecord(
            "src/init.luau", AssertionOutcome.PASSED, "staged, 10 bytes", expected, "worker"
        ),
        AssertionRecord(
            "src/empty.luau", AssertionOutcome.FAILED, "staged, empty", expected, "worker"
        ),
        AssertionRecord("src/no", AssertionOutcome.FAILED, "not staged", expected, "worker"),
    )
    assert (result.dispatch_id, result.provider_version) == ("dispatch-7", "fixture@1")
    ((session, _),) = await world.registry.sessions()
    assert session.operations == (ServedOperation(PROVIDER, OPERATION),)
    assert session.tool_versions == {"fixture": "1"}
    assert await world.registry.refusals(queued.operation_id) == []


async def test_each_call_reads_the_routes_answer_into_the_registrys_own_words():
    """Bug caught: the cadence, the lease's expiry, the cancel or a refusal's reason changed or
    dropped between the route's body and what the worker's loop is handed."""
    world = World()
    api = _api(world)
    queued = await queue(world.registry, request(), max_attempts=2)

    enrolment = await api.register(REGISTRATION)
    assert (enrolment.heartbeat, enrolment.lease) == (
        timedelta(seconds=leasing.HEARTBEAT_SECONDS),
        timedelta(seconds=leasing.LEASE_SECONDS),
    )
    assert await api.heartbeat(enrolment.session_id, "degraded") is None
    claim = await api.claim(enrolment.session_id)
    assert claim.request == queued.request
    assert claim.fence == Fence(queued.operation_id, 1, enrolment.session_id, claim.fence.lease_id)
    assert claim.lease_expires_at == world.clock() + timedelta(seconds=leasing.LEASE_SECONDS)
    assert claim.reconcile_first is False
    assert await api.claim(enrolment.session_id) is None

    world.clock.advance(20)
    await world.registry.cancel(queued.operation_id)
    lease = await api.renew(enrolment.session_id, "online", claim.fence)
    assert (lease.refusal, lease.cancel_requested) == (None, True)
    assert lease.expires_at == world.clock() + timedelta(seconds=leasing.LEASE_SECONDS)

    stale = Fence(queued.operation_id, 1, enrolment.session_id, "lease-of-another-claim")
    assert (await api.renew(enrolment.session_id, "online", stale)).refusal is (
        FenceRefusal.STALE_LEASE
    )
    refused = await api.submit_result(stale, passing())
    assert (refused.refusal, refused.replayed) == (FenceRefusal.STALE_LEASE, False)
    assert [r.refusal for r in await world.registry.refusals(queued.operation_id)] == [
        FenceRefusal.STALE_LEASE
    ]

    accepted = await api.submit_result(claim.fence, passing())
    again = await api.submit_result(claim.fence, passing())
    assert (accepted.refusal, accepted.replayed) == (None, False)
    assert (again.refusal, again.replayed) == (None, True)
    assert (await world.registry.operation(queued.operation_id)).result == passing()
    await api.close()


async def test_a_session_the_runtime_no_longer_knows_is_unknown_session_on_every_call():
    """Bug caught: the route's 404 read as "nothing to claim", so a worker whose session
    ended polls it for ever."""
    api = _api(World())
    with pytest.raises(UnknownSession, match="wks-gone"):
        await api.claim("wks-gone")
    with pytest.raises(UnknownSession):
        await api.heartbeat("wks-gone", "online")
    with pytest.raises(UnknownSession):
        await api.renew("wks-gone", "online", Fence("rop-1", 1, "wks-gone", "lease-1"))


async def test_a_role_without_the_workers_scope_is_refused_and_never_retried_as_unreachable():
    """Bug caught: a 403 treated as the runtime being down, so a worker signed in as the wrong
    client retries for ever and looks idle."""
    world = World()
    world.identity = identity(Role.ADMIN)
    with pytest.raises(WorkerRefused, match="HTTP 403 from /api/v1/workers/sessions"):
        await _api(world).register(REGISTRATION)
    assert await world.registry.sessions() == []


@pytest.mark.parametrize(
    ("status", "body", "raised", "says"),
    [
        (404, {"detail": "Not Found"}, WorkerRefused, "HTTP 404"),
        (404, "<html>not the runtime</html>", RuntimeAnswerUnreadable, "isn't JSON"),
        (401, {"detail": {"error": {"code": "UNAUTHENTICATED"}}}, WorkerRefused, "HTTP 401"),
        (503, {"detail": "starting"}, RuntimeUnreachable, "HTTP 503"),
        (502, "Bad Gateway", RuntimeUnreachable, "HTTP 502"),
        (200, {"claim": {"operation_id": "rop-1"}}, RuntimeAnswerUnreadable, "attempt"),
        (200, {}, RuntimeAnswerUnreadable, "no 'claim'"),
        (200, ["claim"], RuntimeAnswerUnreadable, "an object was expected"),
    ],
    ids=[
        "an-address-that-isn't-the-runtime",
        "a-page-that-isn't-json",
        "no-identity",
        "the-registry-unavailable",
        "a-gateway-with-nothing-behind-it",
        "a-claim-missing-its-ids",
        "an-answer-with-no-claim-key",
        "an-answer-that-isn't-an-object",
    ],
)
async def test_an_answer_that_isnt_the_routes_is_raised_with_what_it_was(
    status, body, raised, says
):
    """Bug caught: any of these read as "no claim": a worker pointed at the wrong address, or
    at another version, that sits idle for ever with nothing in its log."""
    with pytest.raises(raised, match=says):
        await _answering(status, body).claim("wks-1")
    assert SEEN_TOKENS[-1] == "Bearer the-worker-token"


def _claim_body(**changed) -> dict:
    claim = {
        "operation_id": "rop-1",
        "attempt": 1,
        "lease_id": "lease-1",
        "lease_expires_at": "2026-11-10T15:01:00Z",
        "reconcile_first": False,
        "request": request_to_wire(request()),
    }
    return {"claim": {**claim, **changed}}


@pytest.mark.parametrize(
    ("body", "says"),
    [
        (_claim_body(request={}), "the claim's request can't be read"),
        (_claim_body(lease_expires_at="2026-11-10T15:01:00"), "names no time zone"),
        (_claim_body(lease_expires_at="soon"), "a time was expected"),
        (_claim_body(attempt="1"), "claim.attempt is '1'"),
        (_claim_body(reconcile_first=None), "claim.reconcile_first is None"),
    ],
    ids=["no-request", "a-time-with-no-zone", "not-a-time", "a-text-attempt", "no-reconcile"],
)
async def test_a_claim_with_a_value_of_the_wrong_kind_is_unreadable(body, says):
    """Bug caught: a claim run with a guessed value: an expiry read in the worker's own time
    zone, or ``reconcile_first`` read as false when it was absent."""
    with pytest.raises(RuntimeAnswerUnreadable, match=says):
        await _answering(200, body).claim("wks-1")


@pytest.mark.parametrize(
    ("lease", "says"),
    [
        (
            {"held": True, "refusal": "stale_lease", "expires_at": None, "cancel_requested": False},
            "held=True with refusal='stale_lease'",
        ),
        (
            {"held": False, "refusal": "taken", "expires_at": None, "cancel_requested": False},
            "the refusal 'taken' is none of",
        ),
        (
            {"held": True, "refusal": None, "expires_at": "2026-11-10T15:01:00Z"},
            "no 'cancel_requested'",
        ),
    ],
    ids=["held-and-refused", "a-refusal-outside-the-vocabulary", "no-cancel-flag"],
)
async def test_a_lease_reading_that_contradicts_itself_is_unreadable(lease, says):
    """Bug caught: a refused lease read as held (the tool runs on, unowned), or a missing
    cancel flag read as "not cancelled"."""
    with pytest.raises(RuntimeAnswerUnreadable, match=says):
        await _answering(200, {"lease": lease}).renew(
            "wks-1", "online", Fence("rop-1", 1, "wks-1", "lease-1")
        )


@pytest.mark.parametrize(
    ("failure", "raised", "says"),
    [
        (httpx.ConnectError("connection refused"), RuntimeUnreachable, "identity provider"),
        (
            httpx.HTTPStatusError(
                "401",
                request=httpx.Request("POST", "http://idp.test/token"),
                response=httpx.Response(401, text='{"error":"unauthorized_client"}'),
            ),
            WorkerRefused,
            "refused the worker's client credentials \\(HTTP 401\\)",
        ),
        (
            httpx.HTTPStatusError(
                "503",
                request=httpx.Request("POST", "http://idp.test/token"),
                response=httpx.Response(503),
            ),
            RuntimeUnreachable,
            "HTTP 503 from the identity provider",
        ),
    ],
    ids=["the-identity-provider-down", "a-wrong-secret", "the-identity-provider-failing"],
)
async def test_a_token_that_cant_be_had_says_whether_to_try_again(failure, raised, says):
    """Bug caught: a wrong client secret retried for ever as an outage, or an identity
    provider that is restarting ending the worker."""

    async def no_token() -> str:
        raise failure

    api = HttpWorkerApi(
        "http://runtime.test",
        no_token,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"claim": None})),
    )
    with pytest.raises(raised, match=says):
        await api.claim("wks-1")


async def test_a_runtime_that_doesnt_answer_is_unreachable():
    """Bug caught: a dropped connection ending the worker, where it should try again."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    api = HttpWorkerApi("http://runtime.test", _token, transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeUnreachable, match="no answer from /api/v1/workers/sessions"):
        await api.register(REGISTRATION)

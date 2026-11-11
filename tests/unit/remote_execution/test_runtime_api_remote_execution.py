"""The agent's remote-execution port, through the real routes to a worker (SIP-0117 R5.6).

The adapter's requests go through ``httpx``'s ASGI transport into the app the route tests use,
over the real registry. The worker beside it is the real serving loop. Each test reads what the
handler would be handed and what the registry then holds.
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from unittest.mock import MagicMock

import httpx
import pytest

from adapters.remote_execution.factory import create_remote_execution
from adapters.remote_execution.fixture_operation_runner import (
    OPERATION,
    PROVIDER,
    FixtureOperationRunner,
)
from adapters.remote_execution.http_worker_api import HttpWorkerApi
from adapters.remote_execution.runtime_api_remote_execution import (
    POLL_SECONDS,
    RuntimeApiRemoteExecution,
)
from squadops.auth.models import Role
from squadops.capabilities.capability_contracts import VerificationMode
from squadops.capabilities.handlers.context import ExecutionContext
from squadops.capabilities.handlers.cycle import run_remote_operation
from squadops.capabilities.handlers.cycle.run_remote_operation import (
    QARunRemoteOperationHandler,
)
from squadops.capabilities.skillsets import Skillset, SkillsetCapability, ToolRequest
from squadops.cycles.verification_integrity import ResultStatus
from squadops.remote_execution import leasing
from squadops.remote_execution.models import OperationStatus
from squadops.remote_execution.serving import REASON_CANCELLED, Worker
from squadops.remote_execution.wire import result_to_wire
from squadops.remote_execution.workers import (
    OperationState,
    RequestRefused,
    RuntimeAnswerUnreadable,
)
from tests.unit.api.worker_world import World, identity
from tests.unit.remote_execution.registry_contract import T0, passing, registration, request
from tests.unit.remote_execution.worker_harness import (
    RegistryWorkerApi,
    ScriptedRunner,
    Serving,
    sleeping_on,
)

pytestmark = pytest.mark.auth

AGENT_TOKEN = "the-agent-token"
WORKER_TOKEN = "the-worker-token"
ORIGIN = {"agent_id": "eve"}
WAIT = timedelta(seconds=30)


async def _agent_token() -> str:
    return AGENT_TOKEN


async def _worker_token() -> str:
    return WORKER_TOKEN


class Recording(httpx.AsyncBaseTransport):
    """The app's transport, keeping each call's method, path and answer."""

    def __init__(self, world: World) -> None:
        self._inner = httpx.ASGITransport(app=world.app)
        self.calls: list[tuple[str, str, int, dict]] = []

    async def handle_async_request(self, http_request: httpx.Request) -> httpx.Response:
        reply = await self._inner.handle_async_request(http_request)
        await reply.aread()
        self.calls.append(
            (http_request.method, http_request.url.path, reply.status_code, reply.json())
        )
        return reply

    @property
    def operation_id(self) -> str:
        (created,) = [body for method, _, status, body in self.calls if status == 201]
        return created["operation_id"]


def _world() -> World:
    world = World()
    world.tokens = {AGENT_TOKEN: identity(Role.AGENT), WORKER_TOKEN: identity(Role.WORKER)}
    return world


def _port(world: World, *, wait: timedelta = WAIT, max_attempts: int = 2):
    recording = Recording(world)
    port = RuntimeApiRemoteExecution(
        "http://runtime.test/",
        _agent_token,
        origin=ORIGIN,
        wait=wait,
        max_attempts=max_attempts,
        transport=recording,
        clock=lambda: world.clock.now.timestamp(),
        sleep=sleeping_on(world.clock),
    )
    return port, recording


def _answering(*answers: tuple[int, object] | Exception, wait: timedelta = WAIT):
    """A port whose calls are answered in turn with ``answers``, the last one repeating. Time
    passes only as the port sleeps."""
    now = [0.0]
    asked: list[tuple[str, str]] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        asked.append((http_request.method, http_request.url.path))
        answer = answers[min(len(asked), len(answers)) - 1]
        if isinstance(answer, Exception):
            raise answer
        status, body = answer
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)

    async def sleep(seconds: float) -> None:
        now[0] += seconds

    port = RuntimeApiRemoteExecution(
        "http://runtime.test",
        _agent_token,
        origin=ORIGIN,
        wait=wait,
        max_attempts=2,
        transport=httpx.MockTransport(handler),
        clock=lambda: now[0],
        sleep=sleep,
    )
    return port, asked


def _operation(state: str = "queued", result=None, **over) -> dict:
    return {
        "operation_id": "rop_1",
        "state": state,
        "attempt": 0,
        "max_attempts": 2,
        "cancel_requested": False,
        "created_at": "2026-11-10T15:00:00Z",
        "settled_at": None,
        "result": result,
        "lease_seconds": 60,
        **over,
    }


def _envelope(code: str, **details) -> dict:
    return {"detail": {"error": {"code": code, "message": "x", "details": details}}}


# ---------------------------------------------------------------------------------- wiring


def _skillset() -> Skillset:
    return Skillset(
        id="fixture-qa",
        version=1,
        description="fixture",
        roles=("qa",),
        platform_id="fixture",
        platform_variants=("local",),
        prerequisites=("fixture",),
        capabilities=(
            SkillsetCapability(
                "game.scenario_verification",
                (VerificationMode.PLAY,),
                (),
                (ToolRequest(OPERATION, PROVIDER, "worker"),),
            ),
        ),
        skill_digests={},
        digest="digest-1",
    )


async def test_the_handlers_operation_reaches_a_worker_and_its_assertions_come_back(monkeypatch):
    """The wiring (R5.6), entered at the handler's ``handle()``, the call a dispatched
    ``qa.run_remote_operation`` makes: the handler, the port's adapter, the requester's routes,
    the registry, the worker's routes, the worker's loop and the fixture provider. Bug caught:
    either side of the requester's wire naming a field the other doesn't, an operation queued
    that no worker's registration matches, or a result that reaches the registry and never the
    handler. Each is passed by its own side's tests."""
    monkeypatch.setattr(
        run_remote_operation, "packaged_skillsets", lambda: {"fixture-qa": _skillset()}
    )
    world = _world()
    port, recording = _port(world)
    worker = Worker(
        HttpWorkerApi(
            "http://runtime.test/", _worker_token, transport=httpx.ASGITransport(app=world.app)
        ),
        FixtureOperationRunner(sleep=sleeping_on(world.clock)),
        worker_id="macbook",
        platform="darwin-arm64",
        clock=world.clock,
        sleep=sleeping_on(world.clock),
    )
    ports = MagicMock()
    ports.remote_execution = port
    context = ExecutionContext.create(
        agent_id="eve",
        role_id="qa",
        task_id="task-7",
        cycle_id="cyc_1",
        ports=ports,
        dispatch_id="send-7",
    )
    world.sends.waiting["task-7"] = "send-7"
    inputs = {
        "operation": {
            "contract": "game.scenario_verification",
            "mode": "play",
            "role": "qa",
            "skillset": "fixture-qa",
            "skillset_digest": "digest-1",
            "agent_id": "eve",
        },
        "operation_scenario": {
            "scenario_id": "staged",
            "digest": "sha256:scenario",
            "assertions": ["src/init.luau", "src/empty.luau"],
        },
        "acceptance_workspace_files": {"src/init.luau": "return {}\n", "src/empty.luau": ""},
        "workspace_revision_id": "rev_candidate",
    }

    async def registered() -> bool:
        return bool(await world.registry.sessions())

    async with Serving(worker) as serving:
        await serving.until(registered)
        result = await QARunRemoteOperationHandler().handle(context, inputs)

    assert result.outputs["validation_result"]["checks"] == [
        {
            "check": "scenario:staged:src/init.luau",
            "criterion_id": "scenario:staged:src/init.luau",
            "status": ResultStatus.PASSED,
            "reason": "",
        },
        {
            "check": "scenario:staged:src/empty.luau",
            "criterion_id": "scenario:staged:src/empty.luau",
            "status": ResultStatus.FAILED,
            "reason": "observed 'staged, empty', expected 'a staged file with content'",
        },
    ]
    document = json.loads(result.outputs["artifacts"][0]["content"])
    assert (document["status"], document["provider_version"], document["ran_with"]) == (
        "completed",
        "fixture@1",
        {"fixture": "1"},
    )
    stored = await world.registry.operation(recording.operation_id)
    assert stored.state is OperationState.SETTLED
    assert stored.origin == {"agent_id": "eve", "requested_by": Role.AGENT}
    assert (stored.request.task_id, stored.request.dispatch_id) == ("task-7", "send-7")
    assert (stored.attempt, stored.max_attempts) == (1, 2)
    assert stored.request.source_revision == "rev_candidate"


# ---------------------------------------------------------------- over the real registry


async def test_with_no_worker_the_operation_is_not_executed_and_nothing_is_queued():
    """Bug caught: an operation queued for nobody, held for the whole wait, then reported as a
    time-out with no word that no worker serves it."""
    world = _world()
    port, recording = _port(world)

    result = await port.run_operation(world.current(request(dispatch_id="task-7")))
    session = await world.registry.register(registration())

    assert (result.status, result.reason, result.dispatch_id) == (
        OperationStatus.NOT_EXECUTED,
        "no registered worker serves fixture-editor/play_scenario",
        "task-7",
    )
    assert [call[:3] for call in recording.calls] == [("POST", "/api/v1/remote-operations", 409)]
    assert await world.registry.claim(session.session_id) is None


async def test_an_operation_nobody_claims_within_the_wait_is_stopped_and_reads_not_executed():
    """Bug caught: a requester that gives up and leaves its operation queued, for a worker to
    claim and run later with nobody reading the result."""
    world = _world()
    port, recording = _port(world)
    session = await world.registry.register(registration())

    result = await port.run_operation(world.current(request(dispatch_id="task-7")))

    assert (result.status, result.dispatch_id) == (OperationStatus.NOT_EXECUTED, "task-7")
    assert result.reason == (
        f"{leasing.REASON_CANCELLED_UNCLAIMED} (its requester asked it to stop: no result "
        "within 30 s of asking)"
    )
    assert world.clock.now - (
        await world.registry.operation(recording.operation_id)
    ).created_at == (timedelta(seconds=30))
    assert await world.registry.claim(session.session_id) is None


async def test_a_running_operation_past_the_wait_is_cancelled_and_its_worker_answers_interrupted():
    """Bug caught: the requester returning at its wait's end while the tool runs on with
    nobody to stop it (R5.5: the worker has no time limit of its own; the requester cancels)."""
    world = _world()
    port, recording = _port(world)
    tool = ScriptedRunner(world.clock)
    tool.run_seconds = None
    worker = Worker(
        RegistryWorkerApi(world.registry),
        tool,
        worker_id="macbook",
        platform="darwin-arm64",
        clock=world.clock,
        sleep=sleeping_on(world.clock),
    )

    async def registered() -> bool:
        return bool(await world.registry.sessions())

    async with Serving(worker) as serving:
        await serving.until(registered)
        result = await port.run_operation(world.current(request(dispatch_id="task-7")))

    assert (result.status, result.dispatch_id) == (OperationStatus.INTERRUPTED, "task-7")
    assert result.reason == (
        f"{REASON_CANCELLED} (its requester asked it to stop: no result within 30 s of asking)"
    )
    assert len(tool.stopped_at) == 1
    stored = await world.registry.operation(recording.operation_id)
    assert (stored.state, stored.cancel_requested) == (OperationState.SETTLED, True)


async def test_a_claimed_operation_whose_worker_went_silent_ends_interrupted_within_a_lease():
    """Bug caught: a cancel left for a worker that is gone. Its lease runs out, the operation
    is queued again unclaimable, and the requester waits out its grace on nothing (the lease
    rule R5.6 changed, reached here from the port)."""
    world = _world()
    port, recording = _port(world, max_attempts=3)
    session = await world.registry.register(registration())

    async def claim_then_go_silent() -> None:
        while await world.registry.claim(session.session_id) is None:
            await asyncio.sleep(0)

    silent = asyncio.ensure_future(claim_then_go_silent())
    result = await port.run_operation(world.current(request(dispatch_id="task-7")))
    await silent

    assert result.status is OperationStatus.INTERRUPTED
    assert result.reason == (
        f"cancelled while attempt 1 held it, and worker session {session.session_id} stopped "
        "renewing its lease before it answered (its requester asked it to stop: no result "
        "within 30 s of asking)"
    )
    stored = await world.registry.operation(recording.operation_id)
    assert (stored.state, stored.attempt) == (OperationState.SETTLED, 1)
    waited = world.clock.now - stored.created_at
    assert timedelta(seconds=30) < waited <= timedelta(seconds=30 + leasing.LEASE_SECONDS + 2)


async def test_a_result_at_the_waits_last_read_is_returned_and_nothing_is_cancelled():
    """Bug caught: the wait's end read before the operation's own state, so a result already
    in the registry is thrown away for a cancel."""
    world = _world()
    port, recording = _port(world)
    session = await world.registry.register(registration())

    async def claim_and_finish_late() -> None:
        while (claim := await world.registry.claim(session.session_id)) is None:
            await asyncio.sleep(0)
        while world.clock.now - T0 < timedelta(seconds=29):
            await world.registry.heartbeat(session.session_id, "online", claim.fence)
            await asyncio.sleep(0)
        await world.registry.submit_result(claim.fence, passing("task-7"))

    finishing = asyncio.ensure_future(claim_and_finish_late())
    result = await port.run_operation(world.current(request(dispatch_id="task-7")))
    await finishing

    assert result == passing("task-7")
    assert world.clock.now - T0 == timedelta(seconds=30)
    assert (await world.registry.operation(recording.operation_id)).cancel_requested is False
    assert [call[0] for call in recording.calls].count("POST") == 1


async def test_a_requester_that_is_stopped_asks_for_its_operation_to_stop_too():
    """Bug caught: an agent stopped mid-operation leaving it queued for a worker to run with
    nobody to read the result."""
    world = _world()
    port, recording = _port(world)
    await world.registry.register(registration())

    waiting = asyncio.ensure_future(
        port.run_operation(world.current(request(dispatch_id="task-7")))
    )
    while not recording.calls:
        await asyncio.sleep(0)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    stored = await world.registry.operation(recording.operation_id)
    assert stored.state is OperationState.SETTLED
    assert stored.result.reason == leasing.REASON_CANCELLED_UNCLAIMED


async def test_a_parting_cancel_that_fails_is_named_and_the_stop_still_happens(caplog):
    """Bug caught: the cancel's own failure raised in place of the stop it serves, or passed
    over with no word that the operation was left for a worker to run."""
    answers = iter([(201, _operation())])

    def handler(http_request: httpx.Request) -> httpx.Response:
        try:
            status, body = next(answers)
        except StopIteration:
            raise httpx.ConnectError("connection refused") from None
        return httpx.Response(status, json=body)

    parked = asyncio.Event()

    async def sleep(seconds: float) -> None:
        parked.set()
        await asyncio.Event().wait()

    port = RuntimeApiRemoteExecution(
        "http://runtime.test",
        _agent_token,
        origin=ORIGIN,
        wait=WAIT,
        max_attempts=2,
        transport=httpx.MockTransport(handler),
        sleep=sleep,
    )
    waiting = asyncio.ensure_future(port.run_operation(request()))
    await parked.wait()
    waiting.cancel()

    with caplog.at_level("WARNING"), pytest.raises(asyncio.CancelledError):
        await waiting

    (record,) = [r for r in caplog.records if r.message == "remote_operation_left_running"]
    assert record.operation_id == "rop_1"
    assert "ConnectError: connection refused" in record.reason


async def test_an_agent_whose_role_may_not_ask_is_a_refusal_and_never_a_result():
    """Bug caught: a deploy whose agent identity lacks the scope reading as "the operation
    didn't run", cycle after cycle, with the cause one layer down."""
    world = _world()
    world.tokens[AGENT_TOKEN] = identity(Role.VIEWER)
    port, _ = _port(world)
    await world.registry.register(registration())

    with pytest.raises(RequestRefused, match="HTTP 403 from /api/v1/remote-operations"):
        await port.run_operation(world.current(request()))


# ------------------------------------------------------------------ answers one at a time


async def test_no_answer_to_any_request_to_queue_within_the_wait_is_interrupted(caplog):
    """The runtime may have stored the operation and lost only its answer, so it may run
    (R5.6). Bug caught: that read as not executed, nothing is known to be queued, while the
    editor plays it for nobody; or one unanswered request ending the wait."""
    port, asked = _answering(httpx.ConnectError("connection refused"))

    with caplog.at_level("WARNING"):
        result = await port.run_operation(request(dispatch_id="task-7"))

    assert (result.status, result.dispatch_id) == (OperationStatus.INTERRUPTED, "task-7")
    assert result.reason == (
        "the runtime API gave no answer to any request to queue within 30 s, so the operation "
        "may be queued and whether it ran is unknown: no answer from "
        "/api/v1/remote-operations: ConnectError: connection refused"
    )
    assert asked == [("POST", "/api/v1/remote-operations")] * (1 + int(30 / POLL_SECONDS))
    unanswered = [r for r in caplog.records if r.message == "remote_operation_queue_unanswered"]
    assert len(unanswered) == int(30 / POLL_SECONDS)


async def test_a_create_whose_answer_was_lost_asks_again_and_reads_the_one_operation():
    """The machinery Campaign's dropped-response fault, at the port (R5.6, #3050): the runtime
    stores the operation and its answer never arrives. Bug caught: a second operation queued
    for the same send, both run in the editor; or the first reported not executed while it
    runs."""
    world = _world()
    port, recording = _port(world)
    session = await world.registry.register(registration())
    dropped: list[int] = []
    inner = recording.handle_async_request

    async def drop_the_first_create(http_request: httpx.Request) -> httpx.Response:
        reply = await inner(http_request)
        if http_request.method == "POST" and http_request.url.path.endswith("operations"):
            if not dropped:
                dropped.append(reply.status_code)
                raise httpx.ReadTimeout("the answer was lost", request=http_request)
        return reply

    recording.handle_async_request = drop_the_first_create  # type: ignore[method-assign]

    async def claim_and_pass() -> None:
        while (claim := await world.registry.claim(session.session_id)) is None:
            await asyncio.sleep(0)
        await world.registry.submit_result(claim.fence, passing("send-1"))

    passing_it = asyncio.ensure_future(claim_and_pass())
    asked = world.current(request(task_id="task_7", dispatch_id="send-1"))
    result = await port.run_operation(asked)
    await passing_it

    assert result == passing("send-1")
    creates = [(path, status) for method, path, status, _ in recording.calls if method == "POST"]
    assert dropped == [201]
    assert creates == [("/api/v1/remote-operations", 201), ("/api/v1/remote-operations", 200)]
    assert await world.registry.claim(session.session_id) is None


async def test_a_send_that_is_no_longer_current_is_a_refusal_naming_it():
    """Bug caught: a stale send's refusal read as an operation that didn't run, so the task's
    record says not executed while the current send's operation runs."""
    world = _world()
    port, _ = _port(world)
    await world.registry.register(registration())
    world.sends.waiting["task_7"] = "send-2"

    with pytest.raises(RequestRefused, match="REMOTE_OPERATION_SEND_NOT_CURRENT"):
        await port.run_operation(request(task_id="task_7", dispatch_id="send-1"))


async def test_a_runtime_that_restarts_during_the_wait_is_read_again_and_the_result_returned(
    caplog,
):
    """Bug caught: one failed read ending the wait, when the operation and its lease outlive a
    runtime restart (R3.3)."""
    port, asked = _answering(
        (201, _operation()),
        httpx.ConnectError("connection refused"),
        (503, "restarting"),
        (200, _operation("settled", result_to_wire(passing("task-7")))),
    )

    with caplog.at_level("WARNING"):
        result = await port.run_operation(request(dispatch_id="task-7"))

    assert result == passing("task-7")
    assert (
        asked
        == [("POST", "/api/v1/remote-operations")]
        + [("GET", "/api/v1/remote-operations/rop_1")] * 3
    )
    unanswered = [
        r.reason for r in caplog.records if r.message == "remote_operation_read_unanswered"
    ]
    assert unanswered == [
        "no answer from /api/v1/remote-operations/rop_1: ConnectError: connection refused",
        "HTTP 503 from /api/v1/remote-operations/rop_1: restarting",
    ]


async def test_a_runtime_unreachable_to_the_end_of_the_wait_is_interrupted_and_says_so():
    """Bug caught: an operation that was queued, and may have run, read as not executed."""
    port, asked = _answering((201, _operation()), httpx.ConnectError("connection refused"))

    result = await port.run_operation(request(dispatch_id="task-7"))

    assert result.status is OperationStatus.INTERRUPTED
    assert result.reason == (
        "no result within 30 s of asking, and the runtime API can't be reached to stop "
        "operation rop_1: whether it ran is unknown (no answer from "
        "/api/v1/remote-operations/rop_1/cancel: ConnectError: connection refused)"
    )
    assert asked[-1] == ("POST", "/api/v1/remote-operations/rop_1/cancel")
    assert len(asked) == 1 + int(30 / POLL_SECONDS) + 1


async def test_an_operation_still_held_a_lease_after_its_cancel_is_interrupted_naming_its_state():
    """Bug caught: a requester that waits for ever on a worker that keeps its lease and never
    answers the cancel."""
    port, asked = _answering((201, _operation()), (200, _operation("claimed", attempt=1)))

    result = await port.run_operation(request(dispatch_id="task-7"))

    assert result.status is OperationStatus.INTERRUPTED
    assert result.reason == (
        "no result within 30 s of asking; operation rop_1 was asked to stop and is still "
        "claimed 60 s later"
    )
    assert len(asked) == 1 + int(30 / POLL_SECONDS) + 1 + int(60 / POLL_SECONDS)


async def test_a_result_that_crosses_the_cancel_stands_as_it_was_submitted():
    """Bug caught: a completed result relabelled as stopped, because it settled between the
    last read and the cancel."""
    reads = int(30 / POLL_SECONDS)
    port, asked = _answering(
        (201, _operation()),
        *[(200, _operation("claimed", attempt=1))] * reads,
        (200, _operation("settled", result_to_wire(passing("task-7")), cancel_requested=False)),
    )

    result = await port.run_operation(request(dispatch_id="task-7"))

    assert result == passing("task-7")
    assert asked[-1] == ("POST", "/api/v1/remote-operations/rop_1/cancel")
    assert len(asked) == 1 + reads + 1


async def test_an_operation_the_runtime_no_longer_knows_is_interrupted():
    """Bug caught: a registry kept in memory and restarted (its rows gone) read as a refusal
    that fails the task, or as an operation that never ran."""
    port, _ = _answering(
        (201, _operation()),
        (404, _envelope("REMOTE_OPERATION_NOT_FOUND", operation_id="rop_1")),
    )

    result = await port.run_operation(request(dispatch_id="task-7"))

    assert (result.status, result.dispatch_id) == (OperationStatus.INTERRUPTED, "task-7")
    assert result.reason == (
        "the runtime API no longer knows operation rop_1, which it had queued: whether it "
        "ran is unknown"
    )


@pytest.mark.parametrize(
    ("answers", "error", "match"),
    [
        (
            [(404, {"detail": "Not Found"})],
            RequestRefused,
            "HTTP 404 from /api/v1/remote-operations: {'detail': 'Not Found'}",
        ),
        (
            [(201, _operation()), (404, {"detail": "Not Found"})],
            RequestRefused,
            "HTTP 404 from /api/v1/remote-operations/rop_1",
        ),
        ([(401, _envelope("UNAUTHENTICATED"))], RequestRefused, "HTTP 401"),
        ([(202, _operation())], RequestRefused, "HTTP 202 from /api/v1/remote-operations"),
        ([(201, "<html>a proxy</html>")], RuntimeAnswerUnreadable, "a body that isn't JSON"),
        (
            [(201, {k: v for k, v in _operation().items() if k != "state"})],
            RuntimeAnswerUnreadable,
            "the answer has no 'state'",
        ),
        ([(201, _operation("running"))], RuntimeAnswerUnreadable, "state is 'running'"),
        (
            [(201, _operation("settled"))],
            RuntimeAnswerUnreadable,
            "an operation that is settled with result None",
        ),
        (
            [(201, _operation("queued", result_to_wire(passing())))],
            RuntimeAnswerUnreadable,
            "an operation that is queued with result",
        ),
        (
            [(201, _operation("settled", {"status": "completed"}))],
            RuntimeAnswerUnreadable,
            "the operation's result can't be read: result lacks",
        ),
        (
            [(201, _operation(lease_seconds=0))],
            RuntimeAnswerUnreadable,
            "lease_seconds is 0",
        ),
        (
            [(201, _operation()), (200, _operation(operation_id="rop_2"))],
            RuntimeAnswerUnreadable,
            "asked about operation rop_1 and answered about rop_2",
        ),
        (
            [(409, _envelope("NO_WORKER_FOR_OPERATION"))],
            RuntimeAnswerUnreadable,
            "the answer has no 'reason'",
        ),
    ],
    ids=[
        "an-address-that-isnt-the-runtime",
        "a-404-that-isnt-the-routes-own",
        "credentials-refused",
        "a-create-answered-neither-200-nor-201",
        "not-json",
        "a-key-missing",
        "a-state-outside-the-vocabulary",
        "settled-with-no-result",
        "a-result-before-it-settled",
        "a-result-that-cant-be-read",
        "a-lease-of-no-length",
        "another-operations-answer",
        "no-worker-with-no-reason",
    ],
)
async def test_a_refusal_or_an_unreadable_answer_raises_and_is_never_a_result(
    answers, error, match
):
    """Silent fallbacks, at the requester's wire. Bug caught: any of these read as an operation
    that didn't run (a ``blocked_unverified`` cycle with a deploy defect behind it), or as one
    still queued (polled until the wait ends)."""
    port, _ = _answering(*answers)

    with pytest.raises(error, match=match):
        await port.run_operation(request())


async def test_with_no_identity_configured_a_call_carries_no_token():
    """The heartbeats' rule (#326): an auth-disabled deploy sends none. Bug caught: a literal
    ``Bearer None`` sent, which a runtime that authenticates refuses for the wrong reason."""
    seen: list[str | None] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen.append(http_request.headers.get("Authorization"))
        return httpx.Response(201, json=_operation("settled", result_to_wire(passing())))

    port = RuntimeApiRemoteExecution(
        "http://runtime.test",
        None,
        origin=ORIGIN,
        wait=WAIT,
        max_attempts=1,
        transport=httpx.MockTransport(handler),
    )

    assert await port.run_operation(request()) == passing()
    assert seen == [None]


# -------------------------------------------------------------------------- the factory


def test_none_binds_no_port_and_an_unknown_provider_is_refused():
    """Bug caught: ``none`` bound to an adapter that answers for a provider, or a misspelled
    provider read as ``none``."""
    settings = {
        "base_url": "http://runtime-api:8001",
        "token": None,
        "origin": ORIGIN,
        "wait": WAIT,
        "max_attempts": 2,
    }

    assert create_remote_execution("none", **settings) is None
    assert isinstance(create_remote_execution("runtime_api", **settings), RuntimeApiRemoteExecution)
    with pytest.raises(ValueError, match="Unknown remote execution provider: runtime-api"):
        create_remote_execution("runtime-api", **settings)


@pytest.mark.parametrize(
    ("over", "match"),
    [({"wait": timedelta(0)}, "wait is 0:00:00"), ({"max_attempts": 0}, "max_attempts is 0")],
)
def test_a_port_with_no_time_or_no_attempt_to_give_is_refused_when_it_is_built(over, match):
    settings = {"origin": ORIGIN, "wait": WAIT, "max_attempts": 2, **over}
    with pytest.raises(ValueError, match=match):
        RuntimeApiRemoteExecution("http://runtime.test", None, **settings)


async def test_the_attempts_the_port_was_given_are_the_operations():
    """Bug caught: ``max_attempts`` from the config dropped on the way to the queue, and every
    operation given some other number."""
    world = _world()
    port, recording = _port(world, max_attempts=4)
    await world.registry.register(registration())

    waiting = asyncio.ensure_future(port.run_operation(world.current(request())))
    while not recording.calls:
        await asyncio.sleep(0)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    assert (await world.registry.operation(recording.operation_id)).max_attempts == 4

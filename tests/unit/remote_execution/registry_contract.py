"""What the worker registry guarantees, whatever keeps its rows (SIP-0117 R3.3, R5.4).

One suite, run over the memory store by the unit tests and over Postgres by the integration
tests. A subclass supplies ``store``. Each test enters at ``WorkerRegistry``, the object the
routes call, so the rules and the rows are proved together.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from squadops.remote_execution import leasing
from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
    Scenario,
)
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.workers import (
    Fence,
    FenceRefusal,
    OperationState,
    ServedOperation,
    UnknownOperation,
    UnknownSession,
    WorkerRegistration,
)

T0 = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
LEASE = timedelta(seconds=leasing.LEASE_SECONDS)
PLAY = ServedOperation("fixture-editor", "play_scenario")
BUILD = ServedOperation("fixture-editor", "build_place")
ORIGIN = {"cycle_id": "cyc_1", "run_id": "run_1", "task_id": "task_1"}


@dataclass
class Clock:
    now: datetime = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def request(served: ServedOperation = PLAY, dispatch_id: str = "dispatch-1"):
    return RemoteOperationRequest(
        contract="game.playtest",
        mode="simulation",
        provider=served.provider,
        operation=served.operation,
        location="worker",
        source_revision="rev_1",
        source_files={"src/server/init.luau": "return {}\n"},
        scenario=Scenario("scn_1", "sha256:abc", ("door_opens", "score_counts")),
        dispatch_id=dispatch_id,
    )


def passing(dispatch_id: str = "dispatch-1", by: str = "worker") -> RemoteOperationResult:
    return RemoteOperationResult(
        status=OperationStatus.COMPLETED,
        records=(
            AssertionRecord("door_opens", AssertionOutcome.PASSED, "open", "open", "server"),
            AssertionRecord("score_counts", AssertionOutcome.FAILED, "0", "1", "server"),
        ),
        provider_version="fixture-editor@1",
        ran_with={"worker": by},
        dispatch_id=dispatch_id,
    )


def registration(worker_id: str = "macbook", *served: ServedOperation) -> WorkerRegistration:
    return WorkerRegistration(
        worker_id=worker_id,
        platform="macos-arm64",
        tool_versions={"fixture-editor": "1.0"},
        operations=served or (PLAY,),
    )


class WorkerRegistryContract:
    @pytest.fixture
    def clock(self) -> Clock:
        return Clock()

    @pytest.fixture
    def registry(self, store, clock) -> WorkerRegistry:
        return WorkerRegistry(store, clock=clock)

    async def test_a_claim_is_the_oldest_operation_the_session_serves_under_a_new_lease(
        self, registry, clock
    ):
        """Bug caught: a worker handed an operation it doesn't serve, a newer operation before
        an older one, or a second claim while it still holds the first."""
        other = await registry.enqueue(request(BUILD), ORIGIN, max_attempts=2)
        clock.advance(1)
        first = await registry.enqueue(request(PLAY), ORIGIN, max_attempts=2)
        clock.advance(1)
        await registry.enqueue(request(PLAY), ORIGIN, max_attempts=2)
        session = await registry.register(registration("macbook", PLAY))

        claim = await registry.claim(session.session_id)
        again = await registry.claim(session.session_id)

        assert claim.fence.operation_id == first.operation_id
        assert (claim.fence.attempt, claim.fence.session_id) == (1, session.session_id)
        assert claim.request == request(PLAY)
        assert claim.lease_expires_at == clock.now + LEASE
        assert claim.reconcile_first is False
        assert again is None
        assert (await registry.operation(other.operation_id)).state is OperationState.QUEUED

    @pytest.mark.parametrize(
        ("stale", "refusal"),
        [
            ({"attempt": 2}, FenceRefusal.STALE_ATTEMPT),
            ({"session_id": "wks-someone-else"}, FenceRefusal.STALE_SESSION),
            ({"lease_id": "lease-earlier"}, FenceRefusal.STALE_LEASE),
            ({"operation_id": "rop-never-queued"}, FenceRefusal.UNKNOWN_OPERATION),
        ],
        ids=["attempt", "session", "lease", "operation"],
    )
    async def test_a_result_under_any_id_that_is_not_current_is_refused_and_recorded(
        self, registry, stale, refusal
    ):
        """Bug caught: a fence checked on some of its ids, so a result with the right lease
        and the wrong attempt settles the operation. And a refusal that leaves no record."""
        queued = await registry.enqueue(request(), ORIGIN, max_attempts=2)
        session = await registry.register(registration())
        claim = await registry.claim(session.session_id)
        presented = Fence(**{**claim.fence.__dict__, **stale})

        refused = await registry.submit_result(presented, passing())

        assert refused.refusal is refusal
        assert (await registry.operation(queued.operation_id)).state is OperationState.CLAIMED
        recorded = await registry.refusals(presented.operation_id)
        assert [(r.fence, r.refusal) for r in recorded] == [(presented, refusal)]

        accepted = await registry.submit_result(claim.fence, passing())

        assert accepted.refusal is None
        settled = await registry.operation(queued.operation_id)
        assert (settled.state, settled.result) == (OperationState.SETTLED, passing())
        assert settled.fence is None

    async def test_a_late_result_never_satisfies_a_newer_attempt(self, registry, clock):
        """R3.3's fence, whole. Bug caught: the first worker's completion, arriving after its
        lease ran out and another worker took the operation, read as the operation's result."""
        queued = await registry.enqueue(request(), ORIGIN, max_attempts=3)
        first = await registry.register(registration("macbook"))
        second = await registry.register(registration("mac-mini"))
        early = await registry.claim(first.session_id)
        clock.advance(leasing.LEASE_SECONDS + 1)

        newer = await registry.claim(second.session_id)
        late = await registry.submit_result(early.fence, passing(by="macbook"))

        assert newer.fence.attempt == 2
        assert late.refusal is FenceRefusal.STALE_ATTEMPT
        held = await registry.operation(queued.operation_id)
        assert (held.state, held.fence) == (OperationState.CLAIMED, newer.fence)

        assert (await registry.submit_result(newer.fence, passing(by="mac-mini"))).refusal is None
        assert (await registry.operation(queued.operation_id)).result.ran_with == {
            "worker": "mac-mini"
        }

    async def test_a_lease_that_runs_out_requeues_and_the_last_attempt_ends_interrupted(
        self, registry, clock
    ):
        """Bug caught: an operation held for ever by a worker that went to sleep; an attempt
        number that doesn't advance, so a late result's fence matches the next attempt; or an
        exhausted operation read as failed or passed."""
        queued = await registry.enqueue(request(dispatch_id="d-7"), ORIGIN, max_attempts=2)
        session = await registry.register(registration())
        first = await registry.claim(session.session_id)
        clock.advance(leasing.LEASE_SECONDS + 1)

        requeued = await registry.operation(queued.operation_id)
        second = await registry.claim(session.session_id)

        assert (requeued.state, requeued.attempt, requeued.fence) == (
            OperationState.QUEUED,
            1,
            None,
        )
        assert second.fence.attempt == 2
        assert second.fence.lease_id != first.fence.lease_id
        assert second.reconcile_first is True

        clock.advance(leasing.LEASE_SECONDS + 1)
        ended = await registry.operation(queued.operation_id)

        assert ended.state is OperationState.SETTLED
        assert ended.result.status is OperationStatus.INTERRUPTED
        assert "attempt 2 of 2" in ended.result.reason
        assert session.session_id in ended.result.reason
        assert (ended.result.dispatch_id, ended.result.records) == ("d-7", ())
        assert await registry.claim(session.session_id) is None

    async def test_a_heartbeat_renews_the_lease_and_carries_a_cancel(self, registry, clock):
        """Bug caught: a long operation losing its lease while its worker reports in; a cancel
        the worker never hears about; a cancelled operation's ``interrupted`` result refused."""
        queued = await registry.enqueue(request(), ORIGIN, max_attempts=1)
        session = await registry.register(registration())
        claim = await registry.claim(session.session_id)

        clock.advance(40)
        renewed = await registry.heartbeat(session.session_id, "online", claim.fence)
        clock.advance(40)  # 80 s after the claim: past the first expiry, inside the renewed one
        await registry.cancel(queued.operation_id)
        told = await registry.heartbeat(session.session_id, "degraded", claim.fence)

        assert (renewed.refusal, renewed.expires_at) == (None, T0 + timedelta(seconds=40) + LEASE)
        assert renewed.cancel_requested is False
        assert (told.refusal, told.cancel_requested) == (None, True)
        assert await registry.heartbeat(session.session_id, "online", None) is None

        interrupted = RemoteOperationResult(
            status=OperationStatus.INTERRUPTED,
            reason="cancelled during the play session",
            dispatch_id="dispatch-1",
        )
        assert (await registry.submit_result(claim.fence, interrupted)).refusal is None
        assert (await registry.operation(queued.operation_id)).result == interrupted

    async def test_a_heartbeat_after_the_lease_ran_out_is_told_so_and_the_operation_is_freed(
        self, registry, clock
    ):
        """Bug caught: a heartbeat that revives a lease already run out, so two workers can
        hold one operation once the second has claimed it."""
        queued = await registry.enqueue(request(), ORIGIN, max_attempts=2)
        session = await registry.register(registration())
        claim = await registry.claim(session.session_id)
        clock.advance(leasing.LEASE_SECONDS + 1)

        reading = await registry.heartbeat(session.session_id, "online", claim.fence)

        assert (reading.refusal, reading.expires_at) == (FenceRefusal.LEASE_EXPIRED, None)
        assert (await registry.operation(queued.operation_id)).state is OperationState.QUEUED
        late = await registry.submit_result(claim.fence, passing())
        assert late.refusal is FenceRefusal.NOT_CLAIMED

    async def test_a_worker_that_registers_again_ends_its_session_and_the_attempt_it_held(
        self, registry
    ):
        """A restart. Bug caught: the old session still able to renew or submit, or the
        operation it held staying claimed by a process that no longer exists."""
        queued = await registry.enqueue(request(), ORIGIN, max_attempts=2)
        before = await registry.register(registration("macbook"))
        held = await registry.claim(before.session_id)

        after = await registry.register(registration("macbook"))

        assert after.session_id != before.session_id
        with pytest.raises(UnknownSession):
            await registry.heartbeat(before.session_id, "online", held.fence)
        with pytest.raises(UnknownSession):
            await registry.claim(before.session_id)
        assert (await registry.operation(queued.operation_id)).state is OperationState.QUEUED
        assert [s.session_id for s, _ in await registry.sessions()] == [after.session_id]

        reclaimed = await registry.claim(after.session_id)

        assert (reclaimed.fence.attempt, reclaimed.reconcile_first) == (2, True)
        stale = await registry.submit_result(held.fence, passing())
        assert stale.refusal is FenceRefusal.STALE_ATTEMPT

    async def test_the_same_fence_resubmitting_its_accepted_result_is_answered_once(self, registry):
        """A worker whose first submission's reply was lost. Bug caught: the retry refused, so
        the worker reports a failure for work that was accepted; or the retry's body stored
        over the result that was accepted."""
        queued = await registry.enqueue(request(), ORIGIN, max_attempts=1)
        session = await registry.register(registration())
        claim = await registry.claim(session.session_id)
        await registry.submit_result(claim.fence, passing(by="first"))

        again = await registry.submit_result(claim.fence, passing(by="retry"))

        assert (again.refusal, again.replayed) == (None, True)
        assert (await registry.operation(queued.operation_id)).result.ran_with == {
            "worker": "first"
        }
        assert await registry.refusals(queued.operation_id) == []

    async def test_a_cancel_before_any_claim_settles_as_not_executed(self, registry):
        """Bug caught: a cancelled operation a worker can still claim and run; or one that
        reads interrupted, though no worker began it."""
        queued = await registry.enqueue(request(dispatch_id="d-9"), ORIGIN, max_attempts=2)
        session = await registry.register(registration())

        cancelled = await registry.cancel(queued.operation_id)

        assert cancelled.state is OperationState.SETTLED
        assert (cancelled.result.status, cancelled.result.reason, cancelled.result.dispatch_id) == (
            OperationStatus.NOT_EXECUTED,
            leasing.REASON_CANCELLED_UNCLAIMED,
            "d-9",
        )
        assert await registry.claim(session.session_id) is None
        with pytest.raises(UnknownOperation):
            await registry.cancel("rop-never-queued")

    async def test_two_workers_claiming_at_once_never_share_an_operation(self, registry):
        """Bug caught: a claim that reads the queue and writes the lease in two steps, so two
        workers that ask together are both handed the one operation."""
        queued = await registry.enqueue(request(), ORIGIN, max_attempts=2)
        sessions = [await registry.register(registration(f"worker-{n}")) for n in range(4)]

        claims = await asyncio.gather(*(registry.claim(s.session_id) for s in sessions))

        won = [c for c in claims if c is not None]
        assert [c.fence.operation_id for c in won] == [queued.operation_id]
        assert won[0].fence.attempt == 1

    @pytest.mark.parametrize(
        ("silent_for", "serving", "reason", "unreachable"),
        [
            (0, BUILD, "no registered worker serves fixture-editor/play_scenario", ()),
            (
                leasing.SESSION_SILENT_SECONDS + 1,
                PLAY,
                "macbook serves fixture-editor/play_scenario and is offline "
                "(last heard from at 2026-11-10T15:00:00+00:00)",
                ("macbook",),
            ),
            (leasing.SESSION_SILENT_SECONDS, PLAY, None, ()),
        ],
        ids=["nobody serves it", "its worker went silent", "its worker is heard from"],
    )
    async def test_an_operation_no_worker_can_run_now_says_which_reason(
        self, registry, clock, silent_for, serving, reason, unreachable
    ):
        """Bug caught: "no worker" for a worker that is only asleep, which sends the operator
        to install something that is installed; or a silent worker counted as available, so
        the operation waits out its whole timeout."""
        await registry.register(registration("macbook", serving))
        clock.advance(silent_for)

        verdict = await registry.no_worker_for("fixture-editor", "play_scenario")

        assert (verdict.reason if verdict else None) == reason
        assert (verdict.unreachable if verdict else ()) == unreachable
        health = "offline" if silent_for > leasing.SESSION_SILENT_SECONDS else "online"
        assert [status for _, status in await registry.sessions()] == [health]

    async def test_a_registration_that_could_never_be_matched_is_refused_with_every_defect(
        self, registry
    ):
        """Bug caught: a worker registered with nothing to serve, which then looks available
        and is never given work; or only the first defect named."""
        bad = WorkerRegistration(
            worker_id=" ",
            platform="",
            tool_versions={"studio": ""},
            operations=(PLAY, PLAY, ServedOperation("fixture-editor", "")),
        )

        with pytest.raises(ValueError) as raised:
            await registry.register(bad)

        assert str(raised.value).split("; ") == [
            "worker_id is empty",
            "platform is empty",
            "fixture-editor/play_scenario is named more than once",
            "an operation with an empty provider or name: ('fixture-editor', '')",
            "a tool version with an empty name or value: 'studio': ''",
        ]
        assert await registry.sessions() == []
        with pytest.raises(ValueError, match="names no operation"):
            await registry.register(WorkerRegistration("macbook", "macos-arm64", {}, operations=()))

    async def test_a_health_word_outside_the_vocabulary_is_refused(self, registry):
        """Bug caught: ``busy`` stored as a health value. Busy is the lease."""
        session = await registry.register(registration())

        with pytest.raises(ValueError, match="'busy' is none of online, degraded"):
            await registry.heartbeat(session.session_id, "busy", None)

    async def test_a_transaction_that_fails_keeps_none_of_its_writes(self, store, registry):
        """The store's own promise. Bug caught: a claim whose lease is written and whose
        attempt row is not, which leaves an operation no fence can ever settle."""
        queued = await registry.enqueue(request(), ORIGIN, max_attempts=1)
        session = await registry.register(registration())

        with pytest.raises(RuntimeError, match="mid-transaction"):
            async with store.exclusive() as tx:
                operation = await tx.operation(queued.operation_id)
                await tx.save_operation(
                    leasing.claimed(operation, session, "lease-half-written", T0)
                )
                raise RuntimeError("mid-transaction")

        assert (await registry.operation(queued.operation_id)).state is OperationState.QUEUED
        assert (await registry.claim(session.session_id)).fence.attempt == 1

"""Tests for DispatchedFlowExecutor (adapters/cycles/dispatched_flow_executor.py).

Covers dispatch via RabbitMQ publish/consume, sequential happy path,
fail-fast, cancellation, artifact storage, output chaining, and timeout.

Mirrors test_flow_executor.py structure but with mocked QueuePort instead
of mocked AgentOrchestrator.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.events.types import EventType
from squadops.runtime import reasons
from squadops.runtime.coordinator import TransitionOutcome
from squadops.tasks.models import TaskEnvelope, TaskResult

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
# FakeReplyRouter + the `reply_router` fixture live in conftest.py (shared by
# all executor test files post-SIP-0094 cutover).


@pytest.fixture
def mock_registry():
    mock = AsyncMock()
    mock.get_run.return_value = Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )
    mock.update_run_status.side_effect = lambda run_id, status: Run(
        run_id=run_id,
        cycle_id="cyc_001",
        run_number=1,
        status=status.value,
        initiated_by="api",
        resolved_config_hash="hash",
    )
    mock.append_artifact_refs.return_value = mock.get_run.return_value
    # SIP-0079: No checkpoint by default (fresh run)
    mock.get_latest_checkpoint.return_value = None
    return mock


@pytest.fixture
def mock_vault():
    mock = AsyncMock()
    mock.store.side_effect = lambda ref, content: ref
    return mock


@pytest.fixture
def mock_queue(reply_router):
    """Mock QueuePort bound to the reply router: publishing a ``comms.task``
    auto-delivers the agent's reply (SIP-0094 cutover)."""
    mock = AsyncMock()
    mock.ack.return_value = None
    mock.invalidate_queue.return_value = None
    mock.consume.return_value = []
    return reply_router.bind(mock)


@pytest.fixture
def mock_squad_profile():
    mock = AsyncMock()
    profile = SquadProfile(
        profile_id="full",
        name="Full Squad",
        description="All",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )
    mock.resolve_snapshot.return_value = (profile, "sha256:abc")
    return mock


@pytest.fixture
def cycle():
    return Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref_123",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
    )


@pytest.fixture
def run():
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )


@pytest.fixture
def executor(mock_registry, mock_vault, mock_queue, mock_squad_profile, reply_router, cycle, run):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    mock_registry.get_cycle.return_value = cycle
    mock_registry.get_run.return_value = run
    return DispatchedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,  # Short timeout for tests
        reply_router=reply_router,
    )


# ---------------------------------------------------------------------------
# Dispatch mechanics
# ---------------------------------------------------------------------------


class TestDispatchTask:
    """Verify publish/consume mechanics of _dispatch_task."""

    async def test_publishes_to_agent_comms_queue(
        self, executor, mock_queue, mock_registry, cycle
    ) -> None:
        """Task is published to {agent_id}_comms with comms.task action."""
        # Default reply_router responder auto-succeeds the dispatched task.
        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(envelope, "run_001")

        # Verify publish to correct queue
        mock_queue.publish.assert_awaited_once()
        pub_args = mock_queue.publish.call_args
        assert pub_args.args[0] == "neo_comms"

        published = json.loads(pub_args.args[1])
        assert published["action"] == "comms.task"
        # SIP-0094: reply address is now the per-agent reply queue.
        assert published["metadata"]["reply_queue"] == "neo_replies"
        assert published["payload"]["task_id"] == "task_abc"

    async def test_returns_agent_result_from_router(self, executor, reply_router) -> None:
        """The agent's TaskResult (delivered via the reply router) is returned
        by _dispatch_task with its outputs intact (SIP-0094)."""
        reply_router.results["task_abc"] = TaskResult(
            task_id="task_abc", status="SUCCEEDED", outputs={"summary": "implemented"}
        )

        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

        result = await executor._dispatch_task(envelope, "run_001")

        assert result.task_id == "task_abc"
        assert result.status == "SUCCEEDED"
        assert result.outputs["summary"] == "implemented"
        # The reply router/subscribe primitive owns ack now — not the executor
        # (ack behavior is covered in test_reply_router.py).

    async def test_timeout_returns_failed(self, executor, reply_router) -> None:
        """If the agent never replies within the timeout, returns FAILED."""
        reply_router.suppress.add("task_abc")  # agent never replies
        executor._task_timeout = 0.1  # Very short

        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

        # NOTE: do NOT patch asyncio.sleep here. The concurrent heartbeat loop
        # (`while True: await asyncio.sleep(30)`) would then spin instantly and
        # starve the event loop, so wait_for's 0.1s timer never fires. With real
        # sleep the heartbeat parks for 30s and the timeout fires cleanly.
        result = await executor._dispatch_task(envelope, "run_001")

        assert result.status == "FAILED"
        assert "Timed out" in result.error

    # SIP-0094 removed the executor-side reply polling loop (consume_blocking +
    # invalidate_queue recovery). Two tests that asserted that mechanism —
    # transient-consume-error recovery and "uses long-block consume not short
    # poll" — are deleted here; their coverage moved to the reply substrate:
    # channel-close resubscribe is tested in tests/unit/comms/
    # test_rabbitmq_adapter.py (94.2b) and the router resolve path in
    # tests/unit/cycles/test_reply_router.py.


# ---------------------------------------------------------------------------
# Sequential happy path
# ---------------------------------------------------------------------------


class TestSequentialHappyPath:
    """Sequential mode: 5 tasks dispatched via queue, run completes."""

    @staticmethod
    def _wire_canned_replies(mock_queue):
        """Make every dispatched task reply SUCCEEDED with one artifact, so the
        run progresses and artifacts get stored."""

        def responder(env):
            return TaskResult(
                task_id=env["task_id"],
                status="SUCCEEDED",
                outputs={
                    "summary": "stub output",
                    "role": "strat",
                    "artifacts": [
                        {
                            "name": "output.md",
                            "content": "# Output",
                            "media_type": "text/markdown",
                            "type": "document",
                        }
                    ],
                },
            )

        mock_queue.reply_router.responder = responder

    async def test_run_completes(self, executor, mock_registry, mock_queue) -> None:
        """5 tasks dispatched; run transitions queued -> running -> completed."""
        self._wire_canned_replies(mock_queue)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        status_calls = mock_registry.update_run_status.call_args_list
        statuses = [c.args[1] for c in status_calls]
        assert statuses[0] == RunStatus.RUNNING
        assert statuses[-1] == RunStatus.COMPLETED

    async def test_publish_called_5_times(self, executor, mock_queue) -> None:
        """queue.publish called once per pipeline step (5 total)."""
        self._wire_canned_replies(mock_queue)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        assert mock_queue.publish.call_count == 5

    async def test_publishes_to_correct_agent_queues(self, executor, mock_queue) -> None:
        """Each task published to the correct agent's comms queue."""
        self._wire_canned_replies(mock_queue)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        published_queues = [call.args[0] for call in mock_queue.publish.call_args_list]
        assert published_queues == [
            "nat_comms",  # strategy.analyze_prd -> strat -> nat
            "neo_comms",  # development.design -> dev -> neo
            "eve_comms",  # qa.validate -> qa -> eve
            "data-agent_comms",  # data.report -> data -> data-agent
            "max_comms",  # governance.review -> lead -> max
        ]

    async def test_artifacts_stored(self, executor, mock_vault, mock_queue) -> None:
        """vault.store called for each task's artifacts."""
        self._wire_canned_replies(mock_queue)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 5 task artifacts + 1 run report = 6
        assert mock_vault.store.call_count == 6


# ---------------------------------------------------------------------------
# Fail-fast
# ---------------------------------------------------------------------------


class TestFailFast:
    """Outcome routing: persistent failures retry, trigger correction, then abort."""

    async def test_persistent_failure_retries_then_aborts(
        self, executor, mock_queue, mock_registry, reply_router
    ) -> None:
        """All dispatches FAILED → retry + correction protocol → run FAILED.

        With outcome routing (SIP-0079):
        1. First dispatch: FAILED → RETRYABLE_FAILURE (attempt 1 < max_retries 2)
        2. Retry same task: FAILED → SEMANTIC_FAILURE (attempt 2 >= max_retries 2)
        3. Correction protocol: dispatches analyze_failure + correction_decision
        4. Both correction tasks also fail → correction_path defaults to "abort"
        Total publishes: 2 (task retries) + 2 (correction tasks) = 4
        """
        # Every agent reply is a failure -> drives the retry/correction path.
        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"], status="FAILED", error="boom"
        )

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 2 (retry) + 2 (correction tasks) = 4 publishes
        assert mock_queue.publish.call_count == 4

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestCancellation:
    """Run cancellation via local set and registry polling."""

    async def test_cancel_run_sets_local_and_registry(self, executor, mock_registry) -> None:
        await executor.cancel_run("run_001")
        assert "run_001" in executor._cancelled
        mock_registry.cancel_run.assert_awaited_once_with("run_001")

    async def test_cancel_before_first_task(self, executor, mock_registry, mock_queue) -> None:
        """If registry returns cancelled, no tasks published."""
        mock_registry.get_run.return_value = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="cancelled",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        mock_queue.publish.assert_not_awaited()
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.CANCELLED in terminal_statuses


# ---------------------------------------------------------------------------
# SIP-0089 §2.5 — reserve-buffer recruitment guard
# ---------------------------------------------------------------------------


class TestReserveBufferGuard:
    """A participating agent's imminent/active hard duty window defers the run.

    The guard fires after plan generation (the plan names every recruited agent)
    and before dispatch: on conflict the run is PAUSED (a deferral, resumable via
    ``squadops runs resume``), no task is published, and the RUN_PAUSED event
    carries the duty-deferral reason so it is distinguishable from a BLOCKED
    pause. The opposite bug — a wired guard false-positively blocking a clean
    run — is guarded by the no-conflict case.
    """

    @staticmethod
    def _assignment_port(assignments):
        port = AsyncMock()
        port.list_active_assignments.return_value = assignments
        return port

    @staticmethod
    def _hard_duty(agent_id):
        from squadops.runtime.models import Assignment, DutyWindow

        # Window spans a wide range so window_state == "active" at wall-clock now
        # (the guard reads datetime.now(UTC); this avoids coupling to real time).
        return Assignment(
            assignment_id=f"duty-{agent_id}",
            agent_id=agent_id,
            assignment_type="duty",
            assigned_role="support",
            priority=10,
            strictness="hard",
            active_window=DutyWindow(
                start=datetime(2000, 1, 1, tzinfo=UTC),
                end=datetime(2100, 1, 1, tzinfo=UTC),
                timezone="UTC",
            ),
            reserve_before_window=timedelta(minutes=15),
            reserve_after_window=timedelta(minutes=10),
            recall_policy="graceful",
            graceful_window=timedelta(minutes=5),
            missed_window_policy="skip",
            allowed_off_window_modes=("ambient", "cycle"),
        )

    def _build(
        self,
        *,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        reply_router,
        cycle,
        run,
        event_bus,
        assignment_port,
    ):
        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

        mock_registry.get_cycle.return_value = cycle
        mock_registry.get_run.return_value = run
        return DispatchedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
            reply_router=reply_router,
            event_bus=event_bus,
            assignment_port=assignment_port,
        )

    async def test_imminent_hard_duty_pauses_run_before_dispatch(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        reply_router,
        cycle,
        run,
    ) -> None:
        event_bus = MagicMock()
        # "neo" is a participating agent (development.design step).
        port = self._assignment_port([self._hard_duty("neo")])
        executor = self._build(
            mock_registry=mock_registry,
            mock_vault=mock_vault,
            mock_queue=mock_queue,
            mock_squad_profile=mock_squad_profile,
            reply_router=reply_router,
            cycle=cycle,
            run=run,
            event_bus=event_bus,
            assignment_port=port,
        )

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Deferred, not dispatched.
        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[0] == RunStatus.RUNNING
        assert statuses[-1] == RunStatus.PAUSED
        assert mock_queue.publish.call_count == 0

        # RUN_PAUSED carries the duty-deferral reason + the blocking agent.
        paused = [
            c for c in event_bus.emit.call_args_list if c.args and c.args[0] == EventType.RUN_PAUSED
        ]
        assert len(paused) == 1
        payload = paused[0].kwargs["payload"]
        assert payload["reason"] == "upcoming_hard_duty_window"
        assert payload["deferred_for_agent"] == "neo"

    async def test_no_conflicting_assignment_lets_run_proceed(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        reply_router,
        cycle,
        run,
    ) -> None:
        """Guard wired but the active set is empty → no false positive: the run
        dispatches all 5 tasks and completes."""
        event_bus = MagicMock()
        port = self._assignment_port([])
        executor = self._build(
            mock_registry=mock_registry,
            mock_vault=mock_vault,
            mock_queue=mock_queue,
            mock_squad_profile=mock_squad_profile,
            reply_router=reply_router,
            cycle=cycle,
            run=run,
            event_bus=event_bus,
            assignment_port=port,
        )
        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"],
            status="SUCCEEDED",
            outputs={
                "summary": "ok",
                "role": "strat",
                "artifacts": [
                    {
                        "name": "o.md",
                        "content": "# o",
                        "media_type": "text/markdown",
                        "type": "document",
                    }
                ],
            },
        )

        # NB: asyncio.sleep is intentionally NOT patched here. The per-task
        # heartbeat is a `while True: await asyncio.sleep(...)` loop; patching
        # sleep to a non-yielding AsyncMock turns it into a busy-spin that
        # starves the event loop (the same reason TestSequentialHappyPath can
        # hang locally). With real sleep, the heartbeat task is created and
        # cancelled before its first 30s tick, and replies resolve synchronously.
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED
        assert mock_queue.publish.call_count == 5


# ---------------------------------------------------------------------------
# SIP-0089 §3.5 (#233) — recruitment routed through the coordinator
# ---------------------------------------------------------------------------


class _RecordingCoordinator:
    """Fake RuntimeCoordinator: scripts ``ambient→cycle`` outcomes, records transitions.

    Only ``request_transition`` is exercised by the executor. A clean
    ``ambient→cycle`` (or any release) returns ``applied``; an agent in ``reject``
    returns a rejected lease outcome carrying the given ``focus_lease_*`` reason.
    """

    def __init__(self, *, reject: dict[str, str] | None = None) -> None:
        self._reject = reject or {}
        # each entry: (agent_id, target_mode, reason_code)
        self.transitions: list[tuple[str, str, str]] = []

    async def request_transition(
        self,
        agent_id,
        target_mode,
        reason_code,
        *,
        requester_kind,
        owner_ref,
        assignment_id=None,
        scheduled_at=None,
    ):
        self.transitions.append((agent_id, target_mode, reason_code))
        if target_mode == "cycle" and agent_id in self._reject:
            return TransitionOutcome(
                applied=False,
                agent_id=agent_id,
                from_mode="ambient",
                to_mode="cycle",
                reason_code=reason_code,
                rejected_reason=self._reject[agent_id],
            )
        from_mode = "ambient" if target_mode == "cycle" else "cycle"
        return TransitionOutcome(
            applied=True,
            agent_id=agent_id,
            from_mode=from_mode,
            to_mode=target_mode,
            reason_code=reason_code,
            event_name="agent.mode.transition",
        )

    def recruited(self) -> set[str]:
        return {a for a, mode, _ in self.transitions if mode == "cycle"}

    def released(self) -> set[str]:
        return {a for a, mode, _ in self.transitions if mode == "ambient"}


class TestRecruitmentCoordinatorAdmission:
    """Recruitment routes each participant ``ambient→cycle`` via the coordinator.

    A lease conflict defers the run (RUN_PAUSED, typed ``focus_lease_*`` reason,
    no dispatch) on the same path as the §2.5 guard. On any finalize the agents
    the run recruited return to ``ambient`` so no cycle lease strands — the
    acceptance criterion. Wired independently of the §2.5 guard (no
    AssignmentPort here) so this isolates the coordinator admission step.
    """

    def _build(
        self,
        *,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        reply_router,
        cycle,
        run,
        event_bus,
        coordinator,
    ):
        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

        mock_registry.get_cycle.return_value = cycle
        mock_registry.get_run.return_value = run
        return DispatchedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
            reply_router=reply_router,
            event_bus=event_bus,
            coordinator=coordinator,
        )

    async def test_lease_conflict_defers_run_before_dispatch(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        reply_router,
        cycle,
        run,
    ) -> None:
        event_bus = MagicMock()
        # "neo" is a participating agent; its cycle lease conflicts.
        coordinator = _RecordingCoordinator(reject={"neo": reasons.FOCUS_LEASE_CONFLICT})
        executor = self._build(
            mock_registry=mock_registry,
            mock_vault=mock_vault,
            mock_queue=mock_queue,
            mock_squad_profile=mock_squad_profile,
            reply_router=reply_router,
            cycle=cycle,
            run=run,
            event_bus=event_bus,
            coordinator=coordinator,
        )

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Deferred, not dispatched.
        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.PAUSED
        assert mock_queue.publish.call_count == 0

        # RUN_PAUSED rides the lease-conflict reason + the blocking agent — no new
        # EventType, same payload shape as the §2.5 deferral.
        paused = [
            c for c in event_bus.emit.call_args_list if c.args and c.args[0] == EventType.RUN_PAUSED
        ]
        assert len(paused) == 1
        payload = paused[0].kwargs["payload"]
        assert payload["reason"] == reasons.FOCUS_LEASE_CONFLICT
        assert payload["deferred_for_agent"] == "neo"

    async def test_clean_admission_dispatches_then_releases_every_recruit(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        reply_router,
        cycle,
        run,
    ) -> None:
        """No conflict → run completes and every recruited agent is released to
        ambient (no stranded cycle leases), with the canonical recruit/complete
        reason codes."""
        event_bus = MagicMock()
        coordinator = _RecordingCoordinator()
        executor = self._build(
            mock_registry=mock_registry,
            mock_vault=mock_vault,
            mock_queue=mock_queue,
            mock_squad_profile=mock_squad_profile,
            reply_router=reply_router,
            cycle=cycle,
            run=run,
            event_bus=event_bus,
            coordinator=coordinator,
        )
        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"],
            status="SUCCEEDED",
            outputs={
                "summary": "ok",
                "role": "strat",
                "artifacts": [
                    {
                        "name": "o.md",
                        "content": "# o",
                        "media_type": "text/markdown",
                        "type": "document",
                    }
                ],
            },
        )

        # Real asyncio.sleep (see the §2.5 no-conflict test note: patching it to a
        # non-yielding AsyncMock busy-spins the per-task heartbeat loop).
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED
        # Recruitment actually ran, and every agent it put in cycle came back to
        # ambient on finalize — the no-strand guarantee.
        assert coordinator.recruited()  # non-empty: not vacuously passing
        assert coordinator.released() == coordinator.recruited()
        recruit_reasons = {r for _, mode, r in coordinator.transitions if mode == "cycle"}
        release_reasons = {r for _, mode, r in coordinator.transitions if mode == "ambient"}
        assert recruit_reasons == {reasons.CYCLE_RECRUITED}
        assert release_reasons == {reasons.CYCLE_COMPLETED}


# ---------------------------------------------------------------------------
# Artifact storage
# ---------------------------------------------------------------------------


class TestArtifactStorage:
    """Artifact ref creation from distributed results."""

    async def test_artifact_ref_has_metadata(self, executor, mock_vault, reply_router) -> None:
        """ArtifactRef passed to vault.store has task_id and role in metadata."""
        # Every task replies with one artifact so vault.store is exercised with
        # task artifacts (not just the run report).
        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"],
            status="SUCCEEDED",
            outputs={
                "summary": "ok",
                "artifacts": [
                    {
                        "name": "output.md",
                        "content": "# Output",
                        "media_type": "text/markdown",
                        "type": "document",
                    }
                ],
            },
        )

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        for call_item in mock_vault.store.call_args_list:
            ref = call_item.args[0]
            assert isinstance(ref, ArtifactRef)
            # Skip run_report.md — it has report_type metadata, not task_id
            if ref.filename == "run_report.md":
                assert "report_type" in ref.metadata
                continue
            assert "task_id" in ref.metadata
            assert "role" in ref.metadata


# ---------------------------------------------------------------------------
# SIP-0087: Prefect task-run lifecycle + contextvar scope + heartbeat
# ---------------------------------------------------------------------------


class TestDispatchTaskPrefectLifecycle:
    """Verify _dispatch_task drives the Prefect task-run lifecycle, enters the
    correlation contextvar scope, and spawns the heartbeat."""

    @pytest.fixture
    def envelope(self):
        return TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev", "capability_id": "dev.design"},
        )

    @pytest.fixture
    def mock_reporter(self):
        reporter = MagicMock()
        reporter.create_task_run = AsyncMock(return_value="tr_new")
        reporter.set_task_run_state = AsyncMock()
        return reporter

    def _build_executor(self, mock_queue, mock_reporter=None):
        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

        return DispatchedFlowExecutor(
            queue=mock_queue,
            reply_router=mock_queue.reply_router,
            task_timeout=5.0,
            workflow_tracker=mock_reporter,
        )

    def _wire_success_reply(self, mock_queue, task_id: str):
        """Seed the reply router so the dispatched task gets a SUCCEEDED reply."""
        mock_queue.reply_router.results[task_id] = TaskResult(
            task_id=task_id, status="SUCCEEDED", outputs={"summary": "ok", "artifacts": []}
        )

    async def test_creates_task_run_and_sets_running_when_prefect_enabled(
        self, mock_queue, mock_reporter, envelope
    ):
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(envelope, "run_001", flow_run_id="fr_abc")

        # #185: label prefixes with the agent (envelope.agent_id="neo"), not
        # the role ("dev") — proves the executor wires build_task_name through.
        mock_reporter.create_task_run.assert_awaited_once_with(
            "fr_abc", "task_abc", "neo: development.design"
        )
        mock_reporter.set_task_run_state.assert_awaited_once_with("tr_new", "RUNNING", "Running")

    async def test_no_prefect_calls_when_reporter_missing(self, mock_queue, envelope):
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter=None)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await executor._dispatch_task(envelope, "run_001", flow_run_id="fr_abc")

        assert result.status == "SUCCEEDED"

    async def test_no_prefect_calls_when_flow_run_id_missing(
        self, mock_queue, mock_reporter, envelope
    ):
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(envelope, "run_001", flow_run_id=None)

        mock_reporter.create_task_run.assert_not_awaited()
        mock_reporter.set_task_run_state.assert_not_awaited()

    async def test_skips_creation_when_task_run_id_preallocated(
        self, mock_queue, mock_reporter, envelope
    ):
        # Sequential path pre-creates the task_run (so TASK_DISPATCHED can
        # emit it) and passes task_run_id in. _dispatch_task must not create
        # a second one.
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_preallocated"
            )

        mock_reporter.create_task_run.assert_not_awaited()
        mock_reporter.set_task_run_state.assert_not_awaited()

    async def test_published_envelope_carries_run_ids(self, mock_queue, mock_reporter, envelope):
        """SIP-0087 B1: dispatched envelope on the wire carries flow_run_id /
        task_run_id so the agent can scope its handler logs to the right
        Prefect task pane."""
        published_payload: dict[str, object] = {}

        async def capture_publish(_queue_name, body):
            published_payload.update(json.loads(body)["payload"])

        mock_queue.publish.side_effect = capture_publish
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_123"
            )

        assert published_payload["flow_run_id"] == "fr_abc"
        assert published_payload["task_run_id"] == "tr_123"

    async def test_published_envelope_run_ids_empty_when_prefect_disabled(
        self, mock_queue, envelope
    ):
        """No Prefect → run IDs serialize as empty strings (not nulls)."""
        published_payload: dict[str, object] = {}

        async def capture_publish(_queue_name, body):
            published_payload.update(json.loads(body)["payload"])

        mock_queue.publish.side_effect = capture_publish
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter=None)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(envelope, "run_001")

        assert published_payload["flow_run_id"] == ""
        assert published_payload["task_run_id"] == ""

    async def test_scopes_correlation_context_during_publish(
        self, mock_queue, mock_reporter, envelope
    ):
        """The publish coroutine must see the active CorrelationContext so
        any logs emitted during dispatch land in the right Prefect pane."""
        from squadops.telemetry.context import get_correlation_context

        seen: dict[str, object] = {}

        async def capture_ctx(*args, **kwargs):
            ctx = get_correlation_context()
            seen["cycle_id"] = ctx.cycle_id if ctx else None
            seen["flow_run_id"] = ctx.flow_run_id if ctx else None
            seen["task_run_id"] = ctx.task_run_id if ctx else None

        mock_queue.publish.side_effect = capture_ctx
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_123"
            )

        assert seen == {
            "cycle_id": "cyc_001",
            "flow_run_id": "fr_abc",
            "task_run_id": "tr_123",
        }
        # Context must be cleared after dispatch returns.
        assert get_correlation_context() is None

    async def test_task_heartbeat_logs_periodically_under_contextvar_scope(
        self, mock_queue, envelope, caplog
    ):
        """``_task_heartbeat`` emits an INFO line per interval and carries
        the live correlation context so records are tagged for Prefect."""
        import logging as stdlog

        import adapters.cycles.dispatched_flow_executor as dfe
        from squadops.telemetry.context import (
            get_correlation_context,
            use_correlation_context,
            use_run_ids,
        )
        from squadops.telemetry.models import CorrelationContext

        executor = self._build_executor(mock_queue)

        seen_ids: list[tuple[str | None, str | None]] = []
        real_sleep = asyncio.sleep

        async def capturing_sleep(_interval: float) -> None:
            ctx = get_correlation_context()
            seen_ids.append((ctx.flow_run_id if ctx else None, ctx.task_run_id if ctx else None))
            # Let the event loop advance; real sleep avoids tight-looping.
            await real_sleep(0)

        with (
            patch.object(dfe.asyncio, "sleep", capturing_sleep),
            caplog.at_level(stdlog.INFO, logger=dfe.__name__),
        ):
            base = CorrelationContext(cycle_id="cyc_001")
            with (
                use_correlation_context(base),
                use_run_ids(flow_run_id="fr_abc", task_run_id="tr_123"),
            ):
                hb = asyncio.create_task(executor._task_heartbeat(envelope, interval=0.01))
                # Yield a few times so the heartbeat can iterate.
                for _ in range(5):
                    await real_sleep(0)
                hb.cancel()
                try:
                    await hb
                except asyncio.CancelledError:
                    pass

        messages = [r.getMessage() for r in caplog.records if "task_heartbeat" in r.getMessage()]
        assert messages, "expected at least one task_heartbeat log line"
        first = messages[0]
        assert "capability_id=dev.design" in first
        assert "task_id=task_abc" in first
        # Heartbeat coroutine saw the active flow/task run IDs via contextvar
        # inheritance at create_task time.
        assert ("fr_abc", "tr_123") in seen_ids

    async def test_dispatch_task_cancels_heartbeat_on_return(
        self, mock_queue, mock_reporter, envelope
    ):
        """After ``_dispatch_task`` returns, no orphan heartbeat task should
        remain on the event loop."""
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_123"
            )

        leftover = [
            t
            for t in asyncio.all_tasks()
            if t.get_name().startswith("prefect-heartbeat-") and not t.done()
        ]
        assert leftover == []


class TestPublishAndAwaitInvariants:
    """SIP-0094 cutover invariants of _publish_and_await: ordering (D14/#2),
    pending-future-leak safety on every exit path (#9/#10), concurrent
    first-dispatch (#13), and global task_id uniqueness across runs (D14)."""

    @staticmethod
    def _env(task_id="t1", agent_id="neo"):
        return TaskEnvelope(
            task_id=task_id,
            agent_id=agent_id,
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

    async def test_subscribes_and_registers_before_publish(
        self, executor, mock_queue, reply_router
    ):
        """D14/#2: ensure_subscribed + register happen BEFORE publish, so a fast
        reply can't arrive before the consumer is live."""
        seen = {}

        async def _publish(queue_name, payload, delay_seconds=None):
            data = json.loads(payload)
            seen["registered"] = data["payload"]["task_id"] in reply_router.registered
            seen["subscribed"] = "neo" in reply_router.subscribed
            reply_router._autorespond(data["payload"])

        mock_queue.publish.side_effect = _publish

        await executor._publish_and_await(self._env(), "run_001")

        assert seen == {"registered": True, "subscribed": True}

    async def test_publish_failure_removes_pending_future(self, executor, mock_queue, reply_router):
        """#10: if publish raises after register(), the pending future is dropped
        (no leak) and the error propagates."""
        mock_queue.publish.side_effect = RuntimeError("broker down")

        with pytest.raises(RuntimeError, match="broker down"):
            await executor._publish_and_await(self._env("t_fail"), "run_001")

        assert "t_fail" in reply_router.cancelled
        assert "t_fail" not in reply_router._futures

    async def test_timeout_leaves_no_pending_future(self, executor, reply_router):
        """#9: a timed-out dispatch cancels its future (no leak) and returns FAILED."""
        reply_router.suppress.add("t_to")
        executor._task_timeout = 0.1

        result = await executor._publish_and_await(self._env("t_to"), "run_001")

        assert result.status == "FAILED"
        assert "t_to" in reply_router.cancelled
        assert "t_to" not in reply_router._futures

    async def test_concurrent_dispatch_same_agent_both_resolve(
        self, executor, mock_queue, reply_router
    ):
        """#13: two concurrent dispatches to one agent both resolve to their own
        results and both publish to that agent's comms queue."""
        reply_router.results["ta"] = TaskResult(
            task_id="ta", status="SUCCEEDED", outputs={"n": "a"}
        )
        reply_router.results["tb"] = TaskResult(
            task_id="tb", status="SUCCEEDED", outputs={"n": "b"}
        )

        ra, rb = await asyncio.gather(
            executor._publish_and_await(self._env("ta"), "run_001"),
            executor._publish_and_await(self._env("tb"), "run_001"),
        )

        assert ra.outputs["n"] == "a"
        assert rb.outputs["n"] == "b"
        pub_queues = [c.args[0] for c in mock_queue.publish.call_args_list]
        assert pub_queues.count("neo_comms") == 2

    async def test_cross_run_task_ids_dont_collide(self, executor, reply_router):
        """D14: globally-unique task_ids from different runs resolve to their own
        results on the shared per-agent reply queue (no cross-run mixup)."""
        reply_router.results["task-run_aaaa-1"] = TaskResult(
            task_id="task-run_aaaa-1", status="SUCCEEDED", outputs={"r": "a"}
        )
        reply_router.results["task-run_bbbb-1"] = TaskResult(
            task_id="task-run_bbbb-1", status="SUCCEEDED", outputs={"r": "b"}
        )

        r1 = await executor._publish_and_await(self._env("task-run_aaaa-1"), "run_aaaa")
        r2 = await executor._publish_and_await(self._env("task-run_bbbb-1"), "run_bbbb")

        assert r1.outputs["r"] == "a"
        assert r2.outputs["r"] == "b"

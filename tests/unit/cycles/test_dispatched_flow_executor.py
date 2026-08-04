"""Tests for DispatchedFlowExecutor (adapters/cycles/dispatched_flow_executor.py).

Covers dispatch via RabbitMQ publish/consume, sequential happy path,
fail-fast, cancellation, artifact storage, output chaining, and timeout.

Mirrors test_flow_executor.py structure but with mocked QueuePort instead
of mocked AgentOrchestrator.
"""

from __future__ import annotations

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
from squadops.tasks.models import TaskResult

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
# Cancellation probe wiring (#586)
# ---------------------------------------------------------------------------


class TestCancellationProbeWiring:
    """The §6.1 probe is only worth anything if the *composed* dispatcher gets
    it — and if the correction/pulse runners share that same instance.

    #586 was a mutual-delegation hole: ``CorrectionRunner`` documented itself as
    relying on a dispatch-boundary check, ``TaskDispatcher`` documented that
    check as not wired, and the only real probe sat at the sequential loop top —
    which a correction loop never returns to until it exhausts.
    """

    async def test_composed_dispatcher_probe_reflects_registry_cancellation(
        self, executor, mock_registry, run
    ) -> None:
        """Bug caught: the probe parameter exists but the executor's default
        composition doesn't pass it, so the fix is inert in production."""
        probe = executor._task_dispatcher._is_cancelled
        assert probe is not None, "executor composed a dispatcher with no cancellation probe"

        mock_registry.get_run.return_value = run  # status "queued"
        assert await probe("run_001") is False

        mock_registry.get_run.return_value = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status=RunStatus.CANCELLED.value,
            initiated_by="api",
            resolved_config_hash="hash",
        )
        assert await probe("run_001") is True

    async def test_correction_and_pulse_runners_share_the_probed_dispatcher(self, executor) -> None:
        """Bug caught: a runner composing its own unprobed TaskDispatcher would
        leave the repair path — the exact #586 path — uncovered."""
        shared = executor._task_dispatcher
        assert executor._correction_runner._task_dispatcher is shared
        assert executor._pulse_boundary_runner._task_dispatcher is shared

    async def test_probe_honours_the_local_cancel_fast_path(self, executor) -> None:
        """Bug caught: a probe that only reads the registry misses an in-process
        ``cancel_run`` whose registry write failed (the method logs and
        continues), letting dispatch proceed on a run the operator cancelled."""
        executor._cycle_registry.cancel_run.side_effect = RuntimeError("registry down")
        await executor.cancel_run("run_001")

        assert await executor._task_dispatcher._is_cancelled("run_001") is True


# ---------------------------------------------------------------------------
# Error-seam threading onto dev envelopes (#588)
# ---------------------------------------------------------------------------


class TestErrorSeamThreading:
    """The manifest-derived error seam has reached repairs since pf-34 but never
    the INITIAL author, so every scaffolded roll re-made the same mistake —
    ``ApiError(status_code=…, detail=…)`` against a frozen
    ``ApiError(code, message)`` seam — TypeErroring into a 500 on every error
    path, invisible to import- and compile-level checks.
    """

    @staticmethod
    def _manifest():
        from pathlib import Path

        from squadops.capabilities.scaffold import InterfaceManifest

        repo_root = Path(__file__).resolve().parents[3]
        path = repo_root / "examples" / "03_group_run" / "interface_manifest.yaml"
        return InterfaceManifest.from_yaml(path.read_text(encoding="utf-8"))

    @staticmethod
    def _envelope(task_type: str):
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="t1",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type=task_type,
            correlation_id="c",
            causation_id="ca",
            trace_id="tr",
            span_id="s",
        )

    async def test_dev_envelope_carries_the_error_seam(self, executor) -> None:
        """Bug caught: the seam stays repair-only, so the first author keeps
        guessing the ApiError signature (pf-28/33/34, and pf-37's routes.py)."""
        enriched = await executor._enrich_envelope(
            self._envelope("development.develop"),
            {},
            [],
            [],
            interface_manifest=self._manifest(),
        )

        lines = enriched.inputs.get("error_contract")
        assert lines, "development.develop envelope carries no error contract"
        joined = " ".join(lines)
        assert "ApiError(code, message)" in joined
        assert "never `ApiError(status_code=..., detail=...)`" in joined
        assert "run_not_found` → 404" in joined

    async def test_dev_envelope_carries_the_model_surface(self, executor) -> None:
        """pf-45: repairs have had the model surface since #604; the first author did
        not, guessed `pace` for the frozen model's `pace_target`, and every POST /runs
        raised into a 500 — a correction spent learning what the scaffold already knew."""
        enriched = await executor._enrich_envelope(
            self._envelope("development.develop"),
            {},
            [],
            [],
            interface_manifest=self._manifest(),
        )

        lines = enriched.inputs.get("model_surface")
        assert lines, "development.develop envelope carries no model surface"
        joined = " ".join(lines)
        assert "pace_target" in joined  # field-level — the exact pf-45 token
        assert "run_event_store" in joined  # the frozen store the dev shadowed

    async def test_model_surface_follows_the_same_gating_as_the_error_seam(self, executor) -> None:
        for task_type, manifest in (("qa.test", self._manifest()), ("development.develop", None)):
            enriched = await executor._enrich_envelope(
                self._envelope(task_type), {}, [], [], interface_manifest=manifest
            )
            assert "model_surface" not in enriched.inputs

    async def test_dev_envelope_carries_the_testid_surface(self, executor) -> None:
        """#659 (fay-6/fay-12): the anchor inventory must reach the view author on
        the same transport as the model surface — a dev who never sees the pinned
        testids ships views the qa suite (which queries only those) cannot find."""
        enriched = await executor._enrich_envelope(
            self._envelope("development.develop"),
            {},
            [],
            [],
            interface_manifest=self._manifest(),
        )

        lines = enriched.inputs.get("testid_surface")
        assert lines, "development.develop envelope carries no testid surface"
        joined = " ".join(lines)
        assert "`RunsListView`" in joined
        assert "`runs-list`" in joined
        assert "`join-name-input`" in joined

    async def test_testid_surface_follows_the_same_gating(self, executor) -> None:
        for task_type, manifest in (("qa.test", self._manifest()), ("development.develop", None)):
            enriched = await executor._enrich_envelope(
                self._envelope(task_type), {}, [], [], interface_manifest=manifest
            )
            assert "testid_surface" not in enriched.inputs

    async def test_non_authoring_task_types_are_not_given_the_seam(self, executor) -> None:
        """Bug caught: blanket attachment pushes fill-slot authoring instructions
        into roles that do not author into the scaffold (a qa suite told to raise
        ApiError writes assertions against the wrong thing)."""
        enriched = await executor._enrich_envelope(
            self._envelope("qa.test"),
            {},
            [],
            [],
            interface_manifest=self._manifest(),
        )

        assert "error_contract" not in enriched.inputs

    async def test_unscaffolded_run_attaches_nothing(self, executor) -> None:
        """Bug caught: author-mode cycles have no manifest, so attaching a
        fabricated or empty seam would state a contract that does not exist."""
        enriched = await executor._enrich_envelope(
            self._envelope("development.develop"),
            {},
            [],
            [],
            interface_manifest=None,
        )

        assert "error_contract" not in enriched.inputs


class TestRunCompletionActivityWiring:
    async def test_default_run_completion_receives_the_executor_activity_port(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile, reply_router
    ):
        """Bug class (#672 silent no-op): the executor composes its default
        RunCompletion — if the activity port isn't threaded into it, the
        finalize stranded-activity sweep never runs in production while every
        unit test of RunCompletion itself still passes."""
        from unittest.mock import AsyncMock

        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

        activity_port = AsyncMock()
        executor = DispatchedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
            reply_router=reply_router,
            activity_port=activity_port,
        )

        assert executor._run_completion._activity_port is activity_port

    async def test_factory_forwards_the_focus_lease_port(self, mock_registry, mock_vault):
        """Same silent-no-op class for #373: the composition root builds the
        executor through `create_flow_executor`, so a kwarg the factory drops
        leaves the finalize stranded-lease sweep permanently inert — with every
        focus_reaper unit test still green."""
        from unittest.mock import AsyncMock

        from adapters.cycles.factory import create_flow_executor

        focus_lease_port = AsyncMock()
        executor = create_flow_executor(
            "dispatched",
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            focus_lease_port=focus_lease_port,
        )

        assert executor._focus_lease_port is focus_lease_port

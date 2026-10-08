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

from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.cycles.failure_attribution import TerminalKind
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.run_loop_summary import RunTerminalDecision
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
            AgentProfileEntry(
                agent_id="nat", role="strat", model="gpt-4", enabled=True, serves_roles=("strat",)
            ),
            AgentProfileEntry(
                agent_id="neo", role="dev", model="gpt-4", enabled=True, serves_roles=("dev",)
            ),
            AgentProfileEntry(
                agent_id="eve", role="qa", model="gpt-4", enabled=True, serves_roles=("qa",)
            ),
            AgentProfileEntry(
                agent_id="data-agent",
                role="data",
                model="gpt-4",
                enabled=True,
                serves_roles=("data",),
            ),
            AgentProfileEntry(
                agent_id="max", role="lead", model="gpt-4", enabled=True, serves_roles=("lead",)
            ),
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
        applied_defaults={"correction_steps": ["analyze", "decide", "repair"]},
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
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
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

    async def test_finalization_persists_the_runs_usage_summed_over_every_reply(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """SIP-0108 §5 criterion 2, the finalization half. Entry point: ``execute_run``, through
        the dispatcher, to the registry row. Bug caught: the run summary written from anything
        but the replies the run actually got — or a reply without usage read as a free task."""
        from squadops.cycles.failure_attribution import TerminalKind
        from squadops.cycles.llm_usage import UsageTotals
        from squadops.cycles.run_loop_summary import RunTerminalDecision

        unreported_ids: list[str] = []

        def responder(env):
            if env["task_type"] == "data.report":
                unreported_ids.append(env["task_id"])
            usage = (
                None
                if env["task_type"] == "data.report"
                else UsageTotals(calls=2, failed_calls=1, prompt_tokens=100).to_dict()
            )
            return TaskResult(
                task_id=env["task_id"],
                status="SUCCEEDED",
                outputs={"summary": "stub", "role": "strat", "artifacts": []},
                llm_usage=usage,
            )

        mock_queue.reply_router.responder = responder
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        run_id, summary = mock_registry.record_run_loop_summary.await_args.args
        assert run_id == "run_001"
        assert summary.usage.total == UsageTotals(calls=8, failed_calls=4, prompt_tokens=400)
        assert summary.usage.tasks_reported == 4
        assert list(summary.usage.tasks_unreported) == unreported_ids
        # SIP-0108 §4.1: a run that reached the end of its tasks records that it completed.
        assert summary.terminal == RunTerminalDecision(kind=TerminalKind.COMPLETED)

    async def test_finalization_persists_every_revision_form_the_runs_tasks_took(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """#1710, entered at ``execute_run``: the forms a run's tasks took reach its persisted
        summary, each named by its kind and task. Bug caught: the forms only in the agents' logs,
        which the next rebuild destroys, so a campaign's package can never carry them."""
        dispatched: list[tuple[str, str]] = []

        def responder(env):
            dispatched.append((env["task_id"], env["task_type"]))
            return TaskResult(
                task_id=env["task_id"],
                status="SUCCEEDED",
                outputs={"summary": "stub", "artifacts": [], "revision_form": {"form": "edits"}},
            )

        mock_queue.reply_router.responder = responder
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        _run_id, summary = mock_registry.record_run_loop_summary.await_args.args
        assert dispatched, "the plan dispatched its tasks"
        assert list(summary.revision_forms) == [
            {"kind": "repair", "task_id": task_id, "task_type": task_type, "form": "edits"}
            for task_id, task_type in dispatched
        ]

    async def test_finalization_persists_the_runs_latest_lint_reading(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """#1937, entered at ``execute_run``: the lint reading a task's reply carries reaches the
        run's persisted summary, the latest one, with its task. Bug caught: the reading left in
        the reply, so neither the summary nor a campaign's package ever holds it."""
        dispatched: list[str] = []

        def responder(env):
            dispatched.append(env["task_id"])
            return TaskResult(
                task_id=env["task_id"],
                status="SUCCEEDED",
                outputs={
                    "summary": "stub",
                    "artifacts": [],
                    "lint_findings": {"version": 1, "total": len(dispatched)},
                },
            )

        mock_queue.reply_router.responder = responder
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        _run_id, summary = mock_registry.record_run_loop_summary.await_args.args
        assert dispatched, "the plan dispatched its tasks"
        assert summary.lint_findings == {
            "task_id": dispatched[-1],
            "version": 1,
            "total": len(dispatched),
        }

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


class TestAFailedRunFinalizesWithTheStateItReached:
    """#1507 step 2 moved provisioning out of ``execute_run``. Its ``finally`` hands
    ``RunCompletion.finalize`` the cycle, the plan and the contract, and a run that fails partway
    finalizes with whichever it had reached. Entered at ``execute_run``, failing at two points
    past the contract's load. Bug this catches: provisioning returning its results only at the
    end, so a failed run finalizes with ``None`` where the contract was already loaded."""

    @pytest.mark.parametrize(
        ("fails_at", "plan_recorded"),
        [("plan generation", False), ("seeding", True)],
        ids=["the plan fails to generate", "seeding fails after the plan"],
    )
    async def test_finalize_receives_what_was_established_before_the_failure(
        self, executor, cycle, fails_at, plan_recorded
    ) -> None:
        contract = object()
        executor._load_contract_for_run = AsyncMock(return_value=contract)
        executor._seeded_manifest_for_authoring = AsyncMock(return_value=None)
        executor._run_completion.finalize = AsyncMock()
        generated = []
        if fails_at == "plan generation":
            plan_patch = patch(
                "adapters.cycles.run_provisioning.generate_task_plan",
                side_effect=RuntimeError("plan generation failed"),
            )
        else:
            plan_patch = patch(
                "adapters.cycles.run_provisioning.generate_task_plan", return_value=generated
            )
            executor._load_interface_manifest_for_run = AsyncMock(
                side_effect=RuntimeError("seeding failed")
            )

        with plan_patch:
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        kwargs = executor._run_completion.finalize.await_args.kwargs
        assert kwargs["cycle"] is cycle
        assert kwargs["contract"] is contract
        # The plan provisioning reached is the supplied one (SIP-0110 §0.9), equal to what was
        # generated when no lesson applies: compared by value, not identity.
        assert kwargs["plan"] == (generated if plan_recorded else None)


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


def _refuse_same_state(status, current: str) -> None:
    """The registry's rule the #1701 warning came from: a run is never moved to its own state."""
    if status == current:
        raise ValueError(f"illegal transition {current} -> {status}")


class TestCancellation:
    """Run cancellation via local set and registry polling."""

    async def test_cancel_run_sets_local_and_registry(self, executor, mock_registry) -> None:
        await executor.cancel_run("run_001")
        assert "run_001" in executor._cancelled
        mock_registry.cancel_run.assert_awaited_once_with("run_001")

    async def test_cancel_before_first_task(
        self, executor, mock_registry, mock_queue, caplog
    ) -> None:
        """A run the cancel route already cancelled ends cancelled with no task published —
        and, #1701, without a second CANCELLED write the registry would refuse. That refusal
        logged "Failed to transition … cancelled" on every API cancel."""
        import logging

        mock_registry.get_run.return_value = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="cancelled",
            initiated_by="api",
            resolved_config_hash="hash",
        )
        mock_registry.update_run_status.side_effect = lambda run_id, status, **k: (
            _refuse_same_state(status, "cancelled")
        )

        with caplog.at_level(logging.WARNING):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        mock_queue.publish.assert_not_awaited()
        written = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert RunStatus.CANCELLED not in written
        assert not [r for r in caplog.records if "Failed to transition" in r.getMessage()]

    @pytest.mark.parametrize(
        ("current", "read_fails", "writes", "warns"),
        [
            ("running", False, True, True),
            (None, True, True, False),
        ],
        ids=["a real refusal still warns", "an unreadable status still writes"],
    )
    async def test_only_a_same_state_transition_is_skipped(
        self, executor, mock_registry, caplog, current, read_fails, writes, warns
    ) -> None:
        """#1701's edge. Bug this catches: the read-before-write hiding a transition the
        registry really refused (running → failed on a row something else closed), or a
        status read that failed skipping the write altogether."""
        import logging

        if read_fails:
            mock_registry.get_run.side_effect = RuntimeError("registry unavailable")
            mock_registry.update_run_status.side_effect = None
        else:
            mock_registry.get_run.return_value = Run(
                run_id="run_001",
                cycle_id="cyc_001",
                run_number=1,
                status=current,
                initiated_by="api",
                resolved_config_hash="hash",
            )
            mock_registry.update_run_status.side_effect = RuntimeError("illegal transition")

        with caplog.at_level(logging.WARNING):
            await executor._safe_transition("run_001", RunStatus.FAILED, failure_reason="x")

        assert mock_registry.update_run_status.await_count == (1 if writes else 0)
        warned = [r for r in caplog.records if "Failed to transition" in r.getMessage()]
        assert bool(warned) is warns


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
            project_registry=None,
            campaign_registry=None,
            campaign_progress=None,
            box_verdict=None,
            failure_recall=NoOpFailurePatternRecall(),
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
            project_registry=None,
            campaign_registry=None,
            campaign_progress=None,
            box_verdict=None,
            failure_recall=NoOpFailurePatternRecall(),
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
# Ported from the in-process executor's suite when it was deleted (#1984)
# ---------------------------------------------------------------------------


def _one_artifact_reply(env, role: str = "strat") -> TaskResult:
    return TaskResult(
        task_id=env["task_id"],
        status="SUCCEEDED",
        outputs={
            "summary": "ok",
            "role": role,
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


async def _execute(executor) -> None:
    with patch(
        "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")


class TestOutputChaining:
    """Each task sees the outputs of the tasks before it, keyed by the role that produced them.

    Bug caught: a downstream task authored blind to its upstream (an empty or cumulative-by-
    accident ``prior_outputs``), or outputs keyed by something other than the producing role."""

    async def test_each_task_sees_its_predecessors_outputs_keyed_by_role(
        self, executor, reply_router
    ) -> None:
        import copy

        seen: list[set[str]] = []

        def responder(env):
            seen.append(set(copy.deepcopy(env["inputs"].get("prior_outputs") or {})))
            return _one_artifact_reply(env)

        reply_router.responder = responder
        await _execute(executor)

        # strategy.analyze_prd (strat), development.design (dev), qa.validate (qa),
        # data.report (data), governance.review (lead)
        assert seen == [
            set(),
            {"strat"},
            {"strat", "dev"},
            {"strat", "dev", "qa"},
            {"strat", "dev", "qa", "data"},
        ]


class TestArtifactRefsPerStep:
    async def test_each_append_carries_only_that_steps_refs(
        self, executor, mock_registry, reply_router
    ) -> None:
        """Bug caught: the run's refs re-appended cumulatively each step, so the row holds
        duplicates and the next workload's forwarding sees one artifact several times."""
        reply_router.responder = _one_artifact_reply
        await _execute(executor)

        appended = [c.args[1] for c in mock_registry.append_artifact_refs.call_args_list]
        flat = [ref for refs in appended for ref in refs]
        assert len(flat) == len(set(flat))
        assert len(appended) >= 5 and all(len(refs) == 1 for refs in appended[:5])

    @pytest.mark.parametrize("outputs", [{"summary": "done"}, None])
    async def test_a_task_with_no_artifacts_stores_nothing_and_the_run_completes(
        self, executor, mock_registry, mock_vault, reply_router, outputs
    ) -> None:
        """Bug caught: a reply with no ``artifacts`` key (or no outputs at all) crashing the
        loop, or storing an empty artifact."""
        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"], status="SUCCEEDED", outputs=outputs
        )
        await _execute(executor)

        stored = [c.args[0].filename for c in mock_vault.store.call_args_list]
        assert stored == ["run_report.md"]
        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED


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

    async def test_a_registry_cancel_ends_a_wait_already_open(
        self, mock_vault, mock_queue, mock_squad_profile, reply_router, run, monkeypatch
    ) -> None:
        """#1699 wiring, entered where the live cancel lands: ``registry.cancel_run`` — the API
        route's call (``routes/cycles/runs.py``) — against the executor's own composed
        dispatcher, whose probe reads that registry. Bug caught: the probe asked only before
        publishing, so a wait already open on a cancelled run ran to its task bound (deploy A's
        chain: 30 minutes, then a retry and a finalization while the next cycle ran)."""
        import asyncio

        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
        from adapters.cycles.execution_errors import _CancellationError
        from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
        from squadops.tasks.models import TaskEnvelope

        monkeypatch.setattr("adapters.cycles.task_dispatcher.CANCEL_PROBE_SECONDS", 0.01)
        registry = MemoryCycleRegistry()
        await registry.create_run(run)
        executor = DispatchedFlowExecutor(
            cycle_registry=registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
            reply_router=reply_router,
            project_registry=None,
            campaign_registry=None,
            campaign_progress=None,
            box_verdict=None,
            failure_recall=NoOpFailurePatternRecall(),
        )
        envelope = TaskEnvelope(
            task_id="task-run_001-m000-development.develop",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.develop",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )
        reply_router.suppress.add(envelope.task_id)  # the agent dropped it: nothing replies

        wait = asyncio.create_task(executor._task_dispatcher.dispatch_task(envelope, "run_001"))
        await asyncio.sleep(0.05)
        assert not wait.done(), "the task is out and its wait is open"
        await registry.cancel_run("run_001")

        with pytest.raises(_CancellationError):
            await asyncio.wait_for(wait, timeout=1.0)
        mock_queue.publish.assert_awaited_once()


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
            project_registry=None,
            campaign_registry=None,
            campaign_progress=None,
            box_verdict=None,
            failure_recall=NoOpFailurePatternRecall(),
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
            task_timeout=300.0,
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=None,
            squad_profile=None,
            project_registry=None,
            campaign_registry=None,
            campaign_progress=None,
            box_verdict=None,
            failure_recall=NoOpFailurePatternRecall(),
            focus_lease_port=focus_lease_port,
        )

        assert executor._focus_lease_port is focus_lease_port


# ---------------------------------------------------------------------------
# #426 — gate-time build-config net
# ---------------------------------------------------------------------------


class TestGateRejectsBuilderPlanWithoutBuildProfile:
    """#426: a builder-task plan on a config with no build_profile used to
    pass the gate and die 8ms into the implementation run at the #291 guard.
    The gate net must reject it where a re-roll is cheap — and must read the
    SAME merged config generate_task_plan reads, or the two nets disagree."""

    _BUILDER_PLAN_YAML = (
        "version: 1\n"
        "project_id: hello_squad\n"
        "cycle_id: cyc_001\n"
        "prd_hash: abc\n"
        "tasks:\n"
        "  - task_index: 0\n"
        "    task_type: builder.assemble\n"
        "    role: builder\n"
        '    focus: "Package"\n'
        '    description: "Assemble"\n'
        # #888: floor-compliant for python_cli_builder — the "passes" test
        # asserts the profile-configured outcome, so its plan must cover the
        # profile's required_files or the floor rule (correctly) rejects it.
        "    expected_artifacts:\n"
        '      - "qa_handoff.md"\n'
        '      - "Dockerfile"\n'
        '      - "__main__.py"\n'
        '      - "requirements.txt"\n'
        "    depends_on: []\n"
        "summary:\n"
        "  total_tasks: 1\n"
    )

    @staticmethod
    def _stored_plan_artifacts():
        ref = MagicMock()
        ref.filename = "implementation_plan.yaml"
        ref.artifact_type = "control_implementation_plan"
        return [("art_plan", ref)]

    @staticmethod
    def _profile_with_builder():
        agent = MagicMock()
        agent.role = "builder"
        agent.serves_roles = ("builder",)
        agent.enabled = True
        profile = MagicMock()
        profile.profile_id = "full"
        profile.agents = [agent]
        return profile

    async def test_rejected_when_no_build_profile_configured(self, executor, mock_vault, cycle):
        import dataclasses

        from adapters.cycles.execution_errors import _ExecutionError

        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "correction_steps": ["analyze", "decide", "repair"],
            },
        )
        mock_vault.retrieve.return_value = ("ref", self._BUILDER_PLAN_YAML.encode())

        with pytest.raises(_ExecutionError) as exc_info:
            await executor._reject_unsatisfiable_plan_at_gate(
                self._stored_plan_artifacts(),
                self._profile_with_builder(),
                ["progress_plan_review"],
                gated_cycle,
            )
        assert "build_profile" in str(exc_info.value)
        # SIP-0108 §4.1: the refusal is a plan-gate ending, naming the validator that refused.
        assert exc_info.value.terminal == RunTerminalDecision(
            kind=TerminalKind.PLAN_GATE_REFUSED, refused_validators=("validate_build_config",)
        )

    async def test_build_profile_via_execution_overrides_passes(self, executor, mock_vault, cycle):
        """The gate must read the merged config — a build_profile arriving via
        execution_overrides is configured, and rejecting it would kill valid
        cycles (the #426 disease with the polarity flipped)."""
        import dataclasses

        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "correction_steps": ["analyze", "decide", "repair"],
            },
            execution_overrides={"build_profile": "python_cli_builder"},
        )
        mock_vault.retrieve.return_value = ("ref", self._BUILDER_PLAN_YAML.encode())

        await executor._reject_unsatisfiable_plan_at_gate(
            self._stored_plan_artifacts(),
            self._profile_with_builder(),
            ["progress_plan_review"],
            gated_cycle,
        )


class TestMidRunGateRejectsUnwinnableQaTask:
    """#715 on the mid-run gate seam — parity with the workload seam."""

    _QA_JS_PLAN_YAML = (
        TestGateRejectsBuilderPlanWithoutBuildProfile._BUILDER_PLAN_YAML.replace(
            "builder.assemble", "qa.test"
        )
        .replace("role: builder", "role: qa")
        .replace("qa_handoff.md", "backend/tests/test_e2e.js")
    )

    async def test_rejected_when_tests_pass_required(self, executor, mock_vault, cycle):
        import dataclasses

        from adapters.cycles.execution_errors import _ExecutionError

        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "required_checks": ["tests_pass"],
                "correction_steps": ["analyze", "decide", "repair"],
            },
        )
        mock_vault.retrieve.return_value = ("ref", self._QA_JS_PLAN_YAML.encode())

        agent = MagicMock()
        agent.role = "qa"
        agent.serves_roles = ("qa",)
        agent.enabled = True
        profile = MagicMock()
        profile.profile_id = "full"
        profile.agents = [agent]

        with pytest.raises(_ExecutionError) as exc_info:
            await executor._reject_unsatisfiable_plan_at_gate(
                TestGateRejectsBuilderPlanWithoutBuildProfile._stored_plan_artifacts(),
                profile,
                ["progress_plan_review"],
                gated_cycle,
            )
        assert "test_*.py" in str(exc_info.value)
        assert exc_info.value.terminal.refused_validators == ("validate_check_applicability",)


# ---------------------------------------------------------------------------
# #715 + #426 — the workload-gate seam (the path multi-workload cycles traverse)
# ---------------------------------------------------------------------------


class TestWorkloadGateSeamValidation:
    """#715/#426 wiring at `_reject_invalid_plan_before_workload_gate` — the
    seam multi-workload cycles actually traverse (the mid-run gate never fires
    there, per its own docstring). Errors are RETURNED for a system-REJECTED
    gate decision and a free framing re-roll, never raised."""

    _QA_JS_PLAN_YAML = (
        "version: 1\n"
        "project_id: group_run\n"
        "cycle_id: cyc_001\n"
        "prd_hash: abc\n"
        "tasks:\n"
        "  - task_index: 0\n"
        "    task_type: qa.test\n"
        "    role: qa\n"
        '    focus: "Integration smoke"\n'
        '    description: "Node smoke script"\n'
        "    expected_artifacts:\n"
        '      - "backend/tests/test_integration.js"\n'
        "    depends_on: []\n"
        "summary:\n"
        "  total_tasks: 1\n"
    )

    _BUILDER_PLAN_YAML = (
        "version: 1\n"
        "project_id: group_run\n"
        "cycle_id: cyc_001\n"
        "prd_hash: abc\n"
        "tasks:\n"
        "  - task_index: 0\n"
        "    task_type: builder.assemble\n"
        "    role: builder\n"
        '    focus: "Package"\n'
        '    description: "Assemble"\n'
        "    expected_artifacts:\n"
        '      - "qa_handoff.md"\n'
        "    depends_on: []\n"
        "summary:\n"
        "  total_tasks: 1\n"
    )

    @staticmethod
    def _wire(mock_vault, run, plan_yaml):
        import dataclasses

        ref = MagicMock()
        ref.filename = "implementation_plan.yaml"
        ref.artifact_type = "control_implementation_plan"
        mock_vault.retrieve.return_value = (ref, plan_yaml.encode())
        # The plan gate judges the framing run that authored the plan (#1864).
        return dataclasses.replace(run, artifact_refs=("art_plan",), workload_type="framing")

    async def test_unwinnable_qa_task_rejected_at_workload_gate(
        self, executor, mock_vault, cycle, run
    ):
        """The shk-4 shape: required tests_pass + a .js-only qa task must come
        back as a validation error (→ free re-roll), reading required_checks
        from the merged cycle config."""
        import dataclasses

        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "required_checks": ["tests_pass"],
                "correction_steps": ["analyze", "decide", "repair"],
            },
        )
        gated_run = self._wire(mock_vault, run, self._QA_JS_PLAN_YAML)

        errors = await executor._reject_invalid_plan_before_workload_gate(
            gated_run, gated_cycle, "progress_plan_review"
        )
        assert any("test_*.py" in e for e in errors)

    async def test_qa_js_plan_passes_when_tests_pass_not_required(
        self, executor, mock_vault, cycle, run
    ):
        """Polarity guard: without required tests_pass the same plan is legal —
        flagging it would reject valid author-mode cycles."""
        import dataclasses

        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "correction_steps": ["analyze", "decide", "repair"],
            },
        )
        gated_run = self._wire(mock_vault, run, self._QA_JS_PLAN_YAML)

        errors = await executor._reject_invalid_plan_before_workload_gate(
            gated_run, gated_cycle, "progress_plan_review"
        )
        assert errors == []

    async def test_builder_without_build_profile_rejected_at_workload_gate(
        self, executor, mock_vault, cycle, run
    ):
        """#426 gap closure: the original net landed only on the mid-run gate
        seam, which multi-workload cycles never traverse — the exact repro
        shape (framing run, then gate, then implementation run) was still
        reaching the #291 dispatch guard."""
        import dataclasses

        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "correction_steps": ["analyze", "decide", "repair"],
            },
        )
        gated_run = self._wire(mock_vault, run, self._BUILDER_PLAN_YAML)

        errors = await executor._reject_invalid_plan_before_workload_gate(
            gated_run, gated_cycle, "progress_plan_review"
        )
        assert any("build_profile" in e for e in errors)


class TestWorkloadGatePlanAbsent:
    """#424: a completed framing with NO plan artifact on an
    implementation_plan profile = authoring collapsed — reject at the gate
    (free re-roll), never approve into an uninstrumented implementation run."""

    @pytest.mark.parametrize(
        ("workload", "judged"),
        [("framing", True), ("implementation", True), ("proposal", False)],
    )
    async def test_absent_plan_rejected(self, executor, mock_vault, cycle, run, workload, judged):
        """#1864: judged where the gate judges the plan — the framing that authored it and the
        implementation built under it — and never at a proposal's gate, whose run authors a
        change request: every increment was refused there before its supervisor could rule."""
        import dataclasses

        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "correction_steps": ["analyze", "decide", "repair"],
            },
        )
        bare_run = dataclasses.replace(run, artifact_refs=(), workload_type=workload)

        errors = await executor._reject_invalid_plan_before_workload_gate(
            bare_run, gated_cycle, "progress_plan_review"
        )
        assert any("plan_authoring_collapsed" in e for e in errors) is judged

    async def test_unreadable_plan_still_defers(self, executor, mock_vault, cycle, run):
        """Exists-but-unparseable keeps today's deferral — the dispatch net
        gives it a full diagnosis; only true absence is a collapse."""
        import dataclasses

        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "correction_steps": ["analyze", "decide", "repair"],
            },
        )
        ref = MagicMock()
        ref.filename = "implementation_plan.yaml"
        ref.artifact_type = "control_implementation_plan"
        mock_vault.retrieve.return_value = (ref, b"{{{{not yaml")
        wired_run = dataclasses.replace(run, artifact_refs=("art_plan",))

        errors = await executor._reject_invalid_plan_before_workload_gate(
            wired_run, gated_cycle, "progress_plan_review"
        )
        assert not any("plan_authoring_collapsed" in e for e in errors)


# ---------------------------------------------------------------------------
# #881: resume must not re-seed the walking skeleton
# ---------------------------------------------------------------------------


class TestResumeDoesNotReseedSkeleton:
    """#881: skeleton seeding is a run-START act. On resume, the checkpoint's
    artifact_refs already carry the original seed set; a fresh set stores NEW
    artifact ids that are appended AFTER the restored state, and per-filename
    last-writer-wins then hands every fill slot back to a stub that throws by
    design — the resumed run tests the skeleton instead of the app (roll 14's
    resume: probes that passed 38/39 began returning 500 the moment it resumed).
    """

    @staticmethod
    def _manifest_bytes() -> bytes:
        from pathlib import Path

        return (
            Path(__file__).resolve().parents[3]
            / "examples"
            / "03_group_run"
            / "interface_manifest.yaml"
        ).read_bytes()

    def _wire(self, mock_registry, mock_vault, mock_queue, cycle, run):
        import dataclasses

        TestSequentialHappyPath._wire_canned_replies(mock_queue)
        seeded_cycle = dataclasses.replace(
            cycle, execution_overrides={"plan_artifact_refs": ["art_iface"]}
        )
        mock_registry.get_cycle.return_value = seeded_cycle
        ref = MagicMock()
        ref.artifact_id = "art_iface"
        ref.filename = "interface_manifest.yaml"
        ref.artifact_type = "interface_manifest"
        ref.metadata = {}
        mock_vault.retrieve = AsyncMock(return_value=(ref, self._manifest_bytes()))

    @staticmethod
    def _seeded_store_calls(mock_vault) -> list:
        return [
            call.args[0]
            for call in mock_vault.store.await_args_list
            if getattr(call.args[0], "metadata", None)
            and call.args[0].metadata.get("scaffold_seeded")
        ]

    async def test_fresh_run_seeds_the_skeleton(
        self, executor, mock_registry, mock_vault, mock_queue, cycle, run
    ) -> None:
        """Guard for the guard: if seeding stopped happening at all, the resume
        test below would pass vacuously."""
        self._wire(mock_registry, mock_vault, mock_queue, cycle, run)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        assert len(self._seeded_store_calls(mock_vault)) > 0

    async def test_resumed_run_does_not_reseed(
        self, executor, mock_registry, mock_vault, mock_queue, cycle, run
    ) -> None:
        from squadops.cycles.checkpoint import RunCheckpoint

        self._wire(mock_registry, mock_vault, mock_queue, cycle, run)
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_001",
            checkpoint_index=1,
            completed_task_ids=(),
            prior_outputs={},
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=NOW,
        )

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        assert self._seeded_store_calls(mock_vault) == []
        # the guard must not break execution — the resumed run still finishes
        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED


class TestCorrectionDeadlockIsNotRetried:
    """#1221: a repair whose verification can never return a verdict was re-dispatched
    until the budget ran out.

    pf-47/pf-49 named this — "no repair can EVER produce an executed verdict, so the
    loop burns its whole budget rejecting repairs unheard" — and implemented the escape
    for `qa.test`, whose `test_result` can decide instead. `development.develop`
    produces none, so on `nextjs_ts` (whose criteria need node, absent from runtime-api)
    every dev repair was refused unheard. `cyc_05abfc7c1f00` spent all three rounds on
    `app/api/runs/route.ts`, re-dispatching an identical task after two identical
    unverifiable verdicts.
    """

    @staticmethod
    def _deadlocked(status, reason, retest=False):
        from adapters.cycles.patch_acceptance import correction_is_deadlocked

        return correction_is_deadlocked(status, reason, retest_decides=retest)

    def test_the_roll5_shape_terminates(self):
        """The exact verdict that looped: unverifiable, no blocking check executed,
        and a dev task with no behavioral evidence to decide instead."""
        assert self._deadlocked("unverifiable", "no_executed_blocking_checks") is True

    def test_no_typed_criteria_terminates_too(self):
        """The sibling unevaluable reason. Making `checks=1` honestly `checks=0` produces
        this one, so treating only the other would move the deadlock rather than end it."""
        assert self._deadlocked("unverifiable", "no_typed_criteria") is True

    def test_a_task_with_behavioral_evidence_keeps_its_escape(self):
        """pf-47/pf-49's remedy must survive: when a retest CAN decide, the loop is not
        deadlocked and terminating would throw away a verdict that was available."""
        assert self._deadlocked("unverifiable", "no_executed_blocking_checks", retest=True) is False

    def test_a_real_check_failure_still_loops(self):
        """A patch that failed a check that actually executed is repairable — the next
        round has something to act on. Terminating here would abandon repairs that work,
        which is a far worse trade than the waste this fixes."""
        assert self._deadlocked("failed", "unresolved_imports:x imports y") is False

    def test_an_unverifiable_verdict_for_another_reason_still_loops(self):
        """Only the structurally-unevaluable reasons are deadlocks. An evaluator error or
        an unparseable criterion may resolve on the next emission."""
        assert self._deadlocked("unverifiable", "unparseable_criteria") is False

    def test_a_passing_patch_is_not_a_deadlock(self):
        assert self._deadlocked("passed", None) is False


class TestGateRejectsAQaTaskThatAuthorsNoSuite:
    """#1912 on the mid-run gate seam, the one an increment's plan gate passes through: a qa.test
    task declaring no suite is refused under its own validator, so the framing re-rolls for free
    instead of the run ending blocked_unverified. The control is the same task naming its file."""

    _PLAN = (
        TestGateRejectsBuilderPlanWithoutBuildProfile._BUILDER_PLAN_YAML.replace(
            "builder.assemble", "qa.test"
        )
        .replace("role: builder", "role: qa")
        .replace(
            '    expected_artifacts:\n      - "qa_handoff.md"\n      - "Dockerfile"\n'
            '      - "__main__.py"\n      - "requirements.txt"\n',
            "    expected_artifacts: EXPECTED\n",
        )
    )

    @pytest.mark.parametrize(
        ("expected", "refused"),
        [("[]", ("validate_qa_tasks_author_a_suite",)), ('["backend/tests/test_runs.py"]', None)],
    )
    async def test_the_gate_refuses_only_the_suiteless_task(
        self, executor, mock_vault, cycle, expected, refused
    ):
        import dataclasses

        from adapters.cycles.execution_errors import _ExecutionError

        assert "EXPECTED" in self._PLAN
        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "required_checks": ["tests_pass"],
                "build_profile": "fullstack_fastapi_react",
                "correction_steps": ["analyze", "decide", "repair"],
            },
        )
        mock_vault.retrieve.return_value = (
            "ref",
            self._PLAN.replace("EXPECTED", expected).encode(),
        )
        agent = MagicMock()
        agent.role = "qa"
        agent.serves_roles = ("qa",)
        agent.enabled = True
        profile = MagicMock()
        profile.profile_id = "full"
        profile.agents = [agent]

        gate = executor._reject_unsatisfiable_plan_at_gate(
            TestGateRejectsBuilderPlanWithoutBuildProfile._stored_plan_artifacts(),
            profile,
            ["progress_plan_review"],
            gated_cycle,
        )
        if refused is None:
            await gate
            return
        with pytest.raises(_ExecutionError) as exc_info:
            await gate
        assert "declares no expected artifact" in str(exc_info.value)
        assert exc_info.value.terminal.refused_validators == refused


class TestGateRejectsAQaSuiteOutsideTheStacksNamespace:
    """#1587 on the mid-run gate seam: collected is not owned. `tests/test_runs.py` at the
    repository root passes the collection rule (pytest collects it) and is refused by the
    namespace rule, under its own validator name, with the namespace in the message."""

    _QA_ROOT_SUITE_PLAN_YAML = (
        TestGateRejectsBuilderPlanWithoutBuildProfile._BUILDER_PLAN_YAML.replace(
            "builder.assemble", "qa.test"
        )
        .replace("role: builder", "role: qa")
        .replace("qa_handoff.md", "tests/test_runs.py")
    )

    async def test_rejected_under_the_namespace_validator_alone(self, executor, mock_vault, cycle):
        import dataclasses

        from adapters.cycles.execution_errors import _ExecutionError

        gated_cycle = dataclasses.replace(
            cycle,
            applied_defaults={
                "implementation_plan": True,
                "required_checks": ["tests_pass"],
                "build_profile": "fullstack_fastapi_react",
                "correction_steps": ["analyze", "decide", "repair"],
            },
        )
        mock_vault.retrieve.return_value = ("ref", self._QA_ROOT_SUITE_PLAN_YAML.encode())

        agent = MagicMock()
        agent.role = "qa"
        agent.serves_roles = ("qa",)
        agent.enabled = True
        profile = MagicMock()
        profile.profile_id = "full"
        profile.agents = [agent]

        with pytest.raises(_ExecutionError) as exc_info:
            await executor._reject_unsatisfiable_plan_at_gate(
                TestGateRejectsBuilderPlanWithoutBuildProfile._stored_plan_artifacts(),
                profile,
                ["progress_plan_review"],
                gated_cycle,
            )
        assert "'tests/test_runs.py'" in str(exc_info.value)
        assert "backend/tests/" in str(exc_info.value)
        assert exc_info.value.terminal.refused_validators == ("validate_qa_suite_namespace",)


class TestARunStartsOnlyWhenALaunchCould:
    """SIP-0109 §9.3 (#1802, #1928), entering at ``execute_run``: a run does not go ``running``
    when a launch would be refused, whether the supervisor holds the box or a model the deploy
    does not declare is resident. It waits queued and starts once a launch is allowed. Past one
    full lease (``lease_expiry_s``) of the campaign it waits on, it fails without starting; a run
    outside every campaign is refused at once, as its launch is.

    The verdict is the launch's own (``launch_verdict``) over the registry's lease and one
    engine's resident models, against a deploy declaring only the squad's model."""

    @staticmethod
    async def _held(lease_expiry_s: int = 3600):
        from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
        from squadops.campaigns.models import CampaignState, CampaignTransition, ControlOperation
        from tests.unit.campaigns.builders import campaign, move, policy

        reg = MemoryCampaignRegistry()
        await reg.create_campaign(
            campaign("cmp_c", policy=policy(lease_expiry_s=lease_expiry_s)),
            actor="o",
            actor_role="o",
            reason="r",
            idempotency_key="c",
        )
        for i, s in enumerate(("calibrating", "at_proposal", "awaiting_ruling")):
            await reg.transition("cmp_c", move(CampaignState(s), f"k{i}"))

        def lease(op, key, **extra):
            return CampaignTransition(
                operation=op,
                actor="crew",
                actor_role="campaign-supervisor",
                reason="gate",
                idempotency_key=key,
                next_state=None,
                binding={"held_by": "crew", **extra},
            )

        await reg.change_box_lease(
            "cmp_c", lease(ControlOperation.LEASE_ACQUIRE, "a", expires_in_s=900), runs_in_flight=()
        )
        return reg, lease(ControlOperation.LEASE_RELEASE, "r")

    @staticmethod
    def _verdict(reg, resident: list[str]):
        from squadops.campaigns.box import EngineReading, Model, box_quietness, launch_verdict

        async def verdict():
            loaded = tuple(Model(name) for name in resident)
            quietness = box_quietness([Model("qwen3.8:27b")], [EngineReading("ollama", loaded)])
            return launch_verdict(await reg.box_lease(), quietness, datetime.now(UTC))

        return verdict

    @staticmethod
    def _enforcing_transitions(mock_registry) -> dict:
        """The registry's own rule, applied: each status change is checked by
        ``validate_run_transition`` from the run's current status, and the run's status after it
        is kept. #1928's tests drove a registry that checked nothing, so a refusal that could
        never leave ``queued`` passed them and stranded its run live."""
        from squadops.cycles.lifecycle import validate_run_transition

        held = {"status": RunStatus.QUEUED}
        base = mock_registry.update_run_status.side_effect

        def update(run_id, status, *args, **kwargs):
            validate_run_transition(held["status"], status)
            held["status"] = status
            return base(run_id, status)

        mock_registry.update_run_status.side_effect = update
        return held

    @staticmethod
    def _in_campaign(mock_registry, cycle, campaign_id):
        import dataclasses

        mock_registry.get_cycle.return_value = dataclasses.replace(cycle, campaign_id=campaign_id)

    async def test_a_run_waits_queued_until_the_supervisor_gives_the_box_back(
        self, executor, mock_registry, mock_queue
    ):
        reg, release = await self._held()
        executor._campaign_registry = reg
        executor._box_verdict = self._verdict(reg, [])
        TestSequentialHappyPath._wire_canned_replies(mock_queue)
        waits: list[list] = []

        async def sleep(_seconds):
            # asyncio.sleep is one function wherever it is patched; this is the box wait's only
            # while the lease is held, and a no-op for every other sleeper.
            if (await reg.box_lease()).supervisor_holds(datetime.now(UTC)):
                waits.append([c.args[1] for c in mock_registry.update_run_status.call_args_list])
                await reg.change_box_lease("cmp_c", release, runs_in_flight=())

        with patch("adapters.cycles.run_admission.asyncio.sleep", side_effect=sleep):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert waits == [[]]  # it waited once, and nothing had started the run
        assert (statuses[0], statuses[-1]) == (RunStatus.RUNNING, RunStatus.COMPLETED)

    async def test_a_crew_model_left_resident_when_the_lease_returns_keeps_the_run_queued(
        self, executor, mock_registry, mock_queue, cycle
    ):
        """#1928: the framing run after a ruling waited only on the lease, so a release with the
        crew's model still loaded started it beside that model. It waits for the unload now."""
        from squadops.campaigns.box import LaunchRefusal

        reg, release = await self._held()
        resident = ["llama3.1:8b"]
        executor._campaign_registry = reg
        executor._box_verdict = verdict = self._verdict(reg, resident)
        self._in_campaign(mock_registry, cycle, "cmp_c")
        TestSequentialHappyPath._wire_canned_replies(mock_queue)
        refusals: list[tuple] = []

        async def sleep(_seconds):
            now = await verdict()
            if now.allowed:  # another sleeper
                return
            started = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
            refusals.append((now.refusal, started))
            if now.refusal is LaunchRefusal.SUPERVISOR_HOLDS_THE_BOX:
                await reg.change_box_lease("cmp_c", release, runs_in_flight=())  # model still in
            else:
                resident.clear()  # the supervisor unloads it

        with patch("adapters.cycles.run_admission.asyncio.sleep", side_effect=sleep):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert refusals == [
            (LaunchRefusal.SUPERVISOR_HOLDS_THE_BOX, []),
            (LaunchRefusal.BOX_NOT_QUIET, []),
        ]
        assert (statuses[0], statuses[-1]) == (RunStatus.RUNNING, RunStatus.COMPLETED)

    @staticmethod
    def _clock():
        class Clock:
            """Each read is 45 s on: the second poll is past a 60 s bound."""

            at = datetime.now(UTC)

            @classmethod
            def now(cls, tz=None):
                cls.at += timedelta(seconds=45)
                return cls.at

        return Clock

    @pytest.mark.parametrize(
        ("released", "resident", "reason"),
        [
            (False, [], "the supervisor (crew) holds the box until"),
            (True, ["llama3.1:8b"], "engine ollama has llama3.1:8b loaded, which the deploy"),
        ],
        ids=["the lease held", "the lease returned with a crew model resident"],
    )
    async def test_a_box_refused_past_one_full_lease_fails_the_run_unstarted(
        self, executor, mock_registry, cycle, released, resident, reason
    ):
        """Bound by the holding campaign while the lease is held, else by the run's own."""
        reg, release = await self._held(lease_expiry_s=60)
        if released:
            await reg.change_box_lease("cmp_c", release, runs_in_flight=())
        executor._campaign_registry = reg
        executor._box_verdict = self._verdict(reg, resident)
        self._in_campaign(mock_registry, cycle, "cmp_c")
        run = self._enforcing_transitions(mock_registry)

        with (
            patch("adapters.cycles.run_admission.datetime", self._clock()),
            patch("adapters.cycles.run_admission.asyncio.sleep", new_callable=AsyncMock),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        calls = mock_registry.update_run_status.call_args_list
        assert RunStatus.RUNNING not in [c.args[1] for c in calls]
        assert run["status"] is RunStatus.FAILED
        failure = calls[-1].kwargs["failure_reason"]
        assert "waited 60s for the box, one full lease of its campaign" in failure
        assert reason in failure

    async def test_a_run_outside_every_campaign_is_refused_at_once_on_a_box_not_quiet(
        self, executor, mock_registry, cycle
    ):
        """No lease to wait out: refused as its launch is (the create route's 409), not left
        queued with nothing that will ever release it."""
        from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry

        reg = MemoryCampaignRegistry()
        executor._campaign_registry = reg
        executor._box_verdict = self._verdict(reg, ["llama3.1:8b"])
        self._in_campaign(mock_registry, cycle, None)
        run = self._enforcing_transitions(mock_registry)
        box_sleep = AsyncMock()

        with patch("adapters.cycles.run_admission.asyncio.sleep", box_sleep):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        calls = mock_registry.update_run_status.call_args_list
        assert [c.args[1] for c in calls] == [RunStatus.FAILED]
        assert run["status"] is RunStatus.FAILED
        assert "is refused: engine ollama has llama3.1:8b" in calls[-1].kwargs["failure_reason"]
        assert "outside every campaign" in calls[-1].kwargs["failure_reason"]
        box_sleep.assert_not_awaited()

    # The root's box_verdict wiring is now proven with every other required dependency, from
    # main.py's own call: test_flow_executor_factory.py::
    # test_the_runtime_root_wires_every_required_dependency_to_an_object (#1987).


class TestARunTheShutdownInterruptsIsLeftForReattach:
    """#1929, entering at ``execute_run``. A graceful stop closes the pool and fails the reply
    waits, and the run read that as its own failure. Its ``failed`` write survived only because
    the pool was already closed; reaching an open pool, it would record a restart as a failed
    run, which the re-attach (§24am) then skips and the campaign retries. Once the executor is
    told the process is stopping, the run is left exactly as it was."""

    @pytest.mark.parametrize(
        "stopping", [True, False], ids=["the process stopping", "a run failing"]
    )
    async def test_the_same_failure_is_left_when_stopping_and_recorded_otherwise(
        self, executor, mock_registry, stopping
    ):
        import asyncio

        async def interrupted(*args, **kwargs):
            if stopping:
                executor.begin_shutdown()
            raise RuntimeError("pool is closed")

        executor._task_dispatcher.dispatch_task = AsyncMock(side_effect=interrupted)
        finalize = AsyncMock()
        executor._run_completion.finalize = finalize

        if stopping:
            with pytest.raises(asyncio.CancelledError):
                await executor.execute_run(cycle_id="cyc_001", run_id="run_001")
        else:
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        if stopping:
            assert (statuses, finalize.await_count) == ([RunStatus.RUNNING], 0)
        else:
            assert (statuses[-1], finalize.await_count) == (RunStatus.FAILED, 1)

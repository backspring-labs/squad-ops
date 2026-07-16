"""Tests for SIP-0079 outcome routing in DispatchedFlowExecutor.

Covers TaskOutcome-based routing: RETRYABLE_FAILURE retries, SEMANTIC_FAILURE
triggers correction, BLOCKED pauses, SUCCESS resets and checkpoints,
NEEDS_REPLAN from contract aborts immediately, and the D5 fallback table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_outcome import TaskOutcome
from squadops.tasks.models import TaskResult

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    auto-delivers the agent's reply (SIP-0094)."""
    mock = AsyncMock()
    mock.ack.return_value = None
    mock.invalidate_queue.return_value = None
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
def executor(mock_registry, mock_vault, mock_queue, mock_squad_profile, cycle, run):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    mock_registry.get_cycle.return_value = cycle
    mock_registry.get_run.return_value = run
    return DispatchedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
        reply_router=mock_queue.reply_router,
    )


# ---------------------------------------------------------------------------
# Helpers for scripted agent replies
# ---------------------------------------------------------------------------


def _scripted_responder(responses):
    """Build a reply-router responder that returns a different result per
    dispatch (SIP-0094 equivalent of the old per-publish consume side_effect).

    ``responses`` maps dispatch index (0-based, in publish order) to
    (status, outputs, error). Missing indices get status="SUCCEEDED". The
    responder is invoked once per ``comms.task`` publish, so the index advances
    in lockstep with the executor's dispatch sequence — exactly as the old
    consume side_effect's call counter did.
    """
    call_idx = {"n": 0}

    def responder(env):
        idx = call_idx["n"]
        call_idx["n"] += 1
        status, outputs, error = responses.get(
            idx, ("SUCCEEDED", {"summary": "ok", "role": "strat"}, None)
        )
        return TaskResult(
            task_id=env["task_id"],
            status=status,
            outputs=outputs,
            error=error,
        )

    return responder


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRetryableFailure:
    """RETRYABLE_FAILURE outcome → retry the same task."""

    async def test_retryable_retries_same_task(self, executor, mock_queue, mock_registry):
        """First dispatch fails, retried, succeeds on second attempt."""
        # Publish call 0: first task → FAILED (no outcome_class → RETRYABLE)
        # Publish call 1: retry same task → SUCCEEDED
        # Publish calls 2-6: remaining 4 tasks → SUCCEEDED
        responses = {
            0: ("FAILED", None, "transient"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (fail) + 1 (retry) + 4 (remaining) = 6 publishes
        assert mock_queue.publish.call_count == 6

        # Run should complete successfully
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses

    async def test_retryable_uses_max_task_retries(
        self, executor, mock_queue, mock_registry, cycle
    ):
        """With max_task_retries=3, task gets 3 attempts before SEMANTIC."""
        import dataclasses

        cycle_3 = dataclasses.replace(cycle, applied_defaults={"max_task_retries": 3})
        mock_registry.get_cycle.return_value = cycle_3

        # All dispatches fail → attempt 1,2 = RETRYABLE, attempt 3 = SEMANTIC
        responses = {i: ("FAILED", None, "boom") for i in range(10)}
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 3 (retries) + 2 (correction tasks) = 5 publishes
        assert mock_queue.publish.call_count == 5

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


class TestSemanticFailure:
    """SEMANTIC_FAILURE → triggers correction protocol."""

    async def test_explicit_semantic_failure_triggers_correction(
        self, executor, mock_queue, mock_registry
    ):
        """Task returns explicit SEMANTIC_FAILURE → correction protocol runs."""
        outputs_with_semantic = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "summary": "bad output",
            "role": "strat",
        }
        # Dispatch 0: FAILED with SEMANTIC_FAILURE outcome
        # Dispatches 1-2: correction tasks (analyze_failure + correction_decision)
        responses = {
            0: ("FAILED", outputs_with_semantic, "semantic error"),
            1: ("FAILED", None, "correction failed"),
            2: ("FAILED", None, "correction failed"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (task) + 2 (correction) = 3 publishes (no retry for explicit outcome)
        assert mock_queue.publish.call_count == 3

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


class TestBlockedOutcome:
    """BLOCKED outcome → run transitions to PAUSED."""

    async def test_blocked_pauses_run(self, executor, mock_queue, mock_registry):
        """Task returns BLOCKED outcome → run transitions to PAUSED."""
        outputs_blocked = {
            "outcome_class": TaskOutcome.BLOCKED,
            "summary": "waiting for approval",
            "role": "strat",
        }
        responses = {
            0: ("FAILED", outputs_blocked, "blocked"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Only 1 publish (blocked on first task)
        assert mock_queue.publish.call_count == 1

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.PAUSED in terminal_statuses


class TestSuccessOutcome:
    """SUCCESS → checkpoint saved, consecutive_failures reset."""

    async def test_success_checkpoints(self, executor, mock_queue, mock_registry):
        """Each successful task triggers a checkpoint save."""
        # All 5 tasks succeed
        mock_queue.reply_router.responder = _scripted_responder({})

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 5 tasks → 5 checkpoint saves
        assert mock_registry.save_checkpoint.call_count == 5

    async def test_success_after_retry_still_checkpoints(self, executor, mock_queue, mock_registry):
        """Task fails once (retried), then succeeds → checkpoint saved."""
        responses = {
            0: ("FAILED", None, "transient"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 5 successful tasks → 5 checkpoints (retry failure doesn't checkpoint)
        assert mock_registry.save_checkpoint.call_count == 5


class TestNeedReplanFromContract:
    """NEEDS_REPLAN from governance.define_done → immediate abort (D9)."""

    async def test_contract_failure_aborts_immediately(
        self, executor, mock_queue, mock_registry, run
    ):
        """Contract task failure → no correction protocol, immediate abort."""
        import dataclasses

        run_impl = dataclasses.replace(run, workload_type="implementation")
        mock_registry.get_run.return_value = run_impl

        outputs_replan = {
            "outcome_class": TaskOutcome.NEEDS_REPLAN,
            "summary": "contract parse failed",
            "role": "lead",
        }
        responses = {
            0: ("FAILED", outputs_replan, "parse error"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Only 1 publish — contract failure is immediate abort
        assert mock_queue.publish.call_count == 1

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


class TestFallbackTable:
    """D5 fallback table: None outcome_class → RETRYABLE first, SEMANTIC after."""

    async def test_none_outcome_first_failure_retries(self, executor, mock_queue, mock_registry):
        """First unclassified failure → RETRYABLE → retry."""
        # First dispatch fails (no outcome), second succeeds, rest succeed
        responses = {
            0: ("FAILED", None, "transient"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (fail) + 1 (retry succeeds) + 4 (remaining) = 6
        assert mock_queue.publish.call_count == 6
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses

    async def test_exhausted_retries_becomes_semantic(self, executor, mock_queue, mock_registry):
        """All retries exhausted → SEMANTIC_FAILURE → correction → abort."""
        responses = {i: ("FAILED", None, "boom") for i in range(10)}
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 2 (retries) + 2 (correction) = 4
        assert mock_queue.publish.call_count == 4

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


class TestNeedsRepairOutcome:
    """NEEDS_REPAIR outcome → triggers correction protocol."""

    async def test_needs_repair_triggers_correction(self, executor, mock_queue, mock_registry):
        """Explicit NEEDS_REPAIR → correction protocol."""
        outputs_repair = {
            "outcome_class": TaskOutcome.NEEDS_REPAIR,
            "summary": "needs fix",
            "role": "strat",
        }
        responses = {
            0: ("FAILED", outputs_repair, "repair needed"),
            1: ("FAILED", None, "corr"),
            2: ("FAILED", None, "corr"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (task) + 2 (correction tasks) = 3
        assert mock_queue.publish.call_count == 3

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


class TestAcceptPatch:
    """#389: a behaviorally-verified patch is accepted without re-dispatching
    the generative task (re-dispatch re-rolls artifacts and clobbers repairs)."""

    def _failed_builder_result(self):
        return TaskResult(
            task_id="task_5",
            status="FAILED",
            outputs={
                "artifacts": [
                    {"name": "qa_handoff.md", "content": "# QA Handoff\n## How to Run\n"}
                ],
                "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            },
            error="acceptance failed",
        )

    def _builder_envelope(self):
        from squadops.cycles.implementation_plan import TypedCheck
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task_5",
            agent_id="bob",
            cycle_id="cyc_001",
            pulse_id="p",
            project_id="hello_squad",
            task_type="builder.assemble",
            correlation_id="corr",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={
                "resolved_config": {},
                "acceptance_criteria": [
                    TypedCheck(
                        check="regex_match",
                        params={"file": "qa_handoff.md", "pattern": "## How to Test"},
                        severity="error",
                        description="Contains How to Test section",
                    )
                ],
            },
            metadata={"role": "builder"},
        )

    async def test_verified_patch_accepted_with_corrected_result(self, executor):
        """Bug caught: verified repairs re-dispatched into a re-roll — the
        cyc_6841d75f167c oscillation that starved the correction budget."""
        holder: dict = {}
        action = await executor._try_accept_patch(
            self._builder_envelope(),
            self._failed_builder_result(),
            [{"name": "qa_handoff.md", "content": "# QA Handoff\n## How to Test\nok\n"}],
            holder,
        )

        assert action == "accept_patch"
        corrected = holder["patched_result"]
        assert corrected.status == "SUCCEEDED"
        assert corrected.error is None
        assert corrected.outcome_class is None
        assert "outcome_class" not in corrected.outputs
        # The repaired artifact supersedes the broken generation.
        by_name = {a["name"]: a["content"] for a in corrected.outputs["artifacts"]}
        assert "## How to Test" in by_name["qa_handoff.md"]
        # Executed-passed evidence in the shape normalize_task_checks reads.
        checks = corrected.outputs["validation_result"]["checks"]
        assert checks and all(c["status"] == "passed" for c in checks)
        assert corrected.outputs["validation_result"]["patch_verified"] is True

    async def test_failed_verification_falls_back_to_continue(self, executor):
        """Bug caught: accepting a repair that still violates the contract —
        a false green at the task level."""
        holder: dict = {}
        action = await executor._try_accept_patch(
            self._builder_envelope(),
            self._failed_builder_result(),
            [{"name": "qa_handoff.md", "content": "# QA Handoff\nstill missing sections\n"}],
            holder,
        )
        assert action == "continue"
        assert "patched_result" not in holder

    async def test_no_repair_artifacts_falls_back_to_continue(self, executor):
        """Bug caught: 'verifying' an empty patch against the broken original
        (which would fail) or worse, against nothing (which could pass)."""
        holder: dict = {}
        action = await executor._try_accept_patch(
            self._builder_envelope(), self._failed_builder_result(), [], holder
        )
        assert action == "continue"
        assert holder == {}

    async def test_unverifiable_contract_falls_back_to_continue(self, executor):
        """Bug caught: accepting a patch with no typed criteria — zero
        executed evidence (the §6.2 false-green shape)."""
        import dataclasses as _dc

        envelope = self._builder_envelope()
        envelope = _dc.replace(
            envelope, inputs={"resolved_config": {}, "acceptance_criteria": ["prose only"]}
        )
        holder: dict = {}
        action = await executor._try_accept_patch(
            envelope,
            self._failed_builder_result(),
            [{"name": "qa_handoff.md", "content": "# QA Handoff\n## How to Test\n"}],
            holder,
        )
        assert action == "continue"
        assert holder == {}


class TestAcceptPatchRetest:
    """#456: a qa.test-class patch (failed outputs carry ``test_result``) must
    re-execute the repaired suite before acceptance — tests_pass is synthesized
    from test_result, so accepting with the stale one records the pre-repair
    failure as the check's final state (run_8c14a430ad1c false-red)."""

    def _failed_qa_result(self):
        return TaskResult(
            task_id="task_9",
            status="FAILED",
            outputs={
                "artifacts": [
                    {
                        "name": "tests/test_api.py",
                        "content": "def test_x():\n    assert 0\n",
                        "type": "test",
                    },
                    {"name": "test_report.md", "content": "exit 1", "type": "test_report"},
                ],
                "test_result": {"executed": True, "exit_code": 1, "tests_passed": False},
                "validation_result": {"passed": False, "checks": []},
                "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            },
            error="tests failed",
        )

    def _qa_envelope(self):
        from squadops.cycles.implementation_plan import TypedCheck
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task_9",
            agent_id="eve",
            cycle_id="cyc_001",
            pulse_id="p",
            project_id="hello_squad",
            task_type="qa.test",
            correlation_id="corr",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={
                "resolved_config": {},
                "artifact_contents": {"src/main.py": "def main():\n    pass\n"},
                "acceptance_criteria": [
                    TypedCheck(
                        check="regex_match",
                        params={"file": "tests/test_api.py", "pattern": "def test_"},
                        severity="error",
                        description="Suite defines tests",
                    )
                ],
            },
            metadata={"role": "qa"},
        )

    def _repair(self):
        return [{"name": "tests/test_api.py", "content": "def test_x():\n    assert 1\n"}]

    def _retest_success(self):
        return TaskResult(
            task_id="retest-run_001-00-qa.test",
            status="SUCCEEDED",
            outputs={
                "test_result": {"executed": True, "exit_code": 0, "tests_passed": True},
                "validation_result": {
                    "passed": True,
                    "checks": [{"check": "frontend_build", "passed": True}],
                },
            },
        )

    def _kwargs(self, cycle):
        return {
            "run_id": "run_001",
            "cycle": cycle,
            "correction_attempts": 0,
            "prior_outputs": {},
            "all_artifact_refs": [],
            "stored_artifacts": [],
            "completed_task_ids": [],
            "plan_delta_refs": [],
            "profile": None,
            "flow_run_id": None,
        }

    async def test_retest_pass_accepts_with_fresh_evidence(self, executor, cycle):
        """Bug caught (run_8c14a430ad1c): patched result keeping the stale
        exit-1 test_result — the ledger's final tests_pass state stays failed."""
        executor._correction_runner.reexecute_repaired_suite = AsyncMock(
            return_value=self._retest_success()
        )
        holder: dict = {}
        action = await executor._try_accept_patch(
            self._qa_envelope(),
            self._failed_qa_result(),
            self._repair(),
            holder,
            **self._kwargs(cycle),
        )

        assert action == "accept_patch"
        corrected = holder["patched_result"]
        # Fresh behavioral evidence supersedes the stale failure.
        assert corrected.outputs["test_result"]["tests_passed"] is True
        assert corrected.outputs["test_result"]["exit_code"] == 0
        # Retest rows (frontend_build) ride along with the typed rows.
        checks = corrected.outputs["validation_result"]["checks"]
        assert any(c.get("check") == "frontend_build" for c in checks)
        # The retest received the patched (overlaid) suite, not the broken one.
        call = executor._correction_runner.reexecute_repaired_suite.await_args
        patched = call.args[3]
        by_name = {a["name"]: a["content"] for a in patched}
        assert "assert 1" in by_name["tests/test_api.py"]

    async def test_retest_failure_falls_back_to_continue(self, executor, cycle):
        """Bug caught: accepting a repair whose suite still fails when
        re-executed — typed rows alone said yes."""
        executor._correction_runner.reexecute_repaired_suite = AsyncMock(
            return_value=TaskResult(
                task_id="retest",
                status="FAILED",
                outputs={"test_result": {"executed": True, "exit_code": 1, "tests_passed": False}},
                error="still failing",
            )
        )
        holder: dict = {}
        action = await executor._try_accept_patch(
            self._qa_envelope(),
            self._failed_qa_result(),
            self._repair(),
            holder,
            **self._kwargs(cycle),
        )
        assert action == "continue"
        assert "patched_result" not in holder

    async def test_missing_retest_context_never_accepts_stale_evidence(self, executor):
        """Bug caught: a legacy call shape (no cycle) silently accepting with
        the stale test_result — conservative fallback is re-dispatch."""
        holder: dict = {}
        action = await executor._try_accept_patch(
            self._qa_envelope(), self._failed_qa_result(), self._repair(), holder
        )
        assert action == "continue"
        assert holder == {}

    async def test_non_behavioral_patch_skips_retest(self, executor, cycle):
        """Guard: tasks without test_result (builder) accept on typed rows
        alone — no retest dispatch, behavior unchanged from #389."""
        from squadops.cycles.implementation_plan import TypedCheck
        from squadops.tasks.models import TaskEnvelope

        executor._correction_runner.reexecute_repaired_suite = AsyncMock()
        envelope = TaskEnvelope(
            task_id="task_5",
            agent_id="bob",
            cycle_id="cyc_001",
            pulse_id="p",
            project_id="hello_squad",
            task_type="builder.assemble",
            correlation_id="corr",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={
                "resolved_config": {},
                "acceptance_criteria": [
                    TypedCheck(
                        check="regex_match",
                        params={"file": "qa_handoff.md", "pattern": "## How to Test"},
                        severity="error",
                        description="Contains How to Test section",
                    )
                ],
            },
            metadata={"role": "builder"},
        )
        failed = TaskResult(
            task_id="task_5",
            status="FAILED",
            outputs={
                "artifacts": [{"name": "qa_handoff.md", "content": "# QA\n"}],
                "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            },
            error="acceptance failed",
        )
        holder: dict = {}
        action = await executor._try_accept_patch(
            envelope,
            failed,
            [{"name": "qa_handoff.md", "content": "# QA\n## How to Test\nok\n"}],
            holder,
            **self._kwargs(cycle),
        )
        assert action == "accept_patch"
        executor._correction_runner.reexecute_repaired_suite.assert_not_awaited()


class TestAcceptPatchRetestWorkspaceThreading:
    """3.11 instant-fail: the retest was built from the BASE envelope, but
    artifact_contents (the workspace) exists only on the dispatch-time
    enriched envelope — eve rejected every retest at input validation in
    300ms and the fallback re-rolls burned the correction budget."""

    async def test_retest_receives_enriched_envelope(self, executor, cycle):
        import dataclasses

        from squadops.cycles.implementation_plan import TypedCheck
        from squadops.tasks.models import TaskEnvelope

        executor._correction_runner.reexecute_repaired_suite = AsyncMock(
            return_value=TaskResult(
                task_id="retest",
                status="SUCCEEDED",
                outputs={"test_result": {"executed": True, "exit_code": 0, "tests_passed": True}},
            )
        )
        base = TaskEnvelope(
            task_id="task_9",
            agent_id="eve",
            cycle_id="cyc_001",
            pulse_id="p",
            project_id="hello_squad",
            task_type="qa.test",
            correlation_id="corr",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={
                "resolved_config": {},
                "acceptance_criteria": [
                    TypedCheck(
                        check="regex_match",
                        params={"file": "tests/test_api.py", "pattern": "def test_"},
                        severity="error",
                        description="Suite defines tests",
                    )
                ],
            },
            metadata={"role": "qa"},
        )
        enriched = dataclasses.replace(
            base,
            inputs={**base.inputs, "artifact_contents": {"src/main.py": "app = 1\n"}},
        )
        failed = TaskResult(
            task_id="task_9",
            status="FAILED",
            outputs={
                "artifacts": [{"name": "tests/test_api.py", "content": "def test_x(): assert 0\n"}],
                "test_result": {"executed": True, "exit_code": 1, "tests_passed": False},
                "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            },
            error="tests failed",
        )
        holder: dict = {}
        action = await executor._try_accept_patch(
            base,
            failed,
            [{"name": "tests/test_api.py", "content": "def test_x(): assert 1\n"}],
            holder,
            run_id="run_001",
            cycle=cycle,
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            profile=None,
            flow_run_id=None,
            enriched_envelope=enriched,
        )

        assert action == "accept_patch"
        retest_envelope = executor._correction_runner.reexecute_repaired_suite.await_args.args[2]
        assert retest_envelope.inputs["artifact_contents"] == {"src/main.py": "app = 1\n"}

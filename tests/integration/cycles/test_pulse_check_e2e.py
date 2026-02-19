"""End-to-end pulse check verification integration tests (SIP-0070 Phase 4).

These tests exercise the full executor→verification→repair chain using
MemoryCycleRegistry and mocked queue + vault.  They are skipped when
runtime dependencies (aio_pika) are not installed.

Covers:
- Full executor run with verification PASS
- Repair loop: failing check → repair → rerun → PASS
- EXHAUSTED: persistent failure → run FAILED
- Backward compat: no pulse_checks = unchanged
- Run report includes pulse verification section
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

try:
    import aio_pika  # noqa: F401

    _has_runtime_deps = True
except ImportError:
    _has_runtime_deps = False

from squadops.comms.queue_message import QueueMessage
from squadops.cycles.models import (
    Cycle,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.pulse_models import SuiteOutcome
from squadops.tasks.models import TaskResult

pytestmark = [
    pytest.mark.domain_pulse_checks,
    pytest.mark.integration,
    pytest.mark.skipif(not _has_runtime_deps, reason="aio_pika not installed"),
]

NOW = datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cycle(pulse_checks=None, cadence_policy=None):
    defaults = {}
    if pulse_checks:
        defaults["pulse_checks"] = pulse_checks
    if cadence_policy:
        defaults["cadence_policy"] = cadence_policy
    return Cycle(
        cycle_id="cyc_e2e",
        project_id="e2e_project",
        created_at=NOW,
        created_by="system",
        prd_ref="Build an e2e test widget",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:e2e",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=defaults,
    )


def _make_registry(cycle):
    from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry

    registry = MemoryCycleRegistry()
    # Seed cycle and run synchronously via internals
    import asyncio

    loop = asyncio.get_event_loop()

    async def _seed():
        await registry.create_cycle(
            project_id=cycle.project_id,
            prd_ref=cycle.prd_ref,
            squad_profile_id=cycle.squad_profile_id,
            squad_profile_snapshot_ref=cycle.squad_profile_snapshot_ref,
            task_flow_policy=cycle.task_flow_policy,
            build_strategy=cycle.build_strategy,
            applied_defaults=cycle.applied_defaults,
            created_by=cycle.created_by,
            cycle_id_override=cycle.cycle_id,
        )
        await registry.create_run(cycle.cycle_id, run_id_override="run_e2e")

    loop.run_until_complete(_seed())
    return registry


def _make_result_message(task_id, queue_name="cycle_results_run_e2e"):
    result = TaskResult(
        task_id=task_id,
        status="SUCCEEDED",
        outputs={"summary": "ok", "artifacts": []},
    )
    return QueueMessage(
        queue_name=queue_name,
        body=json.dumps(result.to_dict()).encode(),
    )


def _consume_factory(mock_queue):
    async def _consume(queue_name, max_messages=1):
        if not queue_name.startswith("cycle_results_"):
            return []
        last_call = mock_queue.publish.call_args
        if last_call:
            msg_data = json.loads(last_call.args[1])
            task_id = msg_data["payload"]["task_id"]
            return [_make_result_message(task_id, queue_name)]
        return []

    return _consume


def _make_executor(registry, cycle):
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    mock_vault = AsyncMock()
    mock_queue = AsyncMock()
    mock_queue.consume.side_effect = _consume_factory(mock_queue)

    squad_profile = SquadProfile(
        profile_id="full-squad",
        agents=(),
    )
    mock_squad_profile = AsyncMock()
    mock_squad_profile.get_profile.return_value = squad_profile

    executor = DistributedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
    )
    return executor, mock_queue


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPulseCheckE2E:
    async def test_backward_compat_no_pulse_checks(self):
        """No pulse_checks in defaults = unchanged run behavior."""
        cycle = _make_cycle()
        registry = _make_registry(cycle)
        executor, mock_queue = _make_executor(registry, cycle)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_e2e", run_id="run_e2e")

        run = await registry.get_run("run_e2e")
        assert run.status == RunStatus.COMPLETED.value

    async def test_verification_pass_completes(self):
        """All checks PASS → run COMPLETED normally."""
        cycle = _make_cycle(
            pulse_checks=[
                {
                    "suite_id": "post_dev",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        registry = _make_registry(cycle)
        executor, mock_queue = _make_executor(registry, cycle)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        def all_pass(*, suites, **kwargs):
            return [
                PulseVerificationRecord(
                    suite_id=s.suite_id,
                    boundary_id=s.boundary_id,
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_e2e"),
                    suite_outcome=SuiteOutcome.PASS,
                )
                for s in suites
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=all_pass,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_e2e", run_id="run_e2e")

        run = await registry.get_run("run_e2e")
        assert run.status == RunStatus.COMPLETED.value

    async def test_repair_then_pass(self):
        """FAIL → repair chain → rerun PASS → run COMPLETED."""
        cycle = _make_cycle(
            pulse_checks=[
                {
                    "suite_id": "post_dev",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        registry = _make_registry(cycle)
        executor, mock_queue = _make_executor(registry, cycle)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def fail_then_pass(*, suites, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id=s.suite_id,
                    boundary_id=s.boundary_id,
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_e2e"),
                    suite_outcome=outcome,
                )
                for s in suites
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=fail_then_pass,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_e2e", run_id="run_e2e")

        run = await registry.get_run("run_e2e")
        assert run.status == RunStatus.COMPLETED.value

    async def test_exhausted_fails_run(self):
        """Persistent failure → EXHAUSTED → run FAILED."""
        cycle = _make_cycle(
            pulse_checks=[
                {
                    "suite_id": "post_dev",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        registry = _make_registry(cycle)
        executor, mock_queue = _make_executor(registry, cycle)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        def always_fail(*, suites, **kwargs):
            return [
                PulseVerificationRecord(
                    suite_id=s.suite_id,
                    boundary_id=s.boundary_id,
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_e2e"),
                    suite_outcome=SuiteOutcome.FAIL,
                )
                for s in suites
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=always_fail,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_e2e", run_id="run_e2e")

        run = await registry.get_run("run_e2e")
        assert run.status == RunStatus.FAILED.value

    async def test_run_report_includes_pulse_section(self):
        """Run report artifact contains '## Pulse Verification' when checks ran."""
        cycle = _make_cycle(
            pulse_checks=[
                {
                    "suite_id": "post_dev",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        registry = _make_registry(cycle)
        executor, mock_queue = _make_executor(registry, cycle)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        def all_pass(*, suites, **kwargs):
            return [
                PulseVerificationRecord(
                    suite_id=s.suite_id,
                    boundary_id=s.boundary_id,
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_e2e"),
                    suite_outcome=SuiteOutcome.PASS,
                )
                for s in suites
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=all_pass,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_e2e", run_id="run_e2e")

        # Check that vault.store was called with run_report.md containing pulse section
        vault = executor._artifact_vault
        store_calls = vault.store.call_args_list
        report_call = [
            c for c in store_calls if c.args[0].filename == "run_report.md"
        ]
        assert len(report_call) == 1
        content = report_call[0].args[1].decode("utf-8")
        assert "## Pulse Verification" in content
        assert "post_dev" in content

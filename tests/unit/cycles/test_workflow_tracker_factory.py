"""Tests for ``adapters.cycles.workflow_tracker_factory``.

Pins the always-inject contract — the factory MUST return a usable
:class:`WorkflowTrackerPort` even when no backend is configured, so callers
never branch on ``None``. Mirrors the recipe used by SIP-0061 (LangFuse) and
SIP-0087 (log forwarder).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from adapters.cycles.noop_workflow_tracker import NoOpWorkflowTracker
from adapters.cycles.prefect_reporter import PrefectReporter
from adapters.cycles.workflow_tracker_factory import create_workflow_tracker
from squadops.config.schema import PrefectConfig
from squadops.ports.cycles import WorkflowTrackerPort

pytestmark = [pytest.mark.domain_cycles]


def _cfg(**overrides) -> PrefectConfig:
    base = {"api_url": "http://prefect:4200/api"}
    base.update(overrides)
    return PrefectConfig(**base)


def test_returns_noop_when_config_is_none():
    tracker = create_workflow_tracker(None)
    assert isinstance(tracker, NoOpWorkflowTracker)
    assert isinstance(tracker, WorkflowTrackerPort)


def test_returns_noop_when_api_url_unset():
    tracker = create_workflow_tracker(_cfg(api_url=""))
    assert isinstance(tracker, NoOpWorkflowTracker)


def test_returns_prefect_reporter_when_configured():
    tracker = create_workflow_tracker(_cfg())
    assert isinstance(tracker, PrefectReporter)
    assert isinstance(tracker, WorkflowTrackerPort)


def test_falls_back_to_noop_on_init_failure():
    with patch(
        "adapters.cycles.prefect_reporter.PrefectReporter",
        side_effect=RuntimeError("boom"),
    ):
        tracker = create_workflow_tracker(_cfg())
    assert isinstance(tracker, NoOpWorkflowTracker)


# ---------------------------------------------------------------------------
# NoOp surface contract
# ---------------------------------------------------------------------------


async def test_noop_create_methods_return_nonempty_placeholders():
    tracker = NoOpWorkflowTracker()
    flow_id = await tracker.ensure_flow()
    flow_run_id = await tracker.create_flow_run(flow_id, "run-1")
    task_run_id = await tracker.create_task_run(flow_run_id, "task.key", "task name")
    assert flow_id and flow_run_id and task_run_id
    # Distinct call returns distinct placeholder so callers can correlate.
    assert flow_id != flow_run_id != task_run_id


async def test_noop_state_setters_and_close_are_no_ops():
    """Idempotent and never raise — pure no-ops."""
    tracker = NoOpWorkflowTracker()
    await tracker.set_flow_run_state("fr-1", "RUNNING", "Running")
    await tracker.set_task_run_state("tr-1", "COMPLETED", "Completed")
    await tracker.close()
    await tracker.close()  # idempotent

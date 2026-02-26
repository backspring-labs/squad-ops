"""Tests for PrefectReporter (adapters/cycles/prefect_reporter.py).

Covers ensure_flow (create + find existing), create_flow_run,
create_task_run, set_state methods, and graceful degradation.

Uses httpx mock transport to simulate Prefect REST API responses.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from adapters.cycles.prefect_reporter import PrefectReporter

pytestmark = [pytest.mark.domain_orchestration]


PREFECT_URL = "http://prefect-server:4200/api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int = 200, json_data: dict | list | None = None):
    """Build an httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("POST", PREFECT_URL),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnsureFlow:
    async def test_creates_flow_when_none_exists(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)

        # First call: filter returns empty
        # Second call: create returns new flow
        reporter._client.post = AsyncMock(
            side_effect=[
                _mock_response(200, []),  # filter: no existing flows
                _mock_response(201, {"id": "flow-123"}),  # create
            ]
        )

        flow_id = await reporter.ensure_flow()

        assert flow_id == "flow-123"
        assert reporter._flow_id == "flow-123"
        assert reporter._client.post.call_count == 2

        # Verify filter call
        filter_call = reporter._client.post.call_args_list[0]
        assert "/flows/filter" in filter_call.args[0]

        # Verify create call
        create_call = reporter._client.post.call_args_list[1]
        assert "/flows/" in create_call.args[0]

    async def test_finds_existing_flow(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)

        reporter._client.post = AsyncMock(
            return_value=_mock_response(200, [{"id": "existing-flow-456"}])
        )

        flow_id = await reporter.ensure_flow()

        assert flow_id == "existing-flow-456"
        reporter._client.post.assert_called_once()  # Only filter, no create

    async def test_returns_cached_flow_id(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._flow_id = "cached-flow-789"
        reporter._client = AsyncMock(spec=httpx.AsyncClient)

        flow_id = await reporter.ensure_flow()

        assert flow_id == "cached-flow-789"
        reporter._client.post.assert_not_called()


class TestCreateFlowRun:
    async def test_creates_flow_run(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(return_value=_mock_response(201, {"id": "run-abc"}))

        run_id = await reporter.create_flow_run(
            flow_id="flow-123",
            run_name="run-001",
            parameters={"cycle_id": "cyc_001"},
        )

        assert run_id == "run-abc"
        call_args = reporter._client.post.call_args
        assert "/flow_runs/" in call_args.args[0]
        body = call_args.kwargs["json"]
        assert body["flow_id"] == "flow-123"
        assert body["name"] == "run-001"


class TestCreateTaskRun:
    async def test_creates_task_run(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(return_value=_mock_response(201, {"id": "taskrun-xyz"}))

        task_run_id = await reporter.create_task_run(
            flow_run_id="run-abc",
            task_key="strategy.analyze_prd",
            task_name="strat: strategy.analyze_prd",
        )

        assert task_run_id == "taskrun-xyz"
        call_args = reporter._client.post.call_args
        assert "/task_runs/" in call_args.args[0]
        body = call_args.kwargs["json"]
        assert body["flow_run_id"] == "run-abc"
        assert body["task_key"] == "strategy.analyze_prd"


class TestSetStateMethods:
    async def test_set_flow_run_state(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(return_value=_mock_response(200, {"status": "ok"}))

        await reporter.set_flow_run_state("run-abc", "RUNNING", "Running")

        call_args = reporter._client.post.call_args
        assert "/flow_runs/run-abc/set_state" in call_args.args[0]
        body = call_args.kwargs["json"]
        assert body["state"]["type"] == "RUNNING"
        assert body["state"]["name"] == "Running"

    async def test_set_task_run_state(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(return_value=_mock_response(200, {"status": "ok"}))

        await reporter.set_task_run_state("taskrun-xyz", "COMPLETED", "Completed")

        call_args = reporter._client.post.call_args
        assert "/task_runs/taskrun-xyz/set_state" in call_args.args[0]
        body = call_args.kwargs["json"]
        assert body["state"]["type"] == "COMPLETED"


class TestGracefulDegradation:
    """Prefect down -> warning logged, no exception raised."""

    async def test_ensure_flow_handles_connection_error(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        # Should not raise
        flow_id = await reporter.ensure_flow()
        assert flow_id  # Returns a placeholder

    async def test_create_flow_run_handles_error(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        run_id = await reporter.create_flow_run("flow-1", "run-1")
        assert run_id  # Returns a placeholder

    async def test_create_task_run_handles_error(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        task_run_id = await reporter.create_task_run("run-1", "key", "name")
        assert task_run_id  # Returns a placeholder

    async def test_set_flow_run_state_handles_error(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        # Should not raise
        await reporter.set_flow_run_state("run-1", "RUNNING", "Running")

    async def test_set_task_run_state_handles_error(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        # Should not raise
        await reporter.set_task_run_state("taskrun-1", "FAILED", "Failed")

    async def test_http_500_does_not_raise(self):
        reporter = PrefectReporter(api_url=PREFECT_URL)
        reporter._client = AsyncMock(spec=httpx.AsyncClient)
        reporter._client.post = AsyncMock(
            return_value=_mock_response(500, {"detail": "Internal Server Error"})
        )

        # Should not raise — raise_for_status will throw but it's caught
        flow_id = await reporter.ensure_flow()
        assert flow_id  # Returns a placeholder

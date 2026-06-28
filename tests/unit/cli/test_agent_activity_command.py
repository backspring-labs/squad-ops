"""Unit tests for `squadops agent activity` (SIP-0089 §4.7).

What bugs would these catch?
- Wrong endpoint URL → the operator command silently hits the wrong service.
- A 404 (agent idle — no active activity) being surfaced as an ERROR / non-zero
  exit would make "is this agent busy?" scripts treat *idle* as *failure*. Unlike
  `agent state`, idle is a normal answer here, so 404 must report idle at exit 0.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app

pytestmark = [pytest.mark.domain_cli]

NOW_ISO = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC).isoformat()


def _activity_payload(**overrides) -> dict:
    base = {
        "runtime_activity_id": "act-1",
        "agent_id": "max",
        "mode": "cycle",
        "activity_type": "strategy.analyze_prd",
        "goal": "Analyze the PRD",
        "priority": 0,
        "state": "running",
        "source_kind": "cycle_task",
        "source_ref": "t1",
        "cycle_id": "cyc-1",
        "workload_id": None,
        "task_id": "t1",
        "can_pause": False,
        "can_resume": False,
        "can_abort": True,
        "started_at": NOW_ISO,
        "paused_at": None,
        "ended_at": None,
    }
    base.update(overrides)
    return base


def test_activity_command_calls_correct_endpoint():
    """Bug class: an endpoint typo would only fail at runtime for an operator."""
    runner = CliRunner()
    client = MagicMock()
    client.get.return_value = _activity_payload()
    with patch("squadops.cli.commands.agent._get_client", return_value=client):
        result = runner.invoke(app, ["agent", "activity", "max"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    client.get.assert_called_once_with("/health/agents/max/activity")


def test_activity_success_renders_activity():
    """Bug class: a working agent's activity must actually render (the value of the
    command). The running cycle task's type should appear."""
    runner = CliRunner()
    client = MagicMock()
    client.get.return_value = _activity_payload()
    with patch("squadops.cli.commands.agent._get_client", return_value=client):
        result = runner.invoke(app, ["agent", "activity", "max"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "strategy.analyze_prd" in result.stdout


def test_activity_404_reports_idle_at_zero_exit():
    """Bug class (the load-bearing one): idle (no active activity → 404) is a
    NORMAL answer, not an error. The command must exit 0 and say idle, NOT
    propagate a non-zero exit like `agent state` does."""
    runner = CliRunner()
    client = MagicMock()
    client.get.side_effect = CLIError("No active activity", exit_codes.NOT_FOUND)
    with patch("squadops.cli.commands.agent._get_client", return_value=client):
        result = runner.invoke(app, ["agent", "activity", "max"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    assert "idle" in result.stdout.lower()


def test_activity_404_json_reports_null_current_activity():
    """Bug class: scripted `--json` callers need a stable idle shape, not an error
    blob. Idle must serialize as current_activity: null at exit 0."""
    runner = CliRunner()
    client = MagicMock()
    client.get.side_effect = CLIError("No active activity", exit_codes.NOT_FOUND)
    with patch("squadops.cli.commands.agent._get_client", return_value=client):
        result = runner.invoke(app, ["--json", "agent", "activity", "max"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout.strip())
    assert parsed == {"agent_id": "max", "current_activity": None}


def test_activity_non_404_error_propagates_nonzero():
    """Bug class: a real failure (e.g. 500) must NOT be swallowed as idle — only
    404 maps to idle; other errors keep their non-zero exit."""
    runner = CliRunner()
    client = MagicMock()
    client.get.side_effect = CLIError("server boom", exit_codes.GENERAL_ERROR)
    with patch("squadops.cli.commands.agent._get_client", return_value=client):
        result = runner.invoke(app, ["agent", "activity", "max"], catch_exceptions=False)

    assert result.exit_code == exit_codes.GENERAL_ERROR

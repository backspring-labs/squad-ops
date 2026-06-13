"""Unit tests for `squadops agent state` (SIP-0089 §1.5).

What bugs would these catch?
- Wrong endpoint URL → operator command silently hits the wrong service.
- `--json` output silently including the derived `availability` field would
  violate D6 (display-only, never stored/transported).
- A 404 from the API path not propagating a non-zero exit code would break
  scripting workflows.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.commands.agent import _derived_availability
from squadops.cli.main import app

pytestmark = [pytest.mark.domain_cli]

NOW_ISO = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC).isoformat()


def _state_payload(**overrides) -> dict:
    base = {
        "agent_id": "max",
        "mode": "ambient",
        "runtime_status": "online",
        "focus": "",
        "current_runtime_activity_id": None,
        "interruptibility": "high",
        "last_heartbeat_at": NOW_ISO,
        "current_assignment_ref": None,
    }
    base.update(overrides)
    return base


def _patched_client(payload):
    mock_client = MagicMock()
    mock_client.get.return_value = payload
    return mock_client


@pytest.mark.parametrize(
    ("state_overrides", "expected_availability"),
    [
        ({}, "idle"),
        ({"current_runtime_activity_id": "act-1"}, "busy"),
        ({"interruptibility": "none"}, "paused"),
        # busy wins over interruptibility=none because an active activity is
        # the strongest signal — sanity-check the precedence.
        (
            {"current_runtime_activity_id": "act-1", "interruptibility": "none"},
            "busy",
        ),
    ],
)
def test_derived_availability_precedence(state_overrides, expected_availability):
    """Bug class: a wrong precedence between `current_runtime_activity_id` and
    `interruptibility=none` would mislabel a working agent as paused (or vice
    versa) on every operator dashboard."""
    assert _derived_availability(_state_payload(**state_overrides)) == expected_availability


def test_json_output_does_not_include_derived_availability():
    """Bug class (D6): `availability` is computed for display only. Leaking it
    into the `--json` payload would let downstream tooling persist it as if it
    were authoritative."""
    runner = CliRunner()
    payload = _state_payload()
    with patch("squadops.cli.commands.agent._get_client", return_value=_patched_client(payload)):
        # --json is the global flag handled by the top-level Typer callback;
        # it must precede the subcommand path.
        result = runner.invoke(app, ["--json", "agent", "state", "max"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    # Find the JSON body — print_json may add leading/trailing whitespace.
    text = result.stdout.strip()
    parsed = json.loads(text)
    assert "availability" not in parsed
    assert parsed["agent_id"] == "max"
    assert parsed["mode"] == "ambient"


def test_state_command_calls_correct_endpoint():
    """Bug class: an endpoint typo (e.g. `/agents/state/{id}` vs
    `/agents/{id}/runtime-state`) would compile, pass type checks, and only
    fail at runtime when an operator runs the command."""
    runner = CliRunner()
    mock_client = _patched_client(_state_payload())
    with patch("squadops.cli.commands.agent._get_client", return_value=mock_client):
        result = runner.invoke(app, ["agent", "state", "max"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    mock_client.get.assert_called_once_with("/health/agents/max/runtime-state")


def test_state_command_propagates_404_as_nonzero_exit():
    """Bug class: a CLI that silently exits 0 on 'agent not found' breaks every
    operator script that pipes `squadops agent state` into conditional logic.
    The API returns 404 when no runtime-state row exists — the CLI must surface
    that as a non-zero exit code."""
    from squadops.cli import exit_codes
    from squadops.cli.client import CLIError

    runner = CliRunner()
    mock_client = MagicMock()
    mock_client.get.side_effect = CLIError("Agent 'ghost' not found", exit_codes.NOT_FOUND)
    with patch("squadops.cli.commands.agent._get_client", return_value=mock_client):
        result = runner.invoke(app, ["agent", "state", "ghost"], catch_exceptions=False)

    assert result.exit_code == exit_codes.NOT_FOUND

"""Unit tests for `squadops assignment ...` (SIP-0089 §2.7).

What bugs would these catch?
- Wrong endpoint URL → the operator command silently hits the wrong service.
- `create` sending reserve buffers it shouldn't → the server would never apply
  the D7/§11.4 strictness defaults (a hard duty would persist with no buffer).
- A 404 from `show` not propagating a non-zero exit → breaks operator scripts.

Mirrors `test_agent_state_command.py`: CliRunner + a patched `_get_client`, so no
network and no TestClient (blocked locally per #217).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.main import app

pytestmark = [pytest.mark.domain_cli]

WIN_START = "2026-06-24T01:00:00+00:00"
WIN_END = "2026-06-24T06:00:00+00:00"


def _assignment_payload(**overrides) -> dict:
    base = {
        "assignment_id": "a-1",
        "agent_id": "max",
        "assignment_type": "duty",
        "assigned_role": "support",
        "priority": 10,
        "strictness": "hard",
        "active_window": {"start": WIN_START, "end": WIN_END, "timezone": "UTC"},
        "reserve_before_window_seconds": 900,
        "reserve_after_window_seconds": 0,
        "recall_policy": "graceful",
        "graceful_window_seconds": 0,
        "missed_window_policy": "skip",
        "allowed_off_window_modes": ["ambient", "cycle"],
        "active": True,
    }
    base.update(overrides)
    return base


def _client_returning(*, get=None, post=None) -> MagicMock:
    mock = MagicMock()
    if get is not None:
        mock.get.return_value = get
    if post is not None:
        mock.post.return_value = post
    return mock


def test_list_calls_correct_endpoint():
    """Bug class: an endpoint typo (`/api/v1/assignments/agents/...`) compiles and
    only fails when an operator runs it."""
    runner = CliRunner()
    mock_client = _client_returning(get=[_assignment_payload()])
    with patch("squadops.cli.commands.assignment._get_client", return_value=mock_client):
        result = runner.invoke(app, ["assignment", "list", "max"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    mock_client.get.assert_called_once_with("/api/v1/agents/max/assignments")


def test_list_json_emits_raw_payload():
    """Bug class: the `--json` path must pass the API payload through untouched so
    downstream tooling sees the canonical shape (incl. the nested active_window)."""
    runner = CliRunner()
    payload = [_assignment_payload()]
    mock_client = _client_returning(get=payload)
    with patch("squadops.cli.commands.assignment._get_client", return_value=mock_client):
        result = runner.invoke(app, ["--json", "assignment", "list", "max"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout.strip())
    assert parsed == payload
    assert parsed[0]["active_window"]["timezone"] == "UTC"


def test_show_calls_correct_endpoint():
    runner = CliRunner()
    mock_client = _client_returning(get=_assignment_payload())
    with patch("squadops.cli.commands.assignment._get_client", return_value=mock_client):
        result = runner.invoke(app, ["assignment", "show", "a-1"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    mock_client.get.assert_called_once_with("/api/v1/assignments/a-1")


def test_show_propagates_404_as_nonzero_exit():
    """Bug class: a CLI that exits 0 on 'not found' breaks every operator script
    that branches on `squadops assignment show`."""
    from squadops.cli import exit_codes
    from squadops.cli.client import CLIError

    runner = CliRunner()
    mock_client = MagicMock()
    mock_client.get.side_effect = CLIError("not found — ghost", exit_codes.NOT_FOUND)
    with patch("squadops.cli.commands.assignment._get_client", return_value=mock_client):
        result = runner.invoke(app, ["assignment", "show", "ghost"], catch_exceptions=False)

    assert result.exit_code == exit_codes.NOT_FOUND


def test_create_posts_minimal_body_without_reserve_overrides():
    """Bug class: if `create` always sent reserve_*_window_seconds, the server
    could never apply the §11.4 strictness defaults — a hard duty would persist
    with whatever the CLI defaulted to. The omitted keys are load-bearing."""
    runner = CliRunner()
    mock_client = _client_returning(post=_assignment_payload())
    with patch("squadops.cli.commands.assignment._get_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "assignment",
                "create",
                "max",
                "--role",
                "support",
                "--window-start",
                WIN_START,
                "--window-end",
                WIN_END,
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.stdout
    mock_client.post.assert_called_once()
    path, kwargs = mock_client.post.call_args[0], mock_client.post.call_args[1]
    assert path == ("/api/v1/assignments",)
    body = kwargs["json"]
    assert body["agent_id"] == "max"
    assert body["assigned_role"] == "support"
    assert body["window_start"] == WIN_START
    assert body["strictness"] == "hard"
    # Defaults must be left to the server — these keys must be absent.
    assert "reserve_before_window_seconds" not in body
    assert "reserve_after_window_seconds" not in body
    assert "assignment_id" not in body


def test_create_passes_explicit_reserve_override_through():
    """Bug class: when the operator *does* set a reserve buffer, it must reach the
    server verbatim (incl. an explicit 0, which must not be dropped as falsy)."""
    runner = CliRunner()
    mock_client = _client_returning(post=_assignment_payload())
    with patch("squadops.cli.commands.assignment._get_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "assignment",
                "create",
                "max",
                "--role",
                "support",
                "--window-start",
                WIN_START,
                "--window-end",
                WIN_END,
                "--reserve-before-seconds",
                "0",
                "--strictness",
                "soft",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.stdout
    body = mock_client.post.call_args[1]["json"]
    assert body["reserve_before_window_seconds"] == 0
    assert body["strictness"] == "soft"

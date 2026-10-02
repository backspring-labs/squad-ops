"""Campaign commands (SIP-0109 §13, #1799): what each command sends, and how a refusal ends."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app

runner = CliRunner()

_RESULT = {
    "campaign": {"campaign_id": "cmp_1", "state": "paused"},
    "entry": {"operation": "pause", "prior_state": "building", "next_state": "paused"},
    "replayed": False,
    "cancelled_cycles": [],
}


def _client(**returns):
    mock = MagicMock()
    for method, value in returns.items():
        getattr(mock, method).return_value = value
    return mock


@patch("squadops.cli.commands.campaigns._get_client")
def test_a_control_command_sends_its_reason_key_and_expected_state(get_client):
    """Bug caught: the key or the expected state dropped on the way, so a retry acts twice or
    a stale operation applies."""
    client = _client(post=_RESULT)
    get_client.return_value = client

    result = runner.invoke(
        app,
        [
            "campaigns",
            "pause",
            "cmp_1",
            "--reason",
            "watching",
            "--idempotency-key",
            "k-7",
            "--expected-state",
            "building",
        ],
    )

    assert result.exit_code == 0, result.output
    client.post.assert_called_once_with(
        "/api/v1/campaigns/cmp_1/pause",
        json={"reason": "watching", "idempotency_key": "k-7", "expected_state": "building"},
    )
    assert "building → paused" in result.output and "k-7" in result.output


@patch("squadops.cli.commands.campaigns._get_client")
def test_a_key_is_minted_and_printed_when_none_is_given(get_client):
    """A retry can resend what was printed. Bug caught: no key sent, or one the user never sees."""
    client = _client(post=_RESULT)
    get_client.return_value = client

    result = runner.invoke(app, ["campaigns", "abort", "cmp_1", "--reason", "stop"])

    key = client.post.call_args.kwargs["json"]["idempotency_key"]
    assert key.startswith("cli-") and key in result.output


@patch("squadops.cli.commands.campaigns._get_client")
def test_create_sends_the_files_spec_with_the_reason_and_key(get_client, tmp_path):
    client = _client(post={**_RESULT, "entry": {**_RESULT["entry"], "operation": "create"}})
    get_client.return_value = client
    spec = tmp_path / "campaign.yaml"
    spec.write_text(
        "project_id: group_run\nobjective: {statement: s, measurement: m}\npolicy: {max_cycles: 6}\n"
    )

    result = runner.invoke(
        app, ["campaigns", "create", "-f", str(spec), "--reason", "r", "--idempotency-key", "k"]
    )

    assert result.exit_code == 0, result.output
    assert client.post.call_args.kwargs["json"] == {
        "project_id": "group_run",
        "objective": {"statement": "s", "measurement": "m"},
        "policy": {"max_cycles": 6},
        "reason": "r",
        "idempotency_key": "k",
    }


@patch("squadops.cli.commands.campaigns._get_client")
def test_a_refusal_exits_with_the_conflict_code(get_client):
    client = MagicMock()
    client.post.side_effect = CLIError("refused: stale_state", exit_codes.CONFLICT)
    get_client.return_value = client

    result = runner.invoke(app, ["campaigns", "resume", "cmp_1", "--reason", "go"])

    assert result.exit_code == exit_codes.CONFLICT
    assert "stale_state" in result.output


_REFUSED_ROW = {
    "seq": 2,
    "committed_at": "t",
    "operation": "pause",
    "outcome": "refused",
    "refusal": "conflicting_idempotency_key",
    "prior_state": "building",
    "next_state": "building",
    "actor": "ripley",
    "actor_role": "campaign-supervisor",
    "reason": "r",
}


@patch("squadops.cli.commands.campaigns._get_client")
def test_the_log_shows_refusals_with_their_reason(get_client):
    """Bug caught: a refused row shown as a bare outcome, so the reader cannot tell a conflict
    from a stale state."""
    from squadops.cli.commands.campaigns import _log_rows

    get_client.return_value = _client(get=[_REFUSED_ROW])

    result = runner.invoke(app, ["--json", "campaigns", "log", "cmp_1"])

    assert json.loads(result.output)[0]["refusal"] == "conflicting_idempotency_key"
    assert _log_rows([_REFUSED_ROW])[0][3] == "refused (conflicting_idempotency_key)"


def test_create_with_an_unreadable_file_exits_without_calling_the_api(tmp_path):
    result = runner.invoke(
        app, ["campaigns", "create", "-f", str(tmp_path / "missing.yaml"), "--reason", "r"]
    )
    assert result.exit_code == 2
    assert "cannot read" in result.output

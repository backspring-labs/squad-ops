"""Campaign commands (SIP-0109 §13, #1799): what each command sends, and how a refusal ends."""

from __future__ import annotations

import hashlib
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
def test_start_names_the_cycle_it_launched(get_client):
    """Bug caught: a start that reports the campaign moved but not which cycle it launched —
    the one thing the owner next watches."""
    client = _client(
        post={
            **_RESULT,
            "campaign": {"campaign_id": "cmp_1", "state": "calibrating"},
            "entry": {"operation": "start", "prior_state": "draft", "next_state": "calibrating"},
            "launched_cycles": ["cyc_cal000000001"],
        }
    )
    get_client.return_value = client

    result = runner.invoke(
        app, ["campaigns", "start", "cmp_1", "--reason", "go", "--idempotency-key", "k-1"]
    )

    assert result.exit_code == 0, result.output
    client.post.assert_called_once_with(
        "/api/v1/campaigns/cmp_1/start", json={"reason": "go", "idempotency_key": "k-1"}
    )
    assert "launched cycles: cyc_cal000000001" in result.output


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
    spec.write_bytes(
        b"project_id: group_run\nobjective: {statement: s, measurement: m}\npolicy: {max_cycles: 6}\n"
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
        # #1954: the bytes the campaign was made from, so its creation row names this file.
        "definition": {
            "path": str(spec),
            "sha256": hashlib.sha256(spec.read_bytes()).hexdigest(),
        },
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


@patch("squadops.cli.commands.campaigns._get_client")
def test_classify_sends_the_version_and_its_classification(get_client):
    """Bug caught: the version dropped on the way, so a classification lands on the proposal
    rather than the version that went wrong (§9.4 keeps one record per version)."""
    client = _client(post=_RESULT)
    get_client.return_value = client

    result = runner.invoke(
        app,
        [
            "campaigns",
            "classify",
            "cmp_1",
            "--proposal",
            "prop_cap",
            "--version",
            "2",
            "--as",
            "scope_too_large",
            "--reason",
            "three views",
            "--idempotency-key",
            "k-9",
        ],
    )

    assert result.exit_code == 0, result.output
    client.post.assert_called_once_with(
        "/api/v1/campaigns/cmp_1/classifications",
        json={
            "proposal_id": "prop_cap",
            "version": 2,
            "classification": "scope_too_large",
            "reason": "three views",
            "idempotency_key": "k-9",
        },
    )


@patch("squadops.cli.commands.campaigns._get_client")
def test_resume_names_the_owners_action_only_when_given(get_client):
    """#1866: an escalated campaign resumes only on a named action, so a CLI that cannot send
    one leaves the owner no way to move it. Bugs caught: the action dropped on the way; or an
    action sent for a plain resume, which the API would refuse against the held one."""
    client = _client(post={**_RESULT, "entry": {**_RESULT["entry"], "operation": "resume"}})
    get_client.return_value = client
    base = ["campaigns", "resume", "cmp_1", "--reason", "rule", "--idempotency-key", "k-9"]

    named = runner.invoke(app, [*base, "--action", "abandon_and_propose"])
    plain = runner.invoke(app, base)

    assert (named.exit_code, plain.exit_code) == (0, 0), named.output + plain.output
    sent = [c.kwargs["json"] for c in client.post.call_args_list]
    assert sent == [
        {"reason": "rule", "idempotency_key": "k-9", "action": "abandon_and_propose"},
        {"reason": "rule", "idempotency_key": "k-9"},
    ]


@patch("squadops.cli.commands.campaigns._get_client")
def test_the_lease_commands_send_the_hold_and_its_return_to_their_routes(get_client):
    """SIP-0109 §9.3 (#1802). Bugs caught: the hold's length dropped (the API would refuse a
    lease with no expiry, so the supervisor could not take the box from the CLI), or a release
    sent to the acquire route, which would renew the lease instead of returning it."""
    lease = {
        "holder": "supervisor",
        "held_by": "crew",
        "campaign_id": "cmp_1",
        "acquired_at": "2026-10-03T14:00:00Z",
        "expires_at": "2026-10-03T14:15:00Z",
        "supervisor_holds": True,
    }
    client = _client(post={"entry": _RESULT["entry"], "replayed": False, "lease": lease})
    get_client.return_value = client

    took = runner.invoke(
        app,
        [
            "campaigns",
            "lease",
            "acquire",
            "cmp_1",
            "--expires-in",
            "900",
            "--reason",
            "gate",
            "--idempotency-key",
            "k-1",
        ],
    )
    gave = runner.invoke(
        app,
        ["campaigns", "lease", "release", "cmp_1", "--reason", "done", "--idempotency-key", "k-2"],
    )

    assert (took.exit_code, gave.exit_code) == (0, 0), took.output + gave.output
    assert [(c.args[0], c.kwargs["json"]) for c in client.post.call_args_list] == [
        (
            "/api/v1/campaigns/cmp_1/lease",
            {"reason": "gate", "idempotency_key": "k-1", "expires_in_s": 900},
        ),
        ("/api/v1/campaigns/cmp_1/lease/release", {"reason": "done", "idempotency_key": "k-2"}),
    ]
    assert "holds the box" in took.output


@patch("squadops.cli.commands.campaigns._get_client")
def test_show_names_the_definition_its_creation_row_records(get_client):
    """#1954. Bug caught: the record kept but never shown, so the operator still reconciles."""
    client = MagicMock()
    client.get.side_effect = [
        {"campaign_id": "cmp_1", "state": "draft", "objective": {}, "policy": {}},
        [
            {
                "operation": "create",
                "binding": {"definition": {"path": "s.yaml", "sha256": "f" * 64}},
            }
        ],
    ]
    get_client.return_value = client

    result = runner.invoke(app, ["--format", "json", "campaigns", "show", "cmp_1"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["definition"] == {"path": "s.yaml", "sha256": "f" * 64}


@patch("squadops.cli.commands.campaigns._get_client")
def test_answer_sends_the_answer_to_the_escalations_own_route(get_client):
    """SIP-0109 §24bl. Bug caught: the answer posted to the campaign rather than to the
    escalation it answers, or the escalation id dropped, so a later gate cannot match it."""
    client = _client(post=_RESULT)
    get_client.return_value = client

    result = runner.invoke(
        app,
        [
            "campaigns",
            "answer",
            "cmp_1",
            "esc_0123456789ab",
            "--answer",
            "insertion order",
            "--reason",
            "late",
        ],
    )

    assert result.exit_code == 0, result.output
    client.post.assert_called_once_with(
        "/api/v1/campaigns/cmp_1/escalations/esc_0123456789ab/answer",
        json={"answer": "insertion order", "reason": "late"},
    )


@patch("squadops.cli.commands.campaigns._get_client")
def test_escalations_lists_each_ones_state_failed_conditions_and_late_answer(get_client):
    listed = [
        {
            "escalation_id": "esc_0123456789ab",
            "state": "expired",
            "run_id": "run_f",
            "failed": [{"condition": "no_open_question", "reading": "1 open: which order?"}],
            "questions": ["which order?"],
            "answer": None,
        }
    ]
    get_client.return_value = _client(get=listed)

    with patch("squadops.cli.commands.campaigns.print_table") as table:
        result = runner.invoke(app, ["campaigns", "escalations", "cmp_1"])

    assert result.exit_code == 0, result.output
    headers, rows = table.call_args.args
    assert headers == ["Escalation", "State", "Run", "Failed", "Questions", "Late answer"]
    assert rows == [
        ["esc_0123456789ab", "expired", "run_f", "no_open_question", "which order?", "—"]
    ]

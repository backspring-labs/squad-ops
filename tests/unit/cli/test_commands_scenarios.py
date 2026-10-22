"""``squadops scenarios`` (SIP-0113 §4.1; the 2.4 plan's D2): the supervisor's draft and the owner's
review and approval, from the CLI to the routes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.main import app

pytestmark = [pytest.mark.domain_cli]

runner = CliRunner()

_SUITE = """\
name: group_run window suite
scenarios:
  - scenario_id: capacity
    goal: a full run turns a second runner away
    surfaces: [{kind: http_endpoint, method: POST, path: "/runs/{run_id}/join"}]
    steps: [{action: http, method: POST, path: /runs}]
    checks: [{check: status, step: 1, equals: 201}]
"""
_SUMMARY = {
    "digest": "d" * 64,
    "name": "group_run window suite",
    "state": "draft",
    "drafted_by": "supervisor",
    "scenarios": [
        {
            "scenario_id": "capacity",
            "version": "v" * 64,
            "goal": "a full run turns a second runner away",
            "surfaces": [
                {"kind": "http_endpoint", "method": "POST", "path": "/runs/{run_id}/join"}
            ],
        }
    ],
}


@patch("squadops.cli.commands.scenarios._get_client")
def test_a_draft_sends_its_file_and_names_the_digest(mock_get_client, tmp_path):
    """Bug caught: the file read and not sent, or sent without its steps, so the store holds a
    suite whose digest names other content."""
    suite = tmp_path / "suite.yaml"
    suite.write_text(_SUITE)
    client = MagicMock()
    client.post.return_value = _SUMMARY
    mock_get_client.return_value = client

    result = runner.invoke(app, ["scenarios", "draft", "--file", str(suite)])

    assert result.exit_code == 0, result.output
    assert client.post.call_args.args[0] == "/api/v1/scenario-suites"
    body = client.post.call_args.kwargs["json"]
    assert body["scenarios"][0]["steps"] == [{"action": "http", "method": "POST", "path": "/runs"}]
    assert "d" * 64 in "".join(result.output.split())  # #2491: Rich folds a long digest too


@patch("squadops.cli.commands.scenarios._get_client")
def test_a_suite_file_inside_a_git_working_tree_is_refused_and_nothing_is_sent(
    mock_get_client, tmp_path
):
    """Held out: a suite file never lives in a repository. Bug caught: a draft read from inside
    a checkout, where it can be committed into what the squad's images and prompts are built
    from."""
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    suite = tmp_path / "repo" / "suites" / "window.yaml"
    suite.parent.mkdir()
    suite.write_text(_SUITE)

    result = runner.invoke(app, ["scenarios", "draft", "--file", str(suite)])

    assert result.exit_code == 2
    # #2491: Rich wraps at the console width, which a long temporary path can put inside the phrase.
    assert "inside the Git working tree" in " ".join(result.output.split())
    mock_get_client.assert_not_called()


@patch("squadops.cli.commands.scenarios._get_client")
def test_the_owner_reviews_the_steps_and_approves_that_digest(mock_get_client):
    """D2: the owner reads what they approve. Bug caught: the review printing the summary, with
    no steps to read, or the approval sent to another suite's digest."""
    client = MagicMock()
    client.get.return_value = {
        "digest": "d" * 64,
        "state": "draft",
        "content": {
            "name": "s",
            "scenarios": [{"scenario_id": "capacity", "steps": ["held-out-step"]}],
        },
    }
    client.post.return_value = {**_SUMMARY, "state": "approved", "approved_by": "owner"}
    mock_get_client.return_value = client

    reviewed = runner.invoke(app, ["scenarios", "review", "d" * 64])
    approved = runner.invoke(app, ["scenarios", "approve", "d" * 64])

    assert reviewed.exit_code == approved.exit_code == 0
    assert client.get.call_args.args[0] == f"/api/v1/scenario-suites/{'d' * 64}/content"
    assert "held-out-step" in reviewed.output
    assert client.post.call_args.args[0] == f"/api/v1/scenario-suites/{'d' * 64}/approval"
    assert "approved group_run window suite" in " ".join(approved.output.split())


@pytest.mark.parametrize(
    "text", ["- just\n- a list\n", "name: [unclosed\n"], ids=["a-list", "bad-yaml"]
)
@patch("squadops.cli.commands.scenarios._get_client")
def test_a_malformed_suite_file_is_refused_before_anything_is_sent(mock_get_client, tmp_path, text):
    """Bug caught: a malformed file sent anyway, and the API's refusal read as the store's."""
    suite = tmp_path / "suite.yaml"
    suite.write_text(text)

    result = runner.invoke(app, ["scenarios", "draft", "--file", str(suite)])

    assert result.exit_code == 2
    mock_get_client.assert_not_called()


_EVIDENCE = [
    {
        "scenario_id": "join-from-the-page",
        "step": 3,
        "png_b64": "iVBORw0KGgo=",
        "role": "button",
        "nodes": [{"name": "Join", "visible": True, "disabled": True}],
        "errors": ["driver: Node is detached"],
        "failed_requests": [],
        "withheld": [],
        "sha256": "e" * 64,
        "size": 120,
    }
]


@pytest.mark.parametrize("inside", ["a-folder-in-a-checkout", "a-checkout-itself"])
@patch("squadops.cli.commands.scenarios._get_client")
def test_evidence_is_never_written_inside_a_git_working_tree(mock_get_client, tmp_path, inside):
    """SIP-0113 §10p ruling 8. Bug caught: a screenshot of a held-out step written into a
    checkout's ``var/``, which reaches the line's public Release with its records; or an ``--out``
    that is a checkout's own root let through, because only its parents were read."""
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    out = (
        tmp_path / "repo" / "var" / "evidence"
        if inside == "a-folder-in-a-checkout"
        else tmp_path / "repo"
    )

    result = runner.invoke(app, ["scenarios", "evidence", "evl_x", "--out", str(out)])

    assert result.exit_code == 2
    assert "inside the Git working tree" in " ".join(result.output.split())
    mock_get_client.assert_not_called()


@patch("squadops.cli.commands.scenarios._get_client")
def test_evidence_is_written_per_scenario_outside_every_repository(mock_get_client, tmp_path):
    """Bug caught: the screenshot written as its base64 text, or the details lost beside it."""
    client = MagicMock()
    client.get.return_value = _EVIDENCE
    mock_get_client.return_value = client
    out = tmp_path / "evidence"

    result = runner.invoke(app, ["scenarios", "evidence", "evl_x", "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert client.get.call_args.args[0] == "/api/v1/scenario-evaluations/evl_x/evidence"
    shot = out / "join-from-the-page" / "step-3.png"
    assert shot.read_bytes().startswith(b"\x89PNG")
    details = (out / "join-from-the-page" / "step-3.json").read_text()
    assert '"errors"' in details and "png_b64" not in details

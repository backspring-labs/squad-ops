"""``squadops lessons`` (SIP-0110 §0.6–§0.7, slice 3d): the owner's approval and revocation, and the
auditor's draft, from the CLI to the routes.

What bugs would these catch? An approval file read and not sent (the API refuses an approval with
no combined check, and the owner would see a refusal for a check they wrote); a revocation that
does not tell the owner which running units still hold the lesson; a malformed file sent anyway.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.main import app

pytestmark = [pytest.mark.domain_cli]

runner = CliRunner()

_APPROVAL = """\
ruling: "the owner, 2026-10-09: approve it"
replay_check: {reference: replay/arm-a-vs-b, result: "absent 5/6 vs 1/6"}
combined_check: {revision_ids: ["pat_a@1"], verdict: no_conflict, reference: auditor/combined}
"""


@patch("squadops.cli.commands.lessons._get_client")
def test_an_approval_sends_its_file_to_the_revisions_approvals(mock_get_client, tmp_path):
    approval = tmp_path / "approval.yaml"
    approval.write_text(_APPROVAL)
    client = MagicMock()
    client.post.return_value = {"approval_id": "apr_1"}
    mock_get_client.return_value = client

    result = runner.invoke(
        app, ["lessons", "approve", "group_run", "pat_b@1", "--file", str(approval)]
    )

    assert result.exit_code == 0, result.output
    path = client.post.call_args.args[0]
    body = client.post.call_args.kwargs["json"]
    assert path == "/api/v1/projects/group_run/lessons/pat_b@1/approvals"
    assert body["combined_check"] == {
        "revision_ids": ["pat_a@1"],
        "verdict": "no_conflict",
        "reference": "auditor/combined",
    }
    assert "apr_1" in result.output


@patch("squadops.cli.commands.lessons._get_client")
def test_a_revocation_names_the_running_units_that_still_hold_the_lesson(mock_get_client):
    client = MagicMock()
    client.post.return_value = {
        "approval": {},
        "units_holding_it": [{"unit_kind": "campaign", "unit_id": "cmp_running"}],
        "next": "halt or restart its work under a new snapshot",
    }
    mock_get_client.return_value = client

    result = runner.invoke(app, ["lessons", "revoke", "group_run", "apr_1", "--reason", "harmful"])

    assert result.exit_code == 0, result.output
    assert client.post.call_args.kwargs["json"] == {"reason": "harmful"}
    assert "still held by campaign cmp_running" in result.output


@pytest.mark.parametrize("content", ["- a list\n", "not: [valid"])
@patch("squadops.cli.commands.lessons._get_client")
def test_a_draft_file_that_is_not_a_mapping_sends_nothing(mock_get_client, tmp_path, content):
    draft = tmp_path / "draft.yaml"
    draft.write_text(content)

    result = runner.invoke(app, ["lessons", "draft", "group_run", "--file", str(draft)])

    assert result.exit_code == 2
    mock_get_client.return_value.post.assert_not_called()


_ANNOTATION = """\
values: [criteria_not_checkable]
target_behavior: criterion_already_satisfied
evidence: {ruling: "T3 holds because the app has no capacity concept"}
context: {deploy: "rebuild 20", prompt: "the proposal block"}
annotator: claude-opus-5-5
"""


@patch("squadops.cli.commands.lessons._get_client")
def test_an_annotation_is_sent_to_its_observation_and_reviewed_by_its_id(mock_get_client, tmp_path):
    """#2160. Bugs caught: an annotation file read and not sent whole (the route refuses one with
    no context, and the auditor sees a refusal for context it wrote); a review posted to the wrong
    annotation."""
    annotation = tmp_path / "annotation.yaml"
    annotation.write_text(_ANNOTATION)
    client = MagicMock()
    client.post.side_effect = [
        {"annotation_id": "ann_1", "source_id": "proposal_ruling:cmp_5:ctl_d"},
        {
            "annotation_id": "ann_1",
            "source_id": "proposal_ruling:cmp_5:ctl_d",
            "classification": {"values": ["criteria_not_checkable"]},
        },
    ]
    mock_get_client.return_value = client

    proposed = runner.invoke(
        app,
        [
            "lessons",
            "annotate",
            "group_run",
            "proposal_ruling:cmp_5:ctl_d",
            "--file",
            str(annotation),
        ],
    )
    reviewed = runner.invoke(
        app, ["lessons", "review-annotation", "group_run", "ann_1", "--note", "read the ruling"]
    )

    assert proposed.exit_code == 0 and reviewed.exit_code == 0, proposed.output + reviewed.output
    (annotate_call, review_call) = client.post.call_args_list
    assert annotate_call.args[0] == (
        "/api/v1/projects/group_run/observations/proposal_ruling:cmp_5:ctl_d/annotations"
    )
    assert annotate_call.kwargs["json"]["context"] == {
        "deploy": "rebuild 20",
        "prompt": "the proposal block",
    }
    assert review_call.args[0] == "/api/v1/projects/group_run/annotations/ann_1/review"
    assert review_call.kwargs["json"] == {"note": "read the ruling"}
    assert "awaiting the owner's review" in proposed.output


def test_an_annotation_file_that_is_not_a_mapping_is_refused_before_any_call(tmp_path):
    bad = tmp_path / "annotation.yaml"
    bad.write_text("- just a list\n")

    result = runner.invoke(
        app, ["lessons", "annotate", "group_run", "proposal_ruling:cmp_5:ctl_d", "--file", str(bad)]
    )

    assert result.exit_code == 2

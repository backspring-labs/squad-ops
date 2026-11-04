"""``squadops goals show|edit|history`` (SIP-0115 §8.2, #2884)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app
from squadops.projects.goal_set import parse_goal_set
from tests.fixtures.goal_set import goal_set_document

pytestmark = [pytest.mark.domain_cli]

runner = CliRunner()
CLIENT = "squadops.cli.commands.goals._get_client"


def _revision(revision: int, **extra) -> dict:
    return {
        "project_id": "prj-lantern",
        "revision": revision,
        "author": "owner",
        "reason": "the owner added the weekly total",
        "source_ref": None,
        "created_at": "2026-11-03T12:00:00Z",
        "goal_set": parse_goal_set(goal_set_document()).to_document(),
    } | extra


class TestEdit:
    """Bugs caught: a write sent against no revision, so the server can't refuse a concurrent
    edit; the file's goal set altered or wrapped on its way into the body."""

    @pytest.mark.parametrize(
        ("active", "expected_revision"),
        [
            (_revision(3), 3),
            # no goal set yet: the first write is against revision 0
            (CLIError("Error: not found — no goal set", exit_codes.NOT_FOUND), 0),
        ],
    )
    def test_the_active_revision_is_read_and_sent_as_the_expected_one(
        self, active, expected_revision, tmp_path
    ):
        spec = tmp_path / "goals.yaml"
        spec.write_text(yaml.safe_dump(goal_set_document()))
        client = MagicMock()
        if isinstance(active, Exception):
            client.get.side_effect = active
        else:
            client.get.return_value = active
        client.post.return_value = {
            "revision": _revision(expected_revision + 1),
            "idempotency_key": "g-1",
            "replayed": False,
        }

        with patch(CLIENT, return_value=client):
            result = runner.invoke(
                app,
                [
                    "goals",
                    "edit",
                    "prj-lantern",
                    "-f",
                    str(spec),
                    "--reason",
                    "the owner added the weekly total",
                    "--source-ref",
                    "https://chat.example.invalid/thread/42",
                    "--idempotency-key",
                    "g-1",
                ],
            )

        assert result.exit_code == 0, result.output
        assert client.post.call_args.args[0] == "/api/v1/projects/prj-lantern/goal-set/revisions"
        assert client.post.call_args.kwargs["json"] == {
            "idempotency_key": "g-1",
            "expected_revision": expected_revision,
            "reason": "the owner added the weekly total",
            "source_ref": "https://chat.example.invalid/thread/42",
            "goal_set": goal_set_document(),
        }
        assert f"revision {expected_revision + 1} (2 backlog item(s)" in " ".join(
            result.output.split()
        )

    def test_a_given_expected_revision_is_sent_without_reading_the_active_one(self, tmp_path):
        spec = tmp_path / "goals.json"
        spec.write_text(json.dumps(goal_set_document()))
        client = MagicMock()
        client.post.side_effect = CLIError("Error: conflict — at revision 5", exit_codes.CONFLICT)

        with patch(CLIENT, return_value=client):
            result = runner.invoke(
                app,
                ["goals", "edit", "prj-lantern", "-f", str(spec), "--reason", "reorder"]
                + ["--expected-revision", "4"],
            )

        client.get.assert_not_called()
        assert client.post.call_args.kwargs["json"]["expected_revision"] == 4
        # a refused write names the key, so a retry can replay it
        assert result.exit_code == exit_codes.CONFLICT
        assert "idempotency key cli-" in " ".join(result.output.split())

    @pytest.mark.parametrize("content", [None, "- just\n- a list\n", "goal: [unclosed\n"])
    def test_a_file_that_holds_no_goal_set_exits_before_any_call(self, content, tmp_path):
        spec = tmp_path / "goals.yaml"
        if content is not None:
            spec.write_text(content)

        with patch(CLIENT) as get_client:
            result = runner.invoke(
                app, ["goals", "edit", "prj-lantern", "-f", str(spec), "--reason", "r"]
            )

        assert result.exit_code == 2
        get_client.assert_not_called()


class TestShow:
    def test_what_show_prints_is_a_file_edit_takes_back(self):
        """Bug caught: the revision's author and reason printed as YAML keys, or as text that
        isn't YAML, so `goals show > f; goals edit -f f` is refused or writes them into the
        goal set."""
        client = MagicMock()
        client.get.return_value = _revision(2, source_ref="https://chat.example.invalid/t/7")

        with patch(CLIENT, return_value=client):
            result = runner.invoke(app, ["goals", "show", "prj-lantern"])

        assert result.exit_code == 0, result.output
        assert client.get.call_args.args[0] == "/api/v1/projects/prj-lantern/goal-set"
        assert "revision 2, by owner" in result.output
        assert parse_goal_set(yaml.safe_load(result.output)) == parse_goal_set(goal_set_document())

    def test_json_prints_the_revision_as_answered_and_a_revision_is_read_by_number(self):
        client = MagicMock()
        client.get.return_value = _revision(1)

        with patch(CLIENT, return_value=client):
            result = runner.invoke(
                app, ["--json", "goals", "show", "prj-lantern", "--revision", "1"]
            )

        assert client.get.call_args.args[0] == "/api/v1/projects/prj-lantern/goal-set/revisions/1"
        assert json.loads(result.output) == _revision(1)

    def test_no_goal_set_exits_not_found(self):
        client = MagicMock()
        client.get.side_effect = CLIError("Error: not found — no goal set", exit_codes.NOT_FOUND)

        with patch(CLIENT, return_value=client):
            result = runner.invoke(app, ["goals", "show", "prj-lantern"])

        assert result.exit_code == exit_codes.NOT_FOUND


class TestHistory:
    def test_each_revision_is_a_row_newest_first(self):
        client = MagicMock()
        client.get.return_value = [_revision(2, reason="reorder"), _revision(1, reason="first")]

        with patch(CLIENT, return_value=client):
            result = runner.invoke(app, ["--quiet", "goals", "history", "prj-lantern"])

        assert result.exit_code == 0, result.output
        rows = [line.split("\t") for line in result.output.strip().splitlines()]
        assert [(r[0], r[3], r[5]) for r in rows] == [("2", "reorder", "2"), ("1", "first", "2")]

    def test_no_revisions_says_so_rather_than_printing_an_empty_table(self):
        client = MagicMock()
        client.get.return_value = []

        with patch(CLIENT, return_value=client):
            result = runner.invoke(app, ["goals", "history", "prj-lantern"])

        assert result.exit_code == 0
        assert "prj-lantern has no goal set yet" in result.output

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

    def test_the_files_goal_set_is_sent_against_the_revision_it_names(self, tmp_path):
        spec = tmp_path / "goals.yaml"
        spec.write_text("# base-revision: 3\n" + yaml.safe_dump(goal_set_document()))
        client = MagicMock()
        client.post.return_value = {
            "revision": _revision(4),
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
            "expected_revision": 3,
            "reason": "the owner added the weekly total",
            "source_ref": "https://chat.example.invalid/thread/42",
            "goal_set": goal_set_document(),
        }
        assert "revision 4 (2 backlog item(s)" in " ".join(result.output.split())

    @pytest.mark.parametrize(
        ("header", "flag", "why"),
        [
            ("", None, "names no revision it replaces"),
            ("# base-revision: 2\n", "3", "was shown at revision 2"),
        ],
        ids=["a hand-written file with no revision", "the file and the flag disagree"],
    )
    def test_an_edit_that_doesnt_say_which_revision_it_replaces_is_refused_before_any_call(
        self, header, flag, why, tmp_path
    ):
        """Bug caught: the active revision read and used instead, so a stale file is written
        over whatever another editor wrote since (the second review of PR #2899, P1)."""
        spec = tmp_path / "goals.yaml"
        spec.write_text(header + yaml.safe_dump(goal_set_document()))
        args = ["goals", "edit", "prj-lantern", "-f", str(spec), "--reason", "r"]

        with patch(CLIENT) as get_client:
            result = runner.invoke(app, args + (["--expected-revision", flag] if flag else []))

        assert result.exit_code == 2
        assert why in " ".join(result.output.split())
        get_client.assert_not_called()

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
        # a refused write names the key and the revision, so a retry can resend the same request
        assert result.exit_code == exit_codes.CONFLICT
        assert "expected revision 4" in " ".join(result.output.split())
        assert "idempotency key cli-" in " ".join(result.output.split())

    def test_a_hand_written_time_reaches_the_server_in_its_iso_form(self, tmp_path):
        """Bug caught: YAML reads an unquoted ``found_at`` as a datetime, and the request can't
        encode it, so a hand-written candidate fails before it is sent."""
        spec = tmp_path / "goals.yaml"
        spec.write_text(
            "goal: A reader keeps a log\n"
            "candidates:\n"
            "  - {id: C-1, title: Edit a session, found_by: owner, "
            "found_at: 2026-11-02T09:30:00+00:00}\n"
        )
        client = MagicMock()
        client.post.return_value = {
            "revision": _revision(1),
            "idempotency_key": "g-1",
            "replayed": False,
        }

        with patch(CLIENT, return_value=client):
            result = runner.invoke(
                app,
                ["goals", "edit", "prj-lantern", "-f", str(spec), "--reason", "first"]
                + ["--expected-revision", "0"],
            )

        assert result.exit_code == 0, result.output
        sent = client.post.call_args.kwargs["json"]
        json.dumps(sent)  # what httpx does with it
        assert sent["goal_set"]["candidates"][0]["found_at"] == "2026-11-02T09:30:00+00:00"

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
        assert "# base-revision: 2" in result.output
        assert "# written by: owner" in result.output
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


class TestCandidates:
    def test_each_candidate_is_a_row_from_the_active_revision(self):
        """Bug caught: candidates read from the history's first revision rather than the active
        one, or the evidence dropped from the row."""
        client = MagicMock()
        client.get.return_value = _revision(3)

        with patch(CLIENT, return_value=client):
            result = runner.invoke(app, ["--quiet", "goals", "candidates", "prj-lantern"])

        assert result.exit_code == 0, result.output
        assert client.get.call_args.args[0] == "/api/v1/projects/prj-lantern/goal-set"
        rows = [line.split("\t") for line in result.output.strip().splitlines()]
        assert rows == [
            ["C-1", "Edit a session", "cyc_0a1b2c", "2026-11-02T09:30:00+00:00", "vault://cyc_0a1b2c/qa_report.md"]
        ]  # fmt: skip

    def test_no_candidates_says_so_and_json_prints_the_list(self):
        empty = _revision(2)
        empty["goal_set"]["candidates"] = []
        client = MagicMock()
        client.get.return_value = empty

        with patch(CLIENT, return_value=client):
            table = runner.invoke(app, ["goals", "candidates", "prj-lantern"])
            as_json = runner.invoke(app, ["--json", "goals", "candidates", "prj-lantern"])

        assert "prj-lantern has no candidates at revision 2" in table.output
        assert json.loads(as_json.output) == []


def _recorded(revision: int, **goal_set_changes) -> dict:
    written = _revision(revision)
    written["goal_set"].update(goal_set_changes)
    return {"revision": written, "idempotency_key": "g-3", "replayed": False}


class TestActions:
    """``promote``, ``drop`` and ``split`` (SIP-0115 §8.2, slice 3). Bugs caught: an action sent
    against no revision (the server can't refuse a concurrent edit) or against one read when a
    flag already named it; the Campaign, position or parts not reaching the body."""

    def test_a_promotion_is_sent_against_the_active_revision_read_first(self):
        client = MagicMock()
        client.get.return_value = _revision(3)
        client.post.return_value = _recorded(4)

        with patch(CLIENT, return_value=client):
            result = runner.invoke(
                app,
                [
                    "goals", "promote", "prj-lantern", "C-1",
                    "--serves", "ER-week", "--serves", "ER-log", "--position", "2",
                    "--campaign", "cmp_owner", "--reason", "it blocks the weekly total",
                    "--source-ref", "https://chat.example.invalid/t/7", "--idempotency-key", "g-3",
                ],
            )  # fmt: skip

        assert result.exit_code == 0, result.output
        assert client.get.call_args.args[0] == "/api/v1/projects/prj-lantern/goal-set"
        assert client.post.call_args.args[0] == (
            "/api/v1/projects/prj-lantern/goal-set/candidates/C-1/promote"
        )
        assert client.post.call_args.kwargs["json"] == {
            "idempotency_key": "g-3",
            "expected_revision": 3,
            "reason": "it blocks the weekly total",
            "source_ref": "https://chat.example.invalid/t/7",
            "serves": ["ER-week", "ER-log"],
            "position": 2,
            "campaign_id": "cmp_owner",
        }
        assert "written: prj-lantern goal set revision 4, promoted C-1" in " ".join(
            result.output.split()
        )

    def test_a_drop_with_a_given_revision_reads_nothing_and_a_refusal_names_key_and_revision(
        self,
    ):
        """P2's lesson for the actions: a retry resends the printed key and revision, so the
        server replays rather than reads a moved revision and refuses a key conflict."""
        client = MagicMock()
        client.post.side_effect = CLIError(
            "Error: forbidden — NOT_DELEGATED", exit_codes.AUTH_ERROR
        )

        with patch(CLIENT, return_value=client):
            result = runner.invoke(
                app,
                ["goals", "drop", "prj-lantern", "C-1", "--reason", "a duplicate of B-2"]
                + ["--expected-revision", "5", "--idempotency-key", "g-9"],
            )

        client.get.assert_not_called()
        assert client.post.call_args.args[0] == (
            "/api/v1/projects/prj-lantern/goal-set/candidates/C-1/drop"
        )
        assert client.post.call_args.kwargs["json"] == {
            "idempotency_key": "g-9",
            "expected_revision": 5,
            "reason": "a duplicate of B-2",
        }
        assert result.exit_code == exit_codes.AUTH_ERROR
        assert "idempotency key g-9, expected revision 5" in " ".join(result.output.split())

    @pytest.mark.parametrize(
        "content",
        [
            "- {id: B-1a, title: the book}\n- {id: B-1b, title: the minutes, serves: [ER-week]}\n",
            "into:\n  - {id: B-1a, title: the book}\n  - {id: B-1b, title: the minutes, serves: [ER-week]}\n",
        ],
        ids=["a list", "a mapping with into"],
    )
    def test_a_split_sends_the_files_parts_in_order(self, content, tmp_path):
        spec = tmp_path / "split.yaml"
        spec.write_text(content)
        client = MagicMock()
        client.get.return_value = _revision(2)
        client.post.return_value = _recorded(3)

        with patch(CLIENT, return_value=client):
            result = runner.invoke(
                app,
                ["goals", "split", "prj-lantern", "B-1", "--into", str(spec)]
                + ["--reason", "too large for one increment", "--campaign", "cmp_owner"],
            )

        assert result.exit_code == 0, result.output
        assert client.post.call_args.args[0] == (
            "/api/v1/projects/prj-lantern/goal-set/backlog/B-1/split"
        )
        sent = client.post.call_args.kwargs["json"]
        assert sent["expected_revision"] == 2
        assert sent["into"] == [
            {"id": "B-1a", "title": "the book"},
            {"id": "B-1b", "title": "the minutes", "serves": ["ER-week"]},
        ]
        assert sent["campaign_id"] == "cmp_owner"
        assert "split B-1 into B-1a, B-1b" in " ".join(result.output.split())

    @pytest.mark.parametrize(
        "content",
        [None, "- {id: B-1a, title: the book}\n", "goal: not a split\n", "- just\n- strings\n"],
        ids=["no file", "one part", "no into", "not items"],
    )
    def test_a_file_that_holds_no_split_exits_before_any_call(self, content, tmp_path):
        """Bug caught: a one-part file sent and refused by the server after a read, or a file of
        strings sent as parts."""
        spec = tmp_path / "split.yaml"
        if content is not None:
            spec.write_text(content)

        with patch(CLIENT) as get_client:
            result = runner.invoke(
                app, ["goals", "split", "prj-lantern", "B-1", "--into", str(spec), "--reason", "r"]
            )

        assert result.exit_code == 2
        get_client.assert_not_called()


class _Server:
    """The write route's rules, as ``revise_goal_set`` and the store keep them: a write must name
    the active revision, and a key resent with the same request replays what it wrote."""

    def __init__(self, revision: int) -> None:
        self.revision = revision
        self.by_key: dict[str, tuple[dict, dict]] = {}
        self.lose_next_response = False

    def get(self, path: str) -> dict:
        return _revision(self.revision)

    def post(self, path: str, *, json: dict) -> dict:
        body = {k: v for k, v in json.items() if k != "idempotency_key"}
        if json["idempotency_key"] in self.by_key:
            sent, written = self.by_key[json["idempotency_key"]]
            if sent != body:
                raise CLIError("Error: conflict — IDEMPOTENCY_KEY_CONFLICT", exit_codes.CONFLICT)
            return {
                "revision": written,
                "idempotency_key": json["idempotency_key"],
                "replayed": True,
            }
        if json["expected_revision"] != self.revision:
            raise CLIError(
                f"Error: conflict — STALE_GOAL_SET_REVISION: at {self.revision}",
                exit_codes.CONFLICT,
            )
        self.revision += 1
        written = _revision(self.revision, goal_set=json["goal_set"])
        self.by_key[json["idempotency_key"]] = (body, written)
        if self.lose_next_response:
            self.lose_next_response = False
            raise CLIError("Error: the request timed out", exit_codes.NETWORK_ERROR)
        return {"revision": written, "idempotency_key": json["idempotency_key"], "replayed": False}

    def close(self) -> None: ...


def _show_to_file(server: _Server, path, **extra) -> None:
    server_revision = _revision(server.revision, **extra)
    client = MagicMock()
    client.get.return_value = server_revision
    with patch(CLIENT, return_value=client):
        shown = runner.invoke(app, ["goals", "show", "prj-lantern"])
    assert shown.exit_code == 0, shown.output
    path.write_text(shown.output)


def _edit(server: _Server, path, *extra: str):
    with patch(CLIENT, return_value=server):
        return runner.invoke(
            app, ["goals", "edit", "prj-lantern", "-f", str(path), "--reason", "r", *extra]
        )


class TestTheRoundTripAgainstAnotherEditor:
    """The second review of PR #2899: ``show > f; edit -f f`` as two editors and a lost response
    meet it."""

    def test_a_file_shown_before_another_editor_wrote_is_refused_not_written_over_them(
        self, tmp_path
    ):
        """P1. Bug caught: editor A's export from revision 1, submitted after editor B wrote
        revision 2, written as revision 3, so B's change is silently gone."""
        server = _Server(revision=1)
        mine, theirs = tmp_path / "a.yaml", tmp_path / "b.yaml"
        _show_to_file(server, mine)
        _show_to_file(server, theirs)
        assert _edit(server, theirs).exit_code == 0
        assert server.revision == 2

        result = _edit(server, mine)

        assert result.exit_code == exit_codes.CONFLICT
        assert "STALE_GOAL_SET_REVISION" in result.output
        assert server.revision == 2

    def test_a_write_whose_response_was_lost_replays_on_a_retry_with_its_key(self, tmp_path):
        """P2. Bug caught: the retry re-reads the active revision (the one it just wrote), so it
        sends a different request under the same key and is refused as a key conflict."""
        server = _Server(revision=1)
        spec = tmp_path / "goals.yaml"
        _show_to_file(server, spec)
        server.lose_next_response = True

        first = _edit(server, spec, "--idempotency-key", "k-1")
        retry = _edit(server, spec, "--idempotency-key", "k-1")

        assert first.exit_code != 0
        assert "expected revision 1" in " ".join(first.output.split())
        assert retry.exit_code == 0, retry.output
        assert "replayed: prj-lantern goal set revision 2" in " ".join(retry.output.split())
        assert server.revision == 2

    def test_a_multi_line_reason_and_link_still_round_trip(self, tmp_path):
        """P3. Bug caught: only the first line of a reason commented, so its second line is
        plain text above the document and the file no longer reads as the goal set."""
        server = _Server(revision=1)
        spec = tmp_path / "goals.yaml"
        _show_to_file(
            server,
            spec,
            reason="Added item\nAfter owner review\n# base-revision: 9",
            source_ref="https://chat.example.invalid/t/7\nsecond line",
        )

        assert parse_goal_set(yaml.safe_load(spec.read_text())) == parse_goal_set(
            goal_set_document()
        )
        result = _edit(server, spec)
        assert result.exit_code == 0, result.output
        assert server.revision == 2

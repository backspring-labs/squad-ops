"""
Unit tests for run commands (SIP-0065 §6.3).
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app

runner = CliRunner()


def _mock_client(get_val=None, post_val=None):
    mock = MagicMock()
    if get_val is not None:
        mock.get.return_value = get_val
    if post_val is not None:
        mock.post.return_value = post_val
    return mock


class TestRunsList:
    @patch("squadops.cli.commands.runs._get_client")
    def test_list(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {"run_id": "run_1", "run_number": 1, "status": "queued", "started_at": None},
            ]
        )
        result = runner.invoke(app, ["runs", "list", "proj1", "cyc_1"])
        assert result.exit_code == 0
        assert "run_1" in result.output

    @patch("squadops.cli.commands.runs._get_client")
    def test_list_shows_workload_type(self, mock_get_client):
        """runs list renders workload_type column for multi-workload cycles."""
        mock_get_client.return_value = _mock_client(
            get_val=[
                {
                    "run_id": "run_1",
                    "run_number": 1,
                    "status": "completed",
                    "workload_type": "framing",
                    "started_at": None,
                },
                {
                    "run_id": "run_2",
                    "run_number": 2,
                    "status": "running",
                    "workload_type": "implementation",
                    "started_at": None,
                },
            ]
        )
        result = runner.invoke(app, ["runs", "list", "proj1", "cyc_1"])
        assert result.exit_code == 0
        assert "framing" in result.output
        assert "implementation" in result.output
        assert "Workload" in result.output


class TestRunsShow:
    @patch("squadops.cli.commands.runs._get_client")
    def test_show(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val={
                "run_id": "run_1",
                "run_number": 1,
                "status": "queued",
            }
        )
        result = runner.invoke(app, ["runs", "show", "proj1", "cyc_1", "run_1"])
        assert result.exit_code == 0
        assert "run_1" in result.output

    @patch("squadops.cli.commands.runs._get_client")
    def test_a_held_run_names_its_hold_and_why(self, mock_get_client):
        """SIP-0110 §5ag (#2178), from the registry's run through the API's response to the table.
        Bugs caught: a paused run that says nothing of what holds it, so an operator can't tell a
        binding hold from a gate; a released hold still read as held; the hold dumped as raw JSON
        in the detail."""
        from datetime import UTC, datetime

        from squadops.api.routes.cycles.mapping import run_to_response
        from squadops.cycles.models import BindingHold, Run

        held_at = datetime(2026, 10, 21, 12, tzinfo=UTC)
        run = Run(
            run_id="run_1", cycle_id="cyc_1", run_number=1, status="paused",
            initiated_by="api", resolved_config_hash="h",
            binding_holds=(
                BindingHold("hold_1", "t_1", "qa.test", (("mrec_a@1", "unread", "store"),),
                            held_at, released_at=held_at, cause="store_answered"),
                BindingHold("hold_2", "t_2", "development.design_plan",
                            (("mrec_b@3", "takes 900 tokens and the prompt has 500", "input"),),
                            held_at, sections=("task_instructions",)),
            ),
        )  # fmt: skip
        mock_get_client.return_value = _mock_client(
            get_val=run_to_response(run).model_dump(mode="json")
        )

        from rich.console import Console

        # A console wide enough that no cell wraps, whatever width an earlier test left.
        with patch("squadops.cli.output._console", Console(width=240)):
            result = runner.invoke(app, ["runs", "show", "proj1", "cyc_1", "run_1"])

        assert result.exit_code == 0, result.output
        detail, table = result.output.split("Binding holds", 1)
        assert "binding_holds" not in detail
        rows = {
            cells[0]: cells[1:]
            for line in table.splitlines()
            if (cells := [c.strip() for c in line.split("│")[1:-1]] or [""])[0].startswith("hold_")
        }
        assert rows == {
            "hold_1": ["qa.test", "mrec_a@1 (store): unread", "2026-10-21T12:00:00Z",
                       "2026-10-21T12:00:00Z", "store_answered"],
            "hold_2": ["development.design_plan",
                       "mrec_b@3 (input): takes 900 tokens and the prompt has 500",
                       "2026-10-21T12:00:00Z", "held", ""],
        }  # fmt: skip


class TestRunsRetry:
    @patch("squadops.cli.commands.runs._get_client")
    def test_retry(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            post_val={
                "run_id": "run_2",
                "run_number": 2,
                "status": "queued",
            }
        )
        result = runner.invoke(app, ["runs", "retry", "proj1", "cyc_1"])
        assert result.exit_code == 0
        assert "run_2" in result.output


class TestRunsCancel:
    @patch("squadops.cli.commands.runs._get_client")
    def test_cancel(self, mock_get_client):
        mock_get_client.return_value = _mock_client(post_val={"status": "cancelled"})
        result = runner.invoke(app, ["runs", "cancel", "proj1", "cyc_1", "run_1"])
        assert result.exit_code == 0
        assert "cancelled" in result.output


class TestRunsGate:
    @patch("squadops.cli.commands.runs._get_client")
    def test_approve(self, mock_get_client):
        """--approve sends JSON {"decision": "approved"} (D8 wire mapping)."""
        mock_get_client.return_value = _mock_client(post_val={"status": "ok"})

        result = runner.invoke(
            app, ["runs", "gate", "proj1", "cyc_1", "run_1", "quality_gate", "--approve"]
        )
        assert result.exit_code == 0

        call_args = mock_get_client.return_value.post.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert body["decision"] == "approved"

    @patch("squadops.cli.commands.runs._get_client")
    def test_reject(self, mock_get_client):
        """--reject sends JSON {"decision": "rejected"} (D8 wire mapping)."""
        mock_get_client.return_value = _mock_client(post_val={"status": "ok"})

        result = runner.invoke(
            app,
            [
                "runs",
                "gate",
                "proj1",
                "cyc_1",
                "run_1",
                "quality_gate",
                "--reject",
                "--notes",
                "failed tests",
            ],
        )
        assert result.exit_code == 0

        call_args = mock_get_client.return_value.post.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert body["decision"] == "rejected"
        assert body["notes"] == "failed tests"

    def test_neither_approve_nor_reject(self):
        """Must specify exactly one of --approve or --reject."""
        result = runner.invoke(app, ["runs", "gate", "proj1", "cyc_1", "run_1", "quality_gate"])
        assert result.exit_code == 2

    @patch("squadops.cli.commands.runs._get_client")
    def test_conflict_on_terminal_run(self, mock_get_client):
        mock = MagicMock()
        mock.post.side_effect = CLIError("conflict", exit_codes.CONFLICT)
        mock_get_client.return_value = mock

        result = runner.invoke(app, ["runs", "gate", "proj1", "cyc_1", "run_1", "g1", "--approve"])
        assert result.exit_code == exit_codes.CONFLICT


class TestRunsGateIncrementRuling:
    """SIP-0109 §9.2 through ``squadops runs gate``: the ruling binds to the document the
    supervisor reviewed."""

    _CR = (
        "proposal_id: prop_cap\nversion: 2\nbaseline_tree: sha-accepted\n"
        "content_hash: hash-cap-v2\nkind: feature\n"
    )

    @pytest.mark.parametrize(
        ("content", "sent"),
        [
            ("- text: Keep capacity optional.\n  task_types: [development.develop]\n",
             [{"text": "Keep capacity optional.", "task_types": ["development.develop"]}]),
            ("text: not a list\n", None),
        ],
        ids=["a-list-is-sent", "anything-else-is-refused"],
    )  # fmt: skip
    @patch("squadops.cli.commands.runs._get_client")
    def test_an_approvals_task_instructions_are_read_from_their_file(
        self, mock_get_client, tmp_path, content, sent
    ):
        """SIP-0110 §3.5 (#2178). Bugs caught: the instructions file read and not sent, so they
        stay as free notes no prompt sees; a malformed file sent anyway."""
        reviewed, given = tmp_path / "change_request.yaml", tmp_path / "instructions.yaml"
        reviewed.write_text(self._CR)
        given.write_text(content)
        mock_get_client.return_value = _mock_client(post_val={"status": "ok"})

        result = runner.invoke(
            app,
            ["runs", "gate", "group_run", "cyc_1", "run_1", "progress_increment_ruling",
             "--approve", "--notes", "scope reads right", "--change-request", str(reviewed),
             "--idempotency-key", "k-1", "--task-instructions", str(given)],
        )  # fmt: skip

        if sent is None:
            assert result.exit_code == 2
            assert not mock_get_client.return_value.post.called
        else:
            assert result.exit_code == 0, result.output
            body = mock_get_client.return_value.post.call_args.kwargs["json"]
            assert body["task_instructions"] == sent

    @patch("squadops.cli.commands.runs._get_client")
    def test_the_binding_is_read_from_the_reviewed_change_request(self, mock_get_client, tmp_path):
        """Bug caught: a binding typed by hand, or taken from whatever is current, so an approval
        can land on a version nobody read."""
        reviewed = tmp_path / "change_request.yaml"
        reviewed.write_text(self._CR)
        mock_get_client.return_value = _mock_client(post_val={"status": "ok"})

        result = runner.invoke(
            app,
            [
                "runs",
                "gate",
                "group_run",
                "cyc_1",
                "run_1",
                "progress_increment_ruling",
                "--approve",
                "--notes",
                "scope reads right",
                "--change-request",
                str(reviewed),
                "--idempotency-key",
                "k-1",
            ],
        )

        assert result.exit_code == 0, result.output
        body = mock_get_client.return_value.post.call_args.kwargs["json"]
        assert body["binding"] == {
            "proposal_id": "prop_cap",
            "version": 2,
            "content_hash": "hash-cap-v2",
            "baseline_tree": "sha-accepted",
        }
        assert (body["idempotency_key"], body["notes"]) == ("k-1", "scope reads right")

    @patch("squadops.cli.commands.runs._get_client")
    def test_a_returns_classification_is_sent_with_the_ruling(self, mock_get_client, tmp_path):
        """SIP-0109 §24bi. Bug caught: the flags accepted and never sent, so every return the CLI
        makes is refused by the API with no way through."""
        reviewed = tmp_path / "change_request.yaml"
        reviewed.write_text(self._CR)
        mock_get_client.return_value = _mock_client(post_val={"status": "ok"})

        result = runner.invoke(
            app,
            [
                "runs",
                "gate",
                "group_run",
                "cyc_1",
                "run_1",
                "progress_increment_ruling",
                "--reject",
                "--notes",
                "names a route the manifest forbids",
                "--change-request",
                str(reviewed),
                "--classification",
                "unclassified",
                "--classification-rationale",
                "no class names a forbidden route",
            ],
        )

        assert result.exit_code == 0, result.output
        body = mock_get_client.return_value.post.call_args.kwargs["json"]
        assert (body["decision"], body["classification"], body["classification_rationale"]) == (
            "rejected",
            "unclassified",
            "no class names a forbidden route",
        )

    @pytest.mark.parametrize(
        ("gate", "extra", "message"),
        [
            ("progress_increment_ruling", [], "pass --change-request"),
            (
                "progress_plan_review",
                ["--idempotency-key", "k"],
                "belong to progress_increment_ruling",
            ),
            (
                "progress_plan_review",
                ["--classification", "scope_too_large"],
                "belong to progress_increment_ruling",
            ),
        ],
    )
    @patch("squadops.cli.commands.runs._get_client")
    def test_a_ruling_without_its_document_or_flags_on_another_gate_send_nothing(
        self, mock_get_client, gate, extra, message
    ):
        result = runner.invoke(
            app, ["runs", "gate", "group_run", "cyc_1", "run_1", gate, "--approve", *extra]
        )

        assert result.exit_code == 2
        assert message in " ".join(result.output.split())  # the console wraps at 80 columns
        mock_get_client.return_value.post.assert_not_called()


class TestRunsResume:
    @patch("squadops.cli.commands.runs._get_client")
    def test_resume_success(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            post_val={"run_id": "run_1", "status": "running"}
        )
        result = runner.invoke(app, ["runs", "resume", "proj1", "cyc_1", "run_1"])
        assert result.exit_code == 0
        assert "resumed" in result.output

    @patch("squadops.cli.commands.runs._get_client")
    def test_resume_error(self, mock_get_client):
        mock = MagicMock()
        mock.post.side_effect = CLIError("conflict", exit_codes.CONFLICT)
        mock_get_client.return_value = mock
        result = runner.invoke(app, ["runs", "resume", "proj1", "cyc_1", "run_1"])
        assert result.exit_code == exit_codes.CONFLICT


class TestRunsCheckpoints:
    @patch("squadops.cli.commands.runs._get_client")
    def test_checkpoints_table(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {
                    "checkpoint_index": 0,
                    "completed_task_count": 3,
                    "artifact_ref_count": 2,
                    "created_at": "2026-01-15T12:00:00Z",
                }
            ]
        )
        result = runner.invoke(app, ["runs", "checkpoints", "proj1", "cyc_1", "run_1"])
        assert result.exit_code == 0
        assert "3" in result.output

    @patch("squadops.cli.commands.runs._get_client")
    def test_checkpoints_json(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {
                    "checkpoint_index": 0,
                    "completed_task_count": 3,
                    "artifact_ref_count": 2,
                    "created_at": "2026-01-15T12:00:00Z",
                }
            ]
        )
        result = runner.invoke(
            app, ["--format", "json", "runs", "checkpoints", "proj1", "cyc_1", "run_1"]
        )
        assert result.exit_code == 0
        assert "checkpoint_index" in result.output

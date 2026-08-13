"""
Unit tests for run commands (SIP-0065 §6.3).
"""

from unittest.mock import MagicMock, patch

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


class TestAssembleArtifactPreference:
    """#881: a resumed run's artifact list carries re-seeded scaffold stubs stored
    AFTER the dev fills — write-in-list-order would assemble the skeleton, not
    the app. One artifact per filename: produced code beats scaffold-seeded,
    then latest created_at."""

    @staticmethod
    def _meta(art_id, filename, created_at, seeded=False):
        meta = {
            "artifact_id": art_id,
            "filename": filename,
            "artifact_type": "source",
            "created_at": created_at,
        }
        if seeded:
            meta["metadata"] = {"scaffold_seeded": True}
        return meta

    def test_produced_beats_newer_scaffold_stub(self):
        """The roll-14 resume shape: the re-seeded stub is NEWEST but must lose."""
        from squadops.cli.commands.runs import _prefer_artifact

        fill = self._meta("art_fill", "app/api/runs/route.ts", "2026-08-12 18:43:01+00:00")
        reseeded_stub = self._meta(
            "art_stub2", "app/api/runs/route.ts", "2026-08-13 00:07:25+00:00", seeded=True
        )

        assert _prefer_artifact(fill, reseeded_stub) is True
        assert _prefer_artifact(reseeded_stub, fill) is False

    def test_among_produced_versions_latest_wins(self):
        from squadops.cli.commands.runs import _prefer_artifact

        older = self._meta("art_a", "lib/store.ts", "2026-08-12 18:40:00+00:00")
        newer = self._meta("art_b", "lib/store.ts", "2026-08-12 19:10:00+00:00")

        assert _prefer_artifact(newer, older) is True
        assert _prefer_artifact(older, newer) is False

    def test_among_scaffold_versions_latest_wins(self):
        """Frozen files exist only as scaffold artifacts — the newest seed set
        must still be assemblable when no produced version exists."""
        from squadops.cli.commands.runs import _prefer_artifact

        old_seed = self._meta("art_s1", "lib/errors.ts", "2026-08-12 18:34:13+00:00", seeded=True)
        new_seed = self._meta("art_s2", "lib/errors.ts", "2026-08-13 00:07:25+00:00", seeded=True)

        assert _prefer_artifact(new_seed, old_seed) is True

    def test_missing_metadata_treated_as_produced(self):
        """Artifacts predating the scaffold_seeded marker (or with metadata absent
        entirely) must not be mistaken for stubs and shadowed by one."""
        from squadops.cli.commands.runs import _prefer_artifact

        legacy = {
            "artifact_id": "art_x",
            "filename": "main.py",
            "created_at": "2026-08-12 18:00:00+00:00",
        }
        stub = self._meta("art_s", "main.py", "2026-08-13 00:00:00+00:00", seeded=True)

        assert _prefer_artifact(legacy, stub) is True

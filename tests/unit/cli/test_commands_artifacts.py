"""
Unit tests for artifact and baseline commands (SIP-0065 §6.3).
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.main import app

runner = CliRunner()


def _mock_client(get_val=None, post_val=None, upload_val=None, download_val=None):
    mock = MagicMock()
    if get_val is not None:
        mock.get.return_value = get_val
    if post_val is not None:
        mock.post.return_value = post_val
    if upload_val is not None:
        mock.upload.return_value = upload_val
    if download_val is not None:
        mock.download.return_value = download_val
    return mock


class TestArtifactsIngest:
    @patch("squadops.cli.commands.artifacts._get_client")
    def test_ingest(self, mock_get_client, tmp_path):
        test_file = tmp_path / "prd.txt"
        test_file.write_text("PRD Content")

        mock_get_client.return_value = _mock_client(
            upload_val={
                "artifact_id": "art_123",
                "artifact_type": "prd",
                "size_bytes": 11,
            }
        )

        result = runner.invoke(
            app,
            [
                "artifacts",
                "ingest",
                "--project",
                "proj1",
                "--type",
                "prd",
                "--file",
                str(test_file),
            ],
        )
        assert result.exit_code == 0
        assert "art_123" in result.output

        # Verify upload was called with correct fields
        call_args = mock_get_client.return_value.upload.call_args
        fields = call_args.kwargs.get("fields") or call_args[1].get("fields")
        assert fields["artifact_type"] == "prd"
        assert fields["filename"] == "prd.txt"
        assert fields["media_type"] == "text/plain"

    def test_file_not_found(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "artifacts",
                "ingest",
                "--project",
                "proj1",
                "--type",
                "prd",
                "--file",
                str(tmp_path / "nope.md"),
            ],
        )
        assert result.exit_code == exit_codes.GENERAL_ERROR


class TestArtifactsGet:
    @patch("squadops.cli.commands.artifacts._get_client")
    def test_get(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val={
                "artifact_id": "art_1",
                "artifact_type": "prd",
                "filename": "prd.md",
            }
        )
        result = runner.invoke(app, ["artifacts", "get", "art_1"])
        assert result.exit_code == 0
        assert "art_1" in result.output


class TestArtifactsDownload:
    @patch("squadops.cli.commands.artifacts._get_client")
    def test_download(self, mock_get_client, tmp_path):
        out_path = tmp_path / "output.md"
        mock_get_client.return_value = _mock_client(download_val=(b"file content", "output.md"))
        result = runner.invoke(app, ["artifacts", "download", "art_1", "--out", str(out_path)])
        assert result.exit_code == 0
        assert out_path.read_bytes() == b"file content"


class TestArtifactsList:
    @patch("squadops.cli.commands.artifacts._get_client")
    def test_list_project_scoped(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {
                    "artifact_id": "art_1",
                    "artifact_type": "prd",
                    "filename": "prd.md",
                    "size_bytes": 100,
                },
            ]
        )
        result = runner.invoke(app, ["artifacts", "list", "--project", "proj1"])
        assert result.exit_code == 0
        assert "art_1" in result.output

    @patch("squadops.cli.commands.artifacts._get_client")
    def test_list_cycle_scoped(self, mock_get_client):
        """--cycle selects cycle-scoped endpoint."""
        mock_get_client.return_value = _mock_client(get_val=[])
        result = runner.invoke(app, ["artifacts", "list", "--project", "proj1", "--cycle", "cyc_1"])
        assert result.exit_code == 0

        call_args = mock_get_client.return_value.get.call_args
        path = call_args.args[0] if call_args.args else call_args[0][0]
        assert "cycles/cyc_1/artifacts" in path


class TestBaselineSet:
    @patch("squadops.cli.commands.artifacts._get_client")
    def test_set(self, mock_get_client):
        mock_get_client.return_value = _mock_client(post_val={"status": "ok"})
        result = runner.invoke(app, ["baseline", "set", "proj1", "prd", "art_1"])
        assert result.exit_code == 0

        call_args = mock_get_client.return_value.post.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert body["artifact_id"] == "art_1"


class TestBaselineGet:
    @patch("squadops.cli.commands.artifacts._get_client")
    def test_get(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val={
                "artifact_id": "art_1",
                "artifact_type": "prd",
            }
        )
        result = runner.invoke(app, ["baseline", "get", "proj1", "prd"])
        assert result.exit_code == 0
        assert "art_1" in result.output


class TestBaselineList:
    @patch("squadops.cli.commands.artifacts._get_client")
    def test_list(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val={
                "prd": {"artifact_id": "art_1", "filename": "prd.md"},
                "code": {"artifact_id": "art_2", "filename": "code.zip"},
            }
        )
        result = runner.invoke(app, ["baseline", "list", "proj1"])
        assert result.exit_code == 0
        assert "art_1" in result.output
        assert "art_2" in result.output

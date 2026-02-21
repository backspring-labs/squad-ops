"""Unit tests for the runs assemble command (SIP-Enhanced-Agent-Build-Capabilities).

Tests the assembly of build artifacts from a completed run into a local
directory, including file writing, filtering, and error handling.

Part of Phase 3.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app

runner = CliRunner()

pytestmark = [pytest.mark.domain_cli]


def _mock_client(
    cycle_data=None,
    run_data=None,
    artifact_metas=None,
    download_returns=None,
):
    """Build a mock APIClient for assembly tests."""
    mock = MagicMock()

    get_responses = []
    if cycle_data is not None:
        get_responses.append(cycle_data)
    if run_data is not None:
        get_responses.append(run_data)
    if artifact_metas is not None:
        get_responses.extend(artifact_metas)

    mock.get.side_effect = get_responses
    mock.download.side_effect = download_returns or []
    return mock


class TestAssembleWritesFiles:
    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_writes_files(self, mock_get_client, tmp_path):
        """Successful assembly writes files to output directory."""
        mock_get_client.return_value = _mock_client(
            cycle_data={"project_id": "play_game", "cycle_id": "cyc_001"},
            run_data={
                "run_id": "run_001",
                "artifact_refs": ["art_src", "art_test"],
            },
            artifact_metas=[
                {
                    "artifact_id": "art_src",
                    "artifact_type": "source",
                    "filename": "src/main.py",
                    "size_bytes": 42,
                },
                {
                    "artifact_id": "art_test",
                    "artifact_type": "test",
                    "filename": "tests/test_main.py",
                    "size_bytes": 30,
                },
            ],
            download_returns=[
                (b"print('hello')", "main.py"),
                (b"def test_main(): pass", "test_main.py"),
            ],
        )

        result = runner.invoke(app, [
            "runs", "assemble", "play_game", "cyc_001", "run_001",
            "--out", str(tmp_path),
        ])

        assert result.exit_code == 0
        assert (tmp_path / "play_game" / "src" / "main.py").read_bytes() == b"print('hello')"
        assert (tmp_path / "play_game" / "tests" / "test_main.py").exists()
        assert "2 file(s)" in result.output

    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_uses_cycle_id_fallback(self, mock_get_client, tmp_path):
        """When project_id is empty, use cycle_id[:12] as output dir name."""
        mock_get_client.return_value = _mock_client(
            cycle_data={"project_id": "", "cycle_id": "cyc_abcdef123456"},
            run_data={
                "run_id": "run_001",
                "artifact_refs": ["art_src"],
            },
            artifact_metas=[
                {
                    "artifact_id": "art_src",
                    "artifact_type": "source",
                    "filename": "app.py",
                    "size_bytes": 10,
                },
            ],
            download_returns=[
                (b"code", "app.py"),
            ],
        )

        result = runner.invoke(app, [
            "runs", "assemble", "proj", "cyc_abcdef123456", "run_001",
            "--out", str(tmp_path),
        ])

        assert result.exit_code == 0
        assert (tmp_path / "cyc_abcdef12" / "app.py").exists()


class TestAssembleNoBuildArtifacts:
    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_no_build_artifacts(self, mock_get_client, tmp_path):
        """No build artifacts → informative message and non-zero exit."""
        mock_get_client.return_value = _mock_client(
            cycle_data={"project_id": "proj", "cycle_id": "cyc_001"},
            run_data={
                "run_id": "run_001",
                "artifact_refs": ["art_doc"],
            },
            artifact_metas=[
                {
                    "artifact_id": "art_doc",
                    "artifact_type": "document",
                    "filename": "plan.md",
                    "size_bytes": 100,
                },
            ],
        )

        result = runner.invoke(app, [
            "runs", "assemble", "proj", "cyc_001", "run_001",
            "--out", str(tmp_path),
        ])

        assert result.exit_code == exit_codes.NOT_FOUND
        assert "planning artifacts" in result.output


class TestAssembleNoArtifacts:
    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_no_artifacts_at_all(self, mock_get_client, tmp_path):
        """Run with no artifact_refs → error message."""
        mock_get_client.return_value = _mock_client(
            cycle_data={"project_id": "proj", "cycle_id": "cyc_001"},
            run_data={
                "run_id": "run_001",
                "artifact_refs": [],
            },
        )

        result = runner.invoke(app, [
            "runs", "assemble", "proj", "cyc_001", "run_001",
            "--out", str(tmp_path),
        ])

        assert result.exit_code == exit_codes.NOT_FOUND


class TestAssembleAPIError:
    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_api_error(self, mock_get_client, tmp_path):
        """API error is reported with correct exit code."""
        mock = MagicMock()
        mock.get.side_effect = CLIError("not found", exit_codes.NOT_FOUND)
        mock_get_client.return_value = mock

        result = runner.invoke(app, [
            "runs", "assemble", "proj", "cyc_001", "run_001",
            "--out", str(tmp_path),
        ])

        assert result.exit_code == exit_codes.NOT_FOUND


class TestAssembleFiltersCorrectly:
    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_filters_to_build_types(self, mock_get_client, tmp_path):
        """Only source/test/config artifacts are downloaded, not documentation."""
        mock_get_client.return_value = _mock_client(
            cycle_data={"project_id": "proj", "cycle_id": "cyc_001"},
            run_data={
                "run_id": "run_001",
                "artifact_refs": ["art_plan", "art_code", "art_cfg"],
            },
            artifact_metas=[
                {"artifact_id": "art_plan", "artifact_type": "document", "filename": "plan.md", "size_bytes": 50},
                {"artifact_id": "art_code", "artifact_type": "source", "filename": "main.py", "size_bytes": 10},
                {"artifact_id": "art_cfg", "artifact_type": "config", "filename": "config.yaml", "size_bytes": 20},
            ],
            download_returns=[
                (b"print(1)", "main.py"),
                (b"key: val", "config.yaml"),
            ],
        )

        result = runner.invoke(app, [
            "runs", "assemble", "proj", "cyc_001", "run_001",
            "--out", str(tmp_path),
        ])

        assert result.exit_code == 0
        assert (tmp_path / "proj" / "main.py").exists()
        assert (tmp_path / "proj" / "config.yaml").exists()
        assert not (tmp_path / "proj" / "plan.md").exists()
        assert "2 file(s)" in result.output


class TestAssembleReadmeContent:
    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_prints_readme_content(self, mock_get_client, tmp_path):
        """README.md content is printed after file tree."""
        mock_get_client.return_value = _mock_client(
            cycle_data={"project_id": "proj", "cycle_id": "cyc_001"},
            run_data={
                "run_id": "run_001",
                "artifact_refs": ["art_src", "art_readme"],
            },
            artifact_metas=[
                {"artifact_id": "art_src", "artifact_type": "source", "filename": "main.py", "size_bytes": 10},
                {"artifact_id": "art_readme", "artifact_type": "config", "filename": "README.md", "size_bytes": 20},
            ],
            download_returns=[
                (b"print(1)", "main.py"),
                (b"# My Project\nHello world", "README.md"),
            ],
        )

        result = runner.invoke(app, [
            "runs", "assemble", "proj", "cyc_001", "run_001",
            "--out", str(tmp_path),
        ])

        assert result.exit_code == 0
        assert "README.md" in result.output
        assert "# My Project" in result.output
        assert "Hello world" in result.output


class TestAssembleJsonOutput:
    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_respects_format_flag(self, mock_get_client, tmp_path):
        """Assemble still works with --format table (default)."""
        mock_get_client.return_value = _mock_client(
            cycle_data={"project_id": "proj", "cycle_id": "cyc_001"},
            run_data={
                "run_id": "run_001",
                "artifact_refs": ["art_src"],
            },
            artifact_metas=[
                {"artifact_id": "art_src", "artifact_type": "source", "filename": "app.py", "size_bytes": 5},
            ],
            download_returns=[
                (b"code", "app.py"),
            ],
        )

        result = runner.invoke(app, [
            "runs", "assemble", "proj", "cyc_001", "run_001",
            "--out", str(tmp_path),
        ])

        assert result.exit_code == 0
        assert "app.py" in result.output

"""Unit tests for the runs assemble command (SIP-Enhanced-Agent-Build-Capabilities).

Tests the assembly of build artifacts from a completed run into a local
directory, including file writing, filtering, and error handling.

Part of Phase 3.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app

runner = CliRunner()

pytestmark = [pytest.mark.domain_cli]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(output: str) -> str:
    """Strip ANSI style sequences from CLI output before asserting.

    Under CliRunner, output is not a TTY so rich normally emits no styling —
    but a caller environment exporting FORCE_COLOR overrides that detection,
    and rich's auto-highlighter styles numbers as separate tokens, splitting
    substrings like "2 file(s)" across escape sequences (#345). Assert on the
    plain text so the tests are deterministic regardless of the shell's
    color environment.
    """
    return _ANSI_RE.sub("", output)


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


class TestAssembleDeliversWhatTheRunAccepted:
    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_downloads_only_the_delivered_files(self, mock_get_client, tmp_path):
        """#1832, through the command. Bugs caught: a rejected repair candidate or a failed
        emission assembled because it is newer (179 stored runs differed under the old rule),
        or a resumed run's re-seeded stub assembled over the fill (#881)."""

        def meta(art_id, filename, created_at, **extra):
            return {
                "artifact_id": art_id,
                "artifact_type": "source",
                "filename": filename,
                "created_at": created_at,
                "size_bytes": 1,
                "metadata": extra,
            }

        metas = [
            meta(
                "art_dev",
                "backend/routes.py",
                "2026-09-01T10:00:00Z",
                producing_task_type="development.develop",
            ),
            meta(
                "art_cand",
                "backend/routes.py",
                "2026-09-01T10:30:00Z",
                producing_task_type="development.correction_repair",
            ),
            meta("art_main", "backend/main.py", "2026-09-01T10:00:00Z"),
            meta("art_failed", "backend/main.py", "2026-09-01T10:40:00Z", emission_status="failed"),
            meta("art_fill", "frontend/src/App.jsx", "2026-09-01T10:00:00Z"),
            meta("art_stub", "frontend/src/App.jsx", "2026-09-01T11:00:00Z", scaffold_seeded=True),
        ]
        client = _mock_client(
            cycle_data={"project_id": "group_run"},
            run_data={"run_id": "run_001", "artifact_refs": [m["artifact_id"] for m in metas]},
            artifact_metas=metas,
        )
        client.download.side_effect = lambda path: (path.encode(), "x")
        mock_get_client.return_value = client

        result = runner.invoke(
            app,
            ["runs", "assemble", "group_run", "cyc_001", "run_001", "--out", str(tmp_path)],
        )

        assert result.exit_code == 0, result.output
        downloaded = sorted(c.args[0].split("/")[-2] for c in client.download.call_args_list)
        assert downloaded == ["art_dev", "art_fill", "art_main"]
        assert "3 file(s)" in _plain(result.output)


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

        result = runner.invoke(
            app,
            [
                "runs",
                "assemble",
                "play_game",
                "cyc_001",
                "run_001",
                "--out",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0
        assert (tmp_path / "play_game" / "src" / "main.py").read_bytes() == b"print('hello')"
        assert (tmp_path / "play_game" / "tests" / "test_main.py").exists()
        assert "2 file(s)" in _plain(result.output)

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

        result = runner.invoke(
            app,
            [
                "runs",
                "assemble",
                "proj",
                "cyc_abcdef123456",
                "run_001",
                "--out",
                str(tmp_path),
            ],
        )

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

        result = runner.invoke(
            app,
            [
                "runs",
                "assemble",
                "proj",
                "cyc_001",
                "run_001",
                "--out",
                str(tmp_path),
            ],
        )

        assert result.exit_code == exit_codes.NOT_FOUND
        assert "planning artifacts" in _plain(result.output)


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

        result = runner.invoke(
            app,
            [
                "runs",
                "assemble",
                "proj",
                "cyc_001",
                "run_001",
                "--out",
                str(tmp_path),
            ],
        )

        assert result.exit_code == exit_codes.NOT_FOUND


class TestAssembleAPIError:
    @patch("squadops.cli.commands.runs._get_client")
    def test_assemble_api_error(self, mock_get_client, tmp_path):
        """API error is reported with correct exit code."""
        mock = MagicMock()
        mock.get.side_effect = CLIError("not found", exit_codes.NOT_FOUND)
        mock_get_client.return_value = mock

        result = runner.invoke(
            app,
            [
                "runs",
                "assemble",
                "proj",
                "cyc_001",
                "run_001",
                "--out",
                str(tmp_path),
            ],
        )

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
                {
                    "artifact_id": "art_plan",
                    "artifact_type": "document",
                    "filename": "plan.md",
                    "size_bytes": 50,
                },
                {
                    "artifact_id": "art_code",
                    "artifact_type": "source",
                    "filename": "main.py",
                    "size_bytes": 10,
                },
                {
                    "artifact_id": "art_cfg",
                    "artifact_type": "config",
                    "filename": "config.yaml",
                    "size_bytes": 20,
                },
            ],
            download_returns=[
                (b"print(1)", "main.py"),
                (b"key: val", "config.yaml"),
            ],
        )

        result = runner.invoke(
            app,
            [
                "runs",
                "assemble",
                "proj",
                "cyc_001",
                "run_001",
                "--out",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0
        assert (tmp_path / "proj" / "main.py").exists()
        assert (tmp_path / "proj" / "config.yaml").exists()
        assert not (tmp_path / "proj" / "plan.md").exists()
        assert "2 file(s)" in _plain(result.output)


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
                {
                    "artifact_id": "art_src",
                    "artifact_type": "source",
                    "filename": "main.py",
                    "size_bytes": 10,
                },
                {
                    "artifact_id": "art_readme",
                    "artifact_type": "config",
                    "filename": "README.md",
                    "size_bytes": 20,
                },
            ],
            download_returns=[
                (b"print(1)", "main.py"),
                (b"# My Project\nHello world", "README.md"),
            ],
        )

        result = runner.invoke(
            app,
            [
                "runs",
                "assemble",
                "proj",
                "cyc_001",
                "run_001",
                "--out",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0
        assert "README.md" in _plain(result.output)
        assert "# My Project" in _plain(result.output)
        assert "Hello world" in _plain(result.output)


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
                {
                    "artifact_id": "art_src",
                    "artifact_type": "source",
                    "filename": "app.py",
                    "size_bytes": 5,
                },
            ],
            download_returns=[
                (b"code", "app.py"),
            ],
        )

        result = runner.invoke(
            app,
            [
                "runs",
                "assemble",
                "proj",
                "cyc_001",
                "run_001",
                "--out",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0
        assert "app.py" in _plain(result.output)

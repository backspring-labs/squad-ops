"""
Unit tests for cycle commands (SIP-0065 §6.3).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app
from squadops.cycles.lifecycle import compute_config_hash

runner = CliRunner()


def _mock_client(get_val=None, post_val=None):
    mock = MagicMock()
    if get_val is not None:
        mock.get.return_value = get_val
    if post_val is not None:
        mock.post.return_value = post_val
    return mock


class TestCyclesCreate:
    @patch("squadops.cli.commands.cycles._get_client")
    def test_default_profile(self, mock_get_client):
        """cycles create sends correct request body with default CRP profile."""
        from squadops.contracts.cycle_request_profiles import load_profile

        crp = load_profile("default")
        expected_hash = compute_config_hash(crp.defaults, {})

        mock_get_client.return_value = _mock_client(post_val={
            "cycle_id": "cyc_abc",
            "run_id": "run_xyz",
            "status": "queued",
            "resolved_config_hash": expected_hash,
        })

        result = runner.invoke(app, [
            "cycles", "create", "hello_squad", "--squad-profile", "default_v1"
        ])
        assert result.exit_code == 0
        assert "cyc_abc" in result.output

        # Verify the POST body
        call_args = mock_get_client.return_value.post.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert body["squad_profile_id"] == "default_v1"
        assert body["applied_defaults"] == crp.defaults
        assert body["execution_overrides"] == {}

    @patch("squadops.cli.commands.cycles._get_client")
    def test_benchmark_profile(self, mock_get_client):
        mock_get_client.return_value = _mock_client(post_val={
            "cycle_id": "cyc_1",
            "run_id": "run_1",
            "status": "queued",
            "resolved_config_hash": "abc123",
        })

        result = runner.invoke(app, [
            "cycles", "create", "proj1",
            "--squad-profile", "sp1",
            "--profile", "benchmark",
        ])
        assert result.exit_code == 0

        body = mock_get_client.return_value.post.call_args.kwargs.get("json") or \
               mock_get_client.return_value.post.call_args[1].get("json")
        assert body["experiment_context"].get("benchmark") is True

    @patch("squadops.cli.commands.cycles._get_client")
    def test_set_override(self, mock_get_client):
        """--set puts value in execution_overrides when it differs from default."""
        mock_get_client.return_value = _mock_client(post_val={
            "cycle_id": "cyc_1",
            "run_id": "run_1",
            "status": "queued",
            "resolved_config_hash": "x",
        })

        result = runner.invoke(app, [
            "cycles", "create", "proj1",
            "--squad-profile", "sp1",
            "--set", "build_strategy=incremental",
        ])
        assert result.exit_code == 0

        body = mock_get_client.return_value.post.call_args.kwargs.get("json") or \
               mock_get_client.return_value.post.call_args[1].get("json")
        assert body["execution_overrides"]["build_strategy"] == "incremental"
        assert body["build_strategy"] == "incremental"

    @patch("squadops.cli.commands.cycles._get_client")
    def test_hash_round_trip(self, mock_get_client):
        """Local hash matches server response hash."""
        from squadops.contracts.cycle_request_profiles import (
            compute_overrides,
            load_profile,
            merge_config,
        )

        crp = load_profile("default")
        user_vals = {"build_strategy": "incremental"}
        merged = merge_config(crp.defaults, user_vals)
        overrides = compute_overrides(crp.defaults, merged)
        expected_hash = compute_config_hash(crp.defaults, overrides)

        mock_get_client.return_value = _mock_client(post_val={
            "cycle_id": "cyc_1",
            "run_id": "run_1",
            "status": "queued",
            "resolved_config_hash": expected_hash,
        })

        result = runner.invoke(app, [
            "cycles", "create", "proj1",
            "--squad-profile", "sp1",
            "--set", "build_strategy=incremental",
        ])
        assert result.exit_code == 0
        # No hash mismatch warning in output
        assert "mismatch" not in result.output

    @patch("squadops.cli.commands.cycles._get_client")
    def test_not_found(self, mock_get_client):
        mock = MagicMock()
        mock.post.side_effect = CLIError("not found", exit_codes.NOT_FOUND)
        mock_get_client.return_value = mock

        result = runner.invoke(app, [
            "cycles", "create", "nonexistent",
            "--squad-profile", "sp1",
        ])
        assert result.exit_code == exit_codes.NOT_FOUND


    @patch("squadops.cli.commands.cycles._get_client")
    def test_create_with_prd_file_auto_ingests(self, mock_get_client, tmp_path):
        """--prd with a file path auto-ingests via upload and uses returned artifact ID."""
        prd_file = tmp_path / "prd.md"
        prd_file.write_text("# My PRD\nSome content")

        mock_client = _mock_client(post_val={
            "cycle_id": "cyc_prd",
            "run_id": "run_prd",
            "status": "queued",
            "resolved_config_hash": "abc",
        })
        mock_client.upload.return_value = {"artifact_id": "art_prd_123"}
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, [
            "cycles", "create", "proj1",
            "--squad-profile", "sp1",
            "--prd", str(prd_file),
        ])
        assert result.exit_code == 0

        # Verify upload was called with correct args
        upload_call = mock_client.upload.call_args
        assert "/artifacts/ingest" in upload_call[0][0]
        assert upload_call.kwargs["fields"]["artifact_type"] == "prd"

        # Verify the POST body uses the returned artifact ID
        post_call = mock_client.post.call_args
        body = post_call.kwargs.get("json") or post_call[1].get("json")
        assert body["prd_ref"] == "art_prd_123"

    @patch("squadops.cli.commands.cycles._get_client")
    def test_create_with_prd_artifact_id(self, mock_get_client):
        """--prd with an artifact ID passes it through without upload."""
        mock_client = _mock_client(post_val={
            "cycle_id": "cyc_1",
            "run_id": "run_1",
            "status": "queued",
            "resolved_config_hash": "abc",
        })
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, [
            "cycles", "create", "proj1",
            "--squad-profile", "sp1",
            "--prd", "art_existing",
        ])
        assert result.exit_code == 0

        # No upload call
        mock_client.upload.assert_not_called()

        # Verify body has the artifact ID as-is
        post_call = mock_client.post.call_args
        body = post_call.kwargs.get("json") or post_call[1].get("json")
        assert body["prd_ref"] == "art_existing"

    @patch("squadops.cli.commands.cycles._get_client")
    def test_create_with_prd_file_not_found(self, mock_get_client):
        """--prd with a nonexistent file path treats it as an artifact ID."""
        mock_client = _mock_client(post_val={
            "cycle_id": "cyc_1",
            "run_id": "run_1",
            "status": "queued",
            "resolved_config_hash": "abc",
        })
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, [
            "cycles", "create", "proj1",
            "--squad-profile", "sp1",
            "--prd", "/nonexistent/prd.md",
        ])
        assert result.exit_code == 0

        # No upload — treated as artifact ID
        mock_client.upload.assert_not_called()

        post_call = mock_client.post.call_args
        body = post_call.kwargs.get("json") or post_call[1].get("json")
        assert body["prd_ref"] == "/nonexistent/prd.md"


class TestCyclesList:
    @patch("squadops.cli.commands.cycles._get_client")
    def test_list(self, mock_get_client):
        mock_get_client.return_value = _mock_client(get_val=[
            {"cycle_id": "cyc_1", "status": "active", "build_strategy": "fresh", "created_at": "2026-01-01"},
        ])
        result = runner.invoke(app, ["cycles", "list", "proj1"])
        assert result.exit_code == 0
        assert "cyc_1" in result.output

    @patch("squadops.cli.commands.cycles._get_client")
    def test_list_with_status(self, mock_get_client):
        mock_get_client.return_value = _mock_client(get_val=[])
        result = runner.invoke(app, ["cycles", "list", "proj1", "--status", "active"])
        assert result.exit_code == 0

        call_args = mock_get_client.return_value.get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert params["status"] == "active"

    @patch("squadops.cli.commands.cycles._get_client")
    def test_json_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client(get_val=[
            {"cycle_id": "cyc_1", "status": "active"},
        ])
        result = runner.invoke(app, ["--json", "cycles", "list", "proj1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestCyclesShow:
    @patch("squadops.cli.commands.cycles._get_client")
    def test_show(self, mock_get_client):
        mock_get_client.return_value = _mock_client(get_val={
            "cycle_id": "cyc_1",
            "project_id": "proj1",
            "status": "active",
        })
        result = runner.invoke(app, ["cycles", "show", "proj1", "cyc_1"])
        assert result.exit_code == 0
        assert "cyc_1" in result.output


class TestCyclesCancel:
    @patch("squadops.cli.commands.cycles._get_client")
    def test_cancel(self, mock_get_client):
        mock_get_client.return_value = _mock_client(post_val={"status": "cancelled"})
        result = runner.invoke(app, ["cycles", "cancel", "proj1", "cyc_1"])
        assert result.exit_code == 0
        assert "cancelled" in result.output

    @patch("squadops.cli.commands.cycles._get_client")
    def test_cancel_conflict(self, mock_get_client):
        mock = MagicMock()
        mock.post.side_effect = CLIError("conflict", exit_codes.CONFLICT)
        mock_get_client.return_value = mock
        result = runner.invoke(app, ["cycles", "cancel", "proj1", "cyc_1"])
        assert result.exit_code == exit_codes.CONFLICT

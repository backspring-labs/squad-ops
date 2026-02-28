"""Tests for SIP-0076 expanded CLI gate decision flags (Phase 4).

Covers AC 5 (CLI level).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.commands.runs import app

pytestmark = [pytest.mark.domain_cli]

runner = CliRunner()


def _mock_config():
    config = MagicMock()
    config.api_base_url = "http://localhost:8001"
    config.token = "test-token"
    return config


class TestGateDecisionFlags:
    """All four decision flags produce correct API calls."""

    @patch("squadops.cli.commands.runs.load_config")
    @patch("squadops.cli.commands.runs.APIClient")
    def test_approve_flag(self, mock_client_cls, mock_config_fn):
        mock_config_fn.return_value = _mock_config()
        mock_client = MagicMock()
        mock_client.post.return_value = {"status": "ok"}
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["gate", "proj", "cyc", "run", "g1", "--approve"])
        assert result.exit_code == 0
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["decision"] == "approved"

    @patch("squadops.cli.commands.runs.load_config")
    @patch("squadops.cli.commands.runs.APIClient")
    def test_reject_flag(self, mock_client_cls, mock_config_fn):
        mock_config_fn.return_value = _mock_config()
        mock_client = MagicMock()
        mock_client.post.return_value = {"status": "ok"}
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["gate", "proj", "cyc", "run", "g1", "--reject"])
        assert result.exit_code == 0
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["decision"] == "rejected"

    @patch("squadops.cli.commands.runs.load_config")
    @patch("squadops.cli.commands.runs.APIClient")
    def test_with_refinements_flag(self, mock_client_cls, mock_config_fn):
        mock_config_fn.return_value = _mock_config()
        mock_client = MagicMock()
        mock_client.post.return_value = {"status": "ok"}
        mock_client_cls.return_value = mock_client

        result = runner.invoke(
            app, ["gate", "proj", "cyc", "run", "g1", "--with-refinements"]
        )
        assert result.exit_code == 0
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["decision"] == "approved_with_refinements"

    @patch("squadops.cli.commands.runs.load_config")
    @patch("squadops.cli.commands.runs.APIClient")
    def test_return_for_revision_flag(self, mock_client_cls, mock_config_fn):
        mock_config_fn.return_value = _mock_config()
        mock_client = MagicMock()
        mock_client.post.return_value = {"status": "ok"}
        mock_client_cls.return_value = mock_client

        result = runner.invoke(
            app, ["gate", "proj", "cyc", "run", "g1", "--return-for-revision"]
        )
        assert result.exit_code == 0
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["decision"] == "returned_for_revision"


class TestGateFlagMutualExclusion:
    """D20: Exactly one decision flag required."""

    def test_no_flag_exits_with_error(self):
        result = runner.invoke(app, ["gate", "proj", "cyc", "run", "g1"])
        assert result.exit_code == 2
        assert "must specify exactly one" in result.output

    def test_multiple_flags_exits_with_error(self):
        result = runner.invoke(
            app, ["gate", "proj", "cyc", "run", "g1", "--approve", "--reject"]
        )
        assert result.exit_code == 2
        assert "must specify exactly one" in result.output

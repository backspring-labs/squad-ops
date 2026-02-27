"""Tests for models CLI commands (SIP-0075 §2.4)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.main import app

pytestmark = [pytest.mark.domain_cli]

runner = CliRunner()


def _mock_client(get_val=None, post_val=None, delete_val=None):
    mock = MagicMock()
    if get_val is not None:
        mock.get.return_value = get_val
    if post_val is not None:
        mock.post.return_value = post_val
    if delete_val is not None:
        mock.delete.return_value = delete_val
    return mock


class TestModelsPulled:
    @patch("squadops.cli.commands.models._get_client")
    def test_pulled_table(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {
                    "name": "qwen2.5:7b",
                    "size_bytes": 4_000_000_000,
                    "modified_at": "2026-01-01T00:00:00Z",
                    "in_active_profile": True,
                    "used_by_active_profile": ["neo"],
                    "registry_spec": None,
                },
            ]
        )
        result = runner.invoke(app, ["models", "pulled"])
        assert result.exit_code == 0
        assert "qwen2.5:7b" in result.output

    @patch("squadops.cli.commands.models._get_client")
    def test_pulled_shows_active_marker(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {
                    "name": "qwen2.5:7b",
                    "size_bytes": 4_000_000_000,
                    "modified_at": "2026-01-01T00:00:00Z",
                    "in_active_profile": True,
                    "used_by_active_profile": ["neo"],
                    "registry_spec": None,
                },
            ]
        )
        result = runner.invoke(app, ["models", "pulled"])
        assert result.exit_code == 0
        assert "*" in result.output


class TestModelsPull:
    @patch("squadops.cli.commands.models._get_client")
    def test_pull_starts(self, mock_get_client):
        mock_client = _mock_client(
            post_val={"pull_id": "abc-123", "model_name": "qwen2.5:7b", "status": "pulling"},
        )
        # After POST, the poll GET returns complete
        mock_client.get.return_value = {
            "pull_id": "abc-123",
            "model_name": "qwen2.5:7b",
            "status": "complete",
            "error": None,
        }
        mock_get_client.return_value = mock_client
        result = runner.invoke(app, ["models", "pull", "qwen2.5:7b"])
        assert result.exit_code == 0
        assert "pulled successfully" in result.output


class TestModelsRemove:
    @patch("squadops.cli.commands.models._get_client")
    def test_remove_with_yes_flag(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            delete_val={"status": "deleted", "model_name": "qwen2.5:7b"},
        )
        result = runner.invoke(app, ["models", "remove", "qwen2.5:7b", "--yes"])
        assert result.exit_code == 0
        assert "deleted" in result.output

    def test_remove_abort(self):
        result = runner.invoke(app, ["models", "remove", "qwen2.5:7b"], input="n\n")
        assert result.exit_code != 0  # Abort

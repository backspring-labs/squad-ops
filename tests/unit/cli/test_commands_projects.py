"""
Unit tests for project commands (SIP-0065 §6.3).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app

runner = CliRunner()


def _mock_client(return_value):
    """Patch APIClient to return a mock with fixed get/post return values."""
    mock = MagicMock()
    mock.get.return_value = return_value
    return mock


class TestProjectsList:
    @patch("squadops.cli.commands.projects._get_client")
    def test_table_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client([
            {"project_id": "hello_squad", "name": "Hello Squad", "description": "Test project"},
        ])
        result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0
        assert "hello_squad" in result.output

    @patch("squadops.cli.commands.projects._get_client")
    def test_json_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client([
            {"project_id": "hello_squad", "name": "Hello Squad", "description": "Test"},
        ])
        result = runner.invoke(app, ["--json", "projects", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["project_id"] == "hello_squad"

    @patch("squadops.cli.commands.projects._get_client")
    def test_ls_alias(self, mock_get_client):
        mock_get_client.return_value = _mock_client([])
        result = runner.invoke(app, ["projects", "ls"])
        assert result.exit_code == 0

    @patch("squadops.cli.commands.projects._get_client")
    def test_quiet_mode(self, mock_get_client):
        mock_get_client.return_value = _mock_client([
            {"project_id": "p1", "name": "P1", "description": "D"},
        ])
        result = runner.invoke(app, ["--quiet", "projects", "list"])
        assert result.exit_code == 0
        assert "p1" in result.output


class TestProjectsShow:
    @patch("squadops.cli.commands.projects._get_client")
    def test_show(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            {"project_id": "hello_squad", "name": "Hello Squad", "description": "Test"}
        )
        result = runner.invoke(app, ["projects", "show", "hello_squad"])
        assert result.exit_code == 0
        assert "hello_squad" in result.output

    @patch("squadops.cli.commands.projects._get_client")
    def test_not_found(self, mock_get_client):
        mock = MagicMock()
        mock.get.side_effect = CLIError("not found", exit_codes.NOT_FOUND)
        mock_get_client.return_value = mock
        result = runner.invoke(app, ["projects", "show", "nope"])
        assert result.exit_code == exit_codes.NOT_FOUND

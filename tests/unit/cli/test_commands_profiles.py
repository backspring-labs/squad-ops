"""
Unit tests for squad profile commands (SIP-0065 §6.3).
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.main import app

runner = CliRunner()


def _mock_client(get_val=None, post_val=None):
    mock = MagicMock()
    if get_val is not None:
        mock.get.return_value = get_val
    if post_val is not None:
        mock.post.return_value = post_val
    return mock


class TestSquadProfilesList:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_list(self, mock_get_client):
        mock_get_client.return_value = _mock_client(get_val=[
            {"profile_id": "sp1", "name": "Default", "version": 1, "description": "Base"},
        ])
        result = runner.invoke(app, ["squad-profiles", "list"])
        assert result.exit_code == 0
        assert "sp1" in result.output


class TestSquadProfilesActive:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_active(self, mock_get_client):
        mock_get_client.return_value = _mock_client(get_val={
            "profile_id": "sp1",
            "name": "Default",
        })
        result = runner.invoke(app, ["squad-profiles", "active"])
        assert result.exit_code == 0
        assert "sp1" in result.output


class TestSquadProfilesSetActive:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_set_active(self, mock_get_client):
        mock_get_client.return_value = _mock_client(post_val={"status": "ok"})
        result = runner.invoke(app, ["squad-profiles", "set-active", "sp2"])
        assert result.exit_code == 0

        call_args = mock_get_client.return_value.post.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert body["profile_id"] == "sp2"

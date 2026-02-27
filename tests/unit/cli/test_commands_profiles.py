"""
Unit tests for squad profile commands (SIP-0065 §6.3, SIP-0075 CRUD).
"""

import tempfile
from unittest.mock import MagicMock, patch

import yaml
from typer.testing import CliRunner

from squadops.cli.main import app

runner = CliRunner()


def _mock_client(get_val=None, post_val=None, put_val=None, delete_val=None):
    mock = MagicMock()
    if get_val is not None:
        mock.get.return_value = get_val
    if post_val is not None:
        mock.post.return_value = post_val
    if put_val is not None:
        mock.put.return_value = put_val
    if delete_val is not None:
        mock.delete.return_value = delete_val
    return mock


class TestSquadProfilesList:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_list(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {
                    "profile_id": "sp1",
                    "name": "Default",
                    "version": 1,
                    "description": "Base",
                    "is_active": True,
                },
            ]
        )
        result = runner.invoke(app, ["squad-profiles", "list"])
        assert result.exit_code == 0
        assert "sp1" in result.output

    @patch("squadops.cli.commands.profiles._get_client")
    def test_list_shows_active_marker(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {
                    "profile_id": "sp1",
                    "name": "Default",
                    "version": 1,
                    "description": "Base",
                    "is_active": True,
                },
            ]
        )
        result = runner.invoke(app, ["squad-profiles", "list"])
        assert result.exit_code == 0
        assert "*" in result.output


class TestSquadProfilesActive:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_active(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val={
                "profile_id": "sp1",
                "name": "Default",
            }
        )
        result = runner.invoke(app, ["squad-profiles", "active"])
        assert result.exit_code == 0
        assert "sp1" in result.output


class TestSquadProfilesSetActive:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_set_active(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            post_val={"profile_id": "sp2", "is_active": True}
        )
        result = runner.invoke(app, ["squad-profiles", "set-active", "sp2"])
        assert result.exit_code == 0


class TestSquadProfilesCreate:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_create_from_yaml(self, mock_get_client):
        spec = {
            "name": "Test Profile",
            "description": "Test desc",
            "agents": [
                {"agent_id": "neo", "role": "dev", "model": "qwen2.5:7b"},
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(spec, f)
            f.flush()
            mock_get_client.return_value = _mock_client(
                post_val={"profile_id": "test-profile", "warnings": []}
            )
            result = runner.invoke(app, ["squad-profiles", "create", "--file", f.name])
        assert result.exit_code == 0
        assert "test-profile" in result.output

    def test_create_missing_file(self):
        result = runner.invoke(
            app, ["squad-profiles", "create", "--file", "/nonexistent/profile.yaml"]
        )
        assert result.exit_code != 0

    @patch("squadops.cli.commands.profiles._get_client")
    def test_create_invalid_yaml(self, mock_get_client):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"invalid": "no name or agents"}, f)
            f.flush()
            result = runner.invoke(app, ["squad-profiles", "create", "--file", f.name])
        assert result.exit_code != 0


class TestSquadProfilesClone:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_clone(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            post_val={"profile_id": "cloned-squad", "warnings": []}
        )
        result = runner.invoke(
            app, ["squad-profiles", "clone", "full-squad", "--name", "Cloned Squad"]
        )
        assert result.exit_code == 0
        assert "cloned-squad" in result.output


class TestSquadProfilesActivate:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_activate(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            post_val={"profile_id": "full-squad", "is_active": True}
        )
        result = runner.invoke(app, ["squad-profiles", "activate", "full-squad"])
        assert result.exit_code == 0
        assert "full-squad" in result.output


class TestSquadProfilesDelete:
    @patch("squadops.cli.commands.profiles._get_client")
    def test_delete(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            delete_val={"status": "deleted", "profile_id": "old-squad"}
        )
        result = runner.invoke(app, ["squad-profiles", "delete", "old-squad"])
        assert result.exit_code == 0
        assert "old-squad" in result.output

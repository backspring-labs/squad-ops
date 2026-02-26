"""
Unit tests for request-profiles commands (SIP-0074 §5.10).
"""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from squadops.cli.main import app

runner = CliRunner()

_SAMPLE_PROFILES = [
    {
        "name": "default",
        "description": "Default profile",
        "prompts": {},
        "defaults": {"build_strategy": "fresh"},
    },
    {
        "name": "fullstack-fastapi-react",
        "description": "Fullstack profile",
        "prompts": {
            "build_strategy": {"label": "Build Strategy", "choices": ["fresh", "incremental"]}
        },
        "defaults": {"build_strategy": "fresh", "dev_capability": "fullstack_fastapi_react"},
    },
]

_SAMPLE_DETAIL = _SAMPLE_PROFILES[0]


def _mock_client(return_value):
    mock = MagicMock()
    mock.get.return_value = return_value
    return mock


class TestRequestProfilesList:
    @patch("squadops.cli.commands.request_profiles._get_client")
    def test_table_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client(_SAMPLE_PROFILES)
        result = runner.invoke(app, ["request-profiles", "list"])
        assert result.exit_code == 0
        assert "default" in result.output

    @patch("squadops.cli.commands.request_profiles._get_client")
    def test_json_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client(_SAMPLE_PROFILES)
        result = runner.invoke(app, ["--json", "request-profiles", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "default"

    @patch("squadops.cli.commands.request_profiles._get_client")
    def test_ls_alias(self, mock_get_client):
        mock_get_client.return_value = _mock_client([])
        result = runner.invoke(app, ["request-profiles", "ls"])
        assert result.exit_code == 0

    @patch("squadops.cli.commands.request_profiles._get_client")
    def test_shows_prompt_count(self, mock_get_client):
        mock_get_client.return_value = _mock_client(_SAMPLE_PROFILES)
        result = runner.invoke(app, ["request-profiles", "list"])
        assert result.exit_code == 0
        # fullstack profile has 1 prompt
        assert "1" in result.output


class TestRequestProfilesShow:
    @patch("squadops.cli.commands.request_profiles._get_client")
    def test_show_detail(self, mock_get_client):
        mock_get_client.return_value = _mock_client(_SAMPLE_DETAIL)
        result = runner.invoke(app, ["request-profiles", "show", "default"])
        assert result.exit_code == 0
        assert "default" in result.output

    @patch("squadops.cli.commands.request_profiles._get_client")
    def test_json_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client(_SAMPLE_DETAIL)
        result = runner.invoke(app, ["--json", "request-profiles", "show", "default"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "default"

    @patch("squadops.cli.commands.request_profiles._get_client")
    def test_cat_alias(self, mock_get_client):
        mock_get_client.return_value = _mock_client(_SAMPLE_DETAIL)
        result = runner.invoke(app, ["request-profiles", "cat", "default"])
        assert result.exit_code == 0

    @patch("squadops.cli.commands.request_profiles._get_client")
    def test_error_handling(self, mock_get_client):
        from squadops.cli.client import CLIError

        mock = MagicMock()
        mock.get.side_effect = CLIError("Not found", exit_code=1)
        mock_get_client.return_value = mock
        result = runner.invoke(app, ["request-profiles", "show", "nonexistent"])
        assert result.exit_code == 1

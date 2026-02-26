"""
Unit tests for models commands (SIP-0074 §5.10).
"""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from squadops.cli.main import app

runner = CliRunner()

_SAMPLE_MODELS = [
    {
        "name": "qwen2.5:7b",
        "context_window": 8192,
        "default_max_completion": 4096,
    },
    {
        "name": "qwen2.5:72b",
        "context_window": 131072,
        "default_max_completion": 16384,
    },
]


def _mock_client(return_value):
    mock = MagicMock()
    mock.get.return_value = return_value
    return mock


class TestModelsList:
    @patch("squadops.cli.commands.models._get_client")
    def test_table_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client(_SAMPLE_MODELS)
        result = runner.invoke(app, ["models", "list"])
        assert result.exit_code == 0
        assert "qwen2.5:7b" in result.output
        assert "8,192" in result.output

    @patch("squadops.cli.commands.models._get_client")
    def test_json_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client(_SAMPLE_MODELS)
        result = runner.invoke(app, ["--json", "models", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "qwen2.5:7b"

    @patch("squadops.cli.commands.models._get_client")
    def test_ls_alias(self, mock_get_client):
        mock_get_client.return_value = _mock_client([])
        result = runner.invoke(app, ["models", "ls"])
        assert result.exit_code == 0

    @patch("squadops.cli.commands.models._get_client")
    def test_error_handling(self, mock_get_client):
        from squadops.cli.client import CLIError

        mock = MagicMock()
        mock.get.side_effect = CLIError("Connection refused", exit_code=1)
        mock_get_client.return_value = mock
        result = runner.invoke(app, ["models", "list"])
        assert result.exit_code == 1

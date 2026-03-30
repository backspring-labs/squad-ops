"""
Unit tests for meta commands: version, status (SIP-0065 §6.3).
"""

import json
from importlib.metadata import version as pkg_version
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app

runner = CliRunner()

MOCK_CONFIG = MagicMock(
    base_url="http://localhost:8001",
    timeout=30,
)

INFRA_RESPONSE = [
    {
        "component": "RabbitMQ",
        "type": "Message Broker",
        "status": "online",
        "version": "3.12.1",
        "notes": "0 messages",
    },
    {
        "component": "PostgreSQL",
        "type": "Relational DB",
        "status": "online",
        "version": "15.3",
        "notes": "5 agents",
    },
]

AGENTS_RESPONSE = [
    {
        "agent_id": "max",
        "agent_name": "Max",
        "role": "Task Lead",
        "network_status": "online",
        "lifecycle_state": "READY",
        "version": "0.9.3",
        "last_seen": "2026-02-09T14:00:00Z",
    },
    {
        "agent_id": "neo",
        "agent_name": "Neo",
        "role": "Developer",
        "network_status": "online",
        "lifecycle_state": "WORKING",
        "version": "0.9.3",
        "last_seen": "2026-02-09T14:00:00Z",
    },
]


def _mock_client_get(path):
    """Simulate APIClient.get() for health + infra + agents."""
    if path == "/health":
        return {"status": "healthy", "service": "runtime-api", "version": "0.9.3"}
    if path == "/health/infra":
        return INFRA_RESPONSE
    if path == "/health/agents":
        return AGENTS_RESPONSE
    return {}


def _mock_client_get_health_only(path):
    """Simulate APIClient.get() where /health works but /health/infra and /health/agents fail."""
    if path == "/health":
        return {"status": "healthy", "version": "0.9.3"}
    raise CLIError(f"Error: {path} unavailable", exit_codes.NETWORK_ERROR)


class TestVersionFlag:
    def test_prints_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert pkg_version("squadops") in result.output

    def test_short_flag(self):
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert "squadops" in result.output


class TestStatusCommand:
    @patch("squadops.cli.commands.meta.APIClient")
    @patch("squadops.cli.commands.meta.load_config")
    def test_connected_with_infra_and_agents(self, mock_config, mock_client_cls):
        mock_config.return_value = MOCK_CONFIG
        mock_client = MagicMock()
        mock_client.get.side_effect = _mock_client_get
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "connected" in result.output
        # Infra table rendered
        assert "RabbitMQ" in result.output
        assert "PostgreSQL" in result.output
        # Agents table rendered
        assert "Max" in result.output
        assert "Neo" in result.output

    @patch("squadops.cli.commands.meta.APIClient")
    @patch("squadops.cli.commands.meta.load_config")
    def test_connected_health_endpoints_unavailable(self, mock_config, mock_client_cls):
        """Runtime API reachable but /health/infra and /health/agents fail."""
        mock_config.return_value = MOCK_CONFIG
        mock_client = MagicMock()
        mock_client.get.side_effect = _mock_client_get_health_only
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "connected" in result.output
        assert "unavailable" in result.output

    @patch("squadops.cli.commands.meta.APIClient")
    @patch("squadops.cli.commands.meta.load_config")
    def test_unreachable(self, mock_config, mock_client_cls):
        mock_config.return_value = MOCK_CONFIG
        mock_client_cls.return_value.get.side_effect = CLIError(
            "Error: cannot reach http://localhost:8001", exit_codes.NETWORK_ERROR
        )

        result = runner.invoke(app, ["status"])
        assert result.exit_code == exit_codes.NETWORK_ERROR

    @patch("squadops.cli.commands.meta.APIClient")
    @patch("squadops.cli.commands.meta.load_config")
    def test_json_format_combined(self, mock_config, mock_client_cls):
        mock_config.return_value = MOCK_CONFIG
        mock_client = MagicMock()
        mock_client.get.side_effect = _mock_client_get
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["--json", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["runtime"]["status"] == "connected"
        assert len(data["infrastructure"]) == 2
        assert len(data["agents"]) == 2
        assert data["infrastructure"][0]["component"] == "RabbitMQ"
        assert data["agents"][0]["agent_id"] == "max"

    @patch("squadops.cli.commands.meta.APIClient")
    @patch("squadops.cli.commands.meta.load_config")
    def test_json_format_health_endpoints_unavailable(self, mock_config, mock_client_cls):
        """JSON output includes null for infra/agents when health endpoints fail."""
        mock_config.return_value = MOCK_CONFIG
        mock_client = MagicMock()
        mock_client.get.side_effect = _mock_client_get_health_only
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["--json", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["runtime"]["status"] == "connected"
        assert data["infrastructure"] is None
        assert data["agents"] is None

    @patch("squadops.cli.commands.meta.APIClient")
    @patch("squadops.cli.commands.meta.load_config")
    def test_quiet_mode(self, mock_config, mock_client_cls):
        mock_config.return_value = MOCK_CONFIG
        mock_client = MagicMock()
        mock_client.get.side_effect = _mock_client_get
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["--quiet", "status"])
        assert result.exit_code == 0
        # Quiet mode uses tab-separated values, no Rich chrome
        assert "connected" in result.output

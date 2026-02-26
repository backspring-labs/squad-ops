"""
Unit tests for CLI API client (SIP-0065 D1, D4, D10).

Tests error-to-exit-code mapping, auth headers, injected client, User-Agent.
"""

from unittest.mock import MagicMock

import httpx
import pytest

from squadops.cli import exit_codes
from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import CLIConfig

# =============================================================================
# Client construction (D10)
# =============================================================================


class TestAPIClientConstruction:
    """APIClient accepts injected httpx.Client (D10)."""

    def test_uses_injected_client(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_client.request.return_value = mock_response
        api = APIClient(CLIConfig(), client=mock_client)
        result = api.get("/test")
        mock_client.request.assert_called_once()
        assert result == {"ok": True}

    def test_creates_own_client_when_none_injected(self, monkeypatch):
        monkeypatch.delenv("SQUADOPS_TOKEN", raising=False)
        api = APIClient(CLIConfig())
        # Should have created an httpx.Client internally
        assert isinstance(api._client, httpx.Client)
        api.close()

    def test_user_agent_header(self, monkeypatch):
        monkeypatch.delenv("SQUADOPS_TOKEN", raising=False)
        api = APIClient(CLIConfig())
        from squadops import __version__

        assert api._client.headers["user-agent"] == f"squadops-cli/{__version__}"
        api.close()

    def test_auth_header_when_token_provided(self, monkeypatch):
        monkeypatch.setenv("SQUADOPS_TOKEN", "test_token_123")
        api = APIClient(CLIConfig())
        assert api._client.headers["authorization"] == "Bearer test_token_123"
        api.close()

    def test_no_auth_header_when_no_token(self, monkeypatch):
        monkeypatch.delenv("SQUADOPS_TOKEN", raising=False)
        monkeypatch.setattr("squadops.cli.auth.load_cached_token", lambda: None)
        api = APIClient(CLIConfig())
        assert "authorization" not in api._client.headers
        api.close()

    def test_token_flag_overrides_env(self, monkeypatch):
        monkeypatch.setenv("SQUADOPS_TOKEN", "env_token")
        api = APIClient(CLIConfig(), token_flag="flag_token")
        assert api._client.headers["authorization"] == "Bearer flag_token"
        api.close()


# =============================================================================
# Error-to-exit-code mapping
# =============================================================================


def _make_api_client_with_response(status_code, body=None, headers=None):
    """Create APIClient with a mock client that returns a fixed response."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.headers = headers or {}
    mock_response.text = ""
    if body is not None:
        mock_response.json.return_value = body
    else:
        mock_response.json.side_effect = Exception("no json")
        mock_response.text = "raw error text"
    mock_client.request.return_value = mock_response
    return APIClient(CLIConfig(), client=mock_client)


class TestErrorMapping:
    """HTTP status codes map to correct exit codes."""

    def test_401_maps_to_auth_error(self):
        api = _make_api_client_with_response(401, {"error": {"message": "invalid token"}})
        with pytest.raises(CLIError) as exc_info:
            api.get("/test")
        assert exc_info.value.exit_code == exit_codes.AUTH_ERROR
        assert "authentication failed" in str(exc_info.value)

    def test_403_maps_to_auth_error(self):
        api = _make_api_client_with_response(403, {"error": {"message": "forbidden"}})
        with pytest.raises(CLIError) as exc_info:
            api.get("/test")
        assert exc_info.value.exit_code == exit_codes.AUTH_ERROR

    def test_404_maps_to_not_found(self):
        api = _make_api_client_with_response(404, {"error": {"message": "project not found"}})
        with pytest.raises(CLIError) as exc_info:
            api.get("/test")
        assert exc_info.value.exit_code == exit_codes.NOT_FOUND
        assert "not found" in str(exc_info.value)

    def test_409_maps_to_conflict(self):
        api = _make_api_client_with_response(
            409, {"error": {"message": "illegal state transition"}}
        )
        with pytest.raises(CLIError) as exc_info:
            api.post("/test")
        assert exc_info.value.exit_code == exit_codes.CONFLICT
        assert "conflict" in str(exc_info.value)

    def test_422_maps_to_validation_error(self):
        api = _make_api_client_with_response(
            422, {"error": {"message": "invalid field", "details": [{"loc": ["body"]}]}}
        )
        with pytest.raises(CLIError) as exc_info:
            api.post("/test")
        assert exc_info.value.exit_code == exit_codes.VALIDATION_ERROR
        assert "validation failed" in str(exc_info.value)

    def test_413_maps_to_validation_error(self):
        api = _make_api_client_with_response(413)
        with pytest.raises(CLIError) as exc_info:
            api.post("/test")
        assert exc_info.value.exit_code == exit_codes.VALIDATION_ERROR
        assert "file too large" in str(exc_info.value)

    def test_500_maps_to_general_error(self):
        api = _make_api_client_with_response(500, {"error": {"message": "internal error"}})
        with pytest.raises(CLIError) as exc_info:
            api.get("/test")
        assert exc_info.value.exit_code == exit_codes.GENERAL_ERROR

    def test_request_id_appended_to_message(self):
        api = _make_api_client_with_response(
            404,
            {"error": {"message": "not found"}},
            headers={"x-request-id": "req-abc-123"},
        )
        with pytest.raises(CLIError) as exc_info:
            api.get("/test")
        assert "req-abc-123" in str(exc_info.value)

    def test_json_parse_failure(self):
        api = _make_api_client_with_response(200, body=None)
        with pytest.raises(CLIError) as exc_info:
            api.get("/test")
        assert exc_info.value.exit_code == exit_codes.GENERAL_ERROR
        assert "unexpected response" in str(exc_info.value)


# =============================================================================
# Network errors
# =============================================================================


class TestNetworkErrors:
    """Network errors map to exit code 20."""

    def test_connect_error(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request.side_effect = httpx.ConnectError("connection refused")
        api = APIClient(CLIConfig(), client=mock_client)
        with pytest.raises(CLIError) as exc_info:
            api.get("/test")
        assert exc_info.value.exit_code == exit_codes.NETWORK_ERROR
        assert "cannot reach" in str(exc_info.value)

    def test_timeout_error(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request.side_effect = httpx.ReadTimeout("timed out")
        api = APIClient(CLIConfig(), client=mock_client)
        with pytest.raises(CLIError) as exc_info:
            api.get("/test")
        assert exc_info.value.exit_code == exit_codes.NETWORK_ERROR
        assert "timed out" in str(exc_info.value)

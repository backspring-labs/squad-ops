"""
Unit tests for CLI auth commands (login, logout, whoami).
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.auth import CachedToken, save_token
from squadops.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_token_dir(tmp_path, monkeypatch):
    """Route all token I/O to tmp_path so tests are isolated."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


@pytest.fixture()
def saved_token(tmp_path):
    """Save a valid token and return it."""
    token = CachedToken(
        access_token="test_access",
        refresh_token="test_refresh",
        expires_at=time.time() + 300,
        token_endpoint="http://kc/token",
        client_id="squadops-cli",
        grant_type="password",
    )
    save_token(token)
    return token


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


class TestLoginCommand:
    @patch("squadops.cli.commands.auth.password_login")
    def test_password_login_success(self, mock_login):
        mock_login.return_value = CachedToken(
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 300,
            token_endpoint="http://kc/token",
            client_id="squadops-cli",
            grant_type="password",
        )
        result = runner.invoke(app, ["login", "-u", "admin", "-p", "pass"])
        assert result.exit_code == 0
        assert "Login successful" in result.output
        mock_login.assert_called_once()

    @patch("squadops.cli.commands.auth.client_credentials_login")
    def test_client_credentials_login_success(self, mock_login):
        mock_login.return_value = CachedToken(
            access_token="tok",
            refresh_token=None,
            expires_at=time.time() + 300,
            token_endpoint="http://kc/token",
            client_id="svc",
            grant_type="client_credentials",
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--client-credentials",
                "--client-id",
                "svc",
                "--client-secret",
                "sec",
            ],
        )
        assert result.exit_code == 0
        assert "Login successful" in result.output

    def test_client_credentials_requires_secret(self):
        result = runner.invoke(app, ["login", "--client-credentials"])
        assert result.exit_code == exit_codes.GENERAL_ERROR

    def test_password_login_requires_username(self):
        result = runner.invoke(app, ["login"])
        assert result.exit_code == exit_codes.GENERAL_ERROR

    @patch("squadops.cli.commands.auth.password_login")
    def test_login_invalid_credentials(self, mock_login):
        mock_login.side_effect = httpx.HTTPStatusError(
            "401",
            request=httpx.Request("POST", "http://kc/token"),
            response=httpx.Response(401),
        )
        result = runner.invoke(app, ["login", "-u", "admin", "-p", "bad"])
        assert result.exit_code == exit_codes.AUTH_ERROR
        assert "invalid credentials" in result.output

    @patch("squadops.cli.commands.auth.password_login")
    def test_login_connection_refused(self, mock_login):
        mock_login.side_effect = httpx.ConnectError("refused")
        result = runner.invoke(app, ["login", "-u", "admin", "-p", "pass"])
        assert result.exit_code == exit_codes.NETWORK_ERROR

    @patch("squadops.cli.commands.auth.password_login")
    def test_login_timeout(self, mock_login):
        mock_login.side_effect = httpx.ReadTimeout("timeout")
        result = runner.invoke(app, ["login", "-u", "admin", "-p", "pass"])
        assert result.exit_code == exit_codes.NETWORK_ERROR

    @patch("squadops.cli.commands.auth.password_login")
    def test_login_json_output(self, mock_login):
        mock_login.return_value = CachedToken(
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 300,
            token_endpoint="http://kc/token",
            client_id="squadops-cli",
            grant_type="password",
        )
        result = runner.invoke(app, ["--json", "login", "-u", "admin", "-p", "pass"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "authenticated"
        assert data["grant_type"] == "password"


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


class TestLogoutCommand:
    def test_logout_removes_token(self, saved_token):
        result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0
        assert "Logged out" in result.output

    def test_logout_no_token(self):
        result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0
        assert "No cached token" in result.output

    def test_logout_json_output(self, saved_token):
        result = runner.invoke(app, ["--json", "logout"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "logged_out"
        assert data["token_removed"] is True


# ---------------------------------------------------------------------------
# auth whoami
# ---------------------------------------------------------------------------


class TestWhoamiCommand:
    def test_whoami_authenticated(self, saved_token):
        result = runner.invoke(app, ["auth", "whoami"])
        assert result.exit_code == 0
        assert "authenticated" in result.output

    def test_whoami_no_token(self):
        result = runner.invoke(app, ["auth", "whoami"])
        assert result.exit_code == exit_codes.AUTH_ERROR

    def test_whoami_expired_token(self):
        token = CachedToken(
            access_token="old",
            refresh_token=None,
            expires_at=time.time() - 100,
            token_endpoint="http://kc/token",
            client_id="cli",
            grant_type="password",
        )
        save_token(token)
        result = runner.invoke(app, ["auth", "whoami"])
        assert result.exit_code == exit_codes.AUTH_ERROR
        assert "expired" in result.output

    def test_whoami_json_output(self, saved_token):
        result = runner.invoke(app, ["--json", "auth", "whoami"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "authenticated"
        assert data["grant_type"] == "password"

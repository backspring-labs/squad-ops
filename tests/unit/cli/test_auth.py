"""
Unit tests for CLI token storage and OIDC helpers (auth.py).
"""

from __future__ import annotations

import json
import stat
import time
from unittest.mock import patch

import httpx
import pytest

from squadops.cli.auth import (
    CachedToken,
    _build_token_endpoint,
    _parse_token_response,
    clear_token,
    client_credentials_login,
    is_expired,
    load_cached_token,
    password_login,
    refresh_access_token,
    save_token,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def token_dir(tmp_path, monkeypatch):
    """Set XDG_CONFIG_HOME so token files land in tmp_path."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "squadops"


@pytest.fixture()
def sample_token() -> CachedToken:
    return CachedToken(
        access_token="access123",
        refresh_token="refresh456",
        expires_at=time.time() + 300,
        token_endpoint="http://localhost:8180/realms/squadops-dev/protocol/openid-connect/token",
        client_id="squadops-cli",
        grant_type="password",
    )


# ---------------------------------------------------------------------------
# CachedToken dataclass
# ---------------------------------------------------------------------------

class TestCachedToken:
    def test_fields(self, sample_token):
        assert sample_token.access_token == "access123"
        assert sample_token.refresh_token == "refresh456"
        assert sample_token.client_id == "squadops-cli"
        assert sample_token.grant_type == "password"

    def test_no_refresh_token(self):
        t = CachedToken(
            access_token="a",
            refresh_token=None,
            expires_at=0.0,
            token_endpoint="http://kc/token",
            client_id="cli",
            grant_type="client_credentials",
        )
        assert t.refresh_token is None


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

class TestSaveAndLoad:
    def test_round_trip(self, token_dir, sample_token):
        save_token(sample_token)
        loaded = load_cached_token()
        assert loaded is not None
        assert loaded.access_token == sample_token.access_token
        assert loaded.refresh_token == sample_token.refresh_token
        assert loaded.client_id == sample_token.client_id

    def test_creates_directory(self, token_dir, sample_token):
        assert not token_dir.exists()
        save_token(sample_token)
        assert token_dir.exists()

    def test_file_permissions_0600(self, token_dir, sample_token):
        save_token(sample_token)
        path = token_dir / "token.json"
        mode = path.stat().st_mode & 0o777
        assert mode == stat.S_IRUSR | stat.S_IWUSR  # 0o600

    def test_load_returns_none_when_missing(self, token_dir):
        assert load_cached_token() is None

    def test_load_returns_none_on_malformed_json(self, token_dir):
        token_dir.mkdir(parents=True, exist_ok=True)
        (token_dir / "token.json").write_text("not-json!!!")
        assert load_cached_token() is None

    def test_load_returns_none_on_missing_keys(self, token_dir):
        token_dir.mkdir(parents=True, exist_ok=True)
        (token_dir / "token.json").write_text(json.dumps({"access_token": "x"}))
        assert load_cached_token() is None


class TestClearToken:
    def test_removes_existing_file(self, token_dir, sample_token):
        save_token(sample_token)
        assert clear_token() is True
        assert not (token_dir / "token.json").exists()

    def test_returns_false_when_no_file(self, token_dir):
        assert clear_token() is False


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------

class TestIsExpired:
    def test_not_expired(self, sample_token):
        assert is_expired(sample_token) is False

    def test_expired(self):
        t = CachedToken(
            access_token="a",
            refresh_token=None,
            expires_at=time.time() - 100,
            token_endpoint="http://kc/token",
            client_id="cli",
            grant_type="password",
        )
        assert is_expired(t) is True

    def test_margin_seconds(self):
        # Token expires in 10s but margin is 30s -> expired
        t = CachedToken(
            access_token="a",
            refresh_token=None,
            expires_at=time.time() + 10,
            token_endpoint="http://kc/token",
            client_id="cli",
            grant_type="password",
        )
        assert is_expired(t, margin_seconds=30) is True
        assert is_expired(t, margin_seconds=5) is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestBuildTokenEndpoint:
    def test_default(self):
        url = _build_token_endpoint("http://localhost:8180", "squadops-dev")
        assert url == (
            "http://localhost:8180/realms/squadops-dev"
            "/protocol/openid-connect/token"
        )


class TestParseTokenResponse:
    def test_parses_response(self):
        data = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 600,
        }
        t = _parse_token_response(data, "http://kc/token", "cli", "password")
        assert t.access_token == "tok"
        assert t.refresh_token == "ref"
        assert t.expires_at > time.time()
        assert t.grant_type == "password"

    def test_no_refresh_token_in_response(self):
        data = {"access_token": "tok", "expires_in": 300}
        t = _parse_token_response(data, "http://kc/token", "cli", "client_credentials")
        assert t.refresh_token is None


# ---------------------------------------------------------------------------
# OIDC login flows (mocked httpx)
# ---------------------------------------------------------------------------

def _mock_token_response(status_code=200, json_data=None):
    """Build a mock httpx.Response."""
    json_data = json_data or {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_in": 300,
    }
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("POST", "http://kc/token"),
    )


class TestPasswordLogin:
    @patch("squadops.cli.auth.httpx.post")
    def test_success(self, mock_post):
        mock_post.return_value = _mock_token_response()
        t = password_login("http://kc/token", "cli", "user", "pass")
        assert t.access_token == "new_access"
        assert t.grant_type == "password"
        mock_post.assert_called_once()
        call_data = mock_post.call_args.kwargs["data"]
        assert call_data["grant_type"] == "password"
        assert call_data["username"] == "user"

    @patch("squadops.cli.auth.httpx.post")
    def test_401_raises(self, mock_post):
        mock_post.return_value = _mock_token_response(status_code=401, json_data={})
        with pytest.raises(httpx.HTTPStatusError):
            password_login("http://kc/token", "cli", "user", "bad")


class TestClientCredentialsLogin:
    @patch("squadops.cli.auth.httpx.post")
    def test_success(self, mock_post):
        mock_post.return_value = _mock_token_response()
        t = client_credentials_login("http://kc/token", "svc", "secret")
        assert t.access_token == "new_access"
        assert t.grant_type == "client_credentials"
        call_data = mock_post.call_args.kwargs["data"]
        assert call_data["grant_type"] == "client_credentials"
        assert call_data["client_secret"] == "secret"


class TestRefreshAccessToken:
    @patch("squadops.cli.auth.httpx.post")
    def test_success(self, mock_post, sample_token):
        mock_post.return_value = _mock_token_response()
        result = refresh_access_token(sample_token)
        assert result is not None
        assert result.access_token == "new_access"

    def test_no_refresh_token_returns_none(self):
        t = CachedToken(
            access_token="a",
            refresh_token=None,
            expires_at=0.0,
            token_endpoint="http://kc/token",
            client_id="cli",
            grant_type="password",
        )
        assert refresh_access_token(t) is None

    @patch("squadops.cli.auth.httpx.post")
    def test_http_error_returns_none(self, mock_post, sample_token):
        mock_post.return_value = _mock_token_response(status_code=400, json_data={})
        result = refresh_access_token(sample_token)
        assert result is None

    @patch("squadops.cli.auth.httpx.post")
    def test_connect_error_returns_none(self, mock_post, sample_token):
        mock_post.side_effect = httpx.ConnectError("refused")
        result = refresh_access_token(sample_token)
        assert result is None

"""Tests for the SquadOps Console Auth BFF (Backend-for-Frontend).

Exercises the PKCE authorization code flow routes: login, callback,
refresh, and logout, plus OIDC hardening (nonce, ID token validation,
URL encoding, session store, cookie security, loop-breaker, CORS).
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

# Add console/app to sys.path so we can import the auth_bff module
sys.path.insert(0, str(Path(__file__).parents[3] / "console" / "app"))
import auth_bff  # noqa: E402
from auth_bff import (  # noqa: E402
    _LOGIN_TTL_SECONDS,
    _SESSION_TTL_SECONDS,
    _decode_jwt_payload,
    configure,
    router,
)
from session_store import MemorySessionStore  # noqa: E402

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_test_id_token(
    *,
    nonce: str = "test-nonce",
    aud: str = "test-client",
    iss: str = "http://keycloak-test:8080/realms/test",
    exp: float | None = None,
    extra: dict | None = None,
) -> str:
    """Build a minimal JWT with the given claims (no signature verification needed)."""
    if exp is None:
        exp = time.time() + 300  # 5 minutes from now

    payload = {"iss": iss, "aud": aud, "exp": exp, "nonce": nonce, "sub": "test-user"}
    if extra:
        payload.update(extra)

    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    body = base64.urlsafe_b64encode(json.dumps(payload).encode())
    sig = base64.urlsafe_b64encode(b"fake-signature")
    return (
        f"{header.rstrip(b'=').decode()}.{body.rstrip(b'=').decode()}.{sig.rstrip(b'=').decode()}"
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def _clear_stores():
    """Inject fresh MemorySessionStores and configure auth BFF before each test."""
    session_store = MemorySessionStore()
    login_store = MemorySessionStore()

    configure(
        keycloak_url="http://keycloak-test:8080/realms/test",
        keycloak_public_url="http://localhost:8180/realms/test",
        client_id="test-client",
        redirect_uri="http://localhost:4040/auth/callback",
        session_store=session_store,
        login_store=login_store,
        secure_cookies=False,
    )

    yield

    await session_store.close()
    await login_store.close()
    # Close the httpx client created by configure()
    if auth_bff._http_client:
        await auth_bff._http_client.aclose()
        auth_bff._http_client = None


@pytest.fixture()
def auth_app() -> FastAPI:
    """Create a test FastAPI app with the auth BFF router mounted."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture()
async def client(auth_app: FastAPI) -> AsyncClient:
    """Create an httpx async client for the test app."""
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ── Original Route Tests ──────────────────────────────────────────────────────


@pytest.mark.auth
class TestAuthBFF:
    """Tests for Auth BFF routes."""

    async def test_login_returns_auth_url(self, client: AsyncClient):
        """GET /auth/login returns JSON with an auth_url containing expected params."""
        resp = await client.get("/auth/login")
        assert resp.status_code == 200
        body = resp.json()
        assert "auth_url" in body
        auth_url = body["auth_url"]
        assert "state=" in auth_url
        assert "code_challenge=" in auth_url
        assert "client_id=test-client" in auth_url
        assert "code_challenge_method=S256" in auth_url

    async def test_login_creates_pending_login(self, client: AsyncClient):
        """After GET /auth/login, login store has exactly one entry."""
        await client.get("/auth/login")
        count = await auth_bff._login_store.count()
        assert count == 1

    async def test_callback_invalid_state_redirects_to_root(self, client: AsyncClient):
        """GET /auth/callback with unknown state redirects to / for fresh login."""
        resp = await client.get(
            "/auth/callback",
            params={"code": "abc", "state": "bad-state"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["location"] == "/"

    async def test_callback_success_redirects_and_sets_cookie(self, client: AsyncClient):
        """Successful callback exchanges code, sets session cookie, redirects to /."""
        # Create a pending login directly in the store
        nonce = "test-nonce-123"
        state = "valid-state"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "test-verifier", "nonce": nonce},
            _LOGIN_TTL_SECONDS,
        )

        id_token = _make_test_id_token(nonce=nonce)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "id_token": id_token,
            "expires_in": 300,
            "token_type": "Bearer",
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )

        # Callback redirects to shell root
        assert resp.status_code == 302
        assert resp.headers["location"] == "/"

        # Verify session cookie was set
        cookies = resp.headers.get_list("set-cookie")
        assert any("session_id=" in c for c in cookies)

        # Verify a session was stored
        session_count = await auth_bff._session_store.count()
        assert session_count == 1

    async def test_refresh_no_session_returns_401(self, client: AsyncClient):
        """POST /auth/refresh without a session cookie returns 401."""
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401
        assert "No valid session" in resp.json()["detail"]

    async def test_refresh_success(self, client: AsyncClient):
        """POST /auth/refresh with valid session returns new access token."""
        session_id = "test-session-id"
        await auth_bff._session_store.set(
            session_id,
            {"refresh_token": "old-refresh-token"},
            _SESSION_TTL_SECONDS,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 300,
            "token_type": "Bearer",
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.post("/auth/refresh", cookies={"session_id": session_id})

        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "new-access-token"

        # Verify stored refresh token was updated
        session = await auth_bff._session_store.get(session_id)
        assert session["refresh_token"] == "new-refresh-token"

    async def test_logout_clears_session(self, client: AsyncClient):
        """POST /auth/logout removes the session from the store."""
        session_id = "logout-session"
        await auth_bff._session_store.set(
            session_id,
            {"refresh_token": "refresh-to-revoke"},
            _SESSION_TTL_SECONDS,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.post("/auth/logout", cookies={"session_id": session_id})

        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"
        session = await auth_bff._session_store.get(session_id)
        assert session is None

    async def test_logout_without_session_succeeds(self, client: AsyncClient):
        """POST /auth/logout without a session still returns 200."""
        resp = await client.post("/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"

    async def test_logout_accepts_get(self, client: AsyncClient):
        """GET /auth/logout works (for loop-breaker error page link)."""
        resp = await client.get("/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"


# ── Phase 1: Session Store Tests ─────────────────────────────────────────────


@pytest.mark.auth
class TestSessionStore:
    """Tests for MemorySessionStore behavior."""

    async def test_get_set_roundtrip(self):
        """set() then get() returns the stored data."""
        store = MemorySessionStore()
        await store.set("k1", {"foo": "bar"}, ttl=60)
        result = await store.get("k1")
        assert result == {"foo": "bar"}

    async def test_get_expired_returns_none(self):
        """get() returns None for expired entries."""
        store = MemorySessionStore()
        await store.set("k1", {"foo": "bar"}, ttl=1)
        # Manually expire
        store.store["k1"]["_expires_at"] = time.time() - 1
        result = await store.get("k1")
        assert result is None

    async def test_delete_removes_entry(self):
        """delete() removes the entry from the store."""
        store = MemorySessionStore()
        await store.set("k1", {"foo": "bar"}, ttl=60)
        await store.delete("k1")
        result = await store.get("k1")
        assert result is None

    async def test_touch_resets_ttl(self):
        """touch() extends the TTL of an entry."""
        store = MemorySessionStore()
        await store.set("k1", {"foo": "bar"}, ttl=10)
        old_expires = store.store["k1"]["_expires_at"]
        await store.touch("k1", ttl=3600)
        new_expires = store.store["k1"]["_expires_at"]
        assert new_expires > old_expires

    async def test_touch_expired_entry_removes_it(self):
        """touch() on an expired entry removes it instead of extending TTL."""
        store = MemorySessionStore()
        await store.set("k1", {"foo": "bar"}, ttl=1)
        store.store["k1"]["_expires_at"] = time.time() - 1
        await store.touch("k1", ttl=3600)
        result = await store.get("k1")
        assert result is None

    async def test_max_sessions_enforced(self):
        """set() raises ValueError when max_sessions limit is reached."""
        store = MemorySessionStore(max_sessions=2)
        await store.set("k1", {"a": 1}, ttl=60)
        await store.set("k2", {"b": 2}, ttl=60)
        with pytest.raises(ValueError, match="Max sessions"):
            await store.set("k3", {"c": 3}, ttl=60)

    async def test_max_sessions_allows_update_existing(self):
        """set() allows updating an existing key even at max capacity."""
        store = MemorySessionStore(max_sessions=1)
        await store.set("k1", {"a": 1}, ttl=60)
        # Updating existing key should work
        await store.set("k1", {"a": 2}, ttl=60)
        result = await store.get("k1")
        assert result == {"a": 2}

    async def test_expired_sessions_purged_before_count_check(self):
        """Expired entries are purged before enforcing max_sessions."""
        store = MemorySessionStore(max_sessions=1)
        await store.set("k1", {"a": 1}, ttl=1)
        store.store["k1"]["_expires_at"] = time.time() - 1
        # Should succeed because k1 is expired and gets purged
        await store.set("k2", {"b": 2}, ttl=60)
        assert await store.count() == 1

    async def test_count_excludes_expired(self):
        """count() only counts non-expired entries."""
        store = MemorySessionStore()
        await store.set("k1", {"a": 1}, ttl=60)
        await store.set("k2", {"b": 2}, ttl=1)
        store.store["k2"]["_expires_at"] = time.time() - 1
        assert await store.count() == 1

    async def test_sliding_window_on_refresh(self, client: AsyncClient):
        """POST /auth/refresh calls touch() for sliding window idle timeout."""
        session_id = "sliding-session"
        await auth_bff._session_store.set(session_id, {"refresh_token": "rt"}, _SESSION_TTL_SECONDS)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "new-rt",
            "expires_in": 300,
            "token_type": "Bearer",
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.post("/auth/refresh", cookies={"session_id": session_id})
        assert resp.status_code == 200

        # Session should still exist (touch extended it)
        session = await auth_bff._session_store.get(session_id)
        assert session is not None


# ── Phase 2: OIDC Best Practices Tests ───────────────────────────────────────


@pytest.mark.auth
class TestOIDCHardening:
    """Tests for nonce, URL encoding, ID token validation, error sanitization."""

    async def test_login_includes_nonce_in_url(self, client: AsyncClient):
        """GET /auth/login includes nonce parameter in the authorization URL."""
        resp = await client.get("/auth/login")
        auth_url = resp.json()["auth_url"]
        assert "nonce=" in auth_url

    async def test_login_stores_nonce_in_pending(self, client: AsyncClient):
        """GET /auth/login stores nonce alongside code_verifier in login store."""
        await client.get("/auth/login")
        # Get the single entry from the store
        assert isinstance(auth_bff._login_store, MemorySessionStore)
        assert len(auth_bff._login_store.store) == 1
        key = next(iter(auth_bff._login_store.store))
        entry = await auth_bff._login_store.get(key)
        assert "nonce" in entry
        assert "code_verifier" in entry

    async def test_login_url_is_properly_encoded(self, client: AsyncClient):
        """GET /auth/login produces a properly URL-encoded query string."""
        resp = await client.get("/auth/login")
        auth_url = resp.json()["auth_url"]
        # "openid profile email" should be encoded as "openid+profile+email"
        # (urllib.parse.urlencode uses + for spaces by default)
        assert "openid+profile+email" in auth_url or "openid%20profile%20email" in auth_url

    async def test_callback_validates_id_token_nonce(self, client: AsyncClient):
        """Callback rejects ID tokens with mismatched nonce."""
        state = "nonce-test-state"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": "expected-nonce"},
            _LOGIN_TTL_SECONDS,
        )

        wrong_nonce_token = _make_test_id_token(nonce="wrong-nonce")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": wrong_nonce_token,
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 502
        assert "nonce mismatch" in resp.json()["detail"]

    async def test_callback_validates_id_token_audience(self, client: AsyncClient):
        """Callback rejects ID tokens with wrong audience."""
        state = "aud-test-state"
        nonce = "test-nonce"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": nonce},
            _LOGIN_TTL_SECONDS,
        )

        bad_aud_token = _make_test_id_token(nonce=nonce, aud="wrong-client")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": bad_aud_token,
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 502
        assert "audience mismatch" in resp.json()["detail"]

    async def test_callback_validates_id_token_expiry(self, client: AsyncClient):
        """Callback rejects expired ID tokens."""
        state = "exp-test-state"
        nonce = "test-nonce"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": nonce},
            _LOGIN_TTL_SECONDS,
        )

        expired_token = _make_test_id_token(nonce=nonce, exp=time.time() - 100)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": expired_token,
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 502
        assert "expired" in resp.json()["detail"]

    async def test_callback_validates_id_token_issuer(self, client: AsyncClient):
        """Callback rejects ID tokens with wrong issuer."""
        state = "iss-test-state"
        nonce = "test-nonce"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": nonce},
            _LOGIN_TTL_SECONDS,
        )

        bad_iss_token = _make_test_id_token(nonce=nonce, iss="http://evil-keycloak/realms/test")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": bad_iss_token,
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 502
        assert "issuer mismatch" in resp.json()["detail"]

    async def test_callback_accepts_public_url_as_issuer(self, client: AsyncClient):
        """Callback accepts the public Keycloak URL as a valid issuer."""
        state = "pub-iss-state"
        nonce = "test-nonce"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": nonce},
            _LOGIN_TTL_SECONDS,
        )

        # Use public URL as issuer — should be accepted
        pub_iss_token = _make_test_id_token(nonce=nonce, iss="http://localhost:8180/realms/test")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": pub_iss_token,
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 302  # Success — redirect to /

    async def test_token_exchange_error_sanitized(self, client: AsyncClient):
        """Token exchange errors don't leak Keycloak internals to client."""
        state = "error-state"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": "n"},
            _LOGIN_TTL_SECONDS,
        )

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Keycloak internal error: invalid_grant (session not active)"

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 502
        detail = resp.json()["detail"]
        # Should NOT contain Keycloak internals
        assert "invalid_grant" not in detail
        assert "session not active" not in detail
        assert detail == "Token exchange failed"

    async def test_callback_succeeds_without_id_token(self, client: AsyncClient):
        """Callback succeeds when token response has no id_token (graceful skip)."""
        state = "no-id-token-state"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": "n"},
            _LOGIN_TTL_SECONDS,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "expires_in": 300,
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    async def test_id_token_audience_as_list(self, client: AsyncClient):
        """ID token validation accepts audience as a list containing our client_id."""
        state = "aud-list-state"
        nonce = "test-nonce"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": nonce},
            _LOGIN_TTL_SECONDS,
        )

        # Build a token with list-valued aud (the helper sets aud as a string,
        # so we construct one manually with a list audience).
        payload = {
            "iss": "http://keycloak-test:8080/realms/test",
            "aud": ["test-client", "other-client"],
            "exp": time.time() + 300,
            "nonce": nonce,
            "sub": "test-user",
        }
        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        body = base64.urlsafe_b64encode(json.dumps(payload).encode())
        sig = base64.urlsafe_b64encode(b"fake-sig")
        list_aud_token = (
            f"{header.rstrip(b'=').decode()}"
            f".{body.rstrip(b'=').decode()}"
            f".{sig.rstrip(b'=').decode()}"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": list_aud_token,
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 302  # Success


# ── Phase 2: JWT Decode Helper Tests ─────────────────────────────────────────


@pytest.mark.auth
class TestJWTDecode:
    """Tests for _decode_jwt_payload helper."""

    def test_decode_valid_jwt(self):
        """Decodes a valid JWT payload."""
        token = _make_test_id_token(nonce="n1", aud="a1")
        payload = _decode_jwt_payload(token)
        assert payload["nonce"] == "n1"
        assert payload["aud"] == "a1"

    def test_decode_invalid_format(self):
        """Raises ValueError for non-JWT strings."""
        with pytest.raises(ValueError, match="Invalid JWT"):
            _decode_jwt_payload("not-a-jwt")

    def test_decode_two_parts(self):
        """Raises ValueError for JWT with only 2 segments."""
        with pytest.raises(ValueError, match="Invalid JWT"):
            _decode_jwt_payload("header.payload")


# ── Phase 3: Cookie Security Tests ───────────────────────────────────────────


@pytest.mark.auth
class TestCookieSecurity:
    """Tests for Secure cookie flag."""

    async def test_secure_flag_off_for_http(self, client: AsyncClient):
        """Cookie does NOT set Secure flag when redirect_uri is HTTP."""
        state = "sec-http-state"
        nonce = "test-nonce"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": nonce},
            _LOGIN_TTL_SECONDS,
        )

        id_token = _make_test_id_token(nonce=nonce)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": id_token,
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/auth/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        cookies = resp.headers.get_list("set-cookie")
        session_cookie = [c for c in cookies if "session_id=" in c][0]
        # Secure flag should NOT be present for HTTP
        assert "Secure" not in session_cookie

    async def test_secure_flag_on_for_https(self):
        """Cookie sets Secure flag when redirect_uri is HTTPS."""
        session_store = MemorySessionStore()
        login_store = MemorySessionStore()
        configure(
            keycloak_url="http://keycloak-test:8080/realms/test",
            keycloak_public_url="http://localhost:8180/realms/test",
            client_id="test-client",
            redirect_uri="https://console.example.com/auth/callback",
            session_store=session_store,
            login_store=login_store,
            secure_cookies=True,
        )

        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)

        state = "sec-https-state"
        nonce = "test-nonce"
        await auth_bff._login_store.set(
            state,
            {"code_verifier": "verifier", "nonce": nonce},
            _LOGIN_TTL_SECONDS,
        )

        id_token = _make_test_id_token(nonce=nonce, aud="test-client")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": id_token,
        }

        auth_bff._http_client = AsyncMock()
        auth_bff._http_client.post = AsyncMock(return_value=mock_response)

        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.get(
                "/auth/callback",
                params={"code": "c", "state": state},
                follow_redirects=False,
            )

        cookies = resp.headers.get_list("set-cookie")
        session_cookie = [c for c in cookies if "session_id=" in c][0]
        assert "Secure" in session_cookie


# ── Phase 4 & 5: main.py Tests (loop-breaker, CORS) ──────────────────────────
# main.py imports continuum which is not installed locally (Docker-only).
# We inject mock modules before import, matching test_console_main.py pattern.


def _import_main():
    """Import main.py with mocked continuum dependencies."""
    from unittest.mock import MagicMock as _MagicMock

    from fastapi import APIRouter as _APIRouter

    for mod in [
        "continuum",
        "continuum.app",
        "continuum.app.runtime",
        "continuum.adapters",
        "continuum.adapters.web",
        "continuum.adapters.web.api",
    ]:
        if mod not in sys.modules:
            sys.modules[mod] = _MagicMock()

    _mock_api = sys.modules["continuum.adapters.web.api"]
    if not isinstance(getattr(_mock_api, "router", None), _APIRouter):
        _mock_api.router = _APIRouter()

    import main as _main_mod

    return _main_mod


@pytest.mark.auth
class TestLoopBreaker:
    """Tests for auth bootstrap loop-breaker in config.js."""

    async def test_config_js_contains_loop_counter(self):
        """config.js includes sessionStorage-based loop detection."""
        main_mod = _import_main()
        test_app = FastAPI()
        test_app.add_api_route("/config.js", main_mod.config_js)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.get("/config.js")

        js = resp.text
        assert "__squadops_auth_loop_count" in js
        assert "MAX_LOOPS" in js

    async def test_config_js_contains_loop_error_display(self):
        """config.js shows error message when loop max is exceeded."""
        main_mod = _import_main()
        test_app = FastAPI()
        test_app.add_api_route("/config.js", main_mod.config_js)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.get("/config.js")

        js = resp.text
        assert "_showLoopError" in js
        assert "Authentication Error" in js


@pytest.mark.auth
class TestCORSTightening:
    """Tests for CORS middleware configuration."""

    def test_cors_origins_exclude_8001(self):
        """CORS allow_origins does NOT include localhost:8001."""
        main_mod = _import_main()

        for middleware in main_mod.app.user_middleware:
            if middleware.cls is CORSMiddleware:
                assert "http://localhost:8001" not in middleware.kwargs["allow_origins"]
                assert "http://localhost:4040" in middleware.kwargs["allow_origins"]
                assert "http://localhost:5173" in middleware.kwargs["allow_origins"]
                return
        pytest.fail("CORSMiddleware not found")

    def test_cors_methods_restricted(self):
        """CORS allow_methods are restricted (not wildcard)."""
        main_mod = _import_main()

        for middleware in main_mod.app.user_middleware:
            if middleware.cls is CORSMiddleware:
                methods = middleware.kwargs["allow_methods"]
                assert "*" not in methods
                assert "GET" in methods
                assert "POST" in methods
                return
        pytest.fail("CORSMiddleware not found")

    def test_cors_headers_restricted(self):
        """CORS allow_headers are restricted (not wildcard)."""
        main_mod = _import_main()

        for middleware in main_mod.app.user_middleware:
            if middleware.cls is CORSMiddleware:
                headers = middleware.kwargs["allow_headers"]
                assert "*" not in headers
                assert "Authorization" in headers
                assert "Content-Type" in headers
                return
        pytest.fail("CORSMiddleware not found")

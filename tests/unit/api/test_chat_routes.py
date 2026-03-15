"""Tests for chat API routes (SIP-0085 Phase 3).

Tests route logic, validation, and durability semantics using mock deps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.chat import routes as chat_routes_mod
from squadops.api.routes.chat.routes import agents_router, router
from squadops.comms.models import ChatMessage, ChatSession, SessionNotFoundError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEFAULT_AGENT = {
    "id": "comms-agent",
    "display_name": "Joi",
    "description": "Communications",
    "a2a_messaging_enabled": True,
    "a2a_port": 8080,
    "a2a_host": "localhost",
}


def _now():
    return datetime.now(UTC)


def _setup_app(
    all_agents: dict | None = None,
    messaging_agents: dict | None = None,
    chat_repo: object | None = None,
    a2a_client: object | None = None,
    chat_cache: object | None = None,
):
    """Build a test FastAPI app with chat routes and mock deps."""
    app = FastAPI()
    app.include_router(router)
    app.include_router(agents_router)

    # Store original values for cleanup
    orig_repo = chat_routes_mod._chat_repo
    orig_cache = chat_routes_mod._chat_cache
    orig_client = chat_routes_mod._a2a_client
    orig_all = chat_routes_mod._all_agents
    orig_msg = chat_routes_mod._messaging_agents

    # Set mock deps
    chat_routes_mod._chat_repo = chat_repo or _make_chat_repo()
    chat_routes_mod._chat_cache = chat_cache
    chat_routes_mod._a2a_client = a2a_client or _make_a2a_client()

    default_all = {"comms-agent": _DEFAULT_AGENT}
    default_msg = {"comms-agent": _DEFAULT_AGENT}

    chat_routes_mod._all_agents = (
        all_agents if all_agents is not None else default_all
    )
    chat_routes_mod._messaging_agents = (
        messaging_agents if messaging_agents is not None else default_msg
    )

    return app, (orig_repo, orig_cache, orig_client, orig_all, orig_msg)


def _teardown(originals):
    """Restore original module-level state."""
    chat_routes_mod._chat_repo = originals[0]
    chat_routes_mod._chat_cache = originals[1]
    chat_routes_mod._a2a_client = originals[2]
    chat_routes_mod._all_agents = originals[3]
    chat_routes_mod._messaging_agents = originals[4]


def _make_chat_repo():
    """Build a mock ChatRepository."""
    repo = AsyncMock()
    repo.create_session = AsyncMock()
    repo.get_session = AsyncMock(
        return_value=ChatSession(
            session_id="s1",
            agent_id="comms-agent",
            user_id="anonymous",
            started_at=_now(),
        )
    )
    repo.store_message = AsyncMock(side_effect=lambda m: m)
    repo.get_session_messages = AsyncMock(return_value=[])
    repo.list_sessions = AsyncMock(return_value=[])
    return repo


def _make_a2a_client():
    """Build a mock A2AClientAdapter that streams chunks."""

    async def fake_stream(base_url, message, **kwargs):
        yield "Hello"
        yield " there"

    client = MagicMock()
    client.send_message_stream = fake_stream
    return client


def _make_cache():
    """Build a mock ChatSessionCache."""
    cache = AsyncMock()
    cache.cache_message = AsyncMock()
    cache.get_messages = AsyncMock(return_value=None)
    cache.cache_session_meta = AsyncMock()
    cache.get_session_meta = AsyncMock(return_value=None)
    cache.invalidate_session = AsyncMock()
    return cache


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSendChatMessage:
    """POST /api/chat/{agent_id} route."""

    def test_returns_streaming_response(self):
        """Successful POST returns SSE stream with text chunks."""
        app, originals = _setup_app()
        try:
            client = TestClient(app)
            response = client.post(
                "/api/chat/comms-agent",
                json={"message": "hello"},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")

            # Parse SSE events
            events = [
                line for line in response.text.split("\n")
                if line.startswith("data:")
            ]
            assert len(events) >= 2  # at least chunk events + done event

            # Verify session_id is in response header
            assert "x-session-id" in response.headers
        finally:
            _teardown(originals)

    def test_returns_404_for_unknown_agent(self):
        """Unknown agent_id returns 404 AGENT_NOT_FOUND."""
        app, originals = _setup_app()
        try:
            client = TestClient(app)
            response = client.post(
                "/api/chat/nonexistent-agent",
                json={"message": "hello"},
            )
            assert response.status_code == 404
            body = response.json()
            assert body["detail"]["error"]["code"] == "AGENT_NOT_FOUND"
        finally:
            _teardown(originals)

    def test_returns_400_for_disabled_agent(self):
        """Agent that exists but has messaging disabled returns 400."""
        neo_config = {
            "id": "neo",
            "display_name": "Neo",
            "description": "Developer",
            "a2a_messaging_enabled": False,
            "a2a_port": 8080,
            "a2a_host": "localhost",
        }
        # neo is in all_agents but NOT in messaging_agents
        app, originals = _setup_app(
            all_agents={"neo": neo_config},
            messaging_agents={},
        )
        try:
            client = TestClient(app)
            response = client.post(
                "/api/chat/neo",
                json={"message": "hello"},
            )
            assert response.status_code == 400
            body = response.json()
            assert body["detail"]["error"]["code"] == "MESSAGING_NOT_ENABLED"
        finally:
            _teardown(originals)

    def test_persists_user_message_to_postgres(self):
        """User message is stored via ChatRepository (P3-RC2)."""
        repo = _make_chat_repo()
        app, originals = _setup_app(chat_repo=repo)
        try:
            client = TestClient(app)
            client.post(
                "/api/chat/comms-agent",
                json={"message": "test message"},
            )

            # Verify store_message called with user message
            assert repo.store_message.call_count >= 1
            first_call = repo.store_message.call_args_list[0]
            stored_msg = first_call[0][0]
            assert stored_msg.role == "user"
            assert stored_msg.content == "test message"
        finally:
            _teardown(originals)

    def test_creates_new_session_when_no_session_id(self):
        """Omitting session_id creates a new session in Postgres."""
        repo = _make_chat_repo()
        app, originals = _setup_app(chat_repo=repo)
        try:
            client = TestClient(app)
            client.post(
                "/api/chat/comms-agent",
                json={"message": "hello"},
            )

            repo.create_session.assert_called_once()
            created = repo.create_session.call_args[0][0]
            assert created.agent_id == "comms-agent"
        finally:
            _teardown(originals)

    def test_reuses_existing_session(self):
        """Providing session_id reuses the session (no create)."""
        repo = _make_chat_repo()
        app, originals = _setup_app(chat_repo=repo)
        try:
            client = TestClient(app)
            client.post(
                "/api/chat/comms-agent",
                json={"message": "follow-up", "session_id": "s1"},
            )

            repo.create_session.assert_not_called()
            repo.get_session.assert_called_once_with("s1")
        finally:
            _teardown(originals)

    def test_returns_404_for_invalid_session_id(self):
        """Providing a non-existent session_id returns 404."""
        repo = _make_chat_repo()
        repo.get_session = AsyncMock(side_effect=SessionNotFoundError("nope"))
        app, originals = _setup_app(chat_repo=repo)
        try:
            client = TestClient(app)
            response = client.post(
                "/api/chat/comms-agent",
                json={"message": "hello", "session_id": "bad-session"},
            )
            assert response.status_code == 404
            body = response.json()
            assert body["detail"]["error"]["code"] == "SESSION_NOT_FOUND"
        finally:
            _teardown(originals)

    def test_agent_response_persist_failure_still_completes_stream(self):
        """Failed Postgres write on agent response logs error but stream completes (P3-RC2)."""
        repo = _make_chat_repo()
        # First call (user msg) succeeds; second call (agent response) fails
        call_count = 0

        async def fail_on_second(msg):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise ConnectionError("Postgres connection lost")
            return msg

        repo.store_message = AsyncMock(side_effect=fail_on_second)
        app, originals = _setup_app(chat_repo=repo)
        try:
            client = TestClient(app)
            response = client.post(
                "/api/chat/comms-agent",
                json={"message": "hello"},
            )
            # Stream completes despite persistence failure
            assert response.status_code == 200
            events = [
                line for line in response.text.split("\n")
                if line.startswith("data:")
            ]
            # Should still have text chunks and done event
            done_events = [e for e in events if '"done": true' in e.lower() or '"done":true' in e.lower()]
            assert len(done_events) == 1
        finally:
            _teardown(originals)

    def test_caches_user_message_to_redis_when_wired(self):
        """When Redis cache is wired, user message is cached best-effort."""
        cache = _make_cache()
        app, originals = _setup_app(chat_cache=cache)
        try:
            client = TestClient(app)
            client.post(
                "/api/chat/comms-agent",
                json={"message": "hello"},
            )

            # cache_message called for user message (at minimum)
            assert cache.cache_message.call_count >= 1
            cached_msg = cache.cache_message.call_args_list[0][0][0]
            assert cached_msg.role == "user"
            assert cached_msg.content == "hello"
        finally:
            _teardown(originals)


class TestGetSessionMessages:
    """GET /api/chat/sessions/{session_id}/messages route."""

    def test_returns_ordered_messages(self):
        """Messages returned in chronological order."""
        repo = _make_chat_repo()
        now = _now()
        repo.get_session_messages = AsyncMock(return_value=[
            ChatMessage(
                message_id="m1", session_id="s1", role="user",
                content="hello", created_at=now,
            ),
            ChatMessage(
                message_id="m2", session_id="s1", role="assistant",
                content="hi there", created_at=now,
            ),
        ])
        app, originals = _setup_app(chat_repo=repo)
        try:
            client = TestClient(app)
            response = client.get("/api/chat/sessions/s1/messages")

            assert response.status_code == 200
            messages = response.json()
            assert len(messages) == 2
            assert messages[0]["role"] == "user"
            assert messages[1]["role"] == "assistant"
            assert messages[1]["content"] == "hi there"
        finally:
            _teardown(originals)

    def test_returns_404_for_unknown_session(self):
        """Unknown session_id returns 404 with SESSION_NOT_FOUND code."""
        repo = _make_chat_repo()
        repo.get_session = AsyncMock(side_effect=SessionNotFoundError("nope"))
        app, originals = _setup_app(chat_repo=repo)
        try:
            client = TestClient(app)
            response = client.get("/api/chat/sessions/bad-session/messages")
            assert response.status_code == 404
            body = response.json()
            assert body["detail"]["error"]["code"] == "SESSION_NOT_FOUND"
        finally:
            _teardown(originals)

    def test_db_error_is_not_masked_as_404(self):
        """A database connection error propagates, not masked as 404."""
        repo = _make_chat_repo()
        repo.get_session = AsyncMock(side_effect=ConnectionError("DB down"))
        app, originals = _setup_app(chat_repo=repo)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/chat/sessions/s1/messages")
            # Must NOT be 404 — DB errors are not session-not-found
            assert response.status_code == 500
        finally:
            _teardown(originals)


class TestListMessagingAgents:
    """GET /api/agents/messaging route."""

    def test_returns_messaging_agents(self):
        """Returns only messaging-enabled agents."""
        app, originals = _setup_app()
        try:
            client = TestClient(app)
            response = client.get("/api/agents/messaging")

            assert response.status_code == 200
            agents = response.json()
            assert len(agents) == 1
            assert agents[0]["agent_id"] == "comms-agent"
            assert agents[0]["display_name"] == "Joi"
            assert agents[0]["a2a_port"] == 8080
        finally:
            _teardown(originals)

    def test_returns_empty_list_when_none_enabled(self):
        """Empty list when no agents have messaging enabled."""
        app, originals = _setup_app(messaging_agents={})
        try:
            client = TestClient(app)
            response = client.get("/api/agents/messaging")

            assert response.status_code == 200
            assert response.json() == []
        finally:
            _teardown(originals)


class TestListAgentSessions:
    """GET /api/chat/{agent_id}/sessions route."""

    def test_returns_sessions_for_agent(self):
        """Returns sessions for the agent+user pair."""
        repo = _make_chat_repo()
        repo.list_sessions = AsyncMock(return_value=[
            ChatSession(
                session_id="s1", agent_id="comms-agent",
                user_id="anonymous", started_at=_now(),
            ),
        ])
        app, originals = _setup_app(chat_repo=repo)
        try:
            client = TestClient(app)
            response = client.get("/api/chat/comms-agent/sessions")

            assert response.status_code == 200
            sessions = response.json()
            assert len(sessions) == 1
            assert sessions[0]["session_id"] == "s1"
        finally:
            _teardown(originals)

    def test_returns_404_for_unknown_agent(self):
        """Unknown agent returns 404."""
        app, originals = _setup_app()
        try:
            client = TestClient(app)
            response = client.get("/api/chat/nonexistent-agent/sessions")
            assert response.status_code == 404
        finally:
            _teardown(originals)

    def test_returns_400_for_disabled_agent_sessions(self):
        """Agent with messaging disabled returns 400 on session list."""
        neo_config = {
            "id": "neo",
            "display_name": "Neo",
            "description": "Developer",
            "a2a_messaging_enabled": False,
            "a2a_port": 8080,
            "a2a_host": "localhost",
        }
        app, originals = _setup_app(
            all_agents={"neo": neo_config},
            messaging_agents={},
        )
        try:
            client = TestClient(app)
            response = client.get("/api/chat/neo/sessions")
            assert response.status_code == 400
            body = response.json()
            assert body["detail"]["error"]["code"] == "MESSAGING_NOT_ENABLED"
        finally:
            _teardown(originals)


class TestGetUserIdExtraction:
    """_get_user_id() extracts identity from request state."""

    def test_returns_user_id_from_auth_identity(self):
        """Authenticated request returns the identity's user_id."""
        request = MagicMock()
        identity = MagicMock()
        identity.user_id = "user-42"
        request.state.identity = identity

        result = chat_routes_mod._get_user_id(request)
        assert result == "user-42"

    def test_returns_anonymous_when_no_identity(self):
        """Missing auth identity returns 'anonymous' for dev mode."""
        request = MagicMock()
        request.state = MagicMock(spec=[])  # no identity attribute

        result = chat_routes_mod._get_user_id(request)
        assert result == "anonymous"


class TestPortGuards:
    """_get_chat_repo() and _get_a2a_client() guard against unconfigured ports."""

    def test_chat_repo_raises_when_not_configured(self):
        """RuntimeError raised when ChatRepository not set."""
        orig = chat_routes_mod._chat_repo
        try:
            chat_routes_mod._chat_repo = None
            with pytest.raises(RuntimeError, match="ChatRepository not configured"):
                chat_routes_mod._get_chat_repo()
        finally:
            chat_routes_mod._chat_repo = orig

    def test_a2a_client_raises_when_not_configured(self):
        """RuntimeError raised when A2AClientAdapter not set."""
        orig = chat_routes_mod._a2a_client
        try:
            chat_routes_mod._a2a_client = None
            with pytest.raises(RuntimeError, match="A2AClientAdapter not configured"):
                chat_routes_mod._get_a2a_client()
        finally:
            chat_routes_mod._a2a_client = orig


class TestLoadHistory:
    """_load_history() Redis-first with Postgres fallback."""

    async def test_returns_from_redis_cache_on_hit(self):
        """Redis cache hit returns messages without hitting Postgres."""
        cache = _make_cache()
        cache.get_messages = AsyncMock(return_value=[
            {"message_id": "m1", "role": "user", "content": "hi", "created_at": "2025-01-01T00:00:00"},
            {"message_id": "m2", "role": "assistant", "content": "hello", "created_at": "2025-01-01T00:00:01"},
        ])
        repo = _make_chat_repo()

        orig_cache = chat_routes_mod._chat_cache
        orig_repo = chat_routes_mod._chat_repo
        try:
            chat_routes_mod._chat_cache = cache
            chat_routes_mod._chat_repo = repo

            history = await chat_routes_mod._load_history("s1")

            assert len(history) == 2
            assert history[0] == {"role": "user", "content": "hi"}
            assert history[1] == {"role": "assistant", "content": "hello"}
            # Postgres should NOT have been called
            repo.get_session_messages.assert_not_called()
        finally:
            chat_routes_mod._chat_cache = orig_cache
            chat_routes_mod._chat_repo = orig_repo

    async def test_falls_back_to_postgres_on_cache_miss(self):
        """Redis cache miss loads from Postgres and repopulates cache."""
        cache = _make_cache()
        cache.get_messages = AsyncMock(return_value=None)  # cache miss

        now = _now()
        repo = _make_chat_repo()
        repo.get_session_messages = AsyncMock(return_value=[
            ChatMessage(
                message_id="m1", session_id="s1", role="user",
                content="hello", created_at=now,
            ),
        ])

        orig_cache = chat_routes_mod._chat_cache
        orig_repo = chat_routes_mod._chat_repo
        try:
            chat_routes_mod._chat_cache = cache
            chat_routes_mod._chat_repo = repo

            history = await chat_routes_mod._load_history("s1")

            assert len(history) == 1
            assert history[0] == {"role": "user", "content": "hello"}
            # Postgres was called
            repo.get_session_messages.assert_called_once_with("s1")
            # Redis was repopulated
            cache.cache_message.assert_called_once()
        finally:
            chat_routes_mod._chat_cache = orig_cache
            chat_routes_mod._chat_repo = orig_repo

    async def test_works_without_cache(self):
        """When no cache is configured, loads directly from Postgres."""
        repo = _make_chat_repo()
        repo.get_session_messages = AsyncMock(return_value=[])

        orig_cache = chat_routes_mod._chat_cache
        orig_repo = chat_routes_mod._chat_repo
        try:
            chat_routes_mod._chat_cache = None
            chat_routes_mod._chat_repo = repo

            history = await chat_routes_mod._load_history("s1")

            assert history == []
            repo.get_session_messages.assert_called_once_with("s1")
        finally:
            chat_routes_mod._chat_cache = orig_cache
            chat_routes_mod._chat_repo = orig_repo


class TestChatErrors:
    """Error handler module produces correct HTTP responses."""

    @pytest.mark.parametrize(
        "error_cls,expected_status,expected_code",
        [
            (SessionNotFoundError, 404, "SESSION_NOT_FOUND"),
        ],
    )
    def test_handle_chat_error_maps_correctly(self, error_cls, expected_status, expected_code):
        """handle_chat_error maps domain errors to correct HTTP status and code."""
        from squadops.api.routes.chat.errors import handle_chat_error

        exc = handle_chat_error(error_cls("test"))
        assert exc.status_code == expected_status
        assert exc.detail["error"]["code"] == expected_code

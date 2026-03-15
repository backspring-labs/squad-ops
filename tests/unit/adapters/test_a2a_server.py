"""Tests for A2AServerAdapter (SIP-0085 Phase 1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.comms.a2a_server import (
    A2AServerAdapter,
    AgentCardConfig,
    build_agent_card,
)

# ---------------------------------------------------------------------------
# build_agent_card tests
# ---------------------------------------------------------------------------


class TestBuildAgentCard:
    """Tests for build_agent_card() helper."""

    def test_builds_card_with_defaults(self):
        config = AgentCardConfig(
            agent_id="joi-01",
            display_name="Joi",
            description="Comms agent",
            version="1.0.0",
        )
        card = build_agent_card(config)
        assert card.name == "Joi"
        assert card.description == "Comms agent"
        assert card.version == "1.0.0"
        assert card.url == "http://0.0.0.0:5000"
        assert len(card.skills) == 1
        assert card.skills[0].id == "chat"
        assert "chat" in card.skills[0].tags
        assert card.capabilities.streaming is True
        assert card.default_input_modes == ["text"]
        assert card.default_output_modes == ["text"]

    def test_builds_card_with_custom_host_port(self):
        config = AgentCardConfig(
            agent_id="neo-01",
            display_name="Neo",
            description="Dev agent",
            version="2.0.0",
            host="127.0.0.1",
            port=8080,
        )
        card = build_agent_card(config)
        assert card.url == "http://127.0.0.1:8080"

    def test_builds_card_with_custom_skills(self):
        from a2a.types import AgentSkill

        custom_skill = AgentSkill(
            id="code-review",
            name="Code Review",
            description="Reviews code",
            tags=["dev"],
        )
        config = AgentCardConfig(
            agent_id="neo-01",
            display_name="Neo",
            description="Dev agent",
            version="1.0.0",
            skills=(custom_skill,),
        )
        card = build_agent_card(config)
        assert len(card.skills) == 1
        assert card.skills[0].id == "code-review"


# ---------------------------------------------------------------------------
# A2AServerAdapter lifecycle tests
# ---------------------------------------------------------------------------


class TestA2AServerAdapterLifecycle:
    """Tests for A2AServerAdapter start/stop/health."""

    def _make_adapter(self, port: int = 5000) -> A2AServerAdapter:
        """Create an adapter with a mock executor."""
        config = AgentCardConfig(
            agent_id="test-01",
            display_name="Test",
            description="Test agent",
            version="1.0.0",
            port=port,
        )
        card = build_agent_card(config)

        # Mock executor implementing AgentExecutor interface
        executor = MagicMock()
        executor.execute = AsyncMock()
        executor.cancel = AsyncMock()

        return A2AServerAdapter(
            agent_card=card,
            executor=executor,
            port=port,
        )

    async def test_health_before_start(self):
        """Health reports not healthy before start."""
        adapter = self._make_adapter()
        result = await adapter.health()
        assert result["healthy"] is False
        assert result["port"] == 5000
        assert result["agent_name"] == "Test"

    async def test_start_creates_serve_task(self):
        """start() creates a background task."""
        adapter = self._make_adapter(port=5111)

        with patch("adapters.comms.a2a_server.uvicorn") as mock_uvicorn:
            mock_server = MagicMock()
            mock_server.serve = AsyncMock()
            mock_uvicorn.Server.return_value = mock_server
            mock_uvicorn.Config = MagicMock()

            await adapter.start()

            assert adapter._serve_task is not None
            assert adapter._server is mock_server

            # Clean up
            await adapter.stop()

    async def test_double_start_is_idempotent(self):
        """Calling start() twice does not create a second task."""
        adapter = self._make_adapter()

        with patch("adapters.comms.a2a_server.uvicorn") as mock_uvicorn:
            mock_server = MagicMock()
            mock_server.serve = AsyncMock()
            mock_uvicorn.Server.return_value = mock_server
            mock_uvicorn.Config = MagicMock()

            await adapter.start()
            first_task = adapter._serve_task

            await adapter.start()  # Should warn, not create new task
            assert adapter._serve_task is first_task

            await adapter.stop()

    async def test_stop_without_start_is_safe(self):
        """stop() before start() doesn't raise."""
        adapter = self._make_adapter()
        await adapter.stop()  # Should not raise

    async def test_health_after_stop(self):
        """Health reports not healthy after stop."""
        adapter = self._make_adapter()
        # Never started, but calling stop to be explicit
        await adapter.stop()
        result = await adapter.health()
        assert result["healthy"] is False

    async def test_start_failure_cleans_up_state(self):
        """If start() raises, adapter state is reset (no partial initialization)."""
        adapter = self._make_adapter()

        with patch("adapters.comms.a2a_server.uvicorn") as mock_uvicorn:
            mock_uvicorn.Config = MagicMock(side_effect=RuntimeError("config failed"))

            with pytest.raises(RuntimeError, match="config failed"):
                await adapter.start()

            # Adapter must not be left in partial state
            assert adapter._server is None
            assert adapter._serve_task is None

            # Health should report not healthy
            result = await adapter.health()
            assert result["healthy"] is False

"""
AgentRunner heartbeat service-identity wiring (#326).

Reporter behavior is covered in tests/unit/observability/test_healthcheck_http.py.
These tests cover the runner-side wiring: agent_client + oidc config yields a
token-carrying reporter, no agent_client yields an unauthenticated one, and a
half-configured identity fails loudly instead of degrading to anonymous
heartbeats against an authed endpoint.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.config.schema import OIDCConfig, ServiceClientConfig

pytestmark = [pytest.mark.domain_agents]


def _make_runner():
    """Build a bare AgentRunner without invoking __init__ (loads instances.yaml)."""
    from squadops.agents.entrypoint import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    runner.agent_id = "neo"
    runner._service_token_client = None
    return runner


def _config(agent_client=None, oidc=None):
    cfg = MagicMock()
    cfg.auth.agent_client = agent_client
    cfg.auth.oidc = oidc
    return cfg


_AGENT_CLIENT = ServiceClientConfig(client_id="squadops-agent", client_secret="s3cret")
_OIDC = OIDCConfig(
    issuer_url="http://keycloak:8080/realms/squadops-dev",
    audience="squadops-runtime",
)


class TestHeartbeatIdentityWiring:
    def test_agent_client_configured_wires_token_provider(self):
        runner = _make_runner()
        reporter = runner._create_heartbeat_reporter(_config(_AGENT_CLIENT, _OIDC))

        # Reporter authenticates via the runner-owned ServiceTokenClient
        assert reporter._token_provider == runner._service_token_client.get_token
        assert runner._service_token_client._client_id == "squadops-agent"
        assert (
            runner._service_token_client._token_endpoint
            == "http://keycloak:8080/realms/squadops-dev/protocol/openid-connect/token"
        )

    def test_no_agent_client_yields_unauthenticated_reporter(self):
        runner = _make_runner()
        reporter = runner._create_heartbeat_reporter(_config(agent_client=None, oidc=_OIDC))

        assert reporter._token_provider is None
        assert runner._service_token_client is None

    def test_agent_client_without_oidc_raises(self):
        """Misconfiguration must surface at startup: without oidc there is no
        token endpoint, and silently sending anonymous heartbeats would just
        401 forever against the authed lane."""
        runner = _make_runner()
        with pytest.raises(ValueError, match="auth.oidc is missing"):
            runner._create_heartbeat_reporter(_config(agent_client=_AGENT_CLIENT, oidc=None))
        assert runner._service_token_client is None

    async def test_stop_closes_token_client(self):
        """The ServiceTokenClient owns an httpx session — stop() must release
        it or every agent shutdown leaks a connection pool."""
        runner = _make_runner()
        runner._shutdown_event = asyncio.Event()
        runner._heartbeat_task = None
        runner.system = None
        runner._log_forwarder = None
        token_client = AsyncMock()
        runner._service_token_client = token_client

        await runner.stop()

        token_client.close.assert_awaited_once()
        assert runner._service_token_client is None

"""The agent's remote-execution port, as its composition root binds it (SIP-0117 R5.6).

Wiring, entered at ``AgentRunner._create_system``, the call the agent's start makes. The root's
real ``_create_ports`` runs: only the queue, Redis and the identity provider's client are
replaced. What reaches the factory is read at the factory, and what reaches a handler is read
from the system's ports bundle.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.remote_execution.runtime_api_remote_execution import RuntimeApiRemoteExecution
from tests.unit.agents.test_entrypoint_scripted_squad import _config

pytestmark = [pytest.mark.domain_agents]


@pytest.fixture
def agent(monkeypatch):
    from squadops.agents import entrypoint

    monkeypatch.setattr(
        entrypoint,
        "load_instance_config",
        lambda aid: {"id": aid, "role": "qa", "model": "qwen2.5:7b"},
    )
    monkeypatch.setattr("adapters.comms.factory.create_queue_adapter", lambda *a, **k: AsyncMock())
    monkeypatch.setattr("adapters.comms.factory.create_task_attempts", lambda *a, **k: None)
    return entrypoint.AgentRunner(role="qa", agent_id="eve")


def _deploy(provider: str, *, identity: bool = True):
    config = _config()
    config.remote_execution = SimpleNamespace(provider=provider, wait_seconds=600, max_attempts=3)
    config.runtime_api_url = "http://runtime-api:8001"
    config.auth = SimpleNamespace(
        agent_client=SimpleNamespace(client_id="squadops-agent") if identity else None,
        oidc=SimpleNamespace(issuer_url="http://keycloak/realms/squadops") if identity else None,
    )
    return config


async def test_a_deploy_that_runs_no_remote_execution_binds_no_port(agent):
    """Bug caught: ``none`` bound to something that answers, so an operation on a deploy with
    no worker reads as run."""
    agent._config = _deploy("none", identity=False)

    system = await agent._create_system()

    assert system.ports.remote_execution is None


async def test_the_selector_and_the_agents_identity_reach_the_factory_and_its_port_the_bundle(
    agent, monkeypatch
):
    """Bug caught: the port built and never put in the bundle (every operation "no port
    bound" on a deploy that selected one), the wait handed over as the attempts, another
    agent's id as the origin, or the calls sent with no token on a deploy that authenticates."""
    token_client = SimpleNamespace(get_token=AsyncMock(return_value="tok"), close=AsyncMock())
    monkeypatch.setattr(
        "adapters.auth.factory.create_service_token_client", lambda *a, **k: token_client
    )
    seen: dict = {}
    port = object()

    def factory(provider, **settings):
        seen.update(settings, provider=provider)
        return port

    monkeypatch.setattr("adapters.remote_execution.factory.create_remote_execution", factory)
    agent._config = _deploy("runtime_api")

    system = await agent._create_system()

    assert seen == {
        "provider": "runtime_api",
        "base_url": "http://runtime-api:8001",
        "token": token_client.get_token,
        "origin": {"agent_id": "eve"},
        "wait": timedelta(seconds=600),
        "max_attempts": 3,
    }
    assert system.ports.remote_execution is port
    # One identity client for the process: the heartbeats take the same one.
    assert agent._service_token_provider(agent._config) is token_client.get_token


async def test_with_no_agent_identity_the_port_is_built_to_send_no_token(agent):
    """The heartbeats' rule (#326), kept for this caller: an auth-disabled deploy has no agent
    client. Bug caught: the root refusing to start there, or inventing a credential."""
    agent._config = _deploy("runtime_api", identity=False)

    system = await agent._create_system()

    assert isinstance(system.ports.remote_execution, RuntimeApiRemoteExecution)
    assert agent._service_token_client is None


async def test_an_identity_with_no_token_endpoint_stops_the_agent_naming_it(agent):
    """Bug caught: a half-configured identity degrading to calls with no token."""
    agent._config = _deploy("runtime_api")
    agent._config.auth.oidc = None

    with pytest.raises(
        ValueError, match="auth.agent_client is configured but auth.oidc is missing"
    ):
        await agent._create_system()

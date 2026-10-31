"""The database is the runtime API's, and an agent declares none (#2457, IR-4).

Every agent's container held the runtime API's own database credential, only because the config
schema required a database section. No agent connects: its view of a cycle arrives in its task
envelope, and its status goes out over HTTP. So an agent's config carries no database, and the
places a pool is made require one by name.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from squadops.api.runtime import main as runtime_main
from squadops.config.loader import load_config

pytestmark = [pytest.mark.domain_contracts]

#: An agent's environment, as ``docker-compose.yml`` gives it, without the deploy's services:
#: the selectors every process requires, and no ``SQUADOPS__DB__URL``.
_AGENT_ENV = {
    "SQUADOPS__AUTH__ENABLED": "false",
    "SQUADOPS__AUTH__KEYCLOAK__ADMIN__PASSWORD": "literal",
    "SQUADOPS__COMMS__RABBITMQ__URL": "amqp://test:test@localhost:5672/",
    "SQUADOPS__COMMS__REDIS__URL": "redis://localhost:6379/0",
    "SQUADOPS__LLM__PROVIDER": "ollama",
    "SQUADOPS__LLM__URL": "http://ollama:11434",
    "SQUADOPS__COMMS__QUEUE__PROVIDER": "rabbitmq",
    "SQUADOPS__COMMS__A2A__PROVIDER": "http",
    "SQUADOPS__TOOLS__FILESYSTEM__PROVIDER": "local",
    "SQUADOPS__CYCLES__REGISTRY_PROVIDER": "memory",
    "SQUADOPS__CYCLES__SQUAD_PROFILE_PROVIDER": "config",
    "SQUADOPS__CYCLES__PROJECT_REGISTRY_PROVIDER": "config",
    "SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER": "filesystem",
    "SQUADOPS__TELEMETRY__BACKEND": "null",
    "SQUADOPS__SANDBOX__PROVIDER": "noop",
}


@pytest.fixture
def agent_env(monkeypatch):
    monkeypatch.delenv("SQUADOPS__DB__URL", raising=False)
    for key, value in _AGENT_ENV.items():
        monkeypatch.setenv(key, value)


def test_an_agents_config_loads_with_no_database(agent_env):
    """Bug caught: the schema requiring a database again, so an agent whose container holds no
    database credential fails at start, and the credential goes back in to make it boot."""
    assert load_config().db is None


async def test_the_runtime_api_refuses_to_start_with_no_database_and_names_it(
    agent_env, monkeypatch
):
    """Bug caught: the runtime API starting with no database configured and failing later, in a
    pool built from ``None``, with an error that names neither the setting nor the reason.

    Driven through ``_startup``, the runtime's own entry point: the refusal comes before any
    pool is made."""
    create_pool = AsyncMock()
    monkeypatch.setattr(runtime_main, "create_pool", create_pool)
    app = SimpleNamespace(state=SimpleNamespace(config=load_config()))

    with pytest.raises(ValueError, match="SQUADOPS__DB__URL"):
        await runtime_main._startup(app)
    create_pool.assert_not_awaited()


def test_a_configured_database_is_the_one_returned(agent_env, monkeypatch):
    """The paired control: with ``SQUADOPS__DB__URL`` set, ``database()`` returns that database,
    so the refusal above is about its absence and nothing else."""
    monkeypatch.setenv("SQUADOPS__DB__URL", "postgresql://u:p@db:5432/app")
    assert load_config().database().url == "postgresql://u:p@db:5432/app"

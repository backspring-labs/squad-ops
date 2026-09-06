"""#154: the config loader resolves ``secret://`` references through a provider it is
GIVEN — which provider is the composition root's choice, not an import the domain makes.

Before this the loader imported ``adapters.secrets.factory`` to build the provider itself:
a deliberate behaviour with the import pointing the wrong way. Now the factory arrives as
``secret_provider_factory``; a config with references and no factory is refused loudly.
"""

from __future__ import annotations

import pytest

from squadops.config.errors import ConfigValidationError
from squadops.config.loader import load_config
from squadops.ports.secrets import SecretProvider

pytestmark = [pytest.mark.domain_contracts]


class _Stub(SecretProvider):
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values
        self.asked: list[str] = []

    @property
    def provider_name(self) -> str:
        return "stub"

    def resolve(self, name: str) -> str | None:
        self.asked.append(name)
        return self._values.get(name)

    def exists(self, name: str) -> bool:
        return name in self._values


#: The checked-in local profile lacks db/comms and carries one secret:// reference
#: (auth.keycloak.admin.password); the same minimal env the CLI integration test sets
#: makes load_config() validate without Docker services. cli_overrides win over env.
_ENV = {
    "SQUADOPS__AUTH__ENABLED": "false",
    "SQUADOPS__AUTH__KEYCLOAK__ADMIN__PASSWORD": "literal",
    "SQUADOPS__DB__URL": "postgresql://test:test@localhost:5432/test",
    "SQUADOPS__COMMS__RABBITMQ__URL": "amqp://test:test@localhost:5672/",
    "SQUADOPS__COMMS__REDIS__URL": "redis://localhost:6379/0",
    "SQUADOPS__LLM__PROVIDER": "ollama",
}

_OVERRIDES = {
    "secrets": {"provider": "env"},
    "db": {"url": "secret://db_url"},
}


@pytest.fixture(autouse=True)
def _loadable_env(monkeypatch):
    for key, value in _ENV.items():
        monkeypatch.setenv(key, value)


def test_references_with_no_factory_are_refused_naming_the_seam():
    """Bug caught: silently skipping resolution — a ``secret://`` string shipped as the
    live value — or silently defaulting to the env provider, the masking fallback the
    seam rule forbids."""
    with pytest.raises(ConfigValidationError, match="secret_provider_factory"):
        load_config(cli_overrides=_OVERRIDES)


def test_the_given_factory_resolves_the_references():
    """Wiring: the provider the root supplies is the one consulted, once per reference."""
    stub = _Stub({"db_url": "postgresql://resolved:resolved@db:5432/app"})
    seen: list[str] = []

    def factory(secrets_config):
        seen.append(secrets_config.provider)
        return stub

    config = load_config(cli_overrides=_OVERRIDES, secret_provider_factory=factory)
    assert seen == ["env"]
    assert stub.asked == ["db_url"]
    assert config.db.url == "postgresql://resolved:resolved@db:5432/app"


def test_a_config_without_references_needs_no_factory():
    """A secrets section alone selects nothing to resolve; the loader must not demand a
    provider it would never consult."""
    config = load_config(cli_overrides={"secrets": {"provider": "env"}})
    assert config is not None


def test_both_composition_roots_hand_the_loader_the_bootstrap_factory():
    """The roots that load the framework config pass ``secret_provider_for`` — a
    root that forgot would fail at first boot on any config with a reference, and this
    says so in CI instead."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    for rel in ("src/squadops/api/runtime/main.py", "src/squadops/agents/entrypoint.py"):
        text = (repo / rel).read_text(encoding="utf-8")
        assert "secret_provider_factory=secret_provider_for" in text, rel

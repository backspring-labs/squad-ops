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
    # #301: the three selectors are required the way llm.provider is (R2).
    "SQUADOPS__COMMS__QUEUE__PROVIDER": "rabbitmq",
    "SQUADOPS__COMMS__A2A__PROVIDER": "http",
    "SQUADOPS__TOOLS__FILESYSTEM__PROVIDER": "local",
    # #1568: and so is every other selector.
    "SQUADOPS__CYCLES__REGISTRY_PROVIDER": "memory",
    "SQUADOPS__CYCLES__SQUAD_PROFILE_PROVIDER": "config",
    "SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER": "filesystem",
    "SQUADOPS__TELEMETRY__BACKEND": "null",
    "SQUADOPS__SANDBOX__PROVIDER": "noop",
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


def _framework_load_config_calls_without_a_factory(source: str) -> list[int]:
    """The lines where a module calls the FRAMEWORK loader (imported from ``squadops.config``)
    without ``secret_provider_factory``. The CLI's own ``squadops.cli.config.load_config``
    reads the CLI's file, holds no references, and is not this loader."""
    import ast

    tree = ast.parse(source)
    names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module in ("squadops.config", "squadops.config.loader")
        for alias in node.names
        if alias.name == "load_config"
    }
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in names
        and not any(k.arg == "secret_provider_factory" for k in node.keywords)
    ]


def test_every_framework_config_load_hands_the_loader_a_factory():
    """Bug caught: a caller that loads the framework config with no factory fails at its
    first use on any deploy, whose config always carries references. Checking only the two
    roots missed the in-container authoring replay (#2137): its tests entered below
    ``_main``, and the first live run raised ``ConfigValidationError``. Every caller in
    ``src/``, ``adapters/`` and ``scripts/`` is read, not a list of them."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    offenders = [
        f"{path.relative_to(repo)}:{line}"
        for root in ("src", "adapters", "scripts")
        for path in sorted((repo / root).rglob("*.py"))
        for line in _framework_load_config_calls_without_a_factory(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from squadops.config import load_config\nload_config()\n", [2]),
        ("from squadops.config.loader import load_config as lc\nlc(strict=True)\n", [2]),
        (
            "from squadops.config import load_config\nload_config(secret_provider_factory=f)\n",
            [],
        ),
        ("from squadops.cli.config import load_config\nload_config()\n", []),
    ],
)
def test_the_scan_reads_the_framework_loader_and_only_it(source, expected):
    """The guard above is only as good as its scan: an alias must not hide a call, and the
    CLI's loader of the same name must not be flagged."""
    assert _framework_load_config_calls_without_a_factory(source) == expected

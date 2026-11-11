"""Sandbox service entrypoint (SIP-0102 — 102.1 slice d).

Composition root: builds the service core via the factory and wraps it in the
HTTP surface.

Config note: this service reads ONLY its own ``SQUADOPS__SANDBOX__*``
section, deliberately not the full ``load_config()`` — the layered loader
eagerly resolves every ``secret://`` reference in the platform config, which
would make this container require secrets (Keycloak admin, DB passwords) it
must never hold. Same env-var convention, narrower blast radius. Revisit if
the service ever needs file-layered config (the 102.2 environment contract is
its own artifact, not a config layer).

Run with:  uvicorn --factory squadops.sandbox.main:build_app --port 8002
"""

from __future__ import annotations

from fastapi import FastAPI

from squadops.config.env_section import section_from_env
from squadops.config.schema import SandboxConfig
from squadops.core.secrets import SecretManager
from squadops.sandbox.api import create_app

_ENV_PREFIX = "SQUADOPS__SANDBOX__"


def sandbox_config_from_env() -> SandboxConfig:
    """Build the execution section from its env vars (pydantic coerces types)."""
    return SandboxConfig(**section_from_env(_ENV_PREFIX, SandboxConfig.model_fields))


def secret_manager_from_env() -> SecretManager | None:
    """The secrets provider the ``SQUADOPS__SECRETS__*`` section selects, or ``None`` when it
    selects none (#1982). Only the provider's selection is read: no other platform secret is
    resolved here, so the sandbox still holds none it does not use."""
    # deferred (pair): sandbox and bootstrap would import each other at load
    from squadops.bootstrap.secrets import secret_manager_from_env as selected

    return selected()


def build_app() -> FastAPI:
    # Composition root — the one place the execution domain meets adapters.
    from adapters.sandbox.factory import create_sandbox_service, resolve_service_token

    config = sandbox_config_from_env()
    if config.provider == "docker" and not config.app_network:
        # #2451 part 4: inside a deploy the service is a container, and an app published to the
        # host's loopback is out of its reach. Required here, never defaulted (#1568).
        raise ValueError(
            "the sandbox service runs apps on its app network: set SQUADOPS__SANDBOX__APP_NETWORK"
        )
    service = create_sandbox_service(config)
    token = resolve_service_token(config, secret_manager=secret_manager_from_env())
    return create_app(service, service_token=token)

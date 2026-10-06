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

import os
from collections.abc import Iterable

from fastapi import FastAPI

from squadops.config.schema import SandboxConfig, SecretsConfig
from squadops.core.secrets import SecretManager
from squadops.sandbox.api import create_app

_ENV_PREFIX = "SQUADOPS__SANDBOX__"
_SECRETS_PREFIX = "SQUADOPS__SECRETS__"


def _section_from_env(prefix: str, fields: Iterable[str]) -> dict[str, str]:
    """One config section's env vars, keyed by field. Unknown fields fail loudly rather than
    being silently dropped: a typo would otherwise deploy as an unconfigured default."""
    values = {
        key[len(prefix) :].lower(): value
        for key, value in os.environ.items()
        if key.startswith(prefix)
    }
    unknown = set(values) - set(fields)
    if unknown:
        raise ValueError(
            f"unknown {prefix} settings: {sorted(unknown)} "
            "(a typo here would otherwise be silently ignored)"
        )
    return values


def sandbox_config_from_env() -> SandboxConfig:
    """Build the execution section from its env vars (pydantic coerces types)."""
    return SandboxConfig(**_section_from_env(_ENV_PREFIX, SandboxConfig.model_fields))


def secret_manager_from_env() -> SecretManager | None:
    """The secrets provider the ``SQUADOPS__SECRETS__*`` section selects, or ``None`` when it
    selects none (#1982). Only the provider's selection is read: no other platform secret is
    resolved here, so the sandbox still holds none it does not use."""
    values = _section_from_env(_SECRETS_PREFIX, SecretsConfig.model_fields)
    if not values:
        return None
    from squadops.bootstrap.secrets import secret_provider_for

    secrets = SecretsConfig.model_validate(values)
    return SecretManager(provider=secret_provider_for(secrets), name_map=secrets.name_map or {})


def build_app() -> FastAPI:
    # Composition root — the one place the execution domain meets adapters.
    from adapters.sandbox.factory import create_sandbox_service, resolve_service_token

    config = sandbox_config_from_env()
    service = create_sandbox_service(config)
    token = resolve_service_token(config, secret_manager=secret_manager_from_env())
    return create_app(service, service_token=token)

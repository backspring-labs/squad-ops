"""Execution service entrypoint (SIP-0102 — 102.1 slice d).

Composition root: builds the service core via the factory and wraps it in the
HTTP surface.

Config note: this service reads ONLY its own ``SQUADOPS__EXECUTION__*``
section, deliberately not the full ``load_config()`` — the layered loader
eagerly resolves every ``secret://`` reference in the platform config, which
would make this container require secrets (Keycloak admin, DB passwords) it
must never hold. Same env-var convention, narrower blast radius. Revisit if
the service ever needs file-layered config (the 102.2 environment contract is
its own artifact, not a config layer).

Run with:  uvicorn --factory squadops.execution.main:build_app --port 8002
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from squadops.config.schema import ExecutionConfig
from squadops.execution.api import create_app

_ENV_PREFIX = "SQUADOPS__EXECUTION__"


def execution_config_from_env() -> ExecutionConfig:
    """Build the execution section from its env vars (pydantic coerces types;
    unknown fields fail loudly rather than being silently dropped)."""
    values = {
        key[len(_ENV_PREFIX) :].lower(): value
        for key, value in os.environ.items()
        if key.startswith(_ENV_PREFIX)
    }
    unknown = set(values) - set(ExecutionConfig.model_fields)
    if unknown:
        raise ValueError(
            f"unknown SQUADOPS__EXECUTION__ settings: {sorted(unknown)} "
            "(a typo here would otherwise be silently ignored)"
        )
    return ExecutionConfig(**values)


def build_app() -> FastAPI:
    # Composition root — the one place the execution domain meets adapters.
    from adapters.execution.factory import create_execution_service, resolve_service_token

    config = execution_config_from_env()
    service = create_execution_service(config)
    return create_app(service, service_token=resolve_service_token(config))

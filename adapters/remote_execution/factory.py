"""Remote execution's adapters (SIP-0117 R5.4, R5.5, R5.6).

The worker registry's store is chosen by the cycle registry's selector: its operations belong
to the cycles that asked for them, so it lives beside them. A worker's operation runner is
chosen by the worker's own ``provider``, and its way to the runtime is HTTP. An agent's
remote-execution port is chosen by ``remote_execution.provider``, and so is the runtime's own
(#3053), which queues straight into the registry.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from typing import TYPE_CHECKING

from squadops.ports.remote_execution import (
    OperationRunnerPort,
    RemoteExecutionPort,
    WorkerApiPort,
    WorkerRegistryStorePort,
)

if TYPE_CHECKING:
    from squadops.ports.tool_authority import ToolAuthorityPort
    from squadops.remote_execution.registry import WorkerRegistry
    from squadops.remote_execution.workers import HostCheck


def create_remote_execution(
    provider: str,
    *,
    base_url: str,
    token: Callable[[], Awaitable[str]] | None,
    origin: Mapping[str, str],
    wait: timedelta,
    max_attempts: int,
) -> RemoteExecutionPort | None:
    """The agent's remote-execution port, for the provider the config names (R5.6).

    ``none`` is a deploy that runs no remote execution: it binds no port, and the handler of
    ``qa.run_remote_operation`` reports its operation as not executed, with that reason.
    ``runtime_api`` queues the operation at the runtime API at ``base_url`` for a worker.
    """
    if provider == "none":
        return None
    if provider == "runtime_api":
        from adapters.remote_execution.runtime_api_remote_execution import (
            RuntimeApiRemoteExecution,
        )

        return RuntimeApiRemoteExecution(
            base_url, token, origin=origin, wait=wait, max_attempts=max_attempts
        )
    raise ValueError(f"Unknown remote execution provider: {provider}")


def create_runtime_remote_execution(
    provider: str,
    *,
    registry: WorkerRegistry,
    origin: Mapping[str, str],
    wait: timedelta,
    max_attempts: int,
) -> RemoteExecutionPort | None:
    """The runtime's own remote-execution port (#3053, #3044), on the same provider vocabulary
    as an agent's. ``none`` binds nothing. ``runtime_api``, where the runtime is the API,
    queues straight into ``registry``: the one the worker routes serve, never back through its
    own HTTP."""
    if provider == "none":
        return None
    if provider == "runtime_api":
        from adapters.remote_execution.registry_remote_execution import RegistryRemoteExecution

        return RegistryRemoteExecution(
            registry, origin=origin, wait=wait, max_attempts=max_attempts
        )
    raise ValueError(f"Unknown remote execution provider: {provider}")


def create_worker_registry_store(provider: str, **kwargs) -> WorkerRegistryStorePort:
    if provider == "memory":
        from adapters.remote_execution.memory_worker_registry_store import (
            MemoryWorkerRegistryStore,
        )

        return MemoryWorkerRegistryStore()
    if provider == "postgres":
        pool = kwargs.get("pool")
        if pool is None:
            raise ValueError("pool is required for the postgres worker registry store")
        from adapters.remote_execution.postgres_worker_registry_store import (
            PostgresWorkerRegistryStore,
        )

        return PostgresWorkerRegistryStore(pool=pool)
    raise ValueError(f"Unknown worker registry store provider: {provider}")


def create_operation_runner(provider: str, settings: Mapping[str, str]) -> OperationRunnerPort:
    """The runner for the provider a worker's config names, created with that provider's own
    settings. ``fixture`` is this package's. Every other provider is found as the
    ``worker.PROVIDER`` of a provider package under this one, and created by its
    ``worker.create_runner(settings)``, as ``create_tool_authorities`` finds authorities: a
    platform's name stays in its own directory (SIP-0117 R4.6). A provider no package serves, or
    one two packages serve, raises."""
    if provider == "fixture":
        from adapters.remote_execution.fixture_operation_runner import FixtureOperationRunner

        if settings:
            raise ValueError(
                f"the fixture provider takes no settings, and was given {sorted(settings)}"
            )
        return FixtureOperationRunner()
    found = _provider_packages("worker")
    serving = [module for module in found if module.PROVIDER == provider]
    if len(serving) != 1:
        known = sorted({"fixture", *(module.PROVIDER for module in found)})
        raise ValueError(
            f"{len(serving)} provider packages serve {provider!r}, and exactly one must "
            f"(the providers found: {known})"
        )
    return serving[0].create_runner(settings)


def provider_host_checks(provider: str, settings: Mapping[str, str]) -> list[HostCheck]:
    """What the provider checks of the machine its worker runs on (#3046): its tool installed,
    its files where the settings say, and what it was proved on. Found as the provider package's
    ``worker.host_checks(settings)``, so a platform's name stays in its own directory (SIP-0117
    R4.6). ``fixture`` drives no tool and checks nothing. A provider no package serves raises."""
    if provider == "fixture":
        return []
    found = _provider_packages("worker")
    serving = [module for module in found if module.PROVIDER == provider]
    if len(serving) != 1:
        known = sorted({"fixture", *(module.PROVIDER for module in found)})
        raise ValueError(
            f"{len(serving)} provider packages serve {provider!r}, and exactly one must "
            f"(the providers found: {known})"
        )
    return list(serving[0].host_checks(settings))


def _provider_packages(module: str) -> list:
    """Every provider package's ``module``, imported. A package without one is skipped, and one
    that fails to import raises."""
    import importlib
    import importlib.util
    import pkgutil

    import adapters.remote_execution as package

    modules = []
    for found in pkgutil.iter_modules(package.__path__):
        if not found.ispkg:
            continue
        name = f"{package.__name__}.{found.name}.{module}"
        if importlib.util.find_spec(name) is not None:
            modules.append(importlib.import_module(name))
    return modules


def create_tool_authorities() -> dict[str, ToolAuthorityPort]:
    """Each provider's authority over its operations (SIP-0116 §8, §17n), by provider name: the
    ``eligibility.AUTHORITY`` of every provider package under this one that governs its products.
    Found rather than named, so a platform's name stays in its own directory (SIP-0117 R4.6):
    removing the platform removes its authority, and a tool of a provider with none is refused at
    creation. A package's eligibility module that fails to import raises: a provider that governs
    its products never goes ungoverned in silence."""
    authorities: dict[str, ToolAuthorityPort] = {}
    for module in _provider_packages("eligibility"):
        authorities[module.AUTHORITY.provider] = module.AUTHORITY
    return authorities


def create_worker_api(base_url: str, token: Callable[[], Awaitable[str]]) -> WorkerApiPort:
    """The runtime API at ``base_url``, called with the bearer token ``token`` returns."""
    from adapters.remote_execution.http_worker_api import HttpWorkerApi

    return HttpWorkerApi(base_url, token)

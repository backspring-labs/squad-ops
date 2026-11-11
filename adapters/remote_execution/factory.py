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
    from squadops.remote_execution.registry import WorkerRegistry


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


def create_operation_runner(provider: str) -> OperationRunnerPort:
    """The runner for the provider a worker's config names."""
    if provider == "fixture":
        from adapters.remote_execution.fixture_operation_runner import FixtureOperationRunner

        return FixtureOperationRunner()
    raise ValueError(f"Unknown operation runner provider: {provider}")


def create_worker_api(base_url: str, token: Callable[[], Awaitable[str]]) -> WorkerApiPort:
    """The runtime API at ``base_url``, called with the bearer token ``token`` returns."""
    from adapters.remote_execution.http_worker_api import HttpWorkerApi

    return HttpWorkerApi(base_url, token)

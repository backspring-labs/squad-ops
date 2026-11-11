"""The worker registry's store (SIP-0117 R5.4), chosen by the cycle registry's selector: its
operations belong to the cycles that asked for them, so it lives beside them."""

from __future__ import annotations

from squadops.ports.remote_execution import WorkerRegistryStorePort


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

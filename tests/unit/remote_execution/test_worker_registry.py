"""The worker registry over the memory store (SIP-0117 R3.3, R5.4): the contract every store
is held to, and the store factory's refusals."""

from __future__ import annotations

import pytest

from adapters.remote_execution.factory import create_worker_registry_store
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from tests.unit.remote_execution.registry_contract import WorkerRegistryContract


class TestWorkerRegistryInMemory(WorkerRegistryContract):
    @pytest.fixture
    def store(self):
        return create_worker_registry_store("memory")


@pytest.mark.parametrize(
    ("provider", "kwargs", "message"),
    [
        ("postgres", {}, "pool is required"),
        ("redis", {}, "Unknown worker registry store provider: redis"),
        ("", {}, "Unknown worker registry store provider: "),
    ],
    ids=["postgres without its pool", "an unknown provider", "a blank provider"],
)
def test_the_store_factory_refuses_what_it_cannot_build(provider, kwargs, message):
    """Bug caught: a selector the factory doesn't know building the memory store, so a
    deployed runtime keeps its leases in a process that loses them at restart."""
    with pytest.raises(ValueError, match=message):
        create_worker_registry_store(provider, **kwargs)
    assert isinstance(create_worker_registry_store("memory"), MemoryWorkerRegistryStore)

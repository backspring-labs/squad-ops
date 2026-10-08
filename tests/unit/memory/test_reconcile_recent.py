"""The periodic pass beside execution (SIP-0110 §0.3; #2096): the recent cycles and campaigns are
projected again, a source that fails never stops the others, and the runtime composes the store
from the cycle registry's required provider."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.memory.cross_cycle import (
    InMemoryCrossCycleMemoryStore,
    PostgresCrossCycleMemoryStore,
    create_cross_cycle_store,
)
from squadops.memory.reconcile import reconcile_recent
from tests.unit.cycles.test_benchmark_registry import _cycle
from tests.unit.memory.test_observations import _MOCK_MISUSE, _run, _summary

pytestmark = [pytest.mark.domain_memory]

NOW = datetime(2026, 10, 8, 3, 0, tzinfo=UTC)


class _Projects:
    async def list_projects(self):
        return [SimpleNamespace(project_id="group_run")]


class _NoCampaigns:
    async def list_campaigns(self, project_id):
        return []


class _Vault:
    async def list_artifacts(self, **kwargs):
        return []


async def _registry(*cycles: tuple[str, datetime]) -> MemoryCycleRegistry:
    registry = MemoryCycleRegistry()
    for cycle_id, created in cycles:
        await registry.create_cycle(dataclasses.replace(_cycle(cycle_id), created_at=created))
        run = dataclasses.replace(_run(f"run_{cycle_id}"), cycle_id=cycle_id)
        await registry.create_run(run)
        await registry.record_run_loop_summary(run.run_id, _summary(run.run_id, _MOCK_MISUSE))
    return registry


async def test_a_pass_projects_the_recent_cycles_and_leaves_the_old_to_the_backfill():
    """Bug caught: every pass re-reading all of history (hundreds of cycles every five minutes),
    or a recent cycle missed because the walk stopped early."""
    registry = await _registry(
        ("cyc_new", NOW - timedelta(hours=2)), ("cyc_old", NOW - timedelta(days=5))
    )
    store = InMemoryCrossCycleMemoryStore()

    new = await reconcile_recent(
        projects=_Projects(),
        registry=registry,
        campaigns=_NoCampaigns(),
        vault=_Vault(),
        store=store,
        now=NOW,
    )

    assert new == 1
    assert [o.cycle_id for o in await store.list_observations("group_run")] == ["cyc_new"]


async def test_a_cycle_that_fails_to_project_never_stops_the_others():
    """Bug caught: one unreadable cycle starving every later one of its observations until the
    process restarts. The failed one is recovered by the next pass."""
    registry = await _registry(
        ("cyc_a", NOW - timedelta(hours=1)), ("cyc_b", NOW - timedelta(hours=2))
    )
    real_get = registry.get_cycle

    async def flaky(cycle_id):
        if cycle_id == "cyc_a":
            raise ConnectionError("one bad read")
        return await real_get(cycle_id)

    registry.get_cycle = flaky  # type: ignore[method-assign]
    store = InMemoryCrossCycleMemoryStore()

    new = await reconcile_recent(
        projects=_Projects(),
        registry=registry,
        campaigns=_NoCampaigns(),
        vault=_Vault(),
        store=store,
        now=NOW,
    )

    assert new == 1
    assert [o.cycle_id for o in await store.list_observations("group_run")] == ["cyc_b"]


def test_the_runtime_composes_the_store_from_the_registry_provider():
    """Wiring, entered at the runtime's ``_init_memory``. Bug caught: the store built by a default
    rather than the registry's required provider (#1568), so a Postgres deploy kept its
    observations in a process's memory."""
    from squadops.api.runtime.main import _init_memory

    for provider, kind in (
        ("memory", InMemoryCrossCycleMemoryStore),
        ("postgres", PostgresCrossCycleMemoryStore),
    ):
        state = SimpleNamespace()
        config = SimpleNamespace(cycles=SimpleNamespace(registry_provider=provider))
        _init_memory(state, config, pool=object())
        assert isinstance(state.memory_store, kind)

    with pytest.raises(ValueError, match="unknown cross-cycle memory store provider"):
        create_cross_cycle_store("lancedb")

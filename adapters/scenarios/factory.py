"""The scenario store's adapter (SIP-0113 §4.1; #2413), chosen by the cycle registry's selector:
it lives beside the campaigns that pin its suites."""

from __future__ import annotations

from squadops.ports.scenarios import ScenarioStorePort


def create_scenario_store(provider: str, **kwargs) -> ScenarioStorePort:
    if provider == "memory":
        from adapters.scenarios.memory_scenario_store import MemoryScenarioStore

        return MemoryScenarioStore()
    if provider == "postgres":
        pool = kwargs.get("pool")
        if pool is None:
            raise ValueError("pool is required for the postgres scenario store")
        from adapters.scenarios.postgres_scenario_store import PostgresScenarioStore

        return PostgresScenarioStore(pool=pool)
    raise ValueError(f"Unknown scenario store provider: {provider}")

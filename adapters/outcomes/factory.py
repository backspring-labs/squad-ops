"""The intervention ledger's store (SIP-0113 §4.3; #2417), chosen by the cycle registry's
selector: it lives beside the campaigns whose control logs it classifies."""

from __future__ import annotations

from squadops.ports.outcomes import InterventionLedgerPort


def create_intervention_ledger(provider: str, **kwargs) -> InterventionLedgerPort:
    if provider == "memory":
        from adapters.outcomes.memory_ledger import MemoryInterventionLedger

        return MemoryInterventionLedger()
    if provider == "postgres":
        pool = kwargs.get("pool")
        if pool is None:
            raise ValueError("pool is required for the postgres intervention ledger")
        from adapters.outcomes.postgres_ledger import PostgresInterventionLedger

        return PostgresInterventionLedger(pool=pool)
    raise ValueError(f"Unknown intervention ledger provider: {provider}")

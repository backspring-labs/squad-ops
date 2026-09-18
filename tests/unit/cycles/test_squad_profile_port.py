"""
Port contract tests for SquadProfilePort (SIP-0075 §1.9).

Verifies that all abstract methods are defined and that concrete
adapters implement the full interface.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    CycleError,
    SquadProfile,
)
from squadops.ports.cycles.squad_profile import SquadProfilePort

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_PROFILE = SquadProfile(
    profile_id="full",
    name="Full Squad",
    description="All agents",
    version=1,
    agents=(
        AgentProfileEntry(
            agent_id="neo", role="dev", model="qwen2.5:7b", enabled=True, serves_roles=("dev",)
        ),
    ),
    created_at=NOW,
)

# All abstract methods that adapters must implement.
_EXPECTED_METHODS = [
    "list_profiles",
    "get_profile",
    "get_active_profile",
    "set_active_profile",
    "resolve_snapshot",
    "create_profile",
    "update_profile",
    "delete_profile",
    "activate_profile",
    "get_active_profile_id",
    "seed_profiles",
]


class TestPortInterface:
    """Verify the port defines the expected abstract methods."""

    @pytest.mark.parametrize("method_name", _EXPECTED_METHODS)
    def test_port_has_abstract_method(self, method_name):
        assert hasattr(SquadProfilePort, method_name)
        method = getattr(SquadProfilePort, method_name)
        assert callable(method)

    @pytest.mark.parametrize("method_name", _EXPECTED_METHODS)
    def test_port_methods_are_async(self, method_name):
        method = getattr(SquadProfilePort, method_name)
        assert inspect.iscoroutinefunction(method), f"{method_name} should be async"

    def test_port_is_abstract(self):
        with pytest.raises(TypeError):
            SquadProfilePort()  # type: ignore[abstract]


class TestConfigAdapterCompliance:
    """Verify ConfigSquadProfile implements all port methods."""

    def test_implements_all_methods(self):
        from adapters.cycles.config_squad_profile import ConfigSquadProfile

        adapter = ConfigSquadProfile()
        for method_name in _EXPECTED_METHODS:
            assert hasattr(adapter, method_name), (
                f"ConfigSquadProfile missing method: {method_name}"
            )

    async def test_crud_stubs_raise(self):
        from adapters.cycles.config_squad_profile import ConfigSquadProfile

        adapter = ConfigSquadProfile()
        with pytest.raises(CycleError, match="Read-only"):
            await adapter.create_profile(_PROFILE)
        with pytest.raises(CycleError, match="Read-only"):
            await adapter.update_profile("x", name="y")
        with pytest.raises(CycleError, match="Read-only"):
            await adapter.delete_profile("x")
        with pytest.raises(CycleError, match="Read-only"):
            await adapter.activate_profile("x")
        with pytest.raises(CycleError, match="Read-only"):
            await adapter.seed_profiles([])

    async def test_get_active_profile_id_returns_none_by_default(self, tmp_path):
        from adapters.cycles.config_squad_profile import ConfigSquadProfile

        adapter = ConfigSquadProfile(yaml_path=tmp_path / "nonexistent.yaml")
        result = await adapter.get_active_profile_id()
        assert result is None


class TestPostgresAdapterCompliance:
    """Verify PostgresSquadProfile implements all port methods."""

    def test_implements_all_methods(self):
        from adapters.cycles.postgres_squad_profile import PostgresSquadProfile

        adapter = PostgresSquadProfile(pool=MagicMock())
        for method_name in _EXPECTED_METHODS:
            assert hasattr(adapter, method_name), (
                f"PostgresSquadProfile missing method: {method_name}"
            )


class TestFactoryProviders:
    """Verify factory creates both providers."""

    def test_postgres_requires_pool(self):
        from adapters.cycles.factory import create_squad_profile_port

        with pytest.raises(ValueError, match="pool is required"):
            create_squad_profile_port("postgres")

    def test_unknown_provider_raises(self):
        from adapters.cycles.factory import create_squad_profile_port

        with pytest.raises(ValueError, match="Unknown"):
            create_squad_profile_port("nosql")


async def test_every_seeded_profile_keeps_its_snapshot_hash_through_the_postgres_row():
    """#1568 moves the deploy's squad profiles to Postgres, seeded from the YAML. Bug caught: a
    field the row drops or re-types (an override's int read back as a string, an agent's enabled
    flag lost), so a seeded profile hashes differently from the same YAML profile and every
    counted roll's squad snapshot pin moves with no change to the squad.

    Since 1.8.1 the round trip also carries ``serves_roles``, which the snapshot payload covers
    because it decides which agent runs each step (SIP-0108 §10i item 1). That makes this the
    shape check on migration 1510's output too: a backfilled row and the YAML profile it was
    seeded from must still hash alike. ``full-38`` reads ``78955d7988f21eec`` under the current
    formula; refs stamped before it were taken over a payload without the field and are not
    reproducible by it."""
    import json

    from adapters.cycles.config_squad_profile import ConfigSquadProfile
    from adapters.cycles.postgres_squad_profile import PostgresSquadProfile
    from squadops.cycles.lifecycle import compute_profile_snapshot_hash

    adapter = PostgresSquadProfile.__new__(PostgresSquadProfile)
    profiles = await ConfigSquadProfile().list_profiles()
    for profile in profiles:
        row = {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "description": profile.description,
            "version": profile.version,
            # JSONB: what is written is what the codec reads back.
            "agents": json.loads(json.dumps(adapter._agents_to_dicts(profile.agents))),
            "created_at": profile.created_at,
        }
        seeded = adapter._row_to_profile(row)

        assert compute_profile_snapshot_hash(seeded) == compute_profile_snapshot_hash(profile)
        assert seeded.agents[0].serves_roles == profile.agents[0].serves_roles
    assert "full-38" in {p.profile_id for p in profiles}

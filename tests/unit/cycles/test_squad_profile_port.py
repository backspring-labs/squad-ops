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
    profile_id="full-squad",
    name="Full Squad",
    description="All agents",
    version=1,
    agents=(AgentProfileEntry(agent_id="neo", role="dev", model="qwen2.5:7b", enabled=True),),
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

    def test_config_provider(self):
        from adapters.cycles.factory import create_squad_profile_port

        port = create_squad_profile_port("config")
        assert isinstance(port, SquadProfilePort)

    def test_postgres_provider(self):
        from adapters.cycles.factory import create_squad_profile_port

        port = create_squad_profile_port("postgres", pool=MagicMock())
        assert isinstance(port, SquadProfilePort)

    def test_postgres_requires_pool(self):
        from adapters.cycles.factory import create_squad_profile_port

        with pytest.raises(ValueError, match="pool is required"):
            create_squad_profile_port("postgres")

    def test_unknown_provider_raises(self):
        from adapters.cycles.factory import create_squad_profile_port

        with pytest.raises(ValueError, match="Unknown"):
            create_squad_profile_port("nosql")

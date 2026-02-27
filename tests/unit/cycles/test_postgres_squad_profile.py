"""Tests for PostgresSquadProfile adapter (SIP-0075 §1.5)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.cycles.models import (
    ActiveProfileDeletionError,
    AgentProfileEntry,
    ProfileNotFoundError,
    ProfileValidationError,
    SquadProfile,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_AGENTS = (
    AgentProfileEntry(agent_id="neo", role="dev", model="qwen2.5:7b", enabled=True),
    AgentProfileEntry(agent_id="eve", role="qa", model="qwen2.5:7b", enabled=True),
)


def _make_profile(profile_id: str = "full-squad", name: str = "Full Squad") -> SquadProfile:
    return SquadProfile(
        profile_id=profile_id,
        name=name,
        description="Test profile",
        version=1,
        agents=_AGENTS,
        created_at=NOW,
    )


def _make_row(
    profile_id: str = "full-squad",
    name: str = "Full Squad",
    is_active: bool = False,
    version: int = 1,
) -> MagicMock:
    agents_json = json.dumps(
        [
            {
                "agent_id": "neo",
                "role": "dev",
                "model": "qwen2.5:7b",
                "enabled": True,
                "config_overrides": {},
            },
            {
                "agent_id": "eve",
                "role": "qa",
                "model": "qwen2.5:7b",
                "enabled": True,
                "config_overrides": {},
            },
        ]
    )
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "profile_id": profile_id,
        "name": name,
        "description": "Test profile",
        "version": version,
        "is_active": is_active,
        "agents": agents_json,
        "created_at": NOW,
        "updated_at": NOW,
    }[key]
    return row


@pytest.fixture()
def mock_pool():
    return MagicMock()


@pytest.fixture()
def adapter(mock_pool):
    from adapters.cycles.postgres_squad_profile import PostgresSquadProfile

    return PostgresSquadProfile(pool=mock_pool)


class _FakeTransaction:
    """Fake async context manager for conn.transaction()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _setup_conn(mock_pool):
    conn = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=_FakeTransaction())
    mock_pool.acquire.return_value = conn
    return conn


class TestListProfiles:
    async def test_returns_profiles(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetch = AsyncMock(return_value=[_make_row()])
        result = await adapter.list_profiles()
        assert len(result) == 1
        assert result[0].profile_id == "full-squad"

    async def test_empty_list(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetch = AsyncMock(return_value=[])
        result = await adapter.list_profiles()
        assert result == []


class TestGetProfile:
    async def test_found(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=_make_row())
        profile = await adapter.get_profile("full-squad")
        assert profile.profile_id == "full-squad"

    async def test_not_found(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ProfileNotFoundError):
            await adapter.get_profile("nonexistent")


class TestGetActiveProfile:
    async def test_found(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=_make_row(is_active=True))
        profile = await adapter.get_active_profile()
        assert profile.profile_id == "full-squad"

    async def test_none_active(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ProfileNotFoundError):
            await adapter.get_active_profile()


class TestCreateProfile:
    async def test_success(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.execute = AsyncMock()
        profile = _make_profile()
        result = await adapter.create_profile(profile)
        assert result.profile_id == "full-squad"
        conn.execute.assert_awaited_once()

    async def test_duplicate_raises(self, adapter, mock_pool):
        import asyncpg

        conn = _setup_conn(mock_pool)
        conn.execute = AsyncMock(side_effect=asyncpg.UniqueViolationError("dup"))
        with pytest.raises(ProfileValidationError, match="already exists"):
            await adapter.create_profile(_make_profile())


class TestUpdateProfile:
    async def test_updates_version(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(side_effect=[_make_row(), _make_row(version=2)])
        result = await adapter.update_profile("full-squad", name="Updated Name")
        assert result.version == 2

    async def test_not_found(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ProfileNotFoundError):
            await adapter.update_profile("nonexistent", name="New Name")


class TestDeleteProfile:
    async def test_success(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        row = MagicMock()
        row.__getitem__ = lambda self, key: {"is_active": False}[key]
        conn.fetchrow = AsyncMock(return_value=row)
        conn.execute = AsyncMock()
        await adapter.delete_profile("full-squad")
        conn.execute.assert_awaited_once()

    async def test_not_found(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ProfileNotFoundError):
            await adapter.delete_profile("nonexistent")

    async def test_active_profile_rejected(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        row = MagicMock()
        row.__getitem__ = lambda self, key: {"is_active": True}[key]
        conn.fetchrow = AsyncMock(return_value=row)
        with pytest.raises(ActiveProfileDeletionError):
            await adapter.delete_profile("full-squad")


class TestActivateProfile:
    async def test_atomic_activation(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(side_effect=[_make_row(), _make_row(is_active=True)])
        conn.execute = AsyncMock()

        result = await adapter.activate_profile("full-squad")
        assert result.profile_id == "full-squad"
        conn.execute.assert_awaited_once()

    async def test_not_found(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ProfileNotFoundError):
            await adapter.activate_profile("nonexistent")


class TestGetActiveProfileId:
    async def test_with_active(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        row = MagicMock()
        row.__getitem__ = lambda self, key: {"profile_id": "full-squad"}[key]
        conn.fetchrow = AsyncMock(return_value=row)
        result = await adapter.get_active_profile_id()
        assert result == "full-squad"

    async def test_no_active(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=None)
        result = await adapter.get_active_profile_id()
        assert result is None


class TestSeedProfiles:
    async def test_seeds_new_profile(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchval = AsyncMock(side_effect=[None, None, None])
        conn.execute = AsyncMock()

        profiles = [_make_profile()]
        seeded = await adapter.seed_profiles(profiles)
        assert seeded == 1

    async def test_skips_already_seeded(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        conn.fetchval = AsyncMock(return_value=1)  # already in seed_log

        profiles = [_make_profile()]
        seeded = await adapter.seed_profiles(profiles)
        assert seeded == 0

    async def test_sets_active_on_seed(self, adapter, mock_pool):
        conn = _setup_conn(mock_pool)
        # First fetchval: seed_log check (None = not seeded)
        # Then fetchval: profile exists check (1 = yes)
        # Then fetchval: current active check (None = no active)
        conn.fetchval = AsyncMock(side_effect=[None, 1, None])
        conn.execute = AsyncMock()

        profiles = [_make_profile()]
        seeded = await adapter.seed_profiles(profiles, active_id="full-squad")
        assert seeded == 1

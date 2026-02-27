"""Postgres-backed squad profile adapter (SIP-0075).

Implements SquadProfilePort with durable persistence via asyncpg.
Replaces ConfigSquadProfile for production use with full CRUD support.
"""

from __future__ import annotations

import json
import logging

import asyncpg

from squadops.cycles.lifecycle import compute_profile_snapshot_hash
from squadops.cycles.models import (
    ActiveProfileDeletionError,
    AgentProfileEntry,
    ProfileNotFoundError,
    ProfileValidationError,
    SquadProfile,
)
from squadops.ports.cycles.squad_profile import SquadProfilePort

logger = logging.getLogger(__name__)


class PostgresSquadProfile(SquadProfilePort):
    """Postgres-backed SquadProfilePort implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- Read ---

    async def list_profiles(self) -> list[SquadProfile]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM squad_profiles ORDER BY created_at ASC")
        return [self._row_to_profile(row) for row in rows]

    async def get_profile(self, profile_id: str) -> SquadProfile:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM squad_profiles WHERE profile_id = $1", profile_id
            )
        if row is None:
            raise ProfileNotFoundError(f"Squad profile not found: {profile_id}")
        return self._row_to_profile(row)

    async def get_active_profile(self) -> SquadProfile:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM squad_profiles WHERE is_active = TRUE")
        if row is None:
            raise ProfileNotFoundError("No active squad profile configured")
        return self._row_to_profile(row)

    async def set_active_profile(self, profile_id: str) -> None:
        await self.activate_profile(profile_id)

    async def resolve_snapshot(self, profile_id: str) -> tuple[SquadProfile, str]:
        profile = await self.get_profile(profile_id)
        snapshot_hash = compute_profile_snapshot_hash(profile)
        return profile, snapshot_hash

    # --- CRUD ---

    async def create_profile(self, profile: SquadProfile) -> SquadProfile:
        agents_json = json.dumps(self._agents_to_dicts(profile.agents))
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO squad_profiles "
                    "(profile_id, name, description, version, is_active, agents, "
                    "created_at, updated_at) "
                    "VALUES ($1, $2, $3, $4, FALSE, $5, $6, $6)",
                    profile.profile_id,
                    profile.name,
                    profile.description,
                    profile.version,
                    agents_json,
                    profile.created_at,
                )
        except asyncpg.UniqueViolationError as err:
            raise ProfileValidationError(f"Profile already exists: {profile.profile_id}") from err
        return profile

    async def update_profile(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        agents: tuple | None = None,
    ) -> SquadProfile:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM squad_profiles WHERE profile_id = $1", profile_id
            )
            if row is None:
                raise ProfileNotFoundError(f"Squad profile not found: {profile_id}")

            new_name = name if name is not None else row["name"]
            new_desc = description if description is not None else row["description"]
            new_agents = (
                json.dumps(self._agents_to_dicts(agents)) if agents is not None else row["agents"]
            )
            new_version = row["version"] + 1

            updated_row = await conn.fetchrow(
                "UPDATE squad_profiles "
                "SET name = $2, description = $3, agents = $4, "
                "version = $5, updated_at = NOW() "
                "WHERE profile_id = $1 "
                "RETURNING *",
                profile_id,
                new_name,
                new_desc,
                new_agents,
                new_version,
            )
        return self._row_to_profile(updated_row)

    async def delete_profile(self, profile_id: str) -> None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT is_active FROM squad_profiles WHERE profile_id = $1",
                profile_id,
            )
            if row is None:
                raise ProfileNotFoundError(f"Squad profile not found: {profile_id}")
            if row["is_active"]:
                raise ActiveProfileDeletionError(f"Cannot delete active profile: {profile_id}")
            await conn.execute("DELETE FROM squad_profiles WHERE profile_id = $1", profile_id)

    async def activate_profile(self, profile_id: str) -> SquadProfile:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT * FROM squad_profiles WHERE profile_id = $1", profile_id
                )
                if row is None:
                    raise ProfileNotFoundError(f"Squad profile not found: {profile_id}")
                await conn.execute(
                    "UPDATE squad_profiles SET is_active = FALSE WHERE is_active = TRUE"
                )
                updated_row = await conn.fetchrow(
                    "UPDATE squad_profiles SET is_active = TRUE WHERE profile_id = $1 RETURNING *",
                    profile_id,
                )
        return self._row_to_profile(updated_row)

    async def get_active_profile_id(self) -> str | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT profile_id FROM squad_profiles WHERE is_active = TRUE"
            )
        return row["profile_id"] if row else None

    async def seed_profiles(
        self, profiles: list[SquadProfile], active_id: str | None = None
    ) -> int:
        seeded = 0
        async with self._pool.acquire() as conn:
            for profile in profiles:
                async with conn.transaction():
                    already = await conn.fetchval(
                        "SELECT 1 FROM squad_profiles_seed_log WHERE profile_id = $1",
                        profile.profile_id,
                    )
                    if already:
                        continue
                    await conn.execute(
                        "INSERT INTO squad_profiles_seed_log (profile_id) VALUES ($1) "
                        "ON CONFLICT DO NOTHING",
                        profile.profile_id,
                    )
                    await conn.execute(
                        "INSERT INTO squad_profiles "
                        "(profile_id, name, description, version, is_active, agents, "
                        "created_at, updated_at) "
                        "VALUES ($1, $2, $3, $4, FALSE, $5, $6, $6) "
                        "ON CONFLICT DO NOTHING",
                        profile.profile_id,
                        profile.name,
                        profile.description,
                        profile.version,
                        json.dumps(self._agents_to_dicts(profile.agents)),
                        profile.created_at,
                    )
                    seeded += 1
                    logger.info("Seeded squad profile: %s", profile.profile_id)

            if active_id and seeded > 0:
                exists = await conn.fetchval(
                    "SELECT 1 FROM squad_profiles WHERE profile_id = $1", active_id
                )
                if exists:
                    current_active = await conn.fetchval(
                        "SELECT profile_id FROM squad_profiles WHERE is_active = TRUE"
                    )
                    if current_active is None:
                        await conn.execute(
                            "UPDATE squad_profiles SET is_active = TRUE WHERE profile_id = $1",
                            active_id,
                        )
                        logger.info("Set active profile from seed: %s", active_id)

        logger.info("Seeded %d squad profiles", seeded)
        return seeded

    # --- Helpers ---

    @staticmethod
    def _parse_jsonb(value):
        """Decode a JSONB column value (asyncpg returns str by default)."""
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _agents_to_dicts(agents: tuple[AgentProfileEntry, ...]) -> list[dict]:
        """Serialize AgentProfileEntry tuples to list of dicts for JSONB."""
        return [
            {
                "agent_id": a.agent_id,
                "role": a.role,
                "model": a.model,
                "enabled": a.enabled,
                "config_overrides": a.config_overrides,
            }
            for a in agents
        ]

    def _row_to_profile(self, row: asyncpg.Record) -> SquadProfile:
        """Reconstruct SquadProfile from asyncpg Record."""
        agents_data = self._parse_jsonb(row["agents"])
        agents = tuple(
            AgentProfileEntry(
                agent_id=a["agent_id"],
                role=a["role"],
                model=a["model"],
                enabled=a.get("enabled", True),
                config_overrides=a.get("config_overrides", {}),
            )
            for a in agents_data
        )
        return SquadProfile(
            profile_id=row["profile_id"],
            name=row["name"],
            description=row["description"],
            version=row["version"],
            agents=agents,
            created_at=row["created_at"],
        )

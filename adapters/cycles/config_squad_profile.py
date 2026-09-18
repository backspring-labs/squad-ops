"""
Config-file squad profile adapter (SIP-0064).

Loads profiles from config/squad-profiles.yaml.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import yaml

from squadops.cycles.lifecycle import compute_profile_snapshot_hash
from squadops.cycles.models import AgentProfileEntry, CycleError, ProfileNotFoundError, SquadProfile
from squadops.ports.cycles.squad_profile import SquadProfilePort

logger = logging.getLogger(__name__)


def _require_serves_roles(profile_id: str, agent: dict) -> tuple[str, ...]:
    """The agent's declared served roles, refused when an enabled agent declares none.

    SIP-0108 §10i item 1: every profile declares its role → agent map. A disabled agent is
    exempt — it assigns nothing — so a profile may keep a retired member beside the agent
    that replaced it.
    """
    declared = tuple(agent.get("serves_roles") or ())
    if declared or not agent.get("enabled", True):
        return declared
    raise ValueError(
        f"squad profile {profile_id!r}: enabled agent {agent.get('agent_id')!r} declares no "
        "`serves_roles`. Every enabled agent declares the step roles it serves; for an agent "
        f"that serves only its own role write `serves_roles: [{agent.get('role')}]`."
    )


_DEFAULT_YAML_PATH = Path("config/squad-profiles.yaml")


class ConfigSquadProfile(SquadProfilePort):
    """Loads squad profiles from a YAML config file."""

    def __init__(self, yaml_path: str | Path | None = None) -> None:
        self._yaml_path = Path(yaml_path) if yaml_path else _DEFAULT_YAML_PATH
        self._profiles: dict[str, SquadProfile] = {}
        self._active_profile_id: str | None = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if not self._yaml_path.exists():
            logger.warning("Squad profiles YAML not found: %s", self._yaml_path)
            self._loaded = True
            return

        with open(self._yaml_path) as f:
            data = yaml.safe_load(f) or {}

        now = datetime.now(UTC)
        for entry in data.get("profiles", []):
            agents = tuple(
                AgentProfileEntry(
                    agent_id=a["agent_id"],
                    role=a["role"],
                    model=a["model"],
                    enabled=a.get("enabled", True),
                    config_overrides=a.get("config_overrides", {}),
                    serves_roles=_require_serves_roles(entry["profile_id"], a),
                )
                for a in entry.get("agents", [])
            )
            profile = SquadProfile(
                profile_id=entry["profile_id"],
                name=entry["name"],
                description=entry.get("description", ""),
                version=entry.get("version", 1),
                agents=agents,
                created_at=entry.get("created_at", now),
            )
            self._profiles[profile.profile_id] = profile

        self._active_profile_id = data.get("active_profile")
        logger.info("Loaded %d squad profiles from %s", len(self._profiles), self._yaml_path)
        self._loaded = True

    async def list_profiles(self) -> list[SquadProfile]:
        self._load()
        return list(self._profiles.values())

    async def get_profile(self, profile_id: str) -> SquadProfile:
        self._load()
        if profile_id not in self._profiles:
            raise ProfileNotFoundError(f"Squad profile not found: {profile_id}")
        return self._profiles[profile_id]

    async def get_active_profile(self) -> SquadProfile:
        self._load()
        if self._active_profile_id is None or self._active_profile_id not in self._profiles:
            raise CycleError("No active squad profile configured")
        return self._profiles[self._active_profile_id]

    async def set_active_profile(self, profile_id: str) -> None:
        self._load()
        if profile_id not in self._profiles:
            raise ProfileNotFoundError(f"Squad profile not found: {profile_id}")
        self._active_profile_id = profile_id

    async def resolve_snapshot(self, profile_id: str) -> tuple[SquadProfile, str]:
        self._load()
        if profile_id not in self._profiles:
            raise ProfileNotFoundError(f"Squad profile not found: {profile_id}")
        profile = self._profiles[profile_id]
        snapshot_hash = compute_profile_snapshot_hash(profile)
        return profile, snapshot_hash

    # --- CRUD stubs (config provider is read-only) ---

    async def create_profile(self, profile: SquadProfile) -> SquadProfile:
        raise CycleError("Read-only: config provider does not support CRUD")

    async def update_profile(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        agents: tuple | None = None,
    ) -> SquadProfile:
        raise CycleError("Read-only: config provider does not support CRUD")

    async def delete_profile(self, profile_id: str) -> None:
        raise CycleError("Read-only: config provider does not support CRUD")

    async def activate_profile(self, profile_id: str) -> SquadProfile:
        raise CycleError("Read-only: config provider does not support CRUD")

    async def get_active_profile_id(self) -> str | None:
        self._load()
        return self._active_profile_id

    async def seed_profiles(
        self, profiles: list[SquadProfile], active_id: str | None = None
    ) -> int:
        raise CycleError("Read-only: config provider does not support seeding")

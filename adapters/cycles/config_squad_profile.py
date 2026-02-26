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
from squadops.cycles.models import AgentProfileEntry, CycleError, SquadProfile
from squadops.ports.cycles.squad_profile import SquadProfilePort

logger = logging.getLogger(__name__)

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
            raise CycleError(f"Squad profile not found: {profile_id}")
        return self._profiles[profile_id]

    async def get_active_profile(self) -> SquadProfile:
        self._load()
        if self._active_profile_id is None or self._active_profile_id not in self._profiles:
            raise CycleError("No active squad profile configured")
        return self._profiles[self._active_profile_id]

    async def set_active_profile(self, profile_id: str) -> None:
        self._load()
        if profile_id not in self._profiles:
            raise CycleError(f"Squad profile not found: {profile_id}")
        self._active_profile_id = profile_id

    async def resolve_snapshot(self, profile_id: str) -> tuple[SquadProfile, str]:
        self._load()
        if profile_id not in self._profiles:
            raise CycleError(f"Squad profile not found: {profile_id}")
        profile = self._profiles[profile_id]
        snapshot_hash = compute_profile_snapshot_hash(profile)
        return profile, snapshot_hash

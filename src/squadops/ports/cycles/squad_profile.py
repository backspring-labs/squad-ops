"""
SquadProfilePort — abstract interface for squad profile access (SIP-0064 §7.1).
"""

from abc import ABC, abstractmethod

from squadops.cycles.models import SquadProfile


class SquadProfilePort(ABC):
    """Port for read-only squad profile access with active selection."""

    @abstractmethod
    async def list_profiles(self) -> list[SquadProfile]:
        """Return all saved squad profiles."""

    @abstractmethod
    async def get_profile(self, profile_id: str) -> SquadProfile:
        """Return a profile by ID.

        Raises:
            CycleError: If the profile_id is not found.
        """

    @abstractmethod
    async def get_active_profile(self) -> SquadProfile:
        """Return the currently active profile."""

    @abstractmethod
    async def set_active_profile(self, profile_id: str) -> None:
        """Set the active profile.

        Raises:
            CycleError: If the profile_id is not found.
        """

    @abstractmethod
    async def resolve_snapshot(self, profile_id: str) -> tuple[SquadProfile, str]:
        """Resolve a profile and compute its deterministic snapshot hash.

        Returns:
            Tuple of (profile, snapshot_hash).

        Raises:
            CycleError: If the profile_id is not found.
        """

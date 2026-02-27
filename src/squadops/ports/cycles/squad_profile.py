"""
SquadProfilePort — abstract interface for squad profile access (SIP-0064 §7.1, SIP-0075).
"""

from abc import ABC, abstractmethod

from squadops.cycles.models import SquadProfile


class SquadProfilePort(ABC):
    """Port for squad profile access, activation, and CRUD."""

    # --- Read-only (SIP-0064) ---

    @abstractmethod
    async def list_profiles(self) -> list[SquadProfile]:
        """Return all saved squad profiles."""

    @abstractmethod
    async def get_profile(self, profile_id: str) -> SquadProfile:
        """Return a profile by ID.

        Raises:
            ProfileNotFoundError: If the profile_id is not found.
        """

    @abstractmethod
    async def get_active_profile(self) -> SquadProfile:
        """Return the currently active profile."""

    @abstractmethod
    async def set_active_profile(self, profile_id: str) -> None:
        """Set the active profile.

        Raises:
            ProfileNotFoundError: If the profile_id is not found.
        """

    @abstractmethod
    async def resolve_snapshot(self, profile_id: str) -> tuple[SquadProfile, str]:
        """Resolve a profile and compute its deterministic snapshot hash.

        Returns:
            Tuple of (profile, snapshot_hash).

        Raises:
            ProfileNotFoundError: If the profile_id is not found.
        """

    # --- CRUD (SIP-0075) ---

    @abstractmethod
    async def create_profile(self, profile: SquadProfile) -> SquadProfile:
        """Persist a new profile.

        Raises:
            ProfileValidationError: If profile_id already exists (409).
        """

    @abstractmethod
    async def update_profile(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        agents: tuple | None = None,
    ) -> SquadProfile:
        """Update a profile. Increments version and sets updated_at.

        Raises:
            ProfileNotFoundError: If the profile_id is not found.
        """

    @abstractmethod
    async def delete_profile(self, profile_id: str) -> None:
        """Delete a profile.

        Raises:
            ProfileNotFoundError: If the profile_id is not found.
            ActiveProfileDeletionError: If the profile is currently active.
        """

    @abstractmethod
    async def activate_profile(self, profile_id: str) -> SquadProfile:
        """Atomically deactivate current active and activate the given profile.

        Returns the newly activated profile.

        Raises:
            ProfileNotFoundError: If the profile_id is not found.
        """

    @abstractmethod
    async def get_active_profile_id(self) -> str | None:
        """Return the profile_id of the active profile, or None."""

    @abstractmethod
    async def seed_profiles(
        self, profiles: list[SquadProfile], active_id: str | None = None
    ) -> int:
        """Seed profiles from YAML. Skip already-seeded (via seed_log).

        Returns the number of newly seeded profiles.
        """

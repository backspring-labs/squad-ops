"""CampaignRegistryPort — the campaign's state, its control log and its launch outbox (SIP-0109 §16).

Every write is a control operation: the campaign's state change, its control-log row and any
launch intent it writes commit in one transaction, and the operation is acknowledged only after
they do (§13). The rules each operation follows are ``squadops.campaigns.lifecycle``'s, shared by
every adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    LaunchIntent,
    TransitionResult,
)


class CampaignRegistryPort(ABC):
    """Port for campaigns: create, read, transition; the control log; the launch outbox."""

    @abstractmethod
    async def create_campaign(
        self,
        campaign: Campaign,
        *,
        actor: str,
        actor_role: str,
        reason: str,
        idempotency_key: str,
    ) -> TransitionResult:
        """Persist a new campaign in ``draft`` with its creation row.

        A repeat of the same creation (same id, key and content) replays it.

        Raises:
            CampaignExistsError: If the id is held by a different creation.
            ValueError: If the campaign is not a fresh draft.
        """

    @abstractmethod
    async def get_campaign(self, campaign_id: str) -> Campaign:
        """Return a campaign by id.

        Raises:
            CampaignNotFoundError: If the campaign_id is not found.
        """

    @abstractmethod
    async def list_campaigns(self, project_id: str) -> list[Campaign]:
        """A project's campaigns, newest first by ``created_at``."""

    @abstractmethod
    async def campaigns_in_state(self, state: CampaignState) -> list[Campaign]:
        """Every project's campaigns in ``state``, oldest first by ``created_at``: what a sweep
        over the campaigns waiting on something reads (§24ae)."""

    @abstractmethod
    async def transition(
        self, campaign_id: str, transition: CampaignTransition
    ) -> TransitionResult:
        """Apply a control operation atomically, with its row and any launch intent it writes.

        A repeat of an applied idempotency key with the same content returns the recorded row and
        changes nothing.

        Raises:
            CampaignNotFoundError: If the campaign_id is not found.
            ControlOperationRefused: If the operation is refused. The refusal is recorded as a
                control-log row before this is raised.
        """

    @abstractmethod
    async def control_log(self, campaign_id: str) -> list[ControlLogEntry]:
        """The campaign's control log in commit order, refusals included.

        Raises:
            CampaignNotFoundError: If the campaign_id is not found.
        """

    @abstractmethod
    async def pending_launch_intents(self) -> list[LaunchIntent]:
        """Every intent not yet ``launched``, oldest first, whose campaign has not completed: no
        launch follows an abort, whatever was pending when it committed (§12a)."""

    @abstractmethod
    async def launch_intents(self, campaign_id: str) -> list[LaunchIntent]:
        """Every launch intent the campaign wrote, oldest first, in any state: an abort reads it
        to cancel the cycles the campaign launched (§12a).

        Raises:
            CampaignNotFoundError: If the campaign_id is not found.
        """

    @abstractmethod
    async def get_launch_intent(self, launch_id: str) -> LaunchIntent:
        """Return a launch intent by id.

        Raises:
            LaunchIntentNotFoundError: If the launch_id is not found.
        """

    @abstractmethod
    async def mark_launch_intent_launched(
        self, launch_id: str, cycle_id: str, *, actor: str
    ) -> TransitionResult:
        """Mark an intent ``launched`` with its cycle, in a control-log transition (§12b).

        Raises:
            LaunchIntentNotFoundError: If the launch_id is not found.
            ControlOperationRefused: If the intent is already marked with a different cycle.
        """

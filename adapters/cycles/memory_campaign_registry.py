"""Campaigns in memory (SIP-0109 §16): the test and no-database twin of the Postgres adapter.

Each operation computes everything it writes first, then commits it in one step with no await
between the writes, under one lock — the in-memory form of the Postgres adapter's transaction.
Every rule is ``squadops.campaigns.lifecycle``'s; this adapter only stores.
"""

from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime

from squadops.campaigns import lifecycle
from squadops.campaigns.models import (
    Campaign,
    CampaignExistsError,
    CampaignNotFoundError,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperationRefused,
    ControlOutcome,
    LaunchIntent,
    LaunchIntentNotFoundError,
    LaunchIntentState,
    TransitionResult,
)
from squadops.ports.cycles.campaign_registry import CampaignRegistryPort


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryCampaignRegistry(CampaignRegistryPort):
    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}
        self._log: dict[str, list[ControlLogEntry]] = {}
        self._intents: dict[str, LaunchIntent] = {}
        self._lock = asyncio.Lock()

    # --- reads ---

    async def get_campaign(self, campaign_id: str) -> Campaign:
        return copy.deepcopy(self._campaign(campaign_id))

    async def list_campaigns(self, project_id: str) -> list[Campaign]:
        found = [c for c in self._campaigns.values() if c.project_id == project_id]
        found.sort(key=lambda c: c.created_at, reverse=True)
        return copy.deepcopy(found)

    async def control_log(self, campaign_id: str) -> list[ControlLogEntry]:
        self._campaign(campaign_id)
        return copy.deepcopy(self._log[campaign_id])

    async def pending_launch_intents(self) -> list[LaunchIntent]:
        pending = [
            i
            for i in self._intents.values()
            if i.state is LaunchIntentState.PENDING
            and self._campaigns[i.campaign_id].state is not CampaignState.COMPLETED
        ]
        pending.sort(key=lambda i: i.created_at)
        return copy.deepcopy(pending)

    async def launch_intents(self, campaign_id: str) -> list[LaunchIntent]:
        self._campaign(campaign_id)
        found = [i for i in self._intents.values() if i.campaign_id == campaign_id]
        found.sort(key=lambda i: i.created_at)
        return copy.deepcopy(found)

    async def get_launch_intent(self, launch_id: str) -> LaunchIntent:
        return copy.deepcopy(self._intent(launch_id))

    # --- control operations ---

    async def create_campaign(
        self,
        campaign: Campaign,
        *,
        actor: str,
        actor_role: str,
        reason: str,
        idempotency_key: str,
    ) -> TransitionResult:
        async with self._lock:
            now = _now()
            entry = lifecycle.creation_entry(
                campaign,
                actor=actor,
                actor_role=actor_role,
                reason=reason,
                idempotency_key=idempotency_key,
                entry_id=lifecycle.new_entry_id(),
                committed_at=now,
            )
            if campaign.campaign_id in self._campaigns:
                recorded = self._log[campaign.campaign_id][0]
                if not lifecycle.is_creation_replay(recorded, entry):
                    raise CampaignExistsError(
                        f"campaign {campaign.campaign_id} exists with a different creation"
                    )
                return TransitionResult(
                    entry=copy.deepcopy(recorded),
                    campaign=copy.deepcopy(self._campaigns[campaign.campaign_id]),
                    intent=None,
                    replayed=True,
                )
            self._campaigns[campaign.campaign_id] = copy.deepcopy(campaign)
            self._log[campaign.campaign_id] = [entry]
            return TransitionResult(
                entry=copy.deepcopy(entry),
                campaign=copy.deepcopy(campaign),
                intent=None,
                replayed=False,
            )

    async def transition(
        self, campaign_id: str, transition: CampaignTransition
    ) -> TransitionResult:
        async with self._lock:
            return self._commit(campaign_id, transition, marks=None)

    async def mark_launch_intent_launched(
        self, launch_id: str, cycle_id: str, *, actor: str
    ) -> TransitionResult:
        async with self._lock:
            intent = self._intent(launch_id)
            transition = lifecycle.mark_launched_transition(intent, cycle_id, actor=actor)
            return self._commit(intent.campaign_id, transition, marks=(intent, cycle_id))

    # --- internals ---

    def _campaign(self, campaign_id: str) -> Campaign:
        try:
            return self._campaigns[campaign_id]
        except KeyError:
            raise CampaignNotFoundError(f"Campaign not found: {campaign_id}") from None

    def _intent(self, launch_id: str) -> LaunchIntent:
        try:
            return self._intents[launch_id]
        except KeyError:
            raise LaunchIntentNotFoundError(f"Launch intent not found: {launch_id}") from None

    def _applied_with_key(self, campaign_id: str, key: str) -> ControlLogEntry | None:
        for entry in self._log[campaign_id]:
            if entry.outcome is ControlOutcome.APPLIED and entry.idempotency_key == key:
                return entry
        return None

    def _commit(
        self,
        campaign_id: str,
        transition: CampaignTransition,
        *,
        marks: tuple[LaunchIntent, str] | None,
    ) -> TransitionResult:
        campaign = self._campaign(campaign_id)
        recorded = self._applied_with_key(campaign_id, transition.idempotency_key)
        verdict = lifecycle.adjudicate(campaign, transition, recorded)
        if verdict.replay is not None:
            intent_id = verdict.replay.launch_id
            return TransitionResult(
                entry=copy.deepcopy(verdict.replay),
                campaign=copy.deepcopy(campaign),
                intent=copy.deepcopy(self._intents[intent_id]) if intent_id else None,
                replayed=True,
            )

        now = _now()
        entry_id = lifecycle.new_entry_id()
        seq = len(self._log[campaign_id]) + 1
        if verdict.refusal is not None:
            entry = lifecycle.control_log_entry(
                campaign,
                transition,
                entry_id=entry_id,
                seq=seq,
                committed_at=now,
                refusal=verdict.refusal,
                launch_id=None,
            )
            self._log[campaign_id].append(entry)
            raise ControlOperationRefused(copy.deepcopy(entry))

        if marks is not None:
            intent = lifecycle.launched_intent(marks[0], marks[1], now)
        else:
            intent = lifecycle.new_launch_intent(campaign_id, transition, entry_id, now)
        entry = lifecycle.control_log_entry(
            campaign,
            transition,
            entry_id=entry_id,
            seq=seq,
            committed_at=now,
            refusal=None,
            launch_id=intent.launch_id if intent is not None else None,
        )
        updated = lifecycle.applied_campaign(campaign, transition, now)

        # The commit: every write together, nothing awaited between them.
        self._campaigns[campaign_id] = copy.deepcopy(updated)
        self._log[campaign_id].append(entry)
        if intent is not None:
            self._intents[intent.launch_id] = copy.deepcopy(intent)
        return TransitionResult(
            entry=copy.deepcopy(entry),
            campaign=copy.deepcopy(updated),
            intent=copy.deepcopy(intent),
            replayed=False,
        )

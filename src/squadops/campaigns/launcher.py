"""The launcher (SIP-0109 §12b): pending launch intents become cycles, exactly once each.

A decision writes its launch intent in its own transaction; the launcher does the rest, across
the boundary no transaction spans:
1. build the cycle the intent describes;
2. create it through ``create_cycle_for_launch``, idempotent by the launch id;
3. mark the intent ``launched`` with that cycle's id, in a control-log transition.

A crash anywhere in that sequence leaves the intent pending, and the next drain repeats it: a
cycle already created is found by its launch id rather than created again, and a mark already
committed replays. Two launchers on one intent end with one cycle for the same reason.

The launcher creates the cycle record only. Starting its first run is the cycle-create path's
job, which the campaign API wires in when it arrives.

The box comes first (§9.3; #1802). A campaign in a holding state launches nothing, and an intent
the box refuses (the supervisor holds it, or a model the deploy did not load is resident) is not
launched: the campaign moves to ``launch_blocked`` with the intent still pending, and
``retry_blocked`` re-attempts it at the policy's interval, escalating after its count.

An intent whose cycle the cycle-create path refuses (``LaunchRefused``) escalates its campaign at
once, with the intent still pending (§24e item 5, #1971): the same intent would be refused again.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from squadops.campaigns import launch_blocking
from squadops.campaigns.box import LaunchVerdict
from squadops.campaigns.lifecycle import HOLDING_STATES
from squadops.campaigns.models import (
    CampaignState,
    ControlLogEntry,
    ControlOperation,
    ControlOperationRefused,
    LaunchIntent,
)
from squadops.cycles.models import Cycle
from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
from squadops.ports.cycles.cycle_registry import CycleRegistryPort

#: Builds the cycle an intent describes, the way the cycle-create path builds one: its squad
#: profile snapshot, its deploy and its code lineage. Each call may mint a fresh cycle id; when the
#: launch already has a cycle, the stored one wins and the fresh one is discarded.
BuildCycle = Callable[[LaunchIntent], Awaitable[Cycle]]

#: Whether the box allows a launch now (``BoxReader.verdict``).
BoxVerdict = Callable[[], Awaitable[LaunchVerdict]]

logger = logging.getLogger(__name__)


class LaunchRefused(Exception):
    """The cycle-create path refused a launch's cycle: its preflight blocked it, or its request
    names something that does not exist. A refusal of the request, never a transient fault:
    building the same intent again is refused the same way (#1971)."""

    def __init__(self, refusal: str) -> None:
        self.refusal = refusal
        super().__init__(refusal)


@dataclass(frozen=True)
class Launched:
    """One intent's launch: its cycle, whether this call created it, and whether an abort that
    committed before the mark meant the cycle was cancelled as soon as it existed."""

    launch_id: str
    cycle_id: str
    created: bool
    cancelled_after_abort: bool


class CampaignLauncher:
    def __init__(
        self,
        campaigns: CampaignRegistryPort,
        cycles: CycleRegistryPort,
        build_cycle: BuildCycle,
        *,
        actor: str,
        box_verdict: BoxVerdict,
    ) -> None:
        self._campaigns = campaigns
        self._cycles = cycles
        self._build_cycle = build_cycle
        self._actor = actor
        self._box_verdict = box_verdict

    async def drain(self) -> list[Launched]:
        """Launch every pending intent the box allows, oldest first. An intent that fails stays
        pending, and the failure propagates: the next drain repeats it. One the box refuses
        blocks its campaign (§9.3), one the cycle-create path refuses escalates it (#1971), and
        one whose campaign is holding waits for it."""
        launched = []
        for intent in await self._campaigns.pending_launch_intents():
            campaign = await self._campaigns.get_campaign(intent.campaign_id)
            if campaign.state in HOLDING_STATES:
                continue
            verdict = await self._box_verdict()
            if not verdict.allowed:
                await self._block(campaign, intent, verdict)
                continue
            try:
                launched.append(await self.launch(intent))
            except LaunchRefused as refused:
                await self._escalate_refused(campaign, intent, refused)
        return launched

    async def _escalate_refused(self, campaign, intent: LaunchIntent, refused: LaunchRefused):
        log = await self._campaigns.control_log(campaign.campaign_id)
        transition = launch_blocking.refused_launch(
            campaign, log, intent, refused.refusal, actor=self._actor
        )
        try:
            await self._campaigns.transition(campaign.campaign_id, transition)
        except ControlOperationRefused as stale:
            # The campaign moved since it was read (a pause, an abort): its own row says why,
            # and the intent waits for whatever the campaign does next.
            logger.info(
                "campaign_launch_refusal_not_recorded",
                extra={"campaign_id": campaign.campaign_id, "refusal": stale.entry.refusal},
            )
        logger.warning(
            "campaign_launch_refused campaign=%s launch=%s refusal=%s",
            campaign.campaign_id,
            intent.launch_id,
            refused.refusal,
        )

    async def _block(self, campaign, intent: LaunchIntent, verdict: LaunchVerdict) -> None:
        transition = launch_blocking.first_refusal(campaign, intent, verdict, actor=self._actor)
        try:
            await self._campaigns.transition(campaign.campaign_id, transition)
        except ControlOperationRefused as refused:
            # The campaign moved since it was read (a pause, an abort): its own row says why,
            # and the intent waits for whatever the campaign does next.
            logger.info(
                "campaign_launch_block_refused",
                extra={"campaign_id": campaign.campaign_id, "refusal": refused.entry.refusal},
            )
        logger.warning(
            "campaign_launch_blocked campaign=%s launch=%s refusal=%s reasons=%s",
            campaign.campaign_id,
            intent.launch_id,
            verdict.refusal,
            "; ".join(verdict.reasons),
        )

    async def retry_blocked(self, now: datetime) -> list[ControlLogEntry]:
        """§9.3: each blocked campaign whose next attempt is due reads the box again. Allowed,
        it returns to the state its launch was written from (the next drain launches it);
        refused, its next attempt is recorded, escalating at the policy's count. One campaign
        that cannot be retried does not stop the rest. Returns the rows written."""
        written = []
        for campaign in await self._campaigns.campaigns_in_state(CampaignState.LAUNCH_BLOCKED):
            try:
                log = await self._campaigns.control_log(campaign.campaign_id)
                if not launch_blocking.retry_due(campaign, log, now):
                    continue
                transition = launch_blocking.blocked_launch_step(
                    campaign, log, await self._box_verdict(), actor=self._actor
                )
                result = await self._campaigns.transition(campaign.campaign_id, transition)
                if not result.replayed:
                    written.append(result.entry)
            except ControlOperationRefused as refused:
                logger.info(
                    "campaign_launch_retry_refused",
                    extra={"campaign_id": campaign.campaign_id, "refusal": refused.entry.refusal},
                )
            except Exception:
                logger.exception(
                    "campaign_launch_retry_failed", extra={"campaign_id": campaign.campaign_id}
                )
        return written

    async def launch(self, intent: LaunchIntent) -> Launched:
        cycle = await self._build_cycle(intent)
        if cycle.campaign_id != intent.campaign_id or cycle.kind != intent.cycle_kind.value:
            raise ValueError(
                f"launch {intent.launch_id}: the built cycle names campaign {cycle.campaign_id!r} "
                f"and kind {cycle.kind!r}, not the intent's {intent.campaign_id!r} and "
                f"{intent.cycle_kind.value!r}"
            )
        stored = await self._cycles.create_cycle_for_launch(cycle, intent.launch_id)
        marked = await self._campaigns.mark_launch_intent_launched(
            intent.launch_id, stored.cycle_id, actor=self._actor
        )
        cancelled = False
        if marked.campaign.state is CampaignState.COMPLETED:
            # An abort committed after this intent was read, so the cycle exists only because
            # the launch was already under way. No continuation follows an abort (§12a): the
            # cycle is cancelled by the existing path before anything can run in it.
            await self._cycles.cancel_cycle(stored.cycle_id)
            cancelled = True
        return Launched(
            launch_id=intent.launch_id,
            cycle_id=stored.cycle_id,
            created=stored.cycle_id == cycle.cycle_id,
            cancelled_after_abort=cancelled,
        )


def unblocked(rows: list[ControlLogEntry]) -> bool:
    """Whether any of the rows returned a campaign to work, so its intent can be launched."""
    return any(r.operation is ControlOperation.LAUNCH_UNBLOCKED for r in rows)

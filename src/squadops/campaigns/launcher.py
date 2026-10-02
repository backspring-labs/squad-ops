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
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from squadops.campaigns.models import CampaignState, LaunchIntent
from squadops.cycles.models import Cycle
from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
from squadops.ports.cycles.cycle_registry import CycleRegistryPort

#: Builds the cycle an intent describes, the way the cycle-create path builds one: its squad
#: profile snapshot, its deploy and its code lineage. Each call may mint a fresh cycle id; when the
#: launch already has a cycle, the stored one wins and the fresh one is discarded.
BuildCycle = Callable[[LaunchIntent], Awaitable[Cycle]]


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
    ) -> None:
        self._campaigns = campaigns
        self._cycles = cycles
        self._build_cycle = build_cycle
        self._actor = actor

    async def drain(self) -> list[Launched]:
        """Launch every pending intent, oldest first. An intent that fails stays pending, and
        the failure propagates: the next drain repeats it."""
        return [
            await self.launch(intent) for intent in await self._campaigns.pending_launch_intents()
        ]

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

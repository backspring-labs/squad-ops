"""Each campaign cycle evaluated at its end against its campaign's pinned suite (SIP-0113 §4.1, §6
phase 1; #2414). Reporting only: the record is written, and nothing that decides the campaign,
gates a cycle or renders a prompt reads it.

The campaign's hearing calls ``cycle_ended`` once per ending it decides, before the decision, so
the evaluation runs while the box is between cycles rather than beside the next one. A campaign
with no suite pinned has nothing to evaluate against, and is left alone.

- **Which tree:** the cycle's whole app, by SIP-0109's own selection (``evaluate_cycle``). A cycle
  that delivered nothing, a failed run, has no tree and no record.
- **Which previous tree:** the identity the campaign promoted for the accepted cycle this one built
  on, read from its control log. A calibration builds on nothing.
- **Once per cycle and suite:** a cycle heard again after a restart (§12a) is not evaluated twice.
  Only the campaign's own record counts: a reading written with no campaign (§10p ruling 13's
  tool) isn't the cycle's evaluation.
- **How it starts:** a blueprint cycle by its stack. Any other Project needs its Development
  Configuration's start declaration (SIP-0112 E.4.2, contract 7), which this hook doesn't read yet,
  so its applicable scenarios are recorded ``blocked_unverified``, ``no_start_declaration``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from squadops.campaigns.increment_tree import accepted_cycle_of, evaluated_tree_refs
from squadops.campaigns.models import ControlOperation, ControlOutcome
from squadops.scenarios.evaluate import evaluate_cycle
from squadops.scenarios.evaluation import EvaluationRecord
from squadops.scenarios.runner import StartUndeclared

if TYPE_CHECKING:  # the ports name this package's models; the evaluator only takes them
    from squadops.ports.scenarios import ScenarioRunnerPort, ScenarioStorePort

logger = logging.getLogger(__name__)


def promoted_identity(log: list, cycle_id: str | None) -> str | None:
    """The tree identity the campaign promoted for ``cycle_id``, or ``None`` when it promoted
    none (or ``cycle_id`` is ``None``)."""
    if cycle_id is None:
        return None
    for entry in log:
        if (
            entry.operation is ControlOperation.PROMOTE
            and entry.outcome is ControlOutcome.APPLIED
            and entry.binding.get("cycle_id") == cycle_id
        ):
            return entry.binding["identity"]
    return None


async def built_on_identity(campaigns: Any, cycle: Any) -> str | None:
    """The tree ``cycle`` built on, as its evaluation names it: the identity its campaign promoted
    for the accepted cycle it built on. ``None`` for a calibration, which built on nothing, and for
    a cycle with no campaign, whose log isn't read."""
    if not cycle.campaign_id:
        return None
    log = await campaigns.control_log(cycle.campaign_id)
    return promoted_identity(log, accepted_cycle_of(cycle))


class CampaignCycleEvaluator:
    """Evaluates a campaign's cycle at its end, reporting-only (#2414)."""

    def __init__(
        self,
        *,
        store: ScenarioStorePort,
        runner: ScenarioRunnerPort | None,
        vault: Any,
        campaigns: Any,
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._runner = runner
        self._vault = vault
        self._campaigns = campaigns
        self._clock = clock

    async def cycle_ended(self, cycle: Any) -> EvaluationRecord | None:
        """Evaluate ``cycle`` against its campaign's pinned suite and write the record. ``None``
        when there is nothing to evaluate: no campaign, no suite pinned, no delivered tree, or
        a record for this cycle and suite already written."""
        if not cycle.campaign_id:
            return None
        pin = await self._store.get_pin(cycle.campaign_id)
        if pin is None:
            return None
        held = await self._store.evaluations_for_cycle(cycle.cycle_id)
        if any(
            r.campaign_id == cycle.campaign_id and r.suite_digest == pin.suite_digest for r in held
        ):
            return None
        if not await evaluated_tree_refs(self._vault, cycle):
            logger.info("outcome_evaluation_skipped_no_tree", extra={"cycle_id": cycle.cycle_id})
            return None
        stack = cycle.resolved_config().get("build_profile")
        unstartable = (
            None
            if stack
            else StartUndeclared(
                "the Development Configuration's start declaration isn't read at a cycle's end yet"
            )
        )
        return await evaluate_cycle(
            store=self._store,
            runner=self._runner,
            vault=self._vault,
            cycle=cycle,
            suite_digest=pin.suite_digest,
            campaign_id=cycle.campaign_id,
            previous_accepted_tree_identity=await built_on_identity(self._campaigns, cycle),
            evaluated_at=self._clock(),
            unstartable=unstartable,
        )

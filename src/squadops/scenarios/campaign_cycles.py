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
- **How it starts:** a sample application's cycle by its stack. A repository-backed Project's
  cycle by its own start declaration (SIP-0112 contract 7), read from its Development Configuration
  at the revision the cycle pinned (``runner.configured_start``, the reading an increment's routes
  are rendered with, SIP-0109 §24co). A declaration it can't run blocks every applicable scenario
  with contract 7's reason, and none is ever passed.
- **A repository-backed cycle's tree** is the commit its delivery captured (SIP-0112 E.4.3), read
  whole from the managed clone with its executable bits, and checked against the identity the
  capture recorded. A cycle that captured nothing delivered nothing: no record. Its previous tree is
  the head it was pinned at, the campaign branch's (SIP-0113 §10l).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.increment_tree import accepted_cycle_of, evaluated_tree_refs
from squadops.campaigns.models import ControlOperation, ControlOutcome
from squadops.scenarios.evaluate import declared_surfaces, evaluate_cycle
from squadops.scenarios.evaluation import EvaluationRecord
from squadops.scenarios.runner import (
    ReadinessUnsupported,
    SecretUnavailable,
    StartUndeclared,
    configured_start,
)

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
        projects: Any,
        repository: Any,
    ) -> None:
        self._store = store
        self._runner = runner
        self._vault = vault
        self._campaigns = campaigns
        self._clock = clock
        # #2414: a repository-backed cycle's Development Configuration and captured commit, read
        # from the Project registry and its managed clone. ``None`` where the runtime has neither:
        # such a cycle is then never evaluated, rather than evaluated on the vault's partial tree.
        self._projects = projects
        self._repository = repository

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
        if getattr(cycle, "source_context", None) is not None:
            return await self._product_cycle_ended(cycle, pin.suite_digest)
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

    async def _product_cycle_ended(self, cycle: Any, suite_digest: str) -> EvaluationRecord | None:
        """A repository-backed Project's cycle (#2414's remainder): its captured commit, started
        from the Project's own declaration. The vault holds only the squad's changes, so its tree is
        never read from there: that would name a tree that isn't the product.

        A read that fails here (the registry, the configuration, the clone) raises to the hearing's
        reporting boundary, ``CampaignProgress._outcome_evaluated``, which logs it and leaves the
        evaluation absent, as it does for a sample application's: the campaign's decision is
        recorded either way."""
        # deferred (pair): the projects package reads the sandbox's findings, which load this one
        from squadops.projects.workspaces import CAPTURED

        context = cycle.source_context
        if self._projects is None or self._repository is None:
            logger.warning(
                "outcome_evaluation_skipped_no_clone", extra={"cycle_id": cycle.cycle_id}
            )
            return None
        captured = [
            m
            for m in await self._projects.source_mappings(cycle.project_id)
            if m.direction == CAPTURED and m.cycle_id == cycle.cycle_id
        ]
        if not captured:
            logger.info("outcome_evaluation_skipped_no_tree", extra={"cycle_id": cycle.cycle_id})
            return None
        mapping = captured[-1]  # oldest first: the last capture is the run's delivered one
        checkout = await self._repository.tree_at(cycle.project_id, mapping.commit)
        if FileTree.of(checkout.files).identity != mapping.tree_identity:
            logger.warning(
                "outcome_evaluation_skipped_tree_mismatch",
                extra={"cycle_id": cycle.cycle_id, "commit": mapping.commit},
            )
            return None
        configuration = await self._projects.get_development_configuration(
            cycle.project_id, context.development_configuration_revision
        )
        declaration = configuration.commands.start
        # The surfaces the declaration's entry points serve; none read, all applicable, when there
        # is no declaration, so every scenario reads its reason (§10l), never not applicable.
        served = (
            declared_surfaces([{"kind": e.kind} for e in declaration.entry_points])
            if declaration is not None
            else None
        )
        declared, unstartable = None, None
        try:
            declared = configured_start(configuration)
        except (StartUndeclared, SecretUnavailable, ReadinessUnsupported) as e:
            unstartable = e
        return await evaluate_cycle(
            store=self._store,
            runner=self._runner,
            vault=self._vault,
            cycle=cycle,
            suite_digest=suite_digest,
            campaign_id=cycle.campaign_id,
            previous_accepted_tree_identity=await self._pinned_identity(cycle),
            evaluated_at=self._clock(),
            declared=declared,
            served=served,
            unstartable=unstartable,
            tree=checkout.files,
            executable=checkout.executable,
        )

    async def _pinned_identity(self, cycle: Any) -> str | None:
        """The tree the cycle was built on: its pinned commit's (the campaign branch's head, H.9),
        named by its tree identity (contract 4), never by the commit (§4.1's rule)."""
        pinned = getattr(cycle.source_context, "pinned_commit", None)
        if not pinned:
            return None
        return FileTree.of(
            (await self._repository.tree_at(cycle.project_id, pinned)).files
        ).identity

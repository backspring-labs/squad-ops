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

**A repository-backed Campaign's baseline reading** (SIP-0113 §10l): its calibration is a record,
not a cycle (SIP-0109 §24bv point 1), so no cycle ends for it. When the record is heard
(``calibration_recorded``), before its promotion and decision, the record's commit is evaluated once
against the Campaign's pinned suite, by the same read a product cycle's capture takes: the tree
whole from the managed clone, checked against the record's tree identity (contract 4), started from
the Development Configuration revision the record names. The reading names the calibration record in
place of a cycle. A record heard again after a restart is not read twice.

**Lint by a blueprint's rule set** (§10l, §4.2): a product is linted by #1937's rule sets only when
the derived profile at its pin names a scaffold blueprint it was made from (``blueprint_stack``).
Never by a project's name, and never by the product's own linter.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.increment_tree import accepted_cycle_of, evaluated_tree_refs
from squadops.campaigns.models import ControlOperation, ControlOutcome
from squadops.cycles.models import DerivedProfileNotFoundError
from squadops.scenarios.evaluate import (
    declared_surfaces,
    evaluate_calibration_record,
    evaluate_cycle,
)
from squadops.scenarios.evaluation import EvaluationRecord
from squadops.scenarios.models import SurfaceKind
from squadops.scenarios.runner import (
    DeclaredStart,
    ReadinessUnsupported,
    SecretUnavailable,
    StartUndeclared,
    configured_start,
)
from squadops.stacks.scaffold import is_scaffoldable_stack

if TYPE_CHECKING:  # the ports name this package's models; the evaluator only takes them
    from squadops.campaigns.calibration_record import CalibrationRecord
    from squadops.ports.scenarios import ScenarioRunnerPort, ScenarioStorePort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProductRead:
    """A repository-backed Project's tree at a commit, as an evaluation takes it: whole, with its
    executable bits, checked against the tree identity recorded for the commit (contract 4); and
    how it starts, from the Development Configuration revision the unit pinned (contract 7).

    ``declared`` is its start, or ``unstartable`` the refusal reading it met. ``served`` is the
    surface kinds its entry points serve, ``None`` with no declaration, so every scenario applies
    and reads its reason (§10l). ``lint_stack`` is the scaffold blueprint the product was made
    from, by the derived profile at the pin, or ``None``; ``profile_unread`` is why that profile
    couldn't be read, when it couldn't."""

    files: Mapping[str, bytes]
    executable: Collection[str]
    declared: DeclaredStart | None
    served: frozenset[SurfaceKind] | None
    unstartable: StartUndeclared | SecretUnavailable | ReadinessUnsupported | None
    lint_stack: str | None
    profile_unread: str | None = None


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
    """Evaluates a campaign's cycle at its end, and a repository-backed campaign's calibration
    record when it is heard (§10l), reporting-only (#2414)."""

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
        read = await self.product_read(
            cycle.project_id,
            mapping.commit,
            tree_identity=mapping.tree_identity,
            revision=context.development_configuration_revision,
            # SIP-0109 §24cd point 3: an increment pinned at its campaign branch's head reads its
            # profile at the Project's pin all the same, as prepare_cycle does.
            profile_at=(
                context.development_baseline_commit,
                context.development_configuration_revision,
            ),
            unit={"cycle_id": cycle.cycle_id},
        )
        if read is None:
            return None
        return await evaluate_cycle(
            store=self._store,
            runner=self._runner,
            vault=self._vault,
            cycle=cycle,
            suite_digest=suite_digest,
            campaign_id=cycle.campaign_id,
            previous_accepted_tree_identity=await self._pinned_identity(cycle),
            evaluated_at=self._clock(),
            declared=read.declared,
            served=read.served,
            unstartable=read.unstartable,
            tree=read.files,
            executable=read.executable,
            lint_stack=read.lint_stack,
            profile_unread=read.profile_unread,
        )

    async def calibration_recorded(
        self, campaign_id: str, record: CalibrationRecord
    ) -> EvaluationRecord | None:
        """SIP-0113 §10l: the Campaign's baseline reading, its calibration record's commit
        evaluated against its pinned suite, and the record written naming the calibration record.
        ``None`` when there is nothing to read or nothing may be: no suite pinned; a reading of
        this record and suite already written (a record heard again after a restart); no registry
        or clone wired; or a commit whose tree isn't the record's.

        Reporting-only. A read that fails (the configuration, the clone) raises to the hearing's
        reporting boundary, ``CampaignProgress._baseline_evaluated``, which logs it and leaves the
        reading absent: the record, its promotion and its decision go on. A derived profile that
        can't be read costs the reading only its lint (``_blueprint``)."""
        pin = await self._store.get_pin(campaign_id)
        if pin is None:
            return None
        held = await self._store.evaluations_for_calibration_record(record.record_id)
        if any(r.campaign_id == campaign_id and r.suite_digest == pin.suite_digest for r in held):
            return None
        if self._projects is None or self._repository is None:
            logger.warning(
                "baseline_reading_skipped_no_clone",
                extra={"campaign_id": campaign_id, "record_id": record.record_id},
            )
            return None
        read = await self.product_read(
            record.project_id,
            record.commit,
            tree_identity=record.tree_identity,
            revision=record.development_configuration_revision,
            # The record is written only with a profile at its pin (§24bv point 1, contract 8).
            profile_at=(record.commit, record.development_configuration_revision),
            unit={"campaign_id": campaign_id, "record_id": record.record_id},
        )
        if read is None:
            return None
        return await evaluate_calibration_record(
            store=self._store,
            runner=self._runner,
            project_id=record.project_id,
            calibration_record_id=record.record_id,
            campaign_id=campaign_id,
            suite_digest=pin.suite_digest,
            evaluated_at=self._clock(),
            tree=read.files,
            executable=read.executable,
            declared=read.declared,
            served=read.served,
            unstartable=read.unstartable,
            lint_stack=read.lint_stack,
            profile_unread=read.profile_unread,
        )

    async def product_read(
        self,
        project_id: str,
        commit: str,
        *,
        tree_identity: str,
        revision: int,
        profile_at: tuple[str, int],
        unit: Mapping[str, str],
    ) -> ProductRead | None:
        """A repository-backed Project's tree at ``commit``, and how it starts at ``revision``:
        what a product cycle's capture and a calibration record's commit are both evaluated on. The
        tree is read whole from the managed clone, with its executable bits, and must hash to
        ``tree_identity``, the identity recorded for the commit (contract 4). ``None``, logged,
        when it doesn't. ``unit`` names the cycle or the record in the log."""
        checkout = await self._repository.tree_at(project_id, commit)
        if FileTree.of(checkout.files).identity != tree_identity:
            logger.warning(
                "outcome_evaluation_skipped_tree_mismatch", extra={**unit, "commit": commit}
            )
            return None
        configuration = await self._projects.get_development_configuration(project_id, revision)
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
        lint_stack, profile_unread = await self._blueprint(project_id, profile_at, unit)
        return ProductRead(
            files=checkout.files,
            executable=checkout.executable,
            declared=declared,
            served=served,
            unstartable=unstartable,
            lint_stack=lint_stack,
            profile_unread=profile_unread,
        )

    async def _blueprint(
        self, project_id: str, at: tuple[str, int], unit: Mapping[str, str]
    ) -> tuple[str | None, str | None]:
        """The scaffold blueprint the product was made from, by the derived profile at ``at``
        (contract 8's ``blueprint``), and why the profile couldn't be read when it couldn't.
        ``(None, None)``: no profile there, no blueprint, or a stack with no scaffold, whose tree
        has no #1937 rule set (§10l, §4.2). A profile at another pin is never read in its place.

        The second review of #2788 (P3-6): only lint needs the profile, so a profile that can't be
        read never costs the evaluation its scenarios. It is logged, and the lint reads
        ``profile_unread`` with why."""
        try:
            profile = await self._projects.get_derived_profile(project_id, at=at)
        except DerivedProfileNotFoundError:
            return None, None
        except Exception as e:  # noqa: BLE001 — lint alone needs it; the evaluation goes on
            logger.warning("outcome_evaluation_profile_unreadable", extra={**unit, "error": str(e)})
            return None, f"the derived profile at {at[0][:12]}, revision {at[1]}: {e}"
        stack = profile.blueprint_stack
        return (stack if stack and is_scaffoldable_stack(stack) else None), None

    async def _pinned_identity(self, cycle: Any) -> str | None:
        """The tree the cycle was built on: its pinned commit's (the campaign branch's head, H.9),
        named by its tree identity (contract 4), never by the commit (§4.1's rule)."""
        pinned = getattr(cycle.source_context, "pinned_commit", None)
        if not pinned:
            return None
        return FileTree.of(
            (await self._repository.tree_at(cycle.project_id, pinned)).files
        ).identity

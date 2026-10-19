"""Evaluating a cycle against a pinned suite (SIP-0113 §4.1, §4.8; #2414). Reporting only: no
row, gate or prompt reads what this writes, and no scenario goal or result reaches a squad role.

1. The suite must be approved (D2).
2. The evaluated tree is the cycle's whole app, by SIP-0109's own selection
   (``evaluated_tree_refs``), and it is named by its ``FileTree.identity``.
3. Each scenario is applicable when the Project serves every kind of surface it needs. One that
   isn't is recorded not applicable and never runs.
4. The applicable ones run in the runner (A3), on a disposable copy.
5. The record is written whatever happened. No runner means every applicable scenario is
   ``blocked_unverified`` with ``no_runner``, a failed start means ``start_failed``, and a start
   the caller couldn't read carries its own reason: ``no_start_declaration`` for none or a malformed
   one, ``no_runner`` for a readiness kind the runner doesn't check. None of them is ever passed.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any

from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.increment_tree import evaluated_tree_refs
from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    EvaluationRecord,
    ScenarioOutcome,
    ScenarioResult,
    evaluation_record,
)
from squadops.scenarios.models import Scenario, SurfaceKind
from squadops.scenarios.runner import (
    DeclaredStart,
    ReadinessUnsupported,
    RunnerUnavailable,
    StartUndeclared,
)
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import require_pinnable

if TYPE_CHECKING:  # the ports name this package's models; the service only takes them
    from squadops.ports.scenarios import ScenarioRunnerPort, ScenarioStorePort

#: A blueprint Project serves its API and its pages (SIP-0109's stacks).
BLUEPRINT_SURFACES = frozenset({SurfaceKind.HTTP_ENDPOINT, SurfaceKind.PAGE})
#: A start declaration's entry points, by the surface kind each serves (contract 7).
ENTRY_POINT_SURFACES = {"http_base": SurfaceKind.HTTP_ENDPOINT, "ui_base": SurfaceKind.PAGE}


def declared_surfaces(entry_points: Collection[Mapping[str, Any]]) -> frozenset[SurfaceKind]:
    return frozenset(
        ENTRY_POINT_SURFACES[e["kind"]]
        for e in entry_points
        if e.get("kind") in ENTRY_POINT_SURFACES
    )


def _outcome(
    scenario: Scenario,
    served: frozenset[SurfaceKind],
    run: ScenarioRun | None,
    blocked: BlockedReason | None,
) -> ScenarioOutcome:
    def outcome(**kw: Any) -> ScenarioOutcome:
        return ScenarioOutcome(
            scenario_id=scenario.scenario_id, version=scenario.version, goal=scenario.goal, **kw
        )

    if not {s.kind for s in scenario.surfaces} <= served:
        return outcome(applicability=Applicability.NOT_APPLICABLE)
    if blocked is not None or run is None:
        return outcome(
            applicability=Applicability.APPLICABLE,
            result=ScenarioResult.BLOCKED_UNVERIFIED,
            blocked_reason=blocked or BlockedReason.NO_RUNNER,
        )
    result = ScenarioResult(run.result)
    return outcome(
        applicability=Applicability.APPLICABLE,
        result=result,
        blocked_reason=BlockedReason(run.blocked_reason) if run.blocked_reason else None,
        steps_taken=run.steps_taken,
        first_failing_step=run.first_failing_step if result is ScenarioResult.FAILED else None,
        elapsed_seconds=run.elapsed_seconds,
    )


async def evaluate_cycle(
    *,
    store: ScenarioStorePort,
    runner: ScenarioRunnerPort | None,
    vault: Any,
    cycle: Any,
    suite_digest: str,
    campaign_id: str | None,
    previous_accepted_tree_identity: str | None,
    evaluated_at: datetime,
    declared: DeclaredStart | None = None,
    served: frozenset[SurfaceKind] | None = None,
    environment: Mapping[str, str] | None = None,
    unstartable: StartUndeclared | ReadinessUnsupported | None = None,
) -> EvaluationRecord:
    """Evaluate ``cycle``'s delivered app against an approved suite, and write the record.

    A blueprint cycle starts by its stack (``build_profile``). Any other Project passes its
    ``declared`` start and the ``served`` surface kinds of its entry points, or the refusal it met
    reading its declaration as ``unstartable``, whose ``reason`` blocks every applicable scenario."""
    suite = (await require_pinnable(store, suite_digest)).suite
    refs = await evaluated_tree_refs(vault, cycle)
    tree = {path: (await vault.retrieve(art))[1] for path, art in refs.items()}
    identity = FileTree.of(tree).identity
    kinds = served if served is not None else BLUEPRINT_SURFACES
    applicable = [s for s in suite.scenarios if {k.kind for k in s.surfaces} <= kinds]

    blocked: BlockedReason | None = None
    runs: dict[str, ScenarioRun] = {}
    if applicable and unstartable is not None:
        blocked = unstartable.reason
    elif applicable and runner is None:
        blocked = BlockedReason.NO_RUNNER
    elif applicable and runner is not None:
        try:
            evaluated = await runner.evaluate_tree(
                tree=tree,
                tree_identity=identity,
                executable=(),
                stack=cycle.resolved_config().get("build_profile"),
                declared=declared,
                scenarios=[s.content() for s in applicable],
                environment=environment or {},
            )
        except RunnerUnavailable:
            blocked = BlockedReason.NO_RUNNER
        else:
            if not evaluated.started:
                blocked = BlockedReason.START_FAILED
            runs = {r.scenario_id: r for r in evaluated.runs}

    record = evaluation_record(
        suite,
        tuple(_outcome(s, kinds, runs.get(s.scenario_id), blocked) for s in suite.scenarios),
        project_id=cycle.project_id,
        campaign_id=campaign_id,
        cycle_id=cycle.cycle_id,
        evaluated_tree_identity=identity,
        previous_accepted_tree_identity=previous_accepted_tree_identity,
        evaluated_at=evaluated_at,
    )
    await store.save_evaluation(record)
    return record

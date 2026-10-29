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
   one, ``secret_not_available`` for a secret nothing releases, ``no_runner`` for a readiness kind
   the runner doesn't check. None of them is ever passed, and each quality measure the start would
   have served is not measured for the same reason.

A repository-backed Campaign's calibration record is evaluated the same way
(``evaluate_calibration_record``, SIP-0113 §10l): its commit's tree, its declared start, the same
scenarios and measures, in a record that names the calibration record in place of a cycle.

**Lint by a blueprint's rule set (§10l, §4.2).** #1937's rule sets exist only for the scaffold
stacks. A sample application's tree is linted by its stack's. A product is linted only when it is
a greenfield product made from a scaffold blueprint, which the caller reads from the derived
profile at the unit's pin and passes as ``lint_stack``. Any other product's lint is
``not_a_scaffold_stack``, and its own linter is never read in its place.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

import yaml

from squadops.campaigns import seed_plan
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.increment_tree import accepted_cycle_of, evaluated_tree_refs, route_param
from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    EvaluationRecord,
    ScenarioOutcome,
    ScenarioResult,
    evaluation_record,
)
from squadops.scenarios.evidence import ScenarioEvidence
from squadops.scenarios.fields import resolve
from squadops.scenarios.models import Scenario, ScenarioSuite, SurfaceKind
from squadops.scenarios.quality import (
    LintReading,
    NotMeasured,
    QualityReading,
    QualityStatus,
    measurable_pages,
)
from squadops.scenarios.quality_seeds import quality_seed
from squadops.scenarios.runner import (
    DeclaredStart,
    ReadinessUnsupported,
    RunnerUnavailable,
    SecretUnavailable,
    StartUndeclared,
    TreeEvaluation,
)
from squadops.scenarios.steps import ScenarioRun, drives_a_browser
from squadops.scenarios.suites import require_pinnable
from squadops.stacks.scaffold import InterfaceManifest

if TYPE_CHECKING:  # the ports name this package's models; the service only takes them
    from squadops.ports.scenarios import ScenarioRunnerPort, ScenarioStorePort

logger = logging.getLogger(__name__)

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


#: The interface manifest a delivery's fields are named in (#2464).
MANIFEST_FILENAME = "interface_manifest.yaml"


async def delivered_manifest(vault: Any, cycle: Any) -> InterfaceManifest | None:
    """The evaluated delivery's own interface manifest (#2464): the cycle's latest, or else the
    one of the accepted cycle it built on. ``None`` when neither stored one, or the one stored
    can't be read: the record is still written, its concepts under their first names and its
    endpoints unchecked, rather than lost to the delivery's own malformed file."""
    for cycle_id in (cycle.cycle_id, accepted_cycle_of(cycle)):
        if cycle_id is None:
            continue
        refs = await vault.list_artifacts(cycle_id=cycle_id)  # newest first
        stored = next((r for r in refs if r.filename == MANIFEST_FILENAME), None)
        if stored is not None:
            _ref, content = await vault.retrieve(stored.artifact_id)
            try:
                return InterfaceManifest.from_yaml(content.decode("utf-8"))
            except (ValueError, TypeError, KeyError, UnicodeDecodeError, yaml.YAMLError) as e:
                logger.warning(
                    "evaluated_manifest_unreadable",
                    extra={
                        "cycle_id": cycle_id,
                        "artifact_id": stored.artifact_id,
                        "error": str(e),
                    },
                )
                return None
    return None


def delivered_fields(manifest: InterfaceManifest | None) -> dict[str, frozenset[str]]:
    """Each entity's field names, as the delivery declares them. Empty without a manifest, so
    every concept a scenario names reads as absent."""
    if manifest is None:
        return {}
    return {e.name: frozenset(f.name for f in e.fields) for e in manifest.entities}


_PARAM = re.compile(r"\{[^}]*\}")


def _endpoint(method: str, path: str, prefix: str) -> tuple[str, str]:
    """An endpoint as a scenario names it: the PRD's path, its parameters unnamed."""
    if prefix and path.startswith(prefix):
        path = path[len(prefix) :] or "/"
    return method.upper(), _PARAM.sub("{}", path)


def _api_prefix(stack: str) -> str:
    """Where the stack's app serves the PRD's paths: what the runner prefixes (#2466). A manifest's
    own ``base_path`` can't say it, since deliveries set it both ways (read 2026-10-18: 16 of the
    canonical stack's say ``/api`` and serve at the root)."""
    # deferred (pair): squadops.sandbox imports this package's runner models at load
    from squadops.sandbox.environment import get_environment_contract

    return get_environment_contract(stack).api_prefix


def delivered_endpoints(manifest: InterfaceManifest | None, prefix: str) -> frozenset | None:
    """The delivery's declared endpoints, its stack's API prefix taken off (#2464). ``None``
    without a manifest: then a scenario's endpoints aren't checked, since there is nothing to
    check them against (a declared Project's surfaces come from its entry points)."""
    if manifest is None:
        return None
    return frozenset(_endpoint(e.method, e.path, prefix) for e in manifest.api.endpoints)


def _route(path: str) -> str:
    """A client route with its parameters unnamed: ``/runs/:id`` and ``/runs/{run_id}`` are one
    route (``increment_tree.route_param``), as a scenario's ``/runs/{id}`` is."""
    return "/".join("{}" if route_param(part) else part for part in path.split("/"))


def delivered_routes(manifest: InterfaceManifest | None) -> frozenset[str] | None:
    """The delivery's declared client routes, their parameters unnamed (§10p ruling 4). ``None``
    without a manifest: there is nothing to check a page against."""
    if manifest is None:
        return None
    return frozenset(_route(route.path) for route in manifest.frontend.routes)


def declared_pages(
    manifest: InterfaceManifest | None, declared: DeclaredStart | None
) -> tuple[str, ...]:
    """The pages Lighthouse and axe measure (§4.2, #2416): a blueprint delivery's own declared
    routes that load as they are, or a declared Project's ``ui_base``. Never a sample app's."""
    if declared is not None:
        return (declared.ui_path or "/",) if declared.ui_port is not None else ()
    if manifest is None:
        return ()
    return measurable_pages([route.path for route in manifest.frontend.routes])


#: Why the pages weren't measured, when the whole evaluation was blocked before they could be.
_NOT_MEASURED_BY_BLOCK = {
    BlockedReason.NO_RUNNER: NotMeasured.NO_RUNNER,
    BlockedReason.START_FAILED: NotMeasured.START_FAILED,
    BlockedReason.NO_START_DECLARATION: NotMeasured.NO_START_DECLARATION,
    # §10l: a product whose start declares a secret nothing releases serves no page either.
    BlockedReason.SECRET_NOT_AVAILABLE: NotMeasured.SECRET_NOT_AVAILABLE,
}


def quality_of(
    pages: tuple[str, ...], blocked: BlockedReason | None, evaluated: TreeEvaluation | None
) -> QualityReading:
    """A Project that serves pages: the runner's reading, or why there is none. An evaluation
    that couldn't run says so first: a Project that couldn't be started has pages nobody read."""
    if blocked is not None:
        return QualityReading.not_measured(_NOT_MEASURED_BY_BLOCK[blocked])
    if not pages:
        return QualityReading.not_measured(NotMeasured.NO_DECLARED_PAGE)
    if evaluated is not None and evaluated.quality is not None:
        return evaluated.quality
    return QualityReading.not_measured(
        NotMeasured.EVALUATOR_FAILED, "the runner started the app and returned no reading"
    )


def planned_seed(
    project_id: str, manifest: InterfaceManifest | None, *, blueprint: bool, serves_pages: bool
) -> tuple[QualityReading | None, seed_plan.SeedPlan | None]:
    """The seeded reading's plan (§10j, §10n), or the reading it already is: *not applicable* off
    a blueprint delivery that serves pages, ``no_seed`` with none declared, ``seed_refused`` when
    the seed can't be written through the delivery's own interface."""
    if not serves_pages or not blueprint:
        return QualityReading(QualityStatus.NOT_APPLICABLE), None
    try:
        found = quality_seed(project_id)
        if found is None:
            return QualityReading.not_measured(
                NotMeasured.NO_SEED, f"{project_id} declares no quality seed"
            ), None
        if manifest is None:
            return QualityReading.not_measured(
                NotMeasured.SEED_REFUSED,
                "the delivery has no interface manifest to write it through",
            ), None
        seed, raw = found
        return None, seed_plan.plan(manifest, seed, raw)
    except seed_plan.SeedRefused as e:
        return QualityReading.not_measured(NotMeasured.SEED_REFUSED, str(e)), None


def seeded_of(
    planned: QualityReading | None, blocked: BlockedReason | None, evaluated: TreeEvaluation | None
) -> QualityReading:
    """The seeded reading: what planning already decided, else the runner's, or why there is none.
    An evaluation that couldn't run says so first, as ``quality_of`` does."""
    if planned is not None:
        return planned
    if blocked is not None:
        return QualityReading.not_measured(_NOT_MEASURED_BY_BLOCK[blocked])
    if evaluated is not None and evaluated.quality_seeded is not None:
        return evaluated.quality_seeded
    return QualityReading.not_measured(
        NotMeasured.EVALUATOR_FAILED, "the runner started the app and returned no seeded reading"
    )


def lint_of(
    linted: bool, blocked: BlockedReason | None, evaluated: TreeEvaluation | None
) -> LintReading:
    """#1937's lint of the evaluated tree: the runner's, or why there is none. Only a scaffold
    stack's tree has #1937's rule sets (``linted``): a sample application's, or a product made from
    a scaffold blueprint (§10l). Any other Project's own linter is never read in their place. A
    product that couldn't be started was never sent to the runner, so its lint wasn't taken
    either, for the start's reason (§10l)."""
    if not linted:
        return LintReading.not_measured(NotMeasured.NOT_A_SCAFFOLD_STACK)
    if evaluated is not None and evaluated.lint is not None:
        return evaluated.lint
    if evaluated is None and blocked in _NOT_MEASURED_BY_BLOCK:
        return LintReading.not_measured(_NOT_MEASURED_BY_BLOCK[blocked])
    return LintReading.not_measured(
        NotMeasured.EVALUATOR_FAILED, "the runner returned no lint for the tree"
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
        runner=run.runner,
        step_seconds=run.step_seconds,
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
    unstartable: StartUndeclared | ReadinessUnsupported | SecretUnavailable | None = None,
    tree: Mapping[str, bytes] | None = None,
    executable: Collection[str] = (),
    lint_stack: str | None = None,
) -> EvaluationRecord:
    """Evaluate ``cycle``'s delivered app against an approved suite, and write the record.

    A blueprint cycle starts by its stack (``build_profile``). Any other Project passes its
    ``declared`` start and the ``served`` surface kinds of its entry points, or the refusal it met
    reading its declaration as ``unstartable``, whose ``reason`` blocks every applicable scenario.
    ``lint_stack`` is the scaffold blueprint such a product was made from, whose rule set lints it
    (§10l), or ``None``.

    ``tree`` is the evaluated tree when the caller has it whole, with its ``executable`` bits: a
    repository-backed cycle's, its captured commit (#2414). Otherwise it is read from the vault, by
    SIP-0109's own selection."""
    suite = (await require_pinnable(store, suite_digest)).suite
    if tree is None:
        refs = await evaluated_tree_refs(vault, cycle)
        tree = {path: (await vault.retrieve(art))[1] for path, art in refs.items()}
    # Only a blueprint delivery has a manifest of its own. A declared Project, or one whose
    # declaration couldn't be read, never reads one (SIP-0112 §8.3).
    blueprint = declared is None and unstartable is None
    return await _evaluated(
        store=store,
        runner=runner,
        suite=suite,
        unit=_Unit(cycle.project_id, cycle_id=cycle.cycle_id),
        campaign_id=campaign_id,
        previous_accepted_tree_identity=previous_accepted_tree_identity,
        evaluated_at=evaluated_at,
        tree=tree,
        executable=executable,
        stack=cycle.resolved_config().get("build_profile"),
        manifest=await delivered_manifest(vault, cycle) if blueprint else None,
        declared=declared,
        served=served,
        environment=environment,
        unstartable=unstartable,
        lint_stack=lint_stack,
    )


async def evaluate_calibration_record(
    *,
    store: ScenarioStorePort,
    runner: ScenarioRunnerPort | None,
    project_id: str,
    calibration_record_id: str,
    campaign_id: str,
    suite_digest: str,
    evaluated_at: datetime,
    tree: Mapping[str, bytes],
    executable: Collection[str],
    declared: DeclaredStart | None,
    served: frozenset[SurfaceKind] | None,
    unstartable: StartUndeclared | ReadinessUnsupported | SecretUnavailable | None,
    lint_stack: str | None,
) -> EvaluationRecord:
    """SIP-0113 §10l: a repository-backed Campaign's baseline reading, its calibration record's
    commit evaluated against the Campaign's pinned suite, and the record written. It is a product,
    so it starts only by its ``declared`` start (or is blocked by ``unstartable``), with no stack and
    no manifest of its own. A calibration builds on nothing, so the record names no previous tree.
    The record names the calibration record in place of a cycle."""
    if declared is None and unstartable is None:
        raise ValueError(
            f"calibration record {calibration_record_id} is a product's: it starts by its own "
            "declaration, or the reason it can't, never by a stack"
        )
    return await _evaluated(
        store=store,
        runner=runner,
        suite=(await require_pinnable(store, suite_digest)).suite,
        unit=_Unit(project_id, calibration_record_id=calibration_record_id),
        campaign_id=campaign_id,
        previous_accepted_tree_identity=None,
        evaluated_at=evaluated_at,
        tree=tree,
        executable=executable,
        stack=None,
        manifest=None,
        declared=declared,
        served=served,
        environment=None,
        unstartable=unstartable,
        lint_stack=lint_stack,
    )


@dataclass(frozen=True)
class _Unit:
    """What an evaluation names: a cycle, or a calibration record (§10l), exactly one."""

    project_id: str
    cycle_id: str | None = None
    calibration_record_id: str | None = None


async def _evaluated(
    *,
    store: ScenarioStorePort,
    runner: ScenarioRunnerPort | None,
    suite: ScenarioSuite,
    unit: _Unit,
    campaign_id: str | None,
    previous_accepted_tree_identity: str | None,
    evaluated_at: datetime,
    tree: Mapping[str, bytes],
    executable: Collection[str],
    stack: str | None,
    manifest: InterfaceManifest | None,
    declared: DeclaredStart | None,
    served: frozenset[SurfaceKind] | None,
    environment: Mapping[str, str] | None,
    unstartable: StartUndeclared | ReadinessUnsupported | SecretUnavailable | None,
    lint_stack: str | None,
) -> EvaluationRecord:
    """One tree evaluated against an approved ``suite``, and its record written: a cycle's or a
    calibration record's, by the one path."""
    identity = FileTree.of(tree).identity
    kinds = served if served is not None else BLUEPRINT_SURFACES
    applicable = [s for s in suite.scenarios if {k.kind for k in s.surfaces} <= kinds]

    blocked: BlockedReason | None = None
    runs: dict[str, ScenarioRun] = {}
    # #2464: each scenario's endpoints checked against the delivery's own manifest (one it doesn't
    # serve is surface_absent, never failed), and its concept fields resolved against it.
    absent: dict[str, BlockedReason] = {}
    contents: list[dict[str, Any]] = []
    blueprint = declared is None and unstartable is None
    # §4.2, §10l: a tree with a scaffold stack's rule set: a sample application's, or a product
    # made from a scaffold blueprint. Never the product's own linter.
    linted = blueprint or lint_stack is not None
    fields = delivered_fields(manifest)
    prefix = _api_prefix(stack) if manifest is not None and stack else ""
    endpoints = delivered_endpoints(manifest, prefix)
    routes = delivered_routes(manifest)
    for scenario in applicable:
        needed = {
            _endpoint(s.method or "", s.path, "")
            for s in scenario.surfaces
            if s.kind is SurfaceKind.HTTP_ENDPOINT
        }
        page_routes = {_route(s.path) for s in scenario.surfaces if s.kind is SurfaceKind.PAGE}
        if (endpoints is not None and not needed <= endpoints) or (
            # §10p ruling 4: a scenario that drives a browser is checked against the delivery's
            # routes too. An HTTP-only scenario's page surfaces stay as they were: declarative.
            routes is not None and drives_a_browser(scenario.steps) and not page_routes <= routes
        ):
            # #2464: an endpoint the delivery doesn't serve, e.g. a join it takes at
            # /participants rather than /join, or a page at a route it doesn't declare.
            # Unverified, never failed.
            absent[scenario.scenario_id] = BlockedReason.SURFACE_ABSENT
            continue
        content = resolve(scenario.content(), dict(scenario.fields), fields)
        content.pop("fields", None)
        contents.append(content)
    # §4.2 (#2416): Lighthouse and axe on the declared pages, of a Project that serves pages.
    pages = declared_pages(manifest, declared) if SurfaceKind.PAGE in kinds else ()
    # §10j, §10n (#2562): a second, seeded instance, measured on every declared page.
    planned, plan = planned_seed(
        unit.project_id, manifest, blueprint=blueprint, serves_pages=SurfaceKind.PAGE in kinds
    )
    evaluated: TreeEvaluation | None = None
    # A linted tree is linted whether or not anything else runs (§4.2, #2416).
    if (contents or pages or linted) and unstartable is not None:
        blocked = unstartable.reason
    elif (contents or pages or linted) and runner is None:
        blocked = BlockedReason.NO_RUNNER
    elif (contents or pages or linted) and runner is not None:
        # Each is passed only when asked for, so a runner that takes neither is called as before.
        optional: dict[str, Any] = {"seed": plan} if plan is not None else {}
        if lint_stack is not None:
            optional["lint_stack"] = lint_stack
        try:
            evaluated = await runner.evaluate_tree(
                tree=tree,
                tree_identity=identity,
                executable=sorted(executable),
                stack=stack,
                declared=declared,
                scenarios=contents,
                environment=environment or {},
                pages=pages,
                **optional,
            )
        except RunnerUnavailable:
            blocked = BlockedReason.NO_RUNNER
        else:
            if not evaluated.started:
                blocked = BlockedReason.START_FAILED
            runs = {r.scenario_id: r for r in evaluated.runs}

    record = evaluation_record(
        suite,
        tuple(
            _outcome(s, kinds, runs.get(s.scenario_id), absent.get(s.scenario_id) or blocked)
            for s in suite.scenarios
        ),
        project_id=unit.project_id,
        campaign_id=campaign_id,
        cycle_id=unit.cycle_id,
        calibration_record_id=unit.calibration_record_id,
        evaluated_tree_identity=identity,
        previous_accepted_tree_identity=previous_accepted_tree_identity,
        evaluated_at=evaluated_at,
        quality=(
            quality_of(pages, blocked, evaluated)
            if SurfaceKind.PAGE in kinds
            else QualityReading(QualityStatus.NOT_APPLICABLE)
        ),
        lint=lint_of(linted, blocked, evaluated),
        quality_seeded=seeded_of(planned, blocked, evaluated),
    )
    await store.save_evaluation(record)
    # §10p ruling 8: a failed or blocked page scenario's evidence, beside its record and held out:
    # never on the outcome, which the package and the digest read.
    evidence = [
        ScenarioEvidence.from_wire(scenario_id, run.evidence)
        for scenario_id, run in runs.items()
        if run.evidence
    ]
    if evidence:
        await store.save_evidence(record.evaluation_id, evidence)
    return record

"""A repository-backed increment's acceptance, at its delivery, in place of ``qa.evaluate_increment``
(SIP-0109 §24cd point 6; §24cl).

A sample application's increment is judged by the qa role's ``qa.evaluate_increment``, the last
task of its implementation's plan. A repository-backed product's toolchain exists only in the
sandbox, so its plan has no such task (``IncrementBasis.evaluated_at_delivery``), and it is judged
here, runtime-side, once its delivery has verified and captured the candidate:
- **its inputs** are what the plan hands ``qa.evaluate_increment`` (``increment_evaluation_inputs``),
  read from the same approved change request: the increment's id, each new criterion's placed test
  file (§24cj), the frozen criteria its launch pinned with their stored bundles, and what it
  retires or replaces;
- **its trees** are delivery's own: the head it was built on and the squad's changes to it, so the
  candidate judged is the revision delivery verified;
- **its runner** is the derived profile's, read at the Project's pin (§24cd point 3), and its
  argvs run as the configuration's checks run (H.6);
- **its routes** are the profile's client routes, the pages the campaign's accepted increments
  added (§24dq) and the change request's, rendered on the candidate started in the sandbox from the
  product's declared start, by the renderer the root hands in (``scenarios.declared_routes``,
  §24co);
- **its record** is the ``increment_evaluation`` document a sample application's evaluation writes
  (``acceptance_run.evaluation_document``), stored on the implementation run, so the campaign's
  completion reads it unchanged: the verdict, the bundles a promotion freezes, the brief a
  successor is given (§24br) and the reference report. Three keys are added for this evaluator
  alone: ``evaluated_on``; ``runs``, each run's overlay, revision and reading (§8.4's keys); and
  ``renderings``, what was started and what each route's page showed (§24co).

A read that fails, a profile that's absent, or a sandbox that can't run raises
(``ProductAcceptanceRefused``), so the run fails with it, as a ``qa.evaluate_increment`` that
can't be judged fails its task. Nothing is accepted unjudged.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from squadops.campaigns.acceptance_run import (
    NewCriterion,
    evaluation_document,
    frozen_criteria_from,
)
from squadops.campaigns.evaluator_trees import FileTree, candidate_verifier_overlay
from squadops.campaigns.increment_tree import (
    INCREMENT_EVALUATION_ARTIFACT_TYPE,
    INCREMENT_EVALUATION_FILENAME,
    approved_change_request,
    frozen_bundle_contents,
    increment_basis,
    increment_evaluation_inputs,
    increment_scenario_files,
)
from squadops.campaigns.product_routes import (
    ACCEPTED_PAGES,
    page_inventory,
    requested_routes,
    routes_blocked,
)
from squadops.campaigns.runner_acceptance import (
    RunnerAcceptance,
    RunnerSetup,
    SandboxTree,
    evaluate_on_runner,
    increment_surface,
)
from squadops.campaigns.scenario_runs import (
    ScenarioRuns,
    approved_scenario_digests,
    is_scenario_criterion,
    scenario_bundle,
)
from squadops.capabilities.operation_supply import OperationSupplyError, scenario_operation
from squadops.capabilities.skillsets import packaged_skillsets
from squadops.cycles.models import ArtifactRef, Cycle
from squadops.execution.execution_errors import _ExecutionError
from squadops.execution.product_proposal import kept_scenario_vocabulary
from squadops.remote_execution.models import ASSERTION_RECORDS_ARTIFACT_TYPE, ReadingSide

#: What ``evaluated_on`` names on a document this evaluator writes.
PRODUCT_RUNNER = "product_runner"


class ProductAcceptanceRefused(RuntimeError):
    """A repository-backed increment that can't be judged on its product's runner, with why."""


logger = logging.getLogger(__name__)


def evaluated_at_delivery(cycle: Cycle) -> bool:
    """Whether ``cycle``'s delivered change is an increment judged here (§24cd point 6): a
    repository-backed increment, a repair or a retry of one. The plan asks the same property
    (``task_plan._increment_evaluation``), so exactly one evaluator judges each increment."""
    basis = increment_basis(cycle.resolved_config())
    return basis is not None and basis.evaluated_at_delivery


def acceptance_workspace_prefix(run_id: str) -> str:
    """The start of every workspace one run's evaluation seeds: one per overlay."""
    return f"acc-{run_id}-"


async def evaluate_product_increment(
    cycle: Cycle,
    run_id: str,
    delivery: Any,
    *,
    vault: Any,
    projects: Any,
    sandbox: Any,
    route_renderer: Any,
    read_profile: Any,
    remote_execution: Any = None,
) -> str:
    """Judge the delivered increment on its product's runner and store its ``increment_evaluation``
    on the run. Returns the stored artifact's id.

    Raises:
        ProductAcceptanceRefused: Nothing could be judged: no sandbox, no derived profile at the
            pin, no head from delivery, or no approved change request.
    """
    context = cycle.source_context
    if context is None or delivery.head is None:
        raise ProductAcceptanceRefused(
            f"cycle {cycle.cycle_id}'s delivery names no head: a repository-backed increment is "
            "judged on the head its candidate was built on (SIP-0109 §24bv point 3)"
        )
    if sandbox is None:
        raise ProductAcceptanceRefused(
            "a repository-backed increment is judged in the sandbox, and this runtime has none "
            "(SIP-0109 §24cd point 6)"
        )
    profile = await read_profile(cycle)
    if profile is None:
        raise ProductAcceptanceRefused(
            f"Project {cycle.project_id} has no derived profile at its pin "
            f"({context.development_baseline_commit[:12]}, revision "
            f"{context.development_configuration_revision}): the increment's criteria run on the "
            "product's runners, which only the profile names (SIP-0109 §24bv point 3)"
        )
    try:
        change_request = await approved_change_request(vault, cycle)
    except ValueError as e:
        raise ProductAcceptanceRefused(str(e)) from e
    assert change_request is not None  # an increment's, or approved_change_request raised
    resolved = cycle.resolved_config()
    inputs = increment_evaluation_inputs(resolved, change_request, None)
    configuration = await projects.get_development_configuration(
        cycle.project_id, context.development_configuration_revision
    )
    increment_id = str(inputs["increment_id"])
    new, replaced, retired = _criteria(inputs)
    frozen = frozen_criteria_from(
        inputs["increment_frozen_criteria"], await frozen_bundle_contents(vault, resolved)
    )
    accepted = SandboxTree(dict(delivery.head.files), frozenset(delivery.head.executable))
    candidate = SandboxTree(accepted.files, accepted.executable, dict(delivery.changes))
    runs = RunnerAcceptance(
        sandbox=sandbox,
        profile=profile,
        setup=RunnerSetup.of(configuration.commands),
        workspace_prefix=acceptance_workspace_prefix(run_id),
        verified_candidate_revision=delivery.verification.candidate_revision_id,
    )
    # §24co: the profile's routes and the change request's, rendered on the candidate started
    # from its declaration. §24dq: and the pages the campaign's accepted increments added, from
    # the inventory its launch pinned, as the frozen criteria are.
    requested = requested_routes(change_request)
    try:
        # §24dr item 4: required. A block without one was launched by a runtime-api from before
        # §24dq, and reading it as empty is the false acceptance #2783 is.
        accepted_pages = page_inventory(
            (resolved.get("campaign_proposal") or {}).get(ACCEPTED_PAGES), required=True
        )
    except ValueError as e:
        raise ProductAcceptanceRefused(str(e)) from e
    if route_renderer is None:
        routes = routes_blocked(
            tuple(dict.fromkeys((*(profile.client_routes or ()), *accepted_pages, *requested))),
            "no route renderer: this runtime wires none",
        )
    else:
        routes = await route_renderer.render(
            profile=profile,
            configuration=configuration,
            initialization=await projects.get_initialization(cycle.project_id)
            if profile.client_routes
            else None,
            candidate=candidate,
            verified_candidate_revision=delivery.verification.candidate_revision_id,
            requested_routes=requested,
            accepted_pages=accepted_pages,
        )
    evaluation, done = await evaluate_on_runner(
        runs,
        increment_id=increment_id,
        accepted=accepted,
        candidate=candidate,
        new=new,
        frozen=frozen,
        retired=retired,
        routes=routes.results,
        replaced=replaced,
        # #2799: the page loaders delivery wrote into the candidate, which the bundles of the
        # tests that import them are frozen with. The inputs name them only where one is placed.
        placed_support=tuple(inputs.get("increment_page_loaders") or ()),
        # #3053: a scenario criterion is played through the runtime's own remote execution.
        scenarios=await scenario_runs_for(
            cycle, run_id, increment_id, (*new, *replaced, *frozen), vault, remote_execution
        ),
        # Read only where a new scenario criterion holds its declaration to it.
        approved_digests=approved_scenario_digests(change_request)
        if any(is_scenario_criterion(c.criterion_id, c.test_path) for c in (*new, *replaced))
        else None,
    )
    # #2938: what the product's own measurements say of the candidate. It reports, so it runs after
    # the verdict is formed and can't change it.
    readings = [await runs.read(r.id, r.argv, candidate) for r in configuration.commands.readings]
    document = {
        **evaluation_document(
            evaluation,
            increment_id=increment_id,
            accepted=accepted.file_tree,
            candidate=candidate.file_tree,
            new=new,
            retired=retired,
            replaced=replaced,
        ),
        "evaluated_on": PRODUCT_RUNNER,
        "runs": [r.as_dict() for r in done],
        "renderings": routes.record,
        **({"readings": readings} if readings else {}),
    }
    return await _store(cycle, run_id, document, vault)


def _criteria(
    inputs: dict[str, Any],
) -> tuple[list[NewCriterion], list[NewCriterion], tuple[str, ...]]:
    """The increment's new, replaced and retired criteria, from its evaluation inputs."""
    new = [NewCriterion(f["criterion_id"], f["path"]) for f in inputs["increment_criterion_files"]]
    replaced = [
        NewCriterion(f["criterion_id"], f["path"]) for f in inputs["increment_replaced_criteria"]
    ]
    return new, replaced, tuple(inputs["increment_retired_criteria"])


def baseline_scenario_overlay(
    cycle: Cycle, change_request: str, criterion_id: str, *, accepted: FileTree, profile: Any
) -> FileTree:
    """#3044 2b, #3053: the baseline-evaluator overlay a new scenario criterion is played on:
    ``accepted`` (the pin's checkout) less every file the increment's surface places, plus the
    criterion's declaration as its approved change request froze it. Delivery's evaluation
    builds the same overlay from the same inputs (``increment_surface``,
    ``candidate_verifier_overlay``), so a baseline reading taken before development binds to
    the revision delivery judges and is credited there.

    Raises:
        ValueError: The approved change request places no scenario for ``criterion_id``.
    """
    inputs = increment_evaluation_inputs(cycle.resolved_config(), change_request, None)
    new, replaced, retired = _criteria(inputs)
    frozen = [
        NewCriterion(f["criterion_id"], f["test_path"]) for f in inputs["increment_frozen_criteria"]
    ]
    surface = increment_surface(
        profile,
        new=new,
        frozen=frozen,
        replaced=replaced,
        placed_support=tuple(inputs.get("increment_page_loaders") or ()),
        retired=retired,
    )
    bundle = scenario_bundle(criterion_id, FileTree.of(increment_scenario_files(change_request)))
    if bundle is None:
        raise ValueError(
            f"the approved change request places no scenario for criterion {criterion_id}"
        )
    return candidate_verifier_overlay(accepted, bundle, surface).tree


async def scenario_runs_for(
    cycle: Cycle,
    run_id: str,
    increment_id: str,
    criteria: tuple[Any, ...],
    vault: Any,
    remote_execution: Any,
) -> ScenarioRuns | None:
    """#3053: how this increment's scenario criteria are played at delivery, or ``None`` when it
    has none. The operation is the one the cycle's record says supplies a scenario
    (``scenario_operation``, on the packaged skillsets the record's digest is checked against),
    and the vocabulary the one its kept copy holds. What can't be had is named, and every
    reading is then absent with that reason."""
    if not any(is_scenario_criterion(c.criterion_id, c.test_path) for c in criteria):
        return None
    reasons = []
    if remote_execution is None:
        reasons.append("this runtime binds no remote execution (remote_execution.provider none)")
    try:
        operation = scenario_operation(cycle.skillset_record, packaged_skillsets())
    except OperationSupplyError as e:
        operation = None
        reasons.append(str(e))
    try:
        vocabulary = await kept_scenario_vocabulary(cycle, vault)
    except _ExecutionError as e:
        vocabulary = None
        reasons.append(str(e))
    if vocabulary is None and not reasons:
        reasons.append("this cycle keeps no scenario reader's vocabulary")
    return ScenarioRuns(
        remote_execution,
        operation=operation,
        vocabulary=vocabulary,
        campaign_id=cycle.campaign_id or cycle.cycle_id,
        increment_id=increment_id,
        # A re-evaluation of the run is a new send of each ask, and stops the older one's.
        dispatch_id=f"{run_id}:{uuid4().hex[:12]}",
        unavailable="; ".join(reasons),
        stored_baselines=await _stored_baselines(cycle, vault),
    )


async def _stored_baselines(cycle: Cycle, vault: Any) -> dict[str, list[dict[str, Any]]]:
    """#3044 2b: each scenario criterion's baseline readings the baseline step stored on this
    increment cycle, newest first. Delivery credits one only for its own overlay's revision
    (``ScenarioRuns.credited_baseline``); one it can't read is passed over, and the baseline is
    then played."""
    if vault is None:
        return {}
    refs = await vault.list_artifacts(
        cycle_id=cycle.cycle_id, artifact_type=ASSERTION_RECORDS_ARTIFACT_TYPE
    )
    stored: dict[str, list[dict[str, Any]]] = {}
    for ref in sorted(refs, key=lambda r: r.created_at, reverse=True):
        metadata = ref.metadata or {}
        if metadata.get("side") != ReadingSide.BASELINE.value or not metadata.get("criterion_id"):
            continue
        try:
            _, content = await vault.retrieve(ref.artifact_id)
            document = json.loads(content)
        except (ValueError, KeyError) as e:
            logger.warning(
                "scenario_baseline_unreadable",
                extra={"artifact_id": ref.artifact_id, "reason": f"{type(e).__name__}: {e}"},
            )
            continue
        if isinstance(document, dict):
            stored.setdefault(str(metadata["criterion_id"]), []).append(document)
    return stored


async def _store(cycle: Cycle, run_id: str, document: dict, vault: Any) -> str:
    content = json.dumps(document, indent=2, sort_keys=True).encode("utf-8")
    ref = ArtifactRef(
        artifact_id=f"art_{uuid4().hex[:12]}",
        project_id=cycle.project_id,
        cycle_id=cycle.cycle_id,
        run_id=run_id,
        artifact_type=INCREMENT_EVALUATION_ARTIFACT_TYPE,
        filename=INCREMENT_EVALUATION_FILENAME,
        content_hash=sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type="application/json",
        created_at=datetime.now(UTC),
        metadata={"evaluated_on": PRODUCT_RUNNER},
    )
    await vault.store(ref, content)
    return ref.artifact_id

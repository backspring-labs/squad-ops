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
- **its routes** are the profile's client routes, rendered on the candidate started in the sandbox
  from the product's declared start, by the renderer the root hands in
  (``scenarios.declared_routes``, §24co);
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
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from squadops.campaigns.acceptance_run import (
    NewCriterion,
    evaluation_document,
    frozen_criteria_from,
)
from squadops.campaigns.increment_tree import (
    INCREMENT_EVALUATION_ARTIFACT_TYPE,
    INCREMENT_EVALUATION_FILENAME,
    approved_change_request,
    frozen_bundle_contents,
    increment_basis,
    increment_evaluation_inputs,
)
from squadops.campaigns.product_routes import routes_blocked
from squadops.campaigns.runner_acceptance import (
    RunnerAcceptance,
    RunnerSetup,
    SandboxTree,
    evaluate_on_runner,
)
from squadops.cycles.models import ArtifactRef, Cycle

#: What ``evaluated_on`` names on a document this evaluator writes.
PRODUCT_RUNNER = "product_runner"


class ProductAcceptanceRefused(RuntimeError):
    """A repository-backed increment that can't be judged on its product's runner, with why."""


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
    new = [NewCriterion(f["criterion_id"], f["path"]) for f in inputs["increment_criterion_files"]]
    replaced = [
        NewCriterion(f["criterion_id"], f["path"]) for f in inputs["increment_replaced_criteria"]
    ]
    retired = tuple(inputs["increment_retired_criteria"])
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
    # §24co: the profile's routes, rendered on the candidate started from its declaration.
    if route_renderer is None:
        routes = routes_blocked(
            tuple(profile.client_routes or ()), "no route renderer: this runtime wires none"
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
    )
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
    }
    return await _store(cycle, run_id, document, vault)


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

"""What a repository-backed Project's increment proposal is given, composed into its inputs with the
run's plan, before the first dispatch (SIP-0109 §24bv point 5).

A sample application's proposal is given its accepted tree's manifest on its launch's block. A
repository-backed Project's accepted tree is the campaign branch's head, which has no manifest and
which the launch doesn't know until it drains (§24cd point 1). So the proposal task is given, read
at the head its cycle pins (contract 1's ``pinned_commit``):
- **the branch head:** its commit and its tree;
- **the bounded tree view** at it: the task's ``source_repository`` input, as every task of a
  source-backed run is given it (the map, the product's checks and runners, its instruction files);
- **the derived profile, with its disclosed gaps,** read at the Project's pin (§24cd point 3): its
  languages, its public surfaces, each runner with where a criterion's test is placed under it,
  and the gaps that refuse nothing but limit what the increment can show;
- **the previous increment's verification,** or the calibration record's inherited baseline for
  the first: the checks its change is compared with (``source_delivery.regression_baseline``);
- **the requirements source, bound at the head:** a ``repo:file:<path>@current`` read at the pinned
  commit, as SIP-0110 §5ad binds an instruction's, or a stored artifact;
- **or the goal set** (SIP-0115 §5.2), when the Campaign names one in its place: the goal, the
  expected results, the constraints and out of scope, and the backlog with each item's status in
  this Campaign (derived from its control log, ``campaigns.backlog``) and the next item. It is read
  at the revision the Campaign binds: its pinned one, or the latest at this run (``current``,
  §5.5), and the rails record that revision with the proposal (§5.5a). A revision run after a
  return reads it again, so a proposal returned as ``goals_revised`` is revised against the new
  one;
- **a greenfield product's approved manifest** (SIP-0112 H.1), beside them, when it was initialized
  here.

The frozen criteria, the abandoned increment's brief, what qa proposed and each proposal never
approved stay on the launch's block, as a sample application's do.

**Only the task that authors the change request gets it** (``TaskType.authors_change_request``).
**A failed read raises:** the proposal run fails, and the campaign proposes again as after any
failed proposal run (§24bn bounds the retries), never proposing without its inputs.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from squadops.campaigns.backlog import campaign_backlog, latest_readings
from squadops.campaigns.change_request import PRODUCT_PROPOSAL_INPUT
from squadops.campaigns.criterion_placement import runner_placements
from squadops.campaigns.evidence import reading_line
from squadops.campaigns.increment_tree import increment_basis
from squadops.campaigns.models import parse_requirements_source
from squadops.cycles.models import Cycle, GoalSetNotFoundError
from squadops.cycles.vault_reads import retrieve_or_absent
from squadops.execution.execution_errors import _ExecutionError
from squadops.execution.source_delivery import SourceDeliveryRefused, regression_baseline
from squadops.projects.derived_profile import DISCLOSED, DerivedProfile
from squadops.projects.models import SourceUnavailable
from squadops.tasks.models import TaskEnvelope
from squadops.tasks.task_types import authors_change_request

__all__ = ["PRODUCT_PROPOSAL_INPUT", "product_proposal_input", "with_product_proposal"]

#: How many failing finding keys of one check the proposal is shown: enough to read what fails at
#: the head, bounded so a lint check with thousands never fills the prompt. The count is shown
#: whole.
FINDING_KEYS_SHOWN = 20
#: A reading is one line of the proposer's request, so it has a bound of its own (§24dk).
READING_CHARS_SHOWN = 2000


async def with_product_proposal(
    envelopes: list[TaskEnvelope],
    *,
    cycle: Cycle,
    read_profile: Any,
    repository: Any,
    vault: Any,
    projects: Any,
    goal_sets: Any,
    campaigns: Any,
) -> list[TaskEnvelope]:
    """``envelopes`` with the proposal's input on the task that authors the change request, read
    once for the run. Every other cycle's envelopes are returned as they were. ``goal_sets`` and
    ``campaigns`` are read only for a Campaign that names a goal set (SIP-0115 §5.2)."""
    authors = [i for i, e in enumerate(envelopes) if authors_change_request(e.task_type)]
    basis = increment_basis(cycle.resolved_config())
    if not authors or basis is None or basis.has_manifest:
        return envelopes
    product = await product_proposal_input(
        cycle,
        read_profile=read_profile,
        repository=repository,
        vault=vault,
        projects=projects,
        goal_sets=goal_sets,
        campaigns=campaigns,
    )
    composed = list(envelopes)
    for i in authors:
        inputs = {**envelopes[i].inputs, PRODUCT_PROPOSAL_INPUT: product}
        composed[i] = dataclasses.replace(envelopes[i], inputs=inputs)
    return composed


async def product_proposal_input(
    cycle: Cycle,
    *,
    read_profile: Any,
    repository: Any,
    vault: Any,
    projects: Any,
    goal_sets: Any,
    campaigns: Any,
) -> dict[str, Any]:
    """The proposal's input, as plain data the agent's container reads (it has no vault, #1821)."""
    context = cycle.source_context
    if context is None:
        raise _ExecutionError(
            f"cycle {cycle.cycle_id} proposes on a campaign branch and pins no source: a "
            "repository-backed increment is pinned at its branch's head (SIP-0109 §24cd point 1)"
        )
    if repository is None:
        raise _ExecutionError("this runtime has no managed clone to read the product's head from")
    profile = await read_profile(cycle)
    if profile is None:
        raise _ExecutionError(
            f"Project {cycle.project_id} has no derived profile at its pin "
            f"({context.development_baseline_commit[:12]}, revision "
            f"{context.development_configuration_revision}): a repository-backed proposal places "
            "its criteria under the product's runners, which only the profile names (SIP-0109 "
            "§24bv point 5)"
        )
    tree = await repository.tree_at(cycle.project_id, context.pinned_commit)
    block = cycle.resolved_config().get("campaign_proposal") or {}
    objective = block.get("objective") or {}
    try:
        baseline, _verified = await regression_baseline(cycle, vault, projects)
    except SourceDeliveryRefused as e:
        raise _ExecutionError(f"the proposal has no previous verification to be shown: {e}") from e
    return {
        "head": {
            "commit": context.pinned_commit,
            "tree": str(block.get("baseline_tree") or ""),
        },
        "profile": profile_view(profile, tree.files),
        "previous_verification": {
            "source": (
                f"verification {context.previous_verification_ref}"
                if context.previous_verification_ref
                else "the calibration record's inherited baseline"
            ),
            "commit": baseline.commit,
            "checks": [_check(c) for c in baseline.checks],
        },
        **(
            {"goals": await _goals(cycle, goal_sets, campaigns)}
            if objective.get("goals")
            else {
                "requirements": await _requirements(
                    cycle, objective.get("requirements"), repository, vault
                )
            }
        ),
        **await _approved_manifest(projects, cycle.project_id),
    }


async def _approved_manifest(projects: Any, project_id: str) -> dict[str, Any]:
    """§24bv point 5: a greenfield product's approved manifest (SIP-0112 H.1), given beside the
    rest. An existing product was initialized nowhere, and is given none."""
    initialization = await projects.get_initialization(project_id)
    if initialization is None:
        return {}
    return {
        "approved_manifest": {
            "stack": initialization.stack,
            "commit": initialization.commit,
            "content": initialization.manifest,
        }
    }


def profile_view(profile: DerivedProfile, tree_paths: Any) -> dict[str, Any]:
    """What the proposal reads of the derived profile: its languages, its public surfaces, each
    runner with its criterion placement, the file classes, the client routes acceptance judges
    (SIP-0109 §24cp: a page criterion elsewhere adds a route, and names its view's anchor) and the
    disclosed gaps. A blocking gap refused the Campaign's start (§24bv point 1) or this cycle at
    create (H.8), so none is shown."""
    return {
        "languages": [
            {"name": x.name, "package_manager": x.package_manager} for x in profile.languages
        ],
        "public_surfaces": [s.to_document() for s in profile.public_surfaces],
        "placements": [
            p.as_dict() for p in runner_placements(profile.runners, profile.gaps, tree_paths)
        ],
        "test_files": list(profile.test_files),
        "client_routes": list(profile.client_routes or ()),
        "gaps": [
            {
                "id": g.id,
                "subject": g.subject,
                "paths": list(g.paths),
                "stops": g.stops,
                "reason": g.reason,
            }
            for g in profile.gaps
            if g.kind == DISCLOSED
        ],
    }


def _check(check: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": check.id, "result": check.result}
    if check.reason:
        row["reason"] = check.reason
    findings = check.findings
    if findings is not None and findings.readable and findings.counts:
        keys = sorted(findings.counts)
        row["findings"] = {"count": len(keys), "keys": keys[:FINDING_KEYS_SHOWN]}
    return row


async def _goals(cycle: Cycle, goal_sets: Any, campaigns: Any) -> dict[str, Any]:
    """SIP-0115 §5.2: the goal set at the revision the Campaign reads now, with each item's
    status in this Campaign and the next item, as plain data. A goal set that can't be read, or
    a backlog with nothing pending, raises: the proposal would have nothing to serve."""
    if goal_sets is None or campaigns is None:
        raise _ExecutionError(
            f"campaign {cycle.campaign_id} works from a goal set, and this runtime reads no "
            "goal-set store or campaign registry"
        )
    campaign = await campaigns.get_campaign(cycle.campaign_id)
    try:
        view, revisions = await campaign_backlog(campaign, goal_sets=goal_sets, campaigns=campaigns)
    except (GoalSetNotFoundError, ValueError) as e:
        raise _ExecutionError(f"the campaign's goal set can't be read: {e}") from e
    if view.next_item is None:
        raise _ExecutionError(
            f"goal-set revision {view.revision} has no pending item for campaign "
            f"{cycle.campaign_id} to propose: each is accepted or abandoned"
        )
    goal_set = next(r for r in revisions if r.revision == view.revision).goal_set
    document = goal_set.to_document()
    by_id = {b["id"]: b for b in document["backlog"]}
    return {
        "revision": view.revision,
        "reads": "pinned" if campaign.objective.goals.pinned is not None else "current",
        "goal": document["goal"],
        "expected_results": document["expected_results"],
        "constraints": document["constraints"],
        "out_of_scope": document["out_of_scope"],
        "backlog": [
            {
                "id": i.item_id,
                "title": i.title,
                "description": by_id[i.item_id].get("description") or "",
                "serves": list(i.serves),
                "status": i.label,
                **({"reason": i.reason} if i.reason else {}),
            }
            for i in view.items
            if i.position is not None
        ],
        "next_item": view.next_item.item_id,
        # §24dk: how the product measured at the last increment this Campaign accepted.
        "latest_readings": [
            f"{r['id']}: {reading_line(r, READING_CHARS_SHOWN)}"
            for r in latest_readings(await campaigns.control_log(campaign.campaign_id))
        ],
    }


async def _requirements(cycle: Cycle, named: Any, repository: Any, vault: Any) -> dict[str, str]:
    """The requirements source, read as the increment's head has it."""
    if not named:
        raise _ExecutionError(
            f"campaign {cycle.campaign_id}'s objective names no requirements source, which a "
            "repository-backed Campaign declares at its creation (SIP-0109 §24bv point 5)"
        )
    source = parse_requirements_source(str(named))
    context = cycle.source_context
    assert context is not None
    if source.path is not None:
        try:
            content = await repository.file_at(cycle.project_id, context.pinned_commit, source.path)
        except SourceUnavailable as e:
            raise _ExecutionError(
                f"the requirements source {named} can't be read at the head "
                f"{context.pinned_commit[:12]}: {e}"
            ) from e
        return {
            "ref": f"repo:file:{source.path}@{context.pinned_commit}",
            "content": content.decode("utf-8", errors="replace"),
        }
    got = await retrieve_or_absent(vault, str(source.artifact_id))
    if got is None:
        raise _ExecutionError(f"the requirements source {named} is no artifact the vault holds")
    return {"ref": str(source.artifact_id), "content": got[1].decode("utf-8", errors="replace")}

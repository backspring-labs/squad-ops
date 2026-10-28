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
  commit, as SIP-0110 §5ad binds an instruction's, or a stored artifact.

The frozen criteria, the abandoned increment's brief, what qa proposed and each proposal never
approved stay on the launch's block, as a sample application's do.

**Only the task that authors the change request gets it** (``TaskType.authors_change_request``).
**A failed read raises:** the proposal run fails, and the campaign proposes again as after any
failed proposal run (§24bn bounds the retries), never proposing without its inputs.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from squadops.campaigns.change_request import PRODUCT_PROPOSAL_INPUT
from squadops.campaigns.criterion_placement import runner_placements
from squadops.campaigns.increment_tree import increment_basis
from squadops.campaigns.models import parse_requirements_source
from squadops.cycles.models import Cycle
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


async def with_product_proposal(
    envelopes: list[TaskEnvelope],
    *,
    cycle: Cycle,
    read_profile: Any,
    repository: Any,
    vault: Any,
    projects: Any,
) -> list[TaskEnvelope]:
    """``envelopes`` with the proposal's input on the task that authors the change request, read
    once for the run. Every other cycle's envelopes are returned as they were."""
    authors = [i for i, e in enumerate(envelopes) if authors_change_request(e.task_type)]
    basis = increment_basis(cycle.resolved_config())
    if not authors or basis is None or basis.has_manifest:
        return envelopes
    product = await product_proposal_input(
        cycle, read_profile=read_profile, repository=repository, vault=vault, projects=projects
    )
    composed = list(envelopes)
    for i in authors:
        inputs = {**envelopes[i].inputs, PRODUCT_PROPOSAL_INPUT: product}
        composed[i] = dataclasses.replace(envelopes[i], inputs=inputs)
    return composed


async def product_proposal_input(
    cycle: Cycle, *, read_profile: Any, repository: Any, vault: Any, projects: Any
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
        "requirements": await _requirements(
            cycle, (block.get("objective") or {}).get("requirements"), repository, vault
        ),
    }


def profile_view(profile: DerivedProfile, tree_paths: Any) -> dict[str, Any]:
    """What the proposal reads of the derived profile: its languages, its public surfaces, each
    runner with its criterion placement, the file classes and the disclosed gaps. A blocking gap
    refused the Campaign's start (§24bv point 1) or this cycle at create (H.8), so none is shown."""
    return {
        "languages": [
            {"name": x.name, "package_manager": x.package_manager} for x in profile.languages
        ],
        "public_surfaces": [s.to_document() for s in profile.public_surfaces],
        "placements": [
            p.as_dict() for p in runner_placements(profile.runners, profile.gaps, tree_paths)
        ],
        "test_files": list(profile.test_files),
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
            content = await repository.file_at(
                cycle.project_id, context.pinned_commit, source.path
            )
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

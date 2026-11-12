"""The baseline step: each scenario criterion played on the accepted baseline before development
starts (#3044 2b; SIP-0117 R5.7, R5.9).

A scenario criterion is the increment's claim about what a player will see. It is a claim about
the work only if, before the work, it executes and fails on the tree the work starts from. So
before an increment's implementation run dispatches anything, each scenario its plan runs (the
operation steps plan expansion appended, #3070) is played on the baseline:

- **the tree** is the baseline-evaluator overlay delivery's acceptance judges
  (``product_acceptance.baseline_scenario_overlay``): the pin's checkout, less what the
  increment's surface places, plus the declaration as frozen. So the reading binds to the
  revision acceptance credits, and delivery needn't play it again;
- **the ask** goes through the runtime's own port (``ScenarioRuns``, under
  ``acceptance_task_id(..., BASELINE)``), staged by the one rule acceptance stages by;
- **the reading** is kept as the cycle's ``remote_operation_assertions`` artifact, side
  ``baseline`` (``records_document``), and judged by ``baseline_verdict``, the one copy of the
  rule.

The verdict decides the run, by endings the Campaign already reads:

- ``may_start`` for every scenario: development is dispatched;
- a scenario whose named assertion already passes, or whose world isn't the baseline's: the run
  ends ``criteria_not_checkable``, and the Campaign abandons the increment for a new proposal
  (row 19). The scenario is refused to its author. A pass isn't recorded as met: it says the
  scenario proved nothing about the work (§24do's ruling);
- anything not read (no worker, not executed, interrupted, an assertion with no record): the run
  ends ``infrastructure_failed`` with the reason, and is retried. Nothing unread starts work.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from squadops.campaigns.change_request import scenario_criterion_path
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.increment_tree import (
    approved_change_request,
    increment_evaluation_inputs,
    increment_scenario_files,
)
from squadops.campaigns.runner_acceptance import NewCriterion
from squadops.campaigns.scenario_runs import approved_scenario_digests, scenario_bundle
from squadops.cycles.failure_attribution import TerminalKind
from squadops.cycles.models import ArtifactRef, Cycle
from squadops.cycles.run_loop_summary import RunTerminalDecision
from squadops.execution.execution_errors import _ExecutionError
from squadops.execution.product_acceptance import baseline_scenario_overlay, scenario_runs_for
from squadops.projects.configuration import baseline_tree
from squadops.remote_execution.models import (
    ASSERTION_RECORDS_ARTIFACT_TYPE,
    AssertionOutcome,
    OperationStatus,
    ReadingSide,
)
from squadops.remote_execution.scenario import BaselineVerdict, baseline_verdict
from squadops.tasks.models import TaskEnvelope
from squadops.tasks.task_types import runs_an_operation

logger = logging.getLogger(__name__)

#: The baseline reading's file, beside the candidate's ``operation_assertions.json``.
BASELINE_RECORDS_FILENAME = "operation_assertions.baseline.json"


@dataclass(frozen=True)
class BaselineJudgement:
    """One scenario's reading on the baseline, judged."""

    criterion_id: str
    verdict: BaselineVerdict
    why: str


def scenario_criteria_of(plan: Iterable[TaskEnvelope]) -> tuple[str, ...]:
    """The scenario criteria a run's plan plays: each appended operation step's scenario, whose
    id is its criterion's (#3044). ``()`` for every run without one."""
    return tuple(
        str(envelope.inputs["operation_scenario"]["scenario_id"])
        for envelope in plan
        if runs_an_operation(str(envelope.task_type))
        and isinstance(envelope.inputs.get("operation_scenario"), Mapping)
    )


async def judge_scenario_baselines(
    cycle: Cycle,
    run_id: str,
    criterion_ids: tuple[str, ...],
    *,
    vault: Any,
    remote_execution: Any,
    repository: Any,
    registry: Any,
    read_profile: Any,
) -> tuple[BaselineJudgement, ...]:
    """Each of ``criterion_ids`` played on the baseline and judged, its reading stored. What
    can't be read at all (the request, the pin's tree, the profile) raises ``ValueError`` with
    why; a scenario that can't be asked or doesn't execute is judged ``blocked``."""
    change_request = await approved_change_request(vault, cycle)
    context = cycle.source_context
    if change_request is None or context is None:
        raise ValueError(
            f"cycle {cycle.cycle_id} plays scenarios and has no approved change request or "
            "pinned source to read its baseline from"
        )
    if repository is None or registry is None:
        raise ValueError("this runtime has no managed clone or project registry to read the pin")
    project = await registry.get_project(cycle.project_id)
    checkout = await baseline_tree(
        repository, cycle.project_id, context.repo_uri, project.source.base_ref,
        context.pinned_commit,
    )  # fmt: skip
    profile = await read_profile(cycle)
    if profile is None:
        raise ValueError(
            f"Project {cycle.project_id} has no derived profile at its pin, which names the "
            "files the baseline overlay leaves out"
        )
    increment_id = str(
        increment_evaluation_inputs(cycle.resolved_config(), change_request, None)["increment_id"]
    )
    runs = await scenario_runs_for(
        cycle,
        run_id,
        increment_id,
        tuple(NewCriterion(c, scenario_criterion_path(c)) for c in criterion_ids),
        vault,
        remote_execution,
    )
    assert runs is not None  # every criterion here is a scenario's
    accepted = FileTree.of(checkout.files)
    declarations = FileTree.of(increment_scenario_files(change_request))
    digests = approved_scenario_digests(change_request)
    judgements = []
    for criterion_id in criterion_ids:
        bundle = scenario_bundle(criterion_id, declarations)
        if bundle is None:
            raise ValueError(
                f"the approved change request places no scenario for criterion {criterion_id}"
            )
        scenario, why = runs.scenario(bundle, digests.get(criterion_id))
        if scenario is None:
            judgements.append(BaselineJudgement(criterion_id, BaselineVerdict.BLOCKED, why))
            continue
        overlay = baseline_scenario_overlay(
            cycle, change_request, criterion_id, accepted=accepted, profile=profile
        )
        reading = await runs.read(criterion_id, ReadingSide.BASELINE, overlay, scenario)
        if reading.document is None:
            judgements.append(BaselineJudgement(criterion_id, BaselineVerdict.BLOCKED, reading.why))
            continue
        await _store(cycle, run_id, criterion_id, reading.document, vault)
        outcomes = {
            str(a["assertion_id"]): AssertionOutcome(a["outcome"])
            for a in reading.document["assertions"]
        }
        verdict, why = baseline_verdict(outcomes, scenario.named_assertion)
        if reading.document["status"] != OperationStatus.COMPLETED.value:
            why = f"{why}; the operation is {reading.document['status']}: {reading.document['reason']}"
        judgements.append(BaselineJudgement(criterion_id, verdict, why))
    return tuple(judgements)


def baseline_ending(judgements: Iterable[BaselineJudgement]) -> _ExecutionError | None:
    """The run's ending for ``judgements``, or ``None`` when every scenario may start. A scenario
    refused to its author outranks one not read: its increment is re-proposed either way."""
    judged = list(judgements)
    refused = [
        j
        for j in judged
        if j.verdict in (BaselineVerdict.PASSES_ON_BASELINE, BaselineVerdict.PRECONDITION_FAILS)
    ]
    if refused:
        return _ExecutionError(
            "scenario criteria can't be checked on the accepted baseline, so no development "
            "starts on them: " + "; ".join(f"{j.criterion_id}: {j.why}" for j in refused),
            terminal=RunTerminalDecision(kind=TerminalKind.CRITERIA_NOT_CHECKABLE),
        )
    blocked = [j for j in judged if j.verdict is BaselineVerdict.BLOCKED]
    if blocked:
        return _ExecutionError(
            "scenario criteria weren't read on the accepted baseline, so no development starts "
            "on them: " + "; ".join(f"{j.criterion_id}: {j.why}" for j in blocked),
            terminal=RunTerminalDecision(kind=TerminalKind.INFRASTRUCTURE_FAILED),
        )
    return None


async def _store(
    cycle: Cycle, run_id: str, criterion_id: str, document: Mapping[str, Any], vault: Any
) -> None:
    content = json.dumps(document, indent=2, sort_keys=True).encode("utf-8")
    await vault.store(
        ArtifactRef(
            artifact_id=f"art_{uuid4().hex[:12]}",
            project_id=cycle.project_id,
            cycle_id=cycle.cycle_id,
            run_id=run_id,
            artifact_type=ASSERTION_RECORDS_ARTIFACT_TYPE,
            filename=BASELINE_RECORDS_FILENAME,
            content_hash=sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type="application/json",
            created_at=datetime.now(UTC),
            metadata={"side": ReadingSide.BASELINE.value, "criterion_id": criterion_id},
        ),
        content,
    )

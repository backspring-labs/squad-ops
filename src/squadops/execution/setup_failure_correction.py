"""A candidate's own setup failure, read before its play is accepted (SIP-0117 R5.32, #3200).

A played scenario whose setup failed reads *not executed*, and the task that played it
succeeds with unverified rows. That routing stands. This module is the one place the run asks
whether the failure is the candidate's own, by ``remote_execution.setup_attribution``'s six
conditions, and it does two things with the answer:

- **it keeps the reading.** Every condition, held or not, goes beside the play's evidence as
  ``setup_attribution.json``, with the baseline reading it was read against;
- **it spends one correction, when all six hold.** The task's result is refused as a failure
  the correction loop repairs, carrying the error the provider named. Once per task, and only
  while the run has a correction left. The task's check rows are not touched: an unexecuted
  assertion stays unexecuted.

Everything it reads is a record: the task's own reading, this cycle's stored baseline reading
of the same criterion, the pinned checkout, and the approved change request's footprint.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from collections.abc import Mapping
from typing import Any

from squadops.campaigns.change_request import in_footprint
from squadops.campaigns.increment_tree import approved_change_request, approved_footprint
from squadops.cycles.models import Cycle
from squadops.cycles.task_outcome import TaskOutcome
from squadops.cycles.vault_reads import retrieve_recorded
from squadops.projects.configuration import baseline_tree
from squadops.remote_execution.models import (
    ASSERTION_RECORDS_ARTIFACT_TYPE,
    OPERATION_EVIDENCE_ARTIFACT_TYPE,
    ReadingSide,
)
from squadops.remote_execution.setup_attribution import (
    ATTRIBUTION_FILENAME,
    SetupAttribution,
    attribute,
    setup_failed,
)
from squadops.tasks.models import TaskEnvelope, TaskResult, TaskResultStatus
from squadops.tasks.task_types import runs_an_operation

logger = logging.getLogger(__name__)

#: A refused result's outputs carry the attribution under this key. The correction's gate reads
#: it: a played task is repaired for an executed failure (R5.1) or for this, and nothing else.
SETUP_ATTRIBUTION_KEY = "setup_attribution"
#: The candidate reading's file among the task's artifacts
#: (``run_remote_operation.ASSERTION_RECORDS_FILENAME``; held equal by a test).
_CANDIDATE_READING = "operation_assertions.json"

#: Why an attributed failure wasn't sent to correction, as the kept reading says it.
NOT_REPAIRED_ALREADY = "this task's one setup-failure correction was already spent"
NOT_REPAIRED_NO_BUDGET = "the run has no correction left"


def attributed_setup_failure(outputs: Mapping[str, Any] | None) -> bool:
    """Whether a failed result is one this module refused: a setup failure attributed to the
    candidate. The correction's gate asks, beside ``has_blocking_failure``."""
    held = (outputs or {}).get(SETUP_ATTRIBUTION_KEY)
    return isinstance(held, Mapping) and held.get("attributed") is True


async def screen_setup_failure(
    result: TaskResult,
    envelope: TaskEnvelope,
    enriched: TaskEnvelope,
    cycle: Cycle,
    *,
    vault: Any,
    repository: Any,
    registry: Any,
    spent: set[str],
    correction_left: bool,
) -> TaskResult:
    """``result`` as it goes on: unchanged for anything that isn't a played scenario whose
    setup failed; with the attribution kept beside its evidence otherwise; and refused as a
    failure to correct when the attribution holds, the task hasn't had its one, and the run
    has a correction left (``spent`` is the run's set of tasks that have had theirs)."""
    if not runs_an_operation(str(envelope.task_type)):
        return result
    candidate = _candidate_reading(result)
    if candidate is None or not setup_failed(candidate):
        return result
    criterion_id = str((candidate.get("scenario") or {}).get("scenario_id") or "")
    baseline_ref, baseline = await _baseline_reading(cycle, criterion_id, vault)
    tree = enriched.inputs.get("acceptance_workspace_files")
    changed, footprint = await _changed_and_footprint(
        cycle, tree if isinstance(tree, Mapping) else {}, vault, repository, registry
    )
    attribution = attribute(
        candidate,
        baseline,
        changed=changed,
        in_footprint=lambda path: in_footprint(path, footprint),
    )
    task_id = envelope.task_id
    repair = attribution.attributed and task_id not in spent and correction_left
    not_repaired = ""
    if attribution.attributed and not repair:
        not_repaired = NOT_REPAIRED_ALREADY if task_id in spent else NOT_REPAIRED_NO_BUDGET
    document = {
        **attribution.document(
            baseline_reading=baseline_ref,
            candidate_revision=str(candidate.get("source_revision") or ""),
        ),
        "task_id": task_id,
        "repair": "dispatched" if repair else "not_dispatched",
        "not_repaired_because": not_repaired,
    }
    logger.info(
        "setup_failure_attribution task=%s scenario=%s attributed=%s repair=%s failing=%s",
        task_id,
        criterion_id,
        attribution.attributed,
        document["repair"],
        [r.condition.value for r in attribution.readings if not r.holds],
    )
    kept = _with_attribution(result, document)
    if not repair:
        return kept
    spent.add(task_id)
    return _refused(kept, attribution, document)


def _candidate_reading(result: TaskResult) -> dict[str, Any] | None:
    for artifact in (result.outputs or {}).get("artifacts") or ():
        if isinstance(artifact, Mapping) and artifact.get("name") == _CANDIDATE_READING:
            try:
                reading = json.loads(str(artifact.get("content") or ""))
            except ValueError:
                return None
            return reading if isinstance(reading, dict) else None
    return None


async def _baseline_reading(
    cycle: Cycle, criterion_id: str, vault: Any
) -> tuple[str, dict[str, Any] | None]:
    """This cycle's newest stored baseline reading of ``criterion_id``, with its artifact id,
    or ``("", None)``. One the vault lists and can't return ends the run by name (#3128): the
    listing is the record that it exists."""
    if vault is None or not criterion_id:
        return "", None
    refs = await vault.list_artifacts(
        cycle_id=cycle.cycle_id, artifact_type=ASSERTION_RECORDS_ARTIFACT_TYPE
    )
    stored = [
        ref
        for ref in refs
        if (ref.metadata or {}).get("side") == ReadingSide.BASELINE.value
        and (ref.metadata or {}).get("criterion_id") == criterion_id
    ]
    for ref in sorted(stored, key=lambda r: r.created_at, reverse=True):
        _, content = await retrieve_recorded(
            vault, ref.artifact_id, what=f"the stored baseline reading of {criterion_id}"
        )
        try:
            reading = json.loads(content)
        except ValueError:
            continue
        if isinstance(reading, dict):
            return ref.artifact_id, reading
    return "", None


async def _changed_and_footprint(
    cycle: Cycle, tree: Mapping[str, Any], vault: Any, repository: Any, registry: Any
) -> tuple[frozenset[str], tuple[str, ...]]:
    """The staged paths whose text differs from the pinned checkout's, and the approved
    footprint. Empty, both, for a cycle with no pinned source or approved change request, or
    whose pin can't be read: nothing is then a file the candidate changed, and the attribution
    fails its third condition by what it couldn't read."""
    context = cycle.source_context
    try:
        change_request = await approved_change_request(vault, cycle)
    except ValueError as e:
        logger.warning("setup_failure_attribution: no approved change request: %s", e)
        change_request = None
    if change_request is None or context is None or repository is None or registry is None:
        return frozenset(), ()
    try:
        project = await registry.get_project(cycle.project_id)
        checkout = await baseline_tree(
            repository,
            cycle.project_id,
            context.repo_uri,
            project.source.base_ref,
            context.pinned_commit,
        )
    except Exception as e:  # noqa: BLE001 - an unreadable pin attributes nothing, by name
        logger.warning(
            "setup_failure_attribution: the pinned source of %s can't be read (%s: %s), so no "
            "file reads as changed",
            cycle.cycle_id,
            type(e).__name__,
            e,
        )
        return frozenset(), ()
    changed = frozenset(
        path
        for path, text in tree.items()
        if isinstance(text, str) and checkout.files.get(path) != text.encode()
    )
    return changed, approved_footprint(change_request)


def _with_attribution(result: TaskResult, document: Mapping[str, Any]) -> TaskResult:
    outputs = dict(result.outputs or {})
    outputs["artifacts"] = [
        *(a for a in outputs.get("artifacts") or () if a.get("name") != ATTRIBUTION_FILENAME),
        {
            "name": ATTRIBUTION_FILENAME,
            "content": json.dumps(document, indent=2, sort_keys=True),
            "media_type": "application/json",
            "type": OPERATION_EVIDENCE_ARTIFACT_TYPE,
        },
    ]
    return dataclasses.replace(result, outputs=outputs)


def _refused(
    result: TaskResult, attribution: SetupAttribution, document: Mapping[str, Any]
) -> TaskResult:
    """The play's result as the failure it is refused as. Its check rows are the play's own:
    every assertion still reads not executed, and the refusal adds no row."""
    outputs = dict(result.outputs or {})
    outputs[SETUP_ATTRIBUTION_KEY] = dict(document)
    outputs["outcome_class"] = TaskOutcome.SEMANTIC_FAILURE
    return dataclasses.replace(
        result,
        status=TaskResultStatus.FAILED,
        outputs=outputs,
        error=(
            f"scenario {attribution.scenario_id}: its setup failed on the candidate, and was met "
            "on the baseline in this cycle. The candidate's own script raised before the setup "
            f"stopped: {attribution.repair_evidence()}. Attributed to the candidate "
            "(SIP-0117 R5.32); no assertion executed"
        ),
    )

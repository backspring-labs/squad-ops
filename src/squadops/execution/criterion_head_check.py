"""A repository-backed increment's criterion files, run on the campaign branch's head as soon as
the qa task has written them, before the run delivers (SIP-0109 §24cz, #2890).

The 2.6 spike's unattended run (2026-10-31) spent two increments on criteria the head already met:
item 1's first proposal, abandoned at row 16 after a whole cycle, and item 5's T21, read
``no_baseline_failure`` at acceptance after a cycle and its repair. Both would have been found the
moment the test existed. So, once the increment cycle's qa task has emitted a criterion's file and
the run has stored it, that file is run on the product's own runner in the sandbox
(``product_suite.run_on_product_runner``, the run #2818 made) against **the head**: the pinned
commit's tree from the managed clone (``product_tree_at_pin``, seeded as a checkout, H.19), with
the criterion files patched on it and no development emission, a removal included. A file that passes there is already met, and the executor ends the run with
``TerminalKind.CRITERIA_NOT_CHECKABLE``; the completion boundary records the cycle's ending as
``criteria_not_checkable``, and the campaign's decision (row 19) returns the increment to a new
proposal told which criteria the head meets, counted toward no unaccepted limit.

**Where it can't run, the cycle proceeds as today, and the skip is logged with its reason:** no
sandbox or managed clone, no derived profile or configuration at the pin, a criterion file the
request placed nowhere, one no runner holds one by one or no test-id reader can read, or any read
or sandbox run that failed. Nothing here fails a run. Acceptance's own discrimination read (§24cl) stays, as
the last line.

**Unchanged:** a sample application's increment (no source repository) and every task that isn't
the qa suite's author.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from squadops.campaigns.criterion_head import (
    CHECKED_ON,
    CRITERION_HEAD_CHECK_ARTIFACT_TYPE,
    CRITERION_HEAD_CHECK_FILENAME,
    CriterionHeadReading,
    HeadReading,
    head_check_document,
)
from squadops.campaigns.increment_tree import (
    approved_change_request,
    increment_basis,
    increment_criterion_files,
)
from squadops.campaigns.runner_acceptance import RunnerSetup
from squadops.cycles.models import ArtifactRef, Cycle
from squadops.execution.product_suite import (
    SuiteRun,
    product_tree_at_pin,
    run_on_product_runner,
    sandbox_workspace_id,
)
from squadops.execution.source_delivery import squad_changes
from squadops.stacks.scaffold import scaffold_stack_for
from squadops.tasks.task_types import authors_qa_suite

logger = logging.getLogger(__name__)

#: The workspace the check seeds, apart from the re-judged suite's (``suite-``) and acceptance's.
_WORKSPACE_KIND = "head"
#: How every skip's log line opens (``%s`` is the task).
_UNREAD = "criterion head check %s: skipped"


@dataclass(frozen=True)
class CriterionHeadCheck:
    """What one check read: the head it ran on, each criterion's reading, each file's run, and
    the record it stored."""

    head_commit: str
    readings: tuple[CriterionHeadReading, ...]
    runs: tuple[SuiteRun, ...]
    record_id: str

    @property
    def already_met(self) -> tuple[str, ...]:
        return tuple(r.criterion_id for r in self.readings if r.already_met)


def applies(task_type: str, cycle: Any) -> bool:
    """Whether the check applies at this task: the qa suite's author on a repository-backed
    increment, repair or retry (``IncrementBasis.evaluated_at_delivery``, as acceptance asks it).
    A basis the reader refuses is not the check's to judge: the plan refused it first."""
    if not authors_qa_suite(task_type):
        return False
    try:
        basis = increment_basis(cycle.resolved_config())
    except ValueError:
        return False
    return basis is not None and basis.evaluated_at_delivery


def reading_of(run: SuiteRun) -> HeadReading:
    """One file's reading from its run: passed whole is already met; a failure the reader named
    fails on the head; anything else ran nothing readable."""
    if run.passed:
        return HeadReading.ALREADY_MET
    if run.unexecuted is None and run.tests_passed is not None and run.failing:
        return HeadReading.FAILS_ON_HEAD
    return HeadReading.NOT_RUN


async def check_criteria_on_head(
    *,
    task_type: str,
    task_id: str,
    inputs: Mapping[str, Any],
    cycle: Cycle,
    run_id: str,
    stored_artifacts: list[tuple[str, ArtifactRef]],
    vault: Any,
    sandbox: Any,
    projects: Any,
    repository: Any,
    read_profile: Any,
) -> CriterionHeadCheck | None:
    """Run the increment's criterion files the run has stored on the head, record the readings,
    and return them; ``None`` where the check doesn't apply or can't run (logged with why).

    ``inputs`` are the task's dispatched inputs, whose product runners say which of the pin's
    files are tests (``product_tree_at_pin``). Nothing here raises: a check that can't run leaves
    the cycle to proceed as today, whatever stopped it."""
    if not applies(task_type, cycle):
        return None
    why = _why_cant_run(cycle.source_context, sandbox, projects)
    if why is not None:
        _skipped(task_id, why)
        return None
    try:
        return await _read_on_head(
            task_id, inputs, cycle, run_id, stored_artifacts, vault, sandbox, projects, repository,
            read_profile,
        )  # fmt: skip
    except Exception:
        logger.warning(
            "criterion head check %s: skipped: its reads or the sandbox run failed",
            task_id,
            exc_info=True,
        )
        return None


async def _read_on_head(
    task_id: str,
    inputs: Mapping[str, Any],
    cycle: Cycle,
    run_id: str,
    stored_artifacts: list[tuple[str, ArtifactRef]],
    vault: Any,
    sandbox: Any,
    projects: Any,
    repository: Any,
    read_profile: Any,
) -> CriterionHeadCheck | None:
    context = cycle.source_context
    assert context is not None  # _why_cant_run refused a cycle with none
    placed = {
        f.path: f.criterion_id
        for f in increment_criterion_files(
            await _change_request(vault, cycle), scaffold_stack_for(cycle.resolved_config())
        )
    }
    profile = await read_profile(cycle)
    if profile is None:
        _skipped(task_id, "no derived profile at the Project's pin")
        return None
    configuration = await projects.get_development_configuration(
        cycle.project_id, context.development_configuration_revision
    )
    if configuration is None:
        _skipped(task_id, "no development configuration at the Project's pin")
        return None
    # The pin as the re-judged suite reads it (H.19): seeded as the checkout it is, so a tracked
    # lockfile is content there and a Node product's setup can install. Nothing of the run's is
    # laid on it but the criterion files: a removal an earlier task made (H.23) is development's
    # work, and the head still holds that file. Applied here, a test of the removal would pass on
    # "the head" and end an increment that discriminates.
    pinned = await product_tree_at_pin(repository, cycle, inputs, task_id, unread=_UNREAD)
    if pinned is None:
        return None
    tests = await _criterion_tests(vault, stored_artifacts, placed, pinned.files)
    if not tests:
        _skipped(task_id, "no criterion file in the run's stored emissions")
        return None
    runs = await run_on_product_runner(
        sandbox=sandbox,
        profile=profile,
        setup=RunnerSetup.of(configuration.commands),
        pinned=pinned,
        tree={},
        tests=tests,
        workspace_id=sandbox_workspace_id(_WORKSPACE_KIND, run_id, task_id),
    )
    if runs is None:
        _skipped(
            task_id,
            "no runner holds a criterion file one by one with a test-id reader (SIP-0109 §24ci (a))",
        )
        return None
    readings = tuple(
        CriterionHeadReading(placed[run.path], run.path, reading_of(run)) for run in runs
    )
    block = cycle.resolved_config().get("campaign_proposal") or {}
    document = head_check_document(
        increment_id=str(block.get("proposal_id") or ""),
        head_commit=context.pinned_commit,
        readings=readings,
        runs=[run.as_dict() for run in runs],
    )
    record_id = await _store(cycle, run_id, document, vault)
    logger.info(
        "criterion head check %s: head=%s readings=%s",
        task_id,
        context.pinned_commit[:12],
        [r.as_dict() for r in readings],
    )
    return CriterionHeadCheck(context.pinned_commit, readings, tuple(runs), record_id)


def _why_cant_run(context: Any, sandbox: Any, projects: Any) -> str | None:
    if context is None:
        return "the cycle pins no source"
    if sandbox is None:
        return "no sandbox"
    if projects is None:
        return "no project registry"
    return None


def _skipped(task_id: str, why: str) -> None:
    logger.info(_UNREAD + ": %s", task_id, why)


async def _change_request(vault: Any, cycle: Cycle) -> str:
    document = await approved_change_request(vault, cycle)
    if document is None:
        raise ValueError(f"cycle {cycle.cycle_id} is not an increment")
    return document


async def _criterion_tests(
    vault: Any,
    stored_artifacts: list[tuple[str, ArtifactRef]],
    placed: dict[str, str],
    head: Mapping[str, bytes],
) -> dict[str, str]:
    """Each criterion file the run has stored, as delivery would deliver it, by path. A criterion
    file whose latest entry is a removal is no test to run."""
    candidates = [(art_id, ref) for art_id, ref in stored_artifacts if ref.filename in placed]
    contents: dict[str, bytes] = {}
    for art_id, _ref in candidates:
        _stored, contents[art_id] = await vault.retrieve(art_id)
    changes, _left_out = squad_changes(candidates, contents, head)
    return {path: content.decode("utf-8") for path, content in changes.items() if content}


async def _store(cycle: Cycle, run_id: str, document: dict[str, Any], vault: Any) -> str:
    content = json.dumps(document, indent=2, sort_keys=True).encode("utf-8")
    ref = ArtifactRef(
        artifact_id=f"art_{uuid4().hex[:12]}",
        project_id=cycle.project_id,
        cycle_id=cycle.cycle_id,
        run_id=run_id,
        artifact_type=CRITERION_HEAD_CHECK_ARTIFACT_TYPE,
        filename=CRITERION_HEAD_CHECK_FILENAME,
        content_hash=sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type="application/json",
        created_at=datetime.now(UTC),
        metadata={"checked_on": CHECKED_ON},
    )
    await vault.store(ref, content)
    return ref.artifact_id

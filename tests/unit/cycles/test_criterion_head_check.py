"""#2890 (SIP-0109 §24cz): a criterion already met is found as soon as its test exists, run on
the campaign branch's head before the run delivers, and the increment ends
``criteria_not_checkable``.

Entered where the live increment cycle enters: ``_execute_sequential`` on the shared fixture's
Tally, its tree seeded as provisioning seeds it, its plan ``generate_task_plan``'s from the stored
change request, each task dispatched and collected by the executor, with a fake sandbox answering
the product runner's one-file command. Bugs caught: a criterion whose test passes on the head
spending the delivery, the acceptance and a repair before row 16 finds it (the 2.6 spike's item 1
and item 5); the head tree seeded with development's emission on it, so a test of the new
behaviour passes on "the head" and every increment ends; a check that can't run failing the run
or ending it, instead of leaving it to proceed with the reason logged.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.noop.ports import NoOpProposalEvidence
from squadops.campaigns.criterion_head import CRITERION_HEAD_CHECK_ARTIFACT_TYPE
from squadops.cycles.deletions import DELETIONS_KEY
from squadops.cycles.failure_attribution import TerminalKind
from squadops.cycles.models import ArtifactRef
from squadops.cycles.run_ledger import RunLedger
from squadops.cycles.task_plan import generate_task_plan
from squadops.execution.binding_holds import BindingHolds
from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor, _ExecutionError
from squadops.execution.source_checkout import seed_checkout_artifacts
from squadops.projects.derived_profile import parse_profile
from squadops.sandbox.models import RevisionOrigin
from squadops.tasks.models import TaskResult
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.campaigns.test_product_increment_seams import STORED
from tests.unit.cycles._product_increment import (
    CONTEXT,
    NAMED,
    NOW,
    SUITE,
    Vault,
    increment_cycle,
    pinned_recall,
    plan,
    product_tree,
    projects,
    repository,
    run,
    squad,
)
from tests.unit.cycles.test_product_suite_runner import _reading, _Sandbox

pytestmark = [pytest.mark.domain_orchestration]

#: Tally's recorded profile names no test-id reader for unittest (§24ci (a)). The product as the
#: check can read it: the same runner, scoped to one file and read by pytest's reader.
_READ_PROFILE = parse_profile(
    {
        **recorded("derived_profile", "valid"),
        "test_runners": [
            {
                **recorded("derived_profile", "valid")["test_runners"][0],
                "runner": "pytest",
                "single_file_argv": ["python3", "-m", "pytest", "-q", "{path}"],
                "test_ids": "pytest",
            }
        ],
    }
)
_UNREAD_PROFILE = parse_profile(recorded("derived_profile", "valid"))
_DEVELOPED = "def render(entries):\n    return 'total ' + str(sum(entries))\n"
_CRITERION = "from tally.report import render\n\n\ndef test_total():\n    assert render([3, 4]).endswith('total 7')\n"
_FAILS_ON_HEAD = {
    **_reading(0, 1),
    "counts": {f"FAILED {SUITE}::test_total": 1},
}


class _Squad:
    """The dispatcher: the developer writes the report and removes ``removes``, the qa author
    writes the criterion's file."""

    def __init__(self, removes: tuple[str, ...] = ()) -> None:
        self.sent: list[Any] = []
        self.removes = removes

    async def dispatch_task(self, envelope, run_id, **_kwargs) -> TaskResult:
        self.sent.append(envelope)
        if envelope.task_type == "development.develop":
            artifacts = [{"name": NAMED, "content": _DEVELOPED, "type": "source"}]
        else:
            artifacts = [
                {"name": SUITE, "content": _CRITERION, "type": "test"},
                {"name": "test_report.md", "content": "1 passed", "type": "test_report"},
            ]
        return TaskResult(
            task_id=envelope.task_id,
            status="SUCCEEDED",
            outputs={
                "summary": "done",
                "artifacts": artifacts,
                "validation_result": {"passed": True, "checks": []},
                "test_result": {"executed": True, "exit_code": 0, "tests_passed": True},
                **(
                    {DELETIONS_KEY: list(self.removes)}
                    if envelope.task_type == "development.develop"
                    else {}
                ),
            },
        )

    async def create_task_run_if_enabled(self, _flow_run_id, _envelope):
        return None


async def _increment(
    sandbox, profile=_READ_PROFILE, *, with_repository: bool = True, tree=None, removes=()
):
    """The Tally increment composed as the live run composes it, ready to run its plan: the
    change request forwarded to the cycle, the tree seeded, the executor over a fake sandbox."""
    vault = Vault()
    request = ArtifactRef(
        artifact_id="art_cr", project_id=CONTEXT.project_id, artifact_type="change_request",
        filename="change_request.yaml", content_hash="h", size_bytes=len(STORED),
        media_type="text/yaml", created_at=NOW, cycle_id="cyc_tally_inc",
    )  # fmt: skip
    vault.stored["art_cr"] = (request, STORED.encode())
    cycle = increment_cycle()
    cycle = dataclasses.replace(
        cycle,
        execution_overrides={**cycle.execution_overrides, "plan_artifact_refs": ["art_cr"]},
    )
    implementation = run("implementation")
    recall, _store = await pinned_recall(cycle)
    registry = projects()
    registry.get_derived_profile.side_effect = None
    registry.get_derived_profile.return_value = profile
    repo = repository(tree if tree is not None else product_tree())
    seeded = await seed_checkout_artifacts(
        cycle, implementation.run_id, vault=vault, repository=repo, registry=registry
    )
    cycles = AsyncMock()
    cycles.get_run.return_value = implementation
    cycles.get_latest_checkpoint.return_value = None
    dispatcher = _Squad(removes)
    built = DispatchedFlowExecutor(
        cycle_registry=cycles, artifact_vault=vault, queue=AsyncMock(),
        squad_profile=AsyncMock(), project_registry=registry, campaign_registry=None,
        campaign_progress=None, box_verdict=None, failure_recall=recall,
        proposal_evidence=NoOpProposalEvidence(), task_timeout=5.0, event_bus=MagicMock(),
        sandbox=sandbox, source_repository=repo if with_repository else None,
    )  # fmt: skip
    # The executor's own dispatcher drives the retry loop; the squad answers each dispatch.
    built._task_dispatcher.dispatch_task = dispatcher.dispatch_task  # type: ignore[method-assign]
    built._task_dispatcher.create_task_run_if_enabled = dispatcher.create_task_run_if_enabled  # type: ignore[method-assign]
    built.__dict__["_binding_holds"] = BindingHolds(
        cycle_registry=cycles, campaign_registry=None, event_bus=MagicMock(),
        is_cancelled=AsyncMock(return_value=True), await_box=AsyncMock(), fill=None, poll_s=0,
    )  # fmt: skip
    built._cycle_event_bus = MagicMock()
    # Delivery is past this seam: the question is whether the run reaches it.
    built._deliver_source_change = AsyncMock()
    envelopes = generate_task_plan(
        cycle, implementation, squad(), plan=plan(NAMED), change_request=STORED
    )
    return built, dispatcher, cycle, implementation, vault, envelopes, seeded


async def _run_plan(built, cycle, implementation, envelopes, seeded):
    await built._execute_sequential(
        envelopes,
        implementation.run_id,
        cycle,
        seed_artifact_refs=list(seeded),
        profile=squad(),
        ledger=RunLedger(),
    )


def _record(vault: Vault) -> dict | None:
    written = [
        json.loads(content)
        for ref, content in vault.stored.values()
        if ref.artifact_type == CRITERION_HEAD_CHECK_ARTIFACT_TYPE
    ]
    assert len(written) <= 1
    return written[0] if written else None


async def test_a_criterion_passing_on_the_head_ends_the_run_before_it_delivers():
    """The spike's item 1: the criterion's file passes on the head with nothing changed."""
    sandbox = _Sandbox()
    built, dispatcher, cycle, implementation, vault, envelopes, seeded = await _increment(sandbox)

    with pytest.raises(_ExecutionError) as ended:
        await _run_plan(built, cycle, implementation, envelopes, seeded)

    assert ended.value.terminal is not None
    assert ended.value.terminal.kind is TerminalKind.CRITERIA_NOT_CHECKABLE
    assert "R1" in str(ended.value) and CONTEXT.pinned_commit[:12] in str(ended.value)
    # The plan ran through its qa task, and the run went no further: nothing was delivered or
    # judged (the implementation workload: the definition of done, development, then qa).
    assert [str(e.task_type) for e in dispatcher.sent] == [
        "governance.define_done",
        "development.develop",
        "qa.test",
    ]
    built._deliver_source_change.assert_not_awaited()
    # The tree the file ran on is the head: the product's own report, not the developer's.
    assert sandbox.seeded[NAMED] == product_tree()[NAMED]
    assert sandbox.seeded[SUITE] == _CRITERION
    assert "tally/ledger_00.py" in sandbox.seeded
    # The product's own tests are left out, by the runners in the dispatched inputs (H.19).
    assert "checks/check_area_0.py" not in sandbox.seeded
    [command] = sandbox.commands
    assert command["command"] == ("python3", "-m", "pytest", "-q", SUITE)
    assert command["reader"] == "pytest"
    # The record, in acceptance's word for the same finding.
    record = _record(vault)
    assert record is not None
    assert record["criteria"] == [
        {"criterion_id": "R1", "path": SUITE, "reading": "no_baseline_failure"}
    ]
    assert (record["head_commit"], record["increment_id"]) == (
        CONTEXT.pinned_commit,
        "prop_tally0001",
    )
    assert record["runs"][0]["passed"] is True


async def test_a_criterion_failing_on_the_head_proceeds_to_delivery_with_its_reading_recorded():
    """The ordinary increment: the head lacks the behaviour, so the run goes on to be delivered
    and judged, and the reading says what the head showed."""
    sandbox = _Sandbox(exits={SUITE: 1}, readings={SUITE: _FAILS_ON_HEAD})
    built, _dispatcher, cycle, implementation, vault, envelopes, seeded = await _increment(sandbox)

    await _run_plan(built, cycle, implementation, envelopes, seeded)

    built._deliver_source_change.assert_awaited_once()
    record = _record(vault)
    assert record is not None
    assert record["criteria"] == [{"criterion_id": "R1", "path": SUITE, "reading": "fails_on_head"}]


@pytest.mark.parametrize(
    ("sandbox", "profile", "with_repository", "logged"),
    [
        (None, _READ_PROFILE, True, "no sandbox"),
        (_Sandbox(), _READ_PROFILE, False, "no source repository"),
        (_Sandbox(), _UNREAD_PROFILE, True, "no runner holds a criterion file one by one"),
        (_Sandbox(raises=True), _READ_PROFILE, True, "its reads or the sandbox run failed"),
    ],
    ids=["no-sandbox", "no-clone", "no-test-id-reader", "sandbox-error"],
)
async def test_where_the_check_cant_run_the_run_proceeds_and_says_why(
    caplog, sandbox, profile, with_repository, logged
):
    """§24cz: never a failed or ended run for a check that couldn't run; acceptance stays the last
    line. Bug caught: a product whose runner names no reader (Tally's unittest, §24ci (a)), or a
    runtime with no sandbox, ending every increment or failing every run."""
    built, _dispatcher, cycle, implementation, vault, envelopes, seeded = await _increment(
        sandbox, profile, with_repository=with_repository
    )

    with caplog.at_level(logging.INFO, logger="squadops.execution"):
        await _run_plan(built, cycle, implementation, envelopes, seeded)

    built._deliver_source_change.assert_awaited_once()
    assert _record(vault) is None
    assert any(
        "criterion head check" in r.getMessage() and logged in r.getMessage()
        for r in caplog.records
    ), [r.getMessage() for r in caplog.records]


def _break_the_clone(built, _vault):
    built._source_repository.tree_at.side_effect = RuntimeError("the clone refused the pin")


def _lose_the_change_request(_built, vault):
    del vault.stored["art_cr"]


@pytest.mark.parametrize(
    ("breaks", "logged"),
    [
        (_break_the_clone, "is unreadable"),
        (_lose_the_change_request, "its reads or the sandbox run failed"),
    ],
    ids=["clone-refuses-the-pin", "change-request-unreadable"],
)
async def test_a_read_that_fails_skips_the_check_and_never_the_run(caplog, breaks, logged):
    """§24cz item 5. Bug caught: a read outside the sandbox call raising through ``_after_task_
    success``, so a check that couldn't run fails a run that would have delivered."""
    built, _dispatcher, cycle, implementation, vault, envelopes, seeded = await _increment(
        _Sandbox()
    )
    breaks(built, vault)

    with caplog.at_level(logging.INFO, logger="squadops.execution"):
        await _run_plan(built, cycle, implementation, envelopes, seeded)

    built._deliver_source_change.assert_awaited_once()
    assert any(
        r.getMessage().startswith("criterion head check") and logged in r.getMessage()
        for r in caplog.records
    ), [r.getMessage() for r in caplog.records]


#: A Node product as battle-trainer is: its lockfile tracked, its runner vitest. The check's run is
#: read by vitest's reader, and the file sits under the runner's root.
_NODE_TREE = {
    "package.json": b'{"name": "tally", "scripts": {"test": "vitest run"}}\n',
    "package-lock.json": b'{"lockfileVersion": 3}\n',
    "tally/report.py": b"def render(entries):\n    return ''\n",
    "scripts/run.sh": b"#!/bin/sh\n",
}
_NODE_PROFILE = parse_profile(
    {
        **recorded("derived_profile", "valid"),
        "test_runners": [
            {
                **recorded("derived_profile", "valid")["test_runners"][0],
                "runner": "vitest",
                "single_file_argv": ["npx", "vitest", "run", "{path}"],
                "test_ids": "vitest",
            }
        ],
    }
)


async def test_a_node_products_tracked_lockfile_doesnt_turn_the_check_into_a_skip():
    """#2902 (H.19) on this seam. Bug caught: the head seeded as plain revision content, which the
    sandbox refuses for a tracked ``package-lock.json`` (X-2), or built from the run's artifacts,
    which hold it back so ``npm ci`` installs nothing. Either way the check reads nothing on every
    Node product, skipping with a log line, and battle-trainer spends the cycle row 16 would."""
    sandbox = _Sandbox(readings={SUITE: {**_reading(1, 1), "reader": "vitest"}})
    built, _dispatcher, cycle, implementation, vault, envelopes, seeded = await _increment(
        sandbox, _NODE_PROFILE, tree=_NODE_TREE
    )

    with pytest.raises(_ExecutionError) as ended:
        await _run_plan(built, cycle, implementation, envelopes, seeded)

    assert ended.value.terminal is not None
    assert ended.value.terminal.kind is TerminalKind.CRITERIA_NOT_CHECKABLE
    assert sandbox.origin == RevisionOrigin.GIT_CHECKOUT
    assert sandbox.seeded["package-lock.json"] == _NODE_TREE["package-lock.json"]
    # The pin is the seed; the only thing patched on it is the criterion's file.
    assert sandbox.patched == {SUITE: _CRITERION}
    [command] = sandbox.commands
    assert (command["command"], command["reader"]) == (
        ("npx", "vitest", "run", SUITE),
        "vitest",
    )
    record = _record(vault)
    assert record is not None
    assert record["criteria"][0]["reading"] == "no_baseline_failure"


async def test_a_file_development_removed_is_still_on_the_head():
    """H.23 read the other way from the re-judged suite: that tree is the run's, this one is the
    head's, and a removal is development's work. Bug caught: ``_removed`` applied here too, so a
    criterion that a file is gone passes on "the head" and an increment that discriminates ends
    ``criteria_not_checkable``."""
    gone = "tally/ledger_00.py"
    sandbox = _Sandbox(exits={SUITE: 1}, readings={SUITE: _FAILS_ON_HEAD})
    built, dispatcher, cycle, implementation, vault, envelopes, seeded = await _increment(
        sandbox, removes=(gone,)
    )

    await _run_plan(built, cycle, implementation, envelopes, seeded)

    # The removal reached the qa task's view: the case is live, not vacuous.
    assert dispatcher.sent[-1].inputs["source_repository"]["deleted"] == [gone]
    assert sandbox.seeded[gone] == product_tree()[gone]
    assert sandbox.patched == {SUITE: _CRITERION}
    built._deliver_source_change.assert_awaited_once()

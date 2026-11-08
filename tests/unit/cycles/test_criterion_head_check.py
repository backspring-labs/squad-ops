"""#2890 (SIP-0109 §24cz): a criterion's test is run on the campaign branch's head as soon as it
exists, before the run delivers. Since #2933's D1 (§24do) a pass there is refused to the suite's
author, once, and a later pass fails the run: no run ends ``criteria_not_checkable``.

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
from squadops.cycles.correction_signature import (
    REPAIR_SUITE_PASSES_ON_HEAD_MARKER,
    repair_not_applied_in_round,
)
from squadops.cycles.deletions import DELETIONS_KEY
from squadops.cycles.failure_evidence import CRITERIA_PASS_ON_HEAD_KEY
from squadops.cycles.models import ArtifactRef
from squadops.cycles.run_ledger import RunLedger
from squadops.cycles.task_plan import generate_task_plan
from squadops.execution.binding_holds import BindingHolds
from squadops.execution.criterion_head_check import EMISSION_PASSES_ON_HEAD_MARKER
from squadops.execution.dispatched_flow_executor import (
    DispatchedFlowExecutor,
    RunState,
    _Budget,
    _ExecutionError,
)
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
    writes the criterion's file, a ``suites`` text an emission (the last one again after that),
    and its repair writes ``repaired``. The correction's lead decides ``decided``."""

    def __init__(
        self,
        removes: tuple[str, ...] = (),
        *,
        suites: tuple[str, ...] = (_CRITERION,),
        repaired: str = _CRITERION,
        decided: str = "abort",
    ) -> None:
        self.sent: list[Any] = []
        self.removes = removes
        self.suites = list(suites)
        self.repaired = repaired
        self.decided = decided

    def types(self) -> list[str]:
        return [str(e.task_type) for e in self.sent]

    def _suite(self) -> str:
        return self.suites.pop(0) if len(self.suites) > 1 else self.suites[0]

    async def dispatch_task(self, envelope, run_id, **_kwargs) -> TaskResult:
        self.sent.append(envelope)
        task_type = str(envelope.task_type)
        if task_type == "data.analyze_failure":
            outputs = {"classification": "work_product", "analysis_summary": "the suite"}
        elif task_type == "governance.correction_decision":
            outputs = {
                "correction_path": self.decided,
                "decision_rationale": "a model's call",
                # A lead's patch names what it changes; its abort names nothing.
                "affected_task_types": ["qa.test"] if self.decided == "patch" else [],
            }
        else:
            if task_type == "development.develop":
                artifacts = [{"name": NAMED, "content": _DEVELOPED, "type": "source"}]
            else:
                text = {"qa.test_repair": self.repaired, "qa.test": None}.get(task_type, _CRITERION)
                text = self._suite() if text is None else text
                artifacts = [
                    {"name": SUITE, "content": text, "type": "test"},
                    {"name": "test_report.md", "content": "1 passed", "type": "test_report"},
                ]
            outputs = {
                "summary": "done",
                "artifacts": artifacts,
                "validation_result": {"passed": True, "checks": []},
                "test_result": {"executed": True, "exit_code": 0, "tests_passed": True},
                **(
                    {DELETIONS_KEY: list(self.removes)}
                    if task_type == "development.develop"
                    else {}
                ),
            }
        return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs=outputs)

    async def create_task_run_if_enabled(self, _flow_run_id, _envelope):
        return None


async def _increment(
    sandbox,
    profile=_READ_PROFILE,
    *,
    with_repository: bool = True,
    tree=None,
    removes=(),
    squad_answers: _Squad | None = None,
    source_pinned: bool = True,
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
    dispatcher = squad_answers if squad_answers is not None else _Squad(removes)
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
    if not source_pinned:
        # A sample application's increment: no source the cycle pins.
        cycle = dataclasses.replace(cycle, source_context=None)
    return built, dispatcher, cycle, implementation, vault, envelopes, seeded


async def _run_plan(built, cycle, implementation, envelopes, seeded, ledger=None):
    await built._execute_sequential(
        envelopes,
        implementation.run_id,
        cycle,
        seed_artifact_refs=list(seeded),
        profile=squad(),
        ledger=ledger if ledger is not None else RunLedger(),
    )


def _record(vault: Vault) -> dict | None:
    written = [
        json.loads(content)
        for ref, content in vault.stored.values()
        if ref.artifact_type == CRITERION_HEAD_CHECK_ARTIFACT_TYPE
    ]
    assert len(written) <= 1
    return written[0] if written else None


async def test_a_first_emission_passing_on_the_head_is_refused_to_its_author_then_fails_the_run():
    """#2933 D1 (SIP-0109 §24do), the BT-2 and BT-9 shape: qa's first emission, as the agent
    reported it succeeded, passes on the head. Entered at ``_execute_sequential``, the live loop.

    Bugs caught: the emission accepted and the increment abandoned at row 19 as "already met"
    (§24cz's ending, which threw away BT-2's correct change); the refusal sent to a dev repair,
    which can only bend the product to a test that proves nothing; the lead's ``abort`` deciding
    the path, so the round the ruling grants is never spent; the repair not told which file passed
    on which head; and, once the allowance is spent, the run ending with a terminal kind (an
    uncounted abandonment) or a record that tells the next proposal the head meets R1."""
    sandbox = _Sandbox()
    ledger = RunLedger()
    built, squad_, cycle, implementation, vault, envelopes, seeded = await _increment(
        sandbox, squad_answers=_Squad(decided="abort")
    )

    with pytest.raises(_ExecutionError) as ended:
        await _run_plan(built, cycle, implementation, envelopes, seeded, ledger)

    # The emission went to its own author's repair, never a dev repair, never a terminal end.
    # Then the repair's rewrite passed the head too (§24dh refused it), qa's re-dispatched
    # emission did as well, and the allowance was spent: the run failed there.
    assert squad_.types() == [
        "governance.define_done",
        "development.develop",
        "qa.test",
        "data.analyze_failure",
        "governance.correction_decision",
        "qa.test_repair",
        "qa.test",  # the repair's retest
        "qa.test",  # re-dispatched after §24dh refused the repair
    ]
    repair = squad_.sent[5]
    assert repair.inputs["expected_artifacts"] == [SUITE]
    evidence = repair.inputs["failure_evidence"]
    assert evidence[CRITERIA_PASS_ON_HEAD_KEY] == {
        "head_commit": CONTEXT.pinned_commit,
        "criteria": [{"criterion_id": "R1", "path": SUITE, "tests_passed": 1}],
    }
    [told] = evidence["prior_repair_rejections"]
    assert told.startswith(f"qa.test attempt 1: {EMISSION_PASSES_ON_HEAD_MARKER} (R1 ({SUITE}: 1")
    assert CONTEXT.pinned_commit[:12] in told
    # The lead said abort; the rule patched it, and said so.
    [override] = ledger.path_overrides
    assert (override.proposed, override.path, override.reason) == (
        "abort",
        "patch",
        "criterion_passes_on_head",
    )
    # An ordinary failure: no terminal kind, so the campaign repairs it and counts it.
    assert ended.value.terminal is None
    assert "R1" in str(ended.value) and "§24do" in str(ended.value)
    built._deliver_source_change.assert_not_awaited()
    # The tree the file ran on is the head: the product's own report, not the developer's, and
    # none of the product's own tests (H.19).
    assert sandbox.seeded[NAMED] == product_tree()[NAMED]
    assert sandbox.seeded[SUITE] == _CRITERION
    assert "checks/check_area_0.py" not in sandbox.seeded
    assert sandbox.commands[0]["command"] == ("python3", "-m", "pytest", "-q", SUITE)
    # Nothing tells the next proposal the head meets R1.
    assert _record(vault) is None


class _HeadByContent(_Sandbox):
    """The head's answer by what the criterion's file says: ``failing`` texts fail there."""

    def __init__(self, failing: tuple[str, ...]) -> None:
        super().__init__()
        self.failing = failing

    async def run_declared_command(self, *, revision, command, working_dir, setup, findings_reader):
        fails = self.seeded.get(command[-1]) in self.failing
        self.exits = {SUITE: 1} if fails else {}
        self.readings = {SUITE: _FAILS_ON_HEAD} if fails else {}
        return await super().run_declared_command(
            revision=revision,
            command=command,
            working_dir=working_dir,
            setup=setup,
            findings_reader=findings_reader,
        )


#: A criterion's test that discriminates: red on the head, which reports no total.
_DISCRIMINATING = (
    "from tally.report import render\n\n\ndef test_total():\n"
    "    assert render([3, 4]) == 'total 7'\n"
)


async def test_the_refused_emissions_repair_that_fails_on_the_head_is_accepted_and_delivered():
    """The round the refusal buys, spent well: the suite's author rewrites the test so it fails
    on the head, the repair is accepted, and the run goes on to delivery with the reading recorded.
    Bug caught: a refused emission whose sound repair is still failed, or abandoned, because the
    first emission's pass was remembered as the task's reading."""
    sandbox = _HeadByContent(failing=(_DISCRIMINATING,))
    built, squad_, cycle, implementation, vault, envelopes, seeded = await _increment(
        sandbox, squad_answers=_Squad(repaired=_DISCRIMINATING, decided="patch")
    )

    await _run_plan(built, cycle, implementation, envelopes, seeded)

    assert squad_.types()[2:] == [
        "qa.test",
        "data.analyze_failure",
        "governance.correction_decision",
        "qa.test_repair",
        "qa.test",  # the repair's retest
    ]
    built._deliver_source_change.assert_awaited_once()
    record = _record(vault)
    assert record is not None
    assert record["criteria"] == [{"criterion_id": "R1", "path": SUITE, "reading": "fails_on_head"}]


async def test_after_the_refusal_a_re_dispatched_emission_that_fails_on_the_head_is_delivered():
    """The allowance is the head's to spend, not the run's: once spent, the next emission is read
    as any other is, and one that discriminates goes on. Bug caught: a spent allowance read as
    "fail every later reading", so a sound suite qa wrote on its second try fails the run."""
    sandbox = _HeadByContent(failing=(_DISCRIMINATING,))
    built, squad_, cycle, implementation, vault, envelopes, seeded = await _increment(
        sandbox, squad_answers=_Squad(suites=(_CRITERION, _DISCRIMINATING), decided="patch")
    )

    await _run_plan(built, cycle, implementation, envelopes, seeded)

    # The repair kept the passing test (§24dh refused it), and qa's re-dispatch discriminated.
    assert squad_.types()[-3:] == ["qa.test_repair", "qa.test", "qa.test"]
    built._deliver_source_change.assert_awaited_once()
    record = _record(vault)
    assert record is not None
    assert record["criteria"][0]["reading"] == "fails_on_head"


async def test_a_cycle_that_pins_no_source_is_untouched():
    """A sample application's increment: no head to read. Bug caught: the screen refusing, or
    failing, an emission with nothing to read it against."""
    sandbox = _Sandbox()
    built, _squad, cycle, implementation, vault, envelopes, _seeded = await _increment(
        sandbox, source_pinned=False
    )
    qa = next(e for e in envelopes if e.task_type == "qa.test")
    emitted = await _Squad().dispatch_task(qa, implementation.run_id)
    state = RunState(budget=_Budget(seconds=None, started=0.0))
    state.produced.stored_artifacts.extend(_stored_suite(vault, cycle, implementation))

    screened = await built._screen_on_head(emitted, qa, qa, cycle, implementation.run_id, state)
    await built._fail_if_criteria_pass_on_head(qa, qa, cycle, implementation.run_id, state)

    assert screened is emitted
    assert state.correction.refused_on_head == set()
    assert sandbox.commands == []
    assert _record(vault) is None


async def test_a_criterion_failing_on_the_head_proceeds_to_delivery_with_its_reading_recorded():
    """The ordinary increment: the head lacks the behaviour, so the run goes on to be delivered
    and judged, and the reading says what the head showed."""
    sandbox = _Sandbox(exits={SUITE: 1}, readings={SUITE: _FAILS_ON_HEAD})
    built, dispatcher, cycle, implementation, vault, envelopes, seeded = await _increment(sandbox)

    await _run_plan(built, cycle, implementation, envelopes, seeded)

    built._deliver_source_change.assert_awaited_once()
    # No correction, and the head read once: the screen's reading is the one recorded.
    assert dispatcher.types() == ["governance.define_done", "development.develop", "qa.test"]
    assert len(sandbox.commands) == 1
    record = _record(vault)
    assert record is not None
    assert record["criteria"] == [{"criterion_id": "R1", "path": SUITE, "reading": "fails_on_head"}]
    assert (record["head_commit"], record["increment_id"]) == (
        CONTEXT.pinned_commit,
        "prop_tally0001",
    )


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
    built, dispatcher, cycle, implementation, vault, envelopes, seeded = await _increment(
        sandbox, profile, with_repository=with_repository
    )

    with caplog.at_level(logging.INFO, logger="squadops.execution"):
        await _run_plan(built, cycle, implementation, envelopes, seeded)

    built._deliver_source_change.assert_awaited_once()
    # §24do: a head that can't be read refuses nothing.
    assert dispatcher.types() == ["governance.define_done", "development.develop", "qa.test"]
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
    built, dispatcher, cycle, implementation, vault, envelopes, seeded = await _increment(
        sandbox, _NODE_PROFILE, tree=_NODE_TREE
    )

    with pytest.raises(_ExecutionError) as ended:
        await _run_plan(built, cycle, implementation, envelopes, seeded)

    # The check read the head (its pass was refused, then failed the run): not a skip.
    assert ended.value.terminal is None
    assert "qa.test_repair" in dispatcher.types()
    assert sandbox.origin == RevisionOrigin.GIT_CHECKOUT
    assert sandbox.seeded["package-lock.json"] == _NODE_TREE["package-lock.json"]
    # The pin is the seed; the only thing patched on it is the criterion's file.
    assert sandbox.patched == {SUITE: _CRITERION}
    command = sandbox.commands[0]
    assert (command["command"], command["reader"]) == (
        ("npx", "vitest", "run", SUITE),
        "vitest",
    )
    assert _record(vault) is None


async def test_a_file_development_removed_is_still_on_the_head():
    """H.23 read the other way from the re-judged suite: that tree is the run's, this one is the
    head's, and a removal is development's work. Bug caught: ``_removed`` applied here too, so a
    criterion that a file is gone passes on "the head" and an increment that discriminates is
    refused (§24cz then ended it ``criteria_not_checkable``)."""
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


# --- #2933 (SIP-0109 §24dh): a repair's rewrite of a criterion's test, read on the head -----------

_REWRITTEN = "def test_total():\n    assert [] == []\n"
_MADE_IT = "accept_patch"


def _stored_suite(vault, cycle, implementation):
    """qa's own suite as the run stored it, its content in the vault."""
    criterion = ArtifactRef(
        artifact_id="art_suite", project_id=CONTEXT.project_id, artifact_type="test",
        filename=SUITE, content_hash="h", size_bytes=len(_CRITERION), media_type="text/plain",
        created_at=NOW, cycle_id=cycle.cycle_id, run_id=implementation.run_id,
        metadata={"producing_task_type": "qa.test"},
    )  # fmt: skip
    vault.stored["art_suite"] = (criterion, _CRITERION.encode())
    return [("art_suite", criterion)]


async def _repair_of_the_suite(sandbox, repair, carry):
    """A repair reaching acceptance as the router hands it over: the executor's own
    ``_try_accept_patch``, the wiring to the head and the sandbox real. What's stubbed is what comes
    before the head's reading (a verified patch, a passing retest) and the rendering after it."""
    built, _squad, cycle, implementation, vault, envelopes, _seeded = await _increment(sandbox)
    qa = next(e for e in envelopes if e.task_type == "qa.test")
    acceptance = built._patch_acceptance
    acceptance._authorize_repair_artifacts = lambda artifacts, *a, **k: artifacts
    acceptance._build_patch_subject = lambda *a, **k: MagicMock()
    acceptance._verify_patch = AsyncMock()
    acceptance._refuse_unpassed_patch = lambda *a, **k: None
    acceptance._retest_patched_suite = AsyncMock(
        return_value=MagicMock(reduction=None, failed_retest=None)
    )
    acceptance._settle_patch_evidence = lambda *a, **k: ([], [])
    acceptance._accept_patch = lambda *a, **k: _MADE_IT
    action = await built._try_accept_patch(
        qa,
        TaskResult(task_id=qa.task_id, status="FAILED", outputs={}),
        repair,
        {},
        run_id=implementation.run_id,
        cycle=cycle,
        correction_attempts=1,
        enriched_envelope=qa,
        stored_artifacts=_stored_suite(vault, cycle, implementation),
        repair_rejection_carry=carry,
    )
    return action, vault, qa


async def test_a_repair_whose_rewritten_suite_passes_on_the_head_is_refused_and_the_next_round_told():
    """BT-2: the repair's test passed on a head that hard-coded the behaviour's absence."""
    sandbox = _Sandbox()
    carry: dict[str, list[str]] = {}
    repair = [{"name": SUITE, "content": _REWRITTEN, "type": "source"}]

    action, vault, qa = await _repair_of_the_suite(sandbox, repair, carry)

    assert action == "continue"
    # The repair's text ran, on the head: the product's own report, not the developer's.
    assert sandbox.seeded[SUITE] == _REWRITTEN
    assert sandbox.seeded[NAMED] == product_tree()[NAMED]
    [entry] = carry[qa.task_id]
    assert entry.startswith(f"correction attempt 1: {REPAIR_SUITE_PASSES_ON_HEAD_MARKER}")
    assert f"R1 ({SUITE}:" in entry and CONTEXT.pinned_commit[:12] in entry
    assert repair_not_applied_in_round(carry[qa.task_id], 1)
    # No record: the next proposal is told what the record says the head meets.
    assert _record(vault) is None


async def test_a_repaired_suite_that_fails_on_the_head_is_accepted():
    """The repair that worked: green on the run's tree and red without its work."""
    sandbox = _Sandbox(exits={SUITE: 1}, readings={SUITE: _FAILS_ON_HEAD})
    carry: dict[str, list[str]] = {}
    repair = [{"name": SUITE, "content": _REWRITTEN, "type": "source"}]

    action, vault, _qa = await _repair_of_the_suite(sandbox, repair, carry)

    assert action == _MADE_IT
    assert carry == {}
    assert _record(vault) is None  # the task's own check, at its success, writes the record


async def test_a_repair_that_leaves_the_criterion_files_alone_runs_nothing_on_the_head():
    """A dev repair of a qa failure: the test is the one qa wrote, so the task's own check judges
    it: since §24do a pass there fails the run (``_fail_if_criteria_pass_on_head``)."""
    sandbox = _Sandbox()
    repair = [{"name": NAMED, "content": _DEVELOPED, "type": "source"}]

    action, _vault, _qa = await _repair_of_the_suite(sandbox, repair, {})

    assert action == _MADE_IT
    assert sandbox.commands == []


async def test_a_head_that_cant_be_read_leaves_the_repair_to_the_tasks_own_check():
    """Nothing here fails a run: a sandbox that's down is no refusal."""
    carry: dict[str, list[str]] = {}
    repair = [{"name": SUITE, "content": _REWRITTEN, "type": "source"}]

    action, _vault, _qa = await _repair_of_the_suite(_Sandbox(raises=True), repair, carry)

    assert action == _MADE_IT
    assert carry == {}


@pytest.mark.parametrize(
    ("spent", "says"),
    [
        (lambda state, qa: state.correction.refused_on_head.add(qa.task_id), "§24do"),
        (
            lambda state, qa: state.correction.rejection_carry.setdefault(qa.task_id, []).append(
                f"correction attempt 1: {REPAIR_SUITE_PASSES_ON_HEAD_MARKER} (R1)"
            ),
            "§24dh",
        ),
        (lambda state, qa: None, "a repair the head check didn't read"),
    ],
    ids=["emission-refused", "repair-refused", "accepted-through-a-repair"],
)
async def test_a_pass_on_the_head_once_stored_fails_the_run_and_never_reads_as_met(spent, says):
    """The stored emission passes on the head: after its emission or a repair of it was refused,
    or accepted through a repair the screen never sees (a dev repair of a failed qa suite). A
    failure the campaign repairs and counts, with no row 19 and no record to tell the next
    proposal the head meets it. Bug caught: any of these read as already met."""
    sandbox = _Sandbox()
    built, _squad, cycle, implementation, vault, envelopes, _seeded = await _increment(sandbox)
    qa = next(e for e in envelopes if e.task_type == "qa.test")
    state = RunState(budget=_Budget(seconds=None, started=0.0))
    state.produced.stored_artifacts.extend(_stored_suite(vault, cycle, implementation))
    spent(state, qa)

    with pytest.raises(_ExecutionError) as ended:
        await built._fail_if_criteria_pass_on_head(qa, qa, cycle, implementation.run_id, state)

    assert ended.value.terminal is None
    assert "R1" in str(ended.value) and says in str(ended.value)
    assert sandbox.seeded[SUITE] == _CRITERION
    assert _record(vault) is None


async def test_the_screen_reads_the_head_once_and_a_spent_allowance_reads_nothing_before_storage():
    """Bug caught: the head run twice for every qa success (the screen and again after the
    collection, each a product setup in the sandbox), or a spent allowance refusing again."""
    sandbox = _Sandbox(exits={SUITE: 1}, readings={SUITE: _FAILS_ON_HEAD})
    built, _squad, cycle, implementation, vault, envelopes, _seeded = await _increment(sandbox)
    qa = next(e for e in envelopes if e.task_type == "qa.test")
    emitted = await _Squad().dispatch_task(qa, implementation.run_id)
    state = RunState(budget=_Budget(seconds=None, started=0.0))

    screened = await built._screen_on_head(emitted, qa, qa, cycle, implementation.run_id, state)
    state.produced.stored_artifacts.extend(_stored_suite(vault, cycle, implementation))
    await built._fail_if_criteria_pass_on_head(qa, qa, cycle, implementation.run_id, state)

    assert screened is emitted
    assert len(sandbox.commands) == 1
    assert _record(vault)["criteria"][0]["reading"] == "fails_on_head"

    state.correction.refused_on_head.add(qa.task_id)
    passing = _Sandbox()
    built._sandbox = passing
    assert await built._screen_on_head(emitted, qa, qa, cycle, implementation.run_id, state) is (
        emitted
    )
    assert passing.commands == []

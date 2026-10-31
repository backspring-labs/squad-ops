"""Every task a repository-backed product's increment cycle dispatches binds its project
instruction on a product larger than its window (#2810, #2805's class).

A task's prompt budget is the window less what its prompt shows outside memory's sections
(SIP-0110 Appendix A §3.6). Twice the composer counted a product-sized input its handler shows only
a part of, ``qa.test``'s ``artifact_contents`` (#2805) and a repair's accepted tree (#2810), and
each stopped a live demonstration on a 1,330-token project instruction that fitted.

The guard reads every task type the cycle can dispatch from the request profile and the tables the
executor dispatches by, never from a list written here: each workload's steps and its plan's task
types, the correction steps the profile declares, every repair the repair tables route a failure
to, and the pulse-check repair chain where the profile declares pulse checks. For each it composes
the envelopes the live path composes (``tests/unit/cycles/_product_increment.py``) on an invented
product of about 98,000 tokens whose task-named files are small, and asserts:
- **a task at an authoring seam binds the instruction**, through the executor's own supply
  (``_supply_the_dispatch``, or the correction round's ``supplied_or_held``), under its
  ``BindingHolds``;
- **a task at no authoring seam takes no budget**: memory composes nothing for it, so nothing can
  hold it.

A task type the profile or the tables add later is enumerated here, and fails until its estimate
is right, or until it is named in ``_HELD_ON_A_PRODUCT`` with why its prompt shows a product-sized
input whole, which makes its hold the right one.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from adapters.noop.ports import NoOpProposalEvidence
from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.capabilities.handlers.cycle.validation import _classify_file
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles import pulse_verification
from squadops.cycles.agent_config import served_roles
from squadops.cycles.failure_evidence import FailureLocus
from squadops.cycles.implementation_plan import planner_build_task_types
from squadops.cycles.models import WorkloadType
from squadops.cycles.task_plan import (
    _BUILD_TASK_TYPES,
    _CHANGE_REQUEST_WORKLOADS,
    _increment_evaluation,
    _resolve_workload_steps,
    builder_assembles,
    correction_task_steps,
    generate_task_plan,
    repair_steps_for,
)
from squadops.execution.binding_holds import checked_or_held
from squadops.execution.blocked_paths import with_blocked_paths
from squadops.execution.dispatched_flow_executor import _carry_retake_suite
from squadops.execution.execution_errors import _CancellationError
from squadops.execution.product_proposal import with_product_proposal
from squadops.execution.proposal_evidence import with_proposal_evidence
from squadops.execution.source_checkout import seed_checkout_artifacts
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.tasks.task_types import fails_without_correction
from tests.unit.campaigns.test_product_increment_seams import STORED
from tests.unit.cycles._product_increment import (
    INSTRUCTION_ID,
    NAMED,
    PROFILE,
    SUITE,
    Dispatcher,
    Vault,
    correction_round,
    executor,
    failed,
    increment_cycle,
    module,
    pinned_recall,
    plan,
    product_tree,
    projects,
    repository,
    run,
    squad,
)

pytestmark = [pytest.mark.domain_memory]

_PROFILE = "campaign-increment-source"

#: A task type whose prompt shows a product-sized input whole, so a product larger than its window
#: rightly holds it, with what it shows whole. The guard asserts the hold for each. None today.
_HELD_ON_A_PRODUCT: dict[str, str] = {}

#: How a failed task's result reads for each failure locus, as ``classify_failure_locus`` reads it,
#: so a round routes to each repair the tables name for it. A locus added to ``FailureLocus`` with
#: no shape here fails the guard.
_FAILURES: dict[str, list[dict[str, Any]]] = {
    FailureLocus.UNKNOWN: [{"check": "acceptance:regex_match", "passed": False}],
    FailureLocus.SUBJECT: [
        {
            "check": "tests_pass", "passed": False, "executed": True, "exit_code": 1,
            "suite_broken": False,
            "failing_cases": [
                {"file": SUITE, "title": "test_total_line", "failing_line": 6,
                 "message": "assert 'total 7' == 'total 0'"},
            ],
        }
    ],
    FailureLocus.OWN_ARTIFACT: [
        {"check": "tests_pass", "passed": False, "executed": True, "exit_code": 2,
         "suite_broken": True},
    ],
}  # fmt: skip


def _loci() -> list[str]:
    return [v for k, v in vars(FailureLocus).items() if k.isupper() and isinstance(v, str)]


def _dispatched(defaults: dict[str, Any]) -> dict[str, tuple]:
    """Every task type a product increment cycle on ``defaults`` can dispatch, each with how it is
    dispatched: ``("workload", w)``, a step of workload ``w``'s plan; ``("correction",)``, a step
    of every correction round; ``("repair",)``, a repair the tables route a failure to; and
    ``("pulse",)``, the pulse-check repair chain. Read from the profile and the executor's tables."""
    cycle = dataclasses.replace(increment_cycle(), applied_defaults=dict(defaults))
    config = cycle.resolved_config()
    roster = squad()
    found: dict[str, tuple] = {}
    for entry in config["workload_sequence"]:
        workload = entry["type"]
        steps, _builder = _resolve_workload_steps(
            workload, roster, served_roles(roster), config, source_backed=True
        )
        types = [t for t, _role in steps]
        if config.get("implementation_plan") and any(t in _BUILD_TASK_TYPES for t in types):
            # A build workload's steps are the approved plan's tasks (SIP-0086): any build task
            # type the plan author may be offered on this squad.
            types += sorted(
                planner_build_task_types(
                    offer_builder=builder_assembles(roster, config, source_backed=True)
                )
            )
        change = STORED if workload in _CHANGE_REQUEST_WORKLOADS else None
        types += [t for t, _ in _increment_evaluation(run(workload), config, change, None).steps]
        for task_type in types:
            found.setdefault(str(task_type), ("workload", workload))
    failing = [t for t in found if not fails_without_correction(t)]
    for task_type, _role in correction_task_steps(config):
        found.setdefault(str(task_type), ("correction",))
    for failed_type in failing:
        for locus in (None, *_loci()):
            for task_type, _role in repair_steps_for(failed_type, locus):
                found.setdefault(str(task_type), ("repair",))
    if config.get("pulse_checks"):
        for task_type, _role in pulse_verification.REPAIR_TASK_STEPS:
            found.setdefault(str(task_type), ("pulse",))
    return found


_DISPATCHED = _dispatched(load_profile(_PROFILE).defaults)


# --- composing the cycle as the executor composes it -------------------------------------------


class _World:
    """The product seeded, the executor over it, and the snapshot recall pinning the instruction."""

    async def build(self) -> _World:
        self.tree = product_tree()
        self.cycle = increment_cycle()
        self.recall, self.store = await pinned_recall(self.cycle)
        self.vault, self.dispatcher = Vault(), Dispatcher()
        self.executor, self.registry = executor(self.vault, self.recall, self.dispatcher)
        self.composed: dict[str, list[tuple]] = {}
        self.stored: dict[str, list] = {}
        return self

    async def run_workload(self, workload: str) -> list[tuple]:
        """Workload ``workload``'s run: seeded, its plan composed as provisioning composes it and
        checked before its first dispatch, then each task enriched and supplied at its own dispatch
        as the run reaches it, each earlier task having written its named files or a document."""
        if workload in self.composed:
            return self.composed[workload]
        this = run(workload)
        start = len(self.vault.stored)
        await seed_checkout_artifacts(
            self.cycle, this.run_id, vault=self.vault, repository=repository(self.tree),
            registry=projects(),
        )  # fmt: skip
        change = STORED if workload in _CHANGE_REQUEST_WORKLOADS else None
        envelopes = generate_task_plan(
            self.cycle, this, squad(), plan=plan(NAMED), change_request=change
        )
        envelopes = await with_proposal_evidence(
            NoOpProposalEvidence(), envelopes, cycle=self.cycle
        )
        envelopes = await with_product_proposal(
            envelopes, cycle=self.cycle, read_profile=_profile, repository=repository(self.tree),
            vault=self.vault, projects=projects(),
        )  # fmt: skip
        envelopes = await with_blocked_paths(_profile, envelopes, cycle=self.cycle)
        envelopes = await checked_or_held(
            self.executor._binding_holds.supplied, envelopes, recall=self.recall,
            cycle=self.cycle, run_id=this.run_id,
        )  # fmt: skip
        prior_outputs: dict[str, Any] = {}
        composed = []
        for envelope in envelopes:
            enriched = await self.executor._enrich_envelope(
                envelope, prior_outputs, [], self.vault.refs()[start:]
            )
            await self.executor._supply_the_dispatch(envelope, enriched, self.cycle, this.run_id)
            composed.append((envelope, enriched))
            for name, content in _wrote(envelope).items():
                self.vault.produced(name, content, str(envelope.task_type), _classify_file(name)[0])
            role = str(envelope.metadata.get("role"))
            prior_outputs[role] = {
                "summary": f"[{role}] {envelope.task_type} done",
                "validation_result": {"passed": True, "checks": [], "summary": "passed"},
            }
        self.composed[workload] = composed
        self.stored[workload] = self.vault.refs()[start:]
        return composed

    async def correction_rounds(self, task_type: str) -> list[tuple[str, str | None, list]]:
        """A correction round for every failing task the cycle dispatches, at every locus whose
        route dispatches ``task_type``: each round's failed task and locus, and what it sent."""
        rounds = []
        for failed_type, origin in _DISPATCHED.items():
            if origin[0] != "workload" or fails_without_correction(failed_type):
                continue
            [(envelope, enriched)] = [
                pair for pair in await self.run_workload(origin[1])
                if pair[0].task_type == failed_type
            ][:1]  # fmt: skip
            for locus in _loci():
                routed = {t for t, _role in repair_steps_for(failed_type, locus)}
                if task_type not in routed and _DISPATCHED[task_type][0] == "repair":
                    continue
                sent_before = len(self.dispatcher.sent)
                result = failed(envelope, _wrote(envelope), _FAILURES[locus])
                await correction_round(
                    self.executor, envelope, enriched, result, self.cycle, self.stored[origin[1]]
                )
                rounds.append((failed_type, locus, self.dispatcher.sent[sent_before:]))
                if _DISPATCHED[task_type][0] == "correction":
                    break
        return rounds


async def _profile(_cycle):
    return PROFILE


def _wrote(envelope) -> dict[str, str]:
    """What a task wrote: its named files, about 2,000 tokens each, or one document."""
    named = [str(a) for a in envelope.inputs.get("expected_artifacts") or []]
    return {
        path: module("total_line", 8_000)
        for path in named or [f"{str(envelope.task_type).replace('.', '_')}.md"]
    }


def _seam(task_type: str) -> bool:
    return authoring_seam_of(task_type) is not None


@pytest.mark.parametrize(("task_type", "origin"), sorted(_DISPATCHED.items()))
async def test_every_task_a_product_increment_dispatches_binds_its_project_instruction(
    task_type, origin
):
    """Entered where each is composed and supplied live: a run's plan, enriched and supplied at its
    own dispatch; a correction round's steps, composed and supplied by the executor's round. Bug
    caught: a task type whose estimate counts a product-sized input its prompt doesn't show,
    held on an instruction that fits (#2805, #2810), or a type the cycle comes to dispatch that the
    composer was never checked for."""
    world = await _World().build()
    if origin[0] == "pulse":
        pytest.fail(
            f"{task_type}: the profile declares pulse checks, and this guard composes no pulse "
            "repair chain yet; compose it as pulse_boundary_runner does before adding them"
        )
    held = task_type in _HELD_ON_A_PRODUCT
    try:
        if origin[0] == "workload":
            sent = [
                e for _plan, e in await world.run_workload(origin[1]) if e.task_type == task_type
            ]
            label = [origin[1]]
        else:
            rounds = await world.correction_rounds(task_type)
            sent = [e for _f, _l, out in rounds for e in out if e.task_type == task_type]
            label = [(f, locus) for f, locus, _out in rounds]
    except _CancellationError:
        [call] = world.registry.record_binding_hold.await_args_list
        assert held, f"{task_type} was held on the product: {call.args[1]}"
        return
    assert not held, f"{task_type} is named as held on a product, and it bound"

    world.registry.record_binding_hold.assert_not_awaited()
    assert sent, f"{task_type}: nothing composed it ({label})"
    for envelope in sent:
        handed = envelope.inputs.get(PROJECT_INSTRUCTIONS_INPUT)
        if _seam(task_type):
            [instruction] = handed["instructions"]
            assert instruction["record_id"] == INSTRUCTION_ID, (task_type, label)
        else:
            # At no authoring seam: memory composes nothing for it, so no budget can hold it.
            assert handed is None, (task_type, label)


def test_the_guard_reads_the_issues_task_types_from_the_profile_and_the_tables():
    """Guards the enumeration against going vacuous. #2810 named these six from the live cycle, and
    the builder's two are never dispatched for a product, which builds itself (SIP-0112 E.4.3).
    Bug caught: an enumeration that silently loses a workload, the correction steps or a repair
    route, so the guard checks fewer tasks than the cycle dispatches."""
    named = {
        "development.develop": ("workload", WorkloadType.IMPLEMENTATION),
        "qa.test": ("workload", WorkloadType.IMPLEMENTATION),
        "data.analyze_failure": ("correction",),
        "governance.correction_decision": ("correction",),
        "development.correction_repair": ("repair",),
        "qa.test_repair": ("repair",),
    }

    assert {t: _DISPATCHED[t] for t in named} == named
    assert "builder.assemble" not in _DISPATCHED
    assert "builder.assemble_repair" not in _DISPATCHED
    assert "strategy.propose_increment" in _DISPATCHED
    assert "governance.merge_plan" in _DISPATCHED


@pytest.mark.parametrize(
    ("added", "dispatched"),
    [
        (
            {"workload_sequence": [{"type": "wrapup", "gate": None}]},
            {"data.gather_evidence", "governance.publish_handoff"},
        ),
        (
            {"pulse_checks": [{"suite_id": "s", "boundary_id": "b", "checks": []}]},
            {"development.repair", "strategy.corrective_plan"},
        ),
    ],
    ids=["a workload", "pulse checks"],
)
def test_a_task_type_the_profile_adds_is_enumerated(added, dispatched):
    """Bug caught: the guard's types written down rather than read, so a workload or a repair chain
    the profile adds later is dispatched unchecked, the way #2805 and #2810 each were."""
    defaults = dict(load_profile(_PROFILE).defaults)
    for key, value in added.items():
        defaults[key] = [*defaults.get(key, []), *value]

    assert dispatched <= set(_dispatched(defaults)) - set(_DISPATCHED)


async def test_a_qa_suites_retake_binds_and_its_retest_takes_no_budget():
    """The qa task's other two dispatches. The re-take after a refunded round is an edit request on
    the suite it wrote (``_carry_retake_suite``), supplied at its re-dispatch; the retest re-runs a
    repaired suite (``reexecute_repaired_suite``) and is never composed by memory. Bug caught: the
    re-take held on what its first dispatch fitted, or the retest asked for a budget it can't be
    shown."""
    world = await _World().build()
    implementation = run(WorkloadType.IMPLEMENTATION)
    [(envelope, enriched)] = [
        pair for pair in await world.run_workload(WorkloadType.IMPLEMENTATION)
        if pair[0].task_type == "qa.test"
    ]  # fmt: skip
    result = failed(envelope, _wrote(envelope), _FAILURES[FailureLocus.SUBJECT])
    for outputs_artifact in result.outputs["artifacts"]:
        outputs_artifact["type"] = "test"
    world.executor._carry_facts_to_the_next_attempt(result, envelope, enriched)
    _carry_retake_suite(result, envelope, enriched)
    enriched.inputs.pop(PROJECT_INSTRUCTIONS_INPUT)

    await world.executor._supply_the_dispatch(
        envelope, enriched, world.cycle, implementation.run_id
    )
    retest = await world.executor._correction_runner.reexecute_repaired_suite(
        implementation.run_id, world.cycle, enriched, result.outputs["artifacts"], 0,
        prior_outputs={}, all_artifact_refs=[],
        stored_artifacts=world.stored[WorkloadType.IMPLEMENTATION],
        completed_task_ids=[], plan_delta_refs=[], profile=squad(),
    )  # fmt: skip

    assert enriched.inputs["retake_current_files"] == {SUITE: _wrote(envelope)[SUITE]}
    [instruction] = enriched.inputs[PROJECT_INSTRUCTIONS_INPUT]["instructions"]
    assert instruction["record_id"] == INSTRUCTION_ID
    world.registry.record_binding_hold.assert_not_awaited()
    assert retest is not None
    [sent] = [e for e in world.dispatcher.sent if e.metadata.get("retest")]
    assert sent.inputs["retest_files"][0]["filename"] == SUITE
    assert PROJECT_INSTRUCTIONS_INPUT not in sent.inputs
    exposures = await world.store.list_exposures(implementation.run_id)
    assert sent.task_id not in {x.task_id for x in exposures}

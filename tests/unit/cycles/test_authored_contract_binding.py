"""An authored manifest binds its own run (#796).

Until this landed, authored mode was a second pipeline: the manifest was written at framing
step 4 and nothing carried it to the plan authors at steps 6–9, so every contract-gated net
was switched off for exactly the cycles that needed them. V4 roll 1 measured it — zero of
nine expected artifacts on a fill slot, four claiming scaffold-frozen files, and the gate
blind to all of it.

Bug classes guarded:

- the derivation not happening, which is the whole defect;
- it happening in **seeded** mode, which would re-derive over a pinned contract and move the
  hash the 1.4/1.5 evidence was measured against — the control must not shift;
- deriving twice in one run, which is a mid-run moving target (the #494 stale-binding class);
- a derivation failure escaping as an exception instead of leaving the gate to reject with
  the deriver's own reason;
- the contract existing but reaching nobody — bound in the loop and invisible to the gate,
  or injected into the wrong task types;
- **the gate not engaging its bind-mode nets on a run-derived contract**, which is what let
  V4's frozen claims through;
- the implementation run not inheriting it, which would scaffold and then verify nothing;
- an operator-supplied contract being overwritten by a derived one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.contract_derivation import (
    CONTRACT_ARTIFACT_TYPE,
    derive_contract_bytes,
    find_interface_manifest,
)
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.manifest_authoring import MANIFEST_ARTIFACT_TYPE
from squadops.cycles.verification_contract import VerificationContract
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_orchestration]

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "authored_v4"
_MANIFEST = (_FIXTURES / "interface_manifest.yaml").read_text(encoding="utf-8")
_PLAN = (_FIXTURES / "implementation_plan.yaml").read_text(encoding="utf-8")


def _ref(artifact_id: str, filename: str, artifact_type: str) -> Any:
    ref = MagicMock()
    ref.artifact_id = artifact_id
    ref.filename = filename
    ref.artifact_type = artifact_type
    ref.created_at = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    return ref


def _vault(contents: dict[str, tuple[Any, bytes]]) -> Any:
    vault = AsyncMock()

    async def _retrieve(artifact_id: str):
        return contents[artifact_id]

    async def _store(ref, content):
        contents[ref.artifact_id] = (ref, content)
        return ref

    vault.retrieve.side_effect = _retrieve
    vault.store.side_effect = _store
    return vault


def _cycle(**overrides: Any) -> Any:
    cycle = MagicMock()
    cycle.cycle_id = "cyc_test"
    cycle.project_id = "group_run"
    cycle.execution_overrides = dict(overrides)
    return cycle


def _executor_with_manifest() -> tuple[Any, list[tuple[str, Any]], Any]:
    manifest_ref = _ref("art_manifest", "interface_manifest.yaml", MANIFEST_ARTIFACT_TYPE)
    contents = {"art_manifest": (manifest_ref, _MANIFEST.encode())}
    executor = DispatchedFlowExecutor(artifact_vault=_vault(contents))
    executor._cycle_registry = AsyncMock()
    return executor, [("art_manifest", manifest_ref)], contents


# --------------------------------------------------------------------------- #
# Deriving at manifest acceptance
# --------------------------------------------------------------------------- #


async def test_an_authored_manifest_produces_a_contract_bound_to_its_own_hash():
    executor, stored, _ = _executor_with_manifest()

    contract, manifest = await executor._bind_authored_manifest(
        _cycle(), "run_1", stored, (None, None)
    )

    assert contract is not None
    assert contract.skeleton.interface_manifest_hash == manifest.content_hash()
    assert len(contract.fill_files) == 4
    executor._cycle_registry.append_artifact_refs.assert_awaited_once()


async def test_the_derived_contract_lands_on_the_runs_own_artifact_refs():
    """A contract only the dispatch loop knew about would bind the plan and then vanish at
    the gate, which reads the run's refs."""
    executor, stored, _ = _executor_with_manifest()

    await executor._bind_authored_manifest(_cycle(), "run_1", stored, (None, None))

    run_id, refs = executor._cycle_registry.append_artifact_refs.await_args.args
    assert run_id == "run_1"
    assert len(refs) == 1


async def test_a_seeded_cycle_derives_nothing():
    """The control must not move. Re-deriving over a pinned contract would change the hash
    every seeded comparison and replay is measured against."""
    executor, stored, _ = _executor_with_manifest()

    result = await executor._bind_authored_manifest(
        _cycle(contract_ref="art_seeded"), "run_1", stored, (None, None)
    )

    assert result == (None, None)
    executor._cycle_registry.append_artifact_refs.assert_not_awaited()


async def test_the_contract_is_derived_once_per_run():
    """A second derivation mid-run is a moving target — every check, probe and repair after
    it would measure against a different hash than the ones before (#494)."""
    executor, stored, _ = _executor_with_manifest()

    first = await executor._bind_authored_manifest(_cycle(), "run_1", stored, (None, None))
    second = await executor._bind_authored_manifest(_cycle(), "run_1", stored, first)

    assert second is first
    executor._cycle_registry.append_artifact_refs.assert_awaited_once()


async def test_no_manifest_yet_is_not_an_error():
    """Every task before the authoring stage runs through this seam."""
    executor, _, _ = _executor_with_manifest()

    assert await executor._bind_authored_manifest(_cycle(), "run_1", [], (None, None)) == (
        None,
        None,
    )


async def test_an_underivable_manifest_leaves_the_rejection_to_the_gate():
    """Raising here would kill the run; the gate rejects with the deriver's own reason,
    which M6 attributes to infrastructure rather than to the author."""
    bad = _ref("art_bad", "interface_manifest.yaml", MANIFEST_ARTIFACT_TYPE)
    executor = DispatchedFlowExecutor(
        artifact_vault=_vault({"art_bad": (bad, b"::: not yaml :::")})
    )
    executor._cycle_registry = AsyncMock()

    result = await executor._bind_authored_manifest(
        _cycle(), "run_1", [("art_bad", bad)], (None, None)
    )

    assert result == (None, None)


def test_the_latest_manifest_wins():
    """A re-rolled authoring stage stores a second manifest; the later one is the design in
    force, and binding the earlier would freeze a design the squad already replaced."""
    first = _ref("art_1", "interface_manifest.yaml", MANIFEST_ARTIFACT_TYPE)
    second = _ref("art_2", "interface_manifest.yaml", MANIFEST_ARTIFACT_TYPE)

    assert find_interface_manifest([("art_1", first), ("art_2", second)]) == "art_2"


# --------------------------------------------------------------------------- #
# The contract reaching the plan authors
# --------------------------------------------------------------------------- #


def _envelope(task_type: str) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task-1",
        agent_id="neo",
        cycle_id="cyc_test",
        pulse_id="pulse-1",
        project_id="group_run",
        task_type=task_type,
        correlation_id="corr",
        causation_id="cause",
        trace_id="trace",
        span_id="span",
        inputs={},
        metadata={"role": "dev"},
    )


async def _enriched(task_type: str, contract: Any, manifest: Any) -> dict[str, Any]:
    executor = DispatchedFlowExecutor(artifact_vault=AsyncMock())
    envelope = _envelope(task_type)
    enriched = await executor._enrich_envelope(
        envelope,
        prior_outputs={},
        all_artifact_refs=[],
        stored_artifacts=[],
        interface_manifest=manifest,
        run_derived_contract=contract,
    )
    return enriched.inputs


def _derived() -> tuple[Any, Any]:
    manifest = InterfaceManifest.from_yaml(_MANIFEST)
    return VerificationContract.from_yaml(derive_contract_bytes(_MANIFEST).decode()), manifest


async def test_the_dev_proposer_is_told_what_the_squad_just_designed():
    """The V4 defect, at the seam that caused it: the proposer had neither the criteria it
    should bind nor the frozen files it must not claim, so it invented paths."""
    contract, manifest = _derived()

    inputs = await _enriched("development.propose_plan_tasks", contract, manifest)

    assert "backend/routes.py" in inputs["contract_criteria_index"]
    assert "backend/models.py" in inputs["frozen_surface_index"]


async def test_a_run_without_a_derived_contract_is_byte_identical():
    """Seeded runs pass None here — their inputs were injected at plan generation, and a
    second injection would be the same fact arriving twice."""
    inputs = await _enriched("development.propose_plan_tasks", None, None)

    assert "contract_criteria_index" not in inputs
    assert "frozen_surface_index" not in inputs


async def test_injection_follows_the_registry_not_the_task_name():
    """Who receives what stays the context-assembly registry's declaration.

    **This test asserted the opposite until #846, and the assertion was the defect.**
    It read "the merger consumes proposer outputs and is deliberately excluded", which is
    true of the merge path and silent about the one that matters: with no
    ``plan_authoring_contributors`` configured — the default for every CRP but
    ``validation-multirole`` — the proposers never run and ``governance.merge_plan``
    authors the entire plan itself through an LLM. So the only author that reaches
    implementation was the only one never given the contract. Measured on
    ``cyc_0edb55919384``: 0 criteria_refs, 3 frozen files claimed as deliverables,
    8 invented fill-slot paths.

    A test that pins an exclusion has to be read as a claim about every path through the
    excluded task type, not just the one its author had in mind.
    """
    contract, manifest = _derived()

    inputs = await _enriched("governance.merge_plan", contract, manifest)

    assert "backend/routes.py" in inputs["contract_criteria_index"]
    assert "backend/models.py" in inputs["frozen_surface_index"]


async def test_strategy_proposer_is_still_excluded():
    """The registry's exclusions are not all wrong — this one holds.

    Strategy proposes *guidance*, never build tasks, so it binds no covered-file criteria
    and a criteria index would be context it cannot act on. Kept as the polarity guard
    #846 left behind: the fix above widened who receives the contract, and without this
    "everyone gets everything" would pass the suite.
    """
    contract, manifest = _derived()

    inputs = await _enriched("strategy.propose_plan_guidance", contract, manifest)

    assert "contract_criteria_index" not in inputs
    assert "frozen_surface_index" not in inputs


# --------------------------------------------------------------------------- #
# The gate — replaying V4 roll 1
# --------------------------------------------------------------------------- #


def _gate_executor(with_contract: bool) -> tuple[Any, Any, Any]:
    plan_ref = _ref("art_plan", "implementation_plan.yaml", "control_implementation_plan")
    manifest_ref = _ref("art_manifest", "interface_manifest.yaml", MANIFEST_ARTIFACT_TYPE)
    contents = {
        "art_plan": (plan_ref, _PLAN.encode()),
        "art_manifest": (manifest_ref, _MANIFEST.encode()),
    }
    refs = ["art_plan", "art_manifest"]
    if with_contract:
        contract_ref = _ref("art_contract", "verification_contract.yaml", CONTRACT_ARTIFACT_TYPE)
        contents["art_contract"] = (contract_ref, derive_contract_bytes(_MANIFEST))
        refs.append("art_contract")

    executor = DispatchedFlowExecutor(artifact_vault=_vault(contents))
    run = MagicMock()
    run.run_id = "run_1"
    run.artifact_refs = refs
    cycle = _cycle()
    cycle.applied_defaults = {"implementation_plan": True}
    cycle.resolved_config.return_value = {"implementation_plan": True}
    return executor, run, cycle


async def test_the_gate_rejects_v4s_plan_once_the_contract_is_derived():
    """The replay. This exact plan reached a human-review gate unchallenged; with the
    contract derived from the manifest beside it, the frozen claims and the impossible
    import are all provable before anything is built."""
    executor, run, cycle = _gate_executor(with_contract=True)

    errors = await executor._reject_invalid_plan_before_workload_gate(
        run, cycle, "progress_plan_review"
    )

    claimed_frozen = [e for e in errors if "which is frozen" in e]
    assert len(claimed_frozen) == 3, errors
    assert any("backend/models.py" in e for e in claimed_frozen)
    assert any("backend/main.py" in e for e in claimed_frozen)
    assert any("frontend/src/main.jsx" in e for e in claimed_frozen)
    # The impossible import the plan wrote against its own invented path.
    assert any("backend.routes.runs" in e for e in errors)
    # And every criterion aimed at a frozen file, which could never have executed.
    assert any("can never pass" in e for e in errors)


async def test_without_the_derived_contract_the_gate_sees_none_of_it():
    """The state V4 ran in, pinned so the regression is visible if the wiring is ever cut."""
    executor, run, cycle = _gate_executor(with_contract=False)

    errors = await executor._reject_invalid_plan_before_workload_gate(
        run, cycle, "progress_plan_review"
    )

    assert not [e for e in errors if "which is frozen" in e]
    assert not [e for e in errors if "backend.routes.runs" in e]


def test_the_v4_plan_is_the_fixture_the_bug_report_described():
    """Guards the fixture itself: if it is ever replaced with a clean plan, the two tests
    above would pass while proving nothing."""
    manifest = InterfaceManifest.from_yaml(_MANIFEST)
    plan = ImplementationPlan.from_yaml(_PLAN)
    from squadops.capabilities.scaffold import fill_slot_paths

    slots = set(fill_slot_paths(manifest))
    claimed = {a for t in plan.tasks for a in t.expected_artifacts}

    assert claimed, "the fixture plan claims no artifacts at all"
    assert not (claimed & slots), "the fixture plan is supposed to hit ZERO fill slots"


# --------------------------------------------------------------------------- #
# Forwarding to the implementation run
# --------------------------------------------------------------------------- #


async def _forwarded(cycle: Any, *promoted: Any) -> dict[str, Any]:
    vault = AsyncMock()
    vault.list_artifacts.return_value = list(promoted)
    executor = DispatchedFlowExecutor(artifact_vault=vault)
    completed = MagicMock()
    completed.run_id = "run_framing"
    completed.workload_type = "framing"
    return await executor._build_forwarding_overrides(cycle, completed)


async def test_the_implementation_run_inherits_the_derived_contract():
    """Scaffolding without the contract would build the skeleton and verify nothing."""
    overrides = await _forwarded(
        _cycle(),
        _ref("art_plan", "implementation_plan.yaml", "control_implementation_plan"),
        _ref("art_manifest", "interface_manifest.yaml", MANIFEST_ARTIFACT_TYPE),
        _ref("art_contract", "verification_contract.yaml", CONTRACT_ARTIFACT_TYPE),
    )

    assert overrides["contract_ref"] == "art_contract"
    assert overrides["plan_artifact_refs"] == ["art_plan", "art_manifest"]


async def test_an_operator_supplied_contract_is_never_overwritten():
    """Same precedence every other forwarded key has: the operator's value wins."""
    overrides = await _forwarded(
        _cycle(contract_ref="art_operator"),
        _ref("art_contract", "verification_contract.yaml", CONTRACT_ARTIFACT_TYPE),
    )

    assert overrides["contract_ref"] == "art_operator"


async def test_a_framing_run_that_derived_nothing_forwards_no_contract_ref():
    """A non-scaffolded cycle must stay exactly as it is."""
    overrides = await _forwarded(_cycle(), _ref("art_doc", "planning_artifact.md", "document"))

    assert "contract_ref" not in overrides

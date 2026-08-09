"""The gate stops only when the design asks a question (#807, M4).

Bug classes guarded:

- **a design that asks nothing still stopping the pipeline** — the defect this item exists
  for. V4 roll 2's gate was approved with a note repeating what the deterministic gates had
  already proven, while the manifest's one real question went unasked;
- the reverse, and worse: a design that *does* declare a question sailing through, which
  silently converts "the PRD does not determine this" into a guess nobody reviewed;
- the question not reaching the operator, leaving them a bare "approve?" — which is the
  rubber stamp with extra steps;
- a pass-through leaving **no record**, so a later reader cannot tell a design that asked
  nothing from a human who said yes. That reproduces the original defect from the other side;
- behavior correlated with **who wrote the manifest** — Guard 1a. Reading only the run's own
  artifacts would make seeded cycles keep a mandatory review while authored ones lost it;
- a plan-only cycle losing its gate, which this item never claimed to touch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.cycles.manifest_authoring import (
    GATE_DECIDED_BY_NO_QUESTIONS,
    MANIFEST_ARTIFACT_TYPE,
    open_questions,
)
from squadops.cycles.models import GateDecisionValue

pytestmark = [pytest.mark.domain_orchestration]

#: V4 roll 2's real manifest — the observed case this item exists for. It declares exactly
#: one unresolved decision (`expansion-gating`), so it is the fixture that must stop a gate.
#: Roll 1's manifest, beside it in the same directory, resolves everything and would make
#: these tests pass while proving nothing.
_AUTHORED = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "authored_v4"
    / "interface_manifest_roll2.yaml"
).read_text(encoding="utf-8")
_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
).read_text(encoding="utf-8")


def _resolved(manifest_yaml: str) -> str:
    """The same design with every question answered."""
    data = yaml.safe_load(manifest_yaml)
    for d in data.get("decisions", []):
        if d.pop("unresolved", False):
            d["choice"] = "resolved for the test"
            d["warrant"] = "PRD §x"
            d.pop("question", None)
    return yaml.dump(data, sort_keys=False)


def _executor(run_manifest: str | None = None, seeded_manifest: str | None = None):
    store: dict[str, tuple[Any, bytes]] = {}
    run_refs: list[str] = []
    plan_refs: list[str] = []

    def _ref(artifact_id: str) -> Any:
        ref = MagicMock()
        ref.artifact_id = artifact_id
        ref.filename = "interface_manifest.yaml"
        ref.artifact_type = MANIFEST_ARTIFACT_TYPE
        return ref

    if run_manifest is not None:
        store["art_run"] = (_ref("art_run"), run_manifest.encode())
        run_refs.append("art_run")
    if seeded_manifest is not None:
        store["art_seed"] = (_ref("art_seed"), seeded_manifest.encode())
        plan_refs.append("art_seed")

    vault = AsyncMock()

    async def _retrieve(artifact_id: str):
        return store[artifact_id]

    vault.retrieve.side_effect = _retrieve
    executor = DispatchedFlowExecutor(artifact_vault=vault)
    executor._cycle_registry = AsyncMock()
    executor._cycle_event_bus = MagicMock()

    run = MagicMock()
    run.run_id = "run_1"
    run.artifact_refs = run_refs
    cycle = MagicMock()
    cycle.execution_overrides = {"plan_artifact_refs": plan_refs} if plan_refs else {}
    return executor, run, cycle


# --------------------------------------------------------------------------- #
# The firing rule
# --------------------------------------------------------------------------- #


async def test_a_design_that_declares_a_question_stops_the_gate():
    """V4 roll 2's actual manifest. It asked whether Tier-1 expansion has a checkpoint, and
    nothing stopped to ask anyone — the case that motivated the whole item."""
    executor, run, cycle = _executor(run_manifest=_AUTHORED)

    questions = await executor._design_questions_for_gate(run, cycle)

    assert len(questions) == 1
    assert "expansion" in questions[0].lower()


def test_the_fixture_is_the_manifest_that_actually_asked_a_question():
    """Guards the fixture: roll 1's manifest resolves every decision, so pointing these tests
    at it would make them pass while proving the opposite of what they claim."""
    assert open_questions(_AUTHORED), "the roll-2 fixture must declare an open question"
    roll1 = (
        Path(__file__).resolve().parents[2] / "fixtures" / "authored_v4" / "interface_manifest.yaml"
    ).read_text(encoding="utf-8")
    assert open_questions(roll1) == (), "roll 1 resolved everything — that is the contrast"


async def test_a_design_that_asks_nothing_does_not_stop_the_gate():
    executor, run, cycle = _executor(run_manifest=_resolved(_AUTHORED))

    assert await executor._design_questions_for_gate(run, cycle) == ()


async def test_a_cycle_with_no_manifest_keeps_todays_behavior():
    """``None``, not ``()`` — the distinction is load-bearing. A plan-only cycle's gate is a
    plan review, and M4 never claimed to remove it."""
    executor, run, cycle = _executor()

    assert await executor._design_questions_for_gate(run, cycle) is None


async def test_a_seeded_manifest_is_read_from_the_cycles_own_rail():
    """Guard 1a. An operator-seeded manifest lives on ``plan_artifact_refs``, not on the
    run's outputs; reading only the run would leave seeded cycles with a mandatory review and
    authored ones without — behavior correlated with authoring mode, which is forbidden."""
    executor, run, cycle = _executor(seeded_manifest=_AUTHORED)

    questions = await executor._design_questions_for_gate(run, cycle)

    assert len(questions) == 1


async def test_the_runs_own_manifest_wins_over_a_seeded_one():
    """A cycle that authored a design is governed by the design it authored."""
    executor, run, cycle = _executor(run_manifest=_resolved(_AUTHORED), seeded_manifest=_AUTHORED)

    assert await executor._design_questions_for_gate(run, cycle) == ()


# --------------------------------------------------------------------------- #
# The pass-through is recorded
# --------------------------------------------------------------------------- #


async def test_the_pass_through_records_a_decision_a_reader_can_tell_apart():
    """The argument for question-gating is that a rubber stamp cannot be distinguished from a
    considered approval. A machine pass-through leaving no row would do exactly that, one
    level down — so it is recorded, and ``decided_by`` names it."""
    executor, _, _ = _executor()

    decision = await executor._approve_gate_without_questions(
        "run_1", "cyc_1", "progress_plan_review"
    )

    assert decision.decision == GateDecisionValue.APPROVED.value
    assert decision.decided_by == GATE_DECIDED_BY_NO_QUESTIONS
    assert decision.notes.strip()
    executor._cycle_registry.record_gate_decision.assert_awaited_once()
    recorded = executor._cycle_registry.record_gate_decision.await_args.args[1]
    assert recorded is decision, "the returned decision must be the one recorded"


# --------------------------------------------------------------------------- #
# The question reader
# --------------------------------------------------------------------------- #


def test_resolved_decisions_are_not_questions():
    """The reference manifest records four judgments, all answered. Treating a *recorded*
    decision as an open one would stop every cycle that documented its reasoning — punishing
    exactly the discipline M2 asks for."""
    assert open_questions(_REFERENCE) == ()


def test_an_unresolved_decision_with_no_question_asks_nothing():
    """Deferring without saying what was deferred is already a schema-gate finding
    (`decision_record`). Stopping the pipeline on it too would ask an operator to answer a
    question nobody stated."""
    doc = _REFERENCE + "\ndecisions:\n  - id: vague\n    unresolved: true\n"

    assert open_questions(doc) == ()


@pytest.mark.parametrize("content", [None, "", "::: not yaml :::"])
def test_unreadable_content_asks_nothing(content):
    """The gate's plan-validation net already rejects an unparseable manifest with the
    deriver's own reason. A second opinion here would stop a cycle for a defect that is
    already being reported."""
    assert open_questions(content) == ()

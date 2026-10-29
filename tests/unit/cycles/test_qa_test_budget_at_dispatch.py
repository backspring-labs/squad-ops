"""A ``qa.test`` on a product larger than its window binds its project instruction (#2805).

The executor hands ``qa.test`` the whole accepted tree as ``artifact_contents`` (its contract's
filter is ``ACCEPTANCE_WORKSPACE_FILTER``), and the handler's focused prompt shows the top-level
packages the task's expected artifacts live in. The composer counted the whole tree, so on a product
larger than about half the model's window the budget for memory's sections read 0, and a binding
project instruction (SIP-0110 Appendix A §3.6) held every ``qa.test`` before dispatch. A Campaign's
increment can't be built past that.

Entered where the live path takes the budget: the executor's ``_enrich_envelope`` resolves the tree
through the contract's filter from the vault, and ``_supply_the_dispatch`` composes the task under
its binding holds on the copy it sends, with the snapshot recall over a pinned project instruction.

What bugs would these catch?
- **The composer counting what the handler doesn't show:** a task whose prompt fits is held, and
  the run waits on an operator who can't release it (the instruction is already as small as it is).
- **The hold no longer holding:** a task whose shown package alone is larger than the window must
  still be held, with the instruction and the reason named, or its guard refuses the prompt after
  the binding was admitted.
"""

from __future__ import annotations

import dataclasses
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from adapters.noop.ports import NoOpProposalEvidence
from squadops.capabilities import lesson_supply
from squadops.capabilities.prompt_budget import (
    rendered_input_tokens,
    system_prompt_tokens,
    template_prose_tokens,
)
from squadops.capabilities.qa_prompt_contents import qa_test_prompt_contents
from squadops.cycles.models import ArtifactRef
from squadops.execution.binding_holds import BindingHolds
from squadops.execution.execution_errors import _CancellationError
from squadops.llm.model_registry import get_model_spec
from squadops.memory.lessons import UnitKind, _tokens
from squadops.memory.pinning import pin_unit
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.tasks.models import TaskEnvelope
from tests.unit.cycles.test_failure_recall import _NOW, _framing_cycle, _framing_run, _store_with
from tests.unit.memory.test_project_instructions import _instruction

pytestmark = [pytest.mark.domain_memory]

#: A 64k-window model, and the completion reserve the 2.5 demonstration's ``qa.test`` measured
#: (12,288), set by the agent's override so the arithmetic below reads as the live one did.
_MODEL = "qwen3.8-27b-tf-nvfp4"
_RESERVE = 12_288
_RUN = "run_orbit"
#: The project instruction's section as the live hold measured it: 1,330 tokens, framing included.
_INSTRUCTION_TOKENS = 1_330


def _module(name: str, tokens: int) -> str:
    """An invented module ``tokens`` long by the composer's measure (four characters a token)."""
    line = f"def {name}(moon):\n    return moon.period * 2\n"
    return (line * (tokens * 4 // len(line) + 1))[: tokens * 4]


def _tree(app_files: int) -> dict[str, str]:
    """An invented product: its app package, a frontend and its own suite, 2,000 tokens a file."""
    return {
        **{f"orbit/module_{i:02d}.py": _module(f"track_{i}", 2_000) for i in range(app_files)},
        **{f"console/src/view_{i:02d}.jsx": _module(f"render_{i}", 2_000) for i in range(15)},
        **{f"tests/test_area_{i:02d}.py": _module(f"test_area_{i}", 2_000) for i in range(12)},
    }


def _vault(tree: dict[str, str]) -> tuple[AsyncMock, list[tuple[str, ArtifactRef]]]:
    """The tree as the run stored it: each file the development task's ``source`` artifact."""
    stored = [
        (
            f"art_{i:04d}",
            ArtifactRef(
                artifact_id=f"art_{i:04d}",
                project_id="group_run",
                artifact_type="source",
                filename=name,
                content_hash=f"h{i}",
                size_bytes=len(content),
                media_type="text/x-python",
                created_at=_NOW,
                metadata={"producing_task_type": "development.develop"},
            ),
        )
        for i, (name, content) in enumerate(tree.items())
    ]
    by_id = {art_id: (ref, tree[ref.filename].encode()) for art_id, ref in stored}
    vault = AsyncMock()
    vault.retrieve.side_effect = lambda art_id: by_id[art_id]
    return vault, stored


def _qa_task(expected: str) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task-run_orbit-m001-qa.test",
        agent_id="eve",
        cycle_id="cyc_recall",
        pulse_id="pulse-1",
        project_id="group_run",
        task_type="qa.test",
        correlation_id="corr-1",
        causation_id="cause-1",
        trace_id="trace-1",
        span_id="span-1",
        inputs={
            "prd": "# Orbit\n\nOrbit tracks each moon's period around its planet.\n" * 20,
            "agent_model": _MODEL,
            "agent_config_overrides": {"max_completion_tokens": _RESERVE},
            "resolved_config": {"build_profile": "fullstack_fastapi_react"},
            "subtask_focus": "the moon period suite",
            "subtask_description": "Test that a moon's period is reported in days.",
            "expected_artifacts": [expected],
            "acceptance_criteria": ["A moon's period is reported in days."],
        },
        metadata={"role": "qa"},
    )


async def _executor_over(tree: dict[str, str]):
    """An executor whose vault holds ``tree``, its recall a snapshot pinning one 1,330-token
    project instruction for ``qa.test``, and its run registry a run with no hold. Its binding holds
    are the executor's own class, polling at once and cancelled at the first poll, so a held task
    ends its test rather than waiting on a re-supply."""
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor

    text = "Name each moon by its orbit. "
    framing = lesson_supply._framing("request.project_instructions_section")
    text = (text * _INSTRUCTION_TOKENS)[: (_INSTRUCTION_TOKENS - framing) * 4]
    records = InMemoryMemoryRecords()
    await records.create(_instruction("mrec_orbit", "qa.test", text=text))
    store = await _store_with()
    cycle = _framing_cycle()
    await pin_unit(store, unit_kind=UnitKind.CYCLE, unit_id=cycle.cycle_id, project_id="group_run",
                   pinned_at=_NOW, disabled=False, records=records)  # fmt: skip
    registry = AsyncMock()
    registry.get_run.return_value = _framing_run()
    vault, stored = _vault(tree)
    executor = DispatchedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=vault,
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=SnapshotRecall(store, records=records),
        proposal_evidence=NoOpProposalEvidence(),
        task_timeout=5.0,
        event_bus=MagicMock(),
    )
    executor.__dict__["_binding_holds"] = BindingHolds(
        cycle_registry=registry,
        campaign_registry=None,
        event_bus=MagicMock(),
        is_cancelled=AsyncMock(return_value=True),
        await_box=AsyncMock(),
        fill=None,
        poll_s=0,
    )
    return executor, stored, store, registry, cycle


def _json_tokens(value) -> int:
    return _tokens(json.dumps(value, sort_keys=True))


async def test_a_qa_test_on_a_product_larger_than_its_window_binds_its_project_instruction(
    monkeypatch,
):
    """The budget is the window less what the handler would really render, and the 1,330-token
    instruction is handed with no hold. Bug caught (#2805): the whole product tree counted as the
    prompt, so the budget read 0 and the run was held on an instruction that fits."""
    tree = _tree(app_files=26)
    executor, stored, store, registry, cycle = await _executor_over(tree)
    taken: list[int] = []
    budget = lesson_supply.prompt_budget
    monkeypatch.setattr(
        lesson_supply, "prompt_budget", lambda e: taken.append(budget(e)) or taken[-1]
    )
    envelope = _qa_task("tests/test_moon_period.py")

    enriched = await executor._enrich_envelope(envelope, {}, [], stored)
    await executor._supply_the_dispatch(envelope, enriched, cycle, _RUN)

    # The product is more than the window's worth, and as the handler's own input it is whole.
    spec = get_model_spec(_MODEL)
    room = spec.context_window - _RESERVE - system_prompt_tokens("qa.test")
    room -= template_prose_tokens("qa.test")
    assert enriched.inputs["artifact_contents"] == tree
    assert _json_tokens(tree) > spec.context_window
    # What the prompt shows is the suite's own package, and the budget is the window less that.
    shown = qa_test_prompt_contents(enriched.inputs)
    assert sorted(shown) == sorted(name for name in tree if name.startswith("tests/"))
    without_tree = dataclasses.replace(
        enriched, inputs={k: v for k, v in enriched.inputs.items() if k != "artifact_contents"}
    )
    expected = room - rendered_input_tokens(without_tree) - _json_tokens(shown)
    assert taken == [expected]
    # The whole tree would have left nothing, which is the hold the demonstration met.
    assert room - rendered_input_tokens(without_tree) - _json_tokens(tree) < 0
    # The instruction binds: handed on the envelope the agent receives, disclosed as supplied.
    [handed] = enriched.inputs[PROJECT_INSTRUCTIONS_INPUT]["instructions"]
    assert handed["record_id"] == "mrec_orbit"
    [exposure] = await store.list_exposures(_RUN)
    assert exposure.project_instructions["disposition"] == "supplied"
    assert not exposure.held
    registry.record_binding_hold.assert_not_awaited()


async def test_a_qa_test_whose_shown_package_alone_exceeds_the_window_is_still_held():
    """The control: the suite's expected file sits in the app package, which alone is larger than
    the window. The run is held on the instruction with why, as before. Bug caught: the scoping
    read as room the prompt doesn't have, so the guard refuses a prompt the composer admitted."""
    tree = _tree(app_files=34)
    executor, stored, store, registry, cycle = await _executor_over(tree)
    envelope = _qa_task("orbit/tests/test_moon_period.py")

    enriched = await executor._enrich_envelope(envelope, {}, [], stored)
    shown = qa_test_prompt_contents(enriched.inputs)
    assert sorted(shown) == sorted(name for name in tree if name.startswith("orbit/"))
    assert _json_tokens(shown) > get_model_spec(_MODEL).context_window
    with pytest.raises(_CancellationError):
        await executor._supply_the_dispatch(envelope, enriched, cycle, _RUN)

    [call] = registry.record_binding_hold.await_args_list
    hold = call.args[1]
    assert hold.task_id == envelope.task_id
    assert hold.unresolved == (
        (
            "mrec_orbit@1",
            f"the project instructions take {_INSTRUCTION_TOKENS} tokens and the prompt has 0",
            "input",
        ),
    )
    assert PROJECT_INSTRUCTIONS_INPUT not in enriched.inputs

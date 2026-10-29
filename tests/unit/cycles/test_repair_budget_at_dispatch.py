"""A correction repair on a product larger than its window binds its project instruction (#2810).

A repair carries the whole accepted tree its failed task was evaluated on
(``acceptance_workspace_files``, for its own evaluation, #1229) and the failed task's own files
(#1264). Its prompt shows the named files of them it may revise, their edit form and a qa repair's
failing-case frames (``repair_prompt_contents``). The composer counted the whole tree, so on a
repository-backed product larger than about half the model's window the budget for memory's
sections read 0, and the 2.5 main demonstration's round 2 was held on a 1,330-token project
instruction at its first repair.

Entered where the live run takes a repair's budget: the executor enriches the failed develop task
(``_enrich_envelope``), and its own correction round (``_dispatch_correction_protocol``) composes
the repair through the correction runner and repair it built, which supply it under the executor's
``BindingHolds`` (``supplied_or_held``), with the snapshot recall over a pinned project instruction.
The product is seeded as provisioning seeds it (``seed_checkout_artifacts``), and the plan is
``generate_task_plan``'s (``tests/unit/cycles/_product_increment.py``).

What bugs would these catch?
- **The composer counting what the repair doesn't show:** a repair whose prompt fits is held, and
  the run waits on an operator who can't release it.
- **The hold no longer holding:** a repair whose shown files alone are larger than the window is
  still held, with the instruction and the reason named. Admitted, its prompt would overflow the
  model's window: no prompt guard checks a repair's call (SIP-0073's guard is develop's and
  ``qa.test``'s), so the composer's hold is the only check there is.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from squadops.capabilities import lesson_supply
from squadops.capabilities.prompt_budget import (
    completion_reserve,
    rendered_input_tokens,
    system_prompt_tokens,
    template_prose_tokens,
)
from squadops.capabilities.repair_prompt_contents import (
    REPAIR_BASE_INPUTS,
    anchorable_files,
    repair_prompt_contents,
)
from squadops.cycles.task_plan import generate_task_plan
from squadops.execution.execution_errors import _CancellationError
from squadops.execution.source_checkout import seed_checkout_artifacts
from squadops.llm.model_registry import get_model_spec
from squadops.memory.lessons import _tokens
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from tests.unit.campaigns.test_product_increment_seams import STORED
from tests.unit.cycles._product_increment import (
    INSTRUCTION_ID,
    INSTRUCTION_TOKENS,
    MODEL,
    NAMED,
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

_REPAIR = "development.correction_repair"


def _json_tokens(value) -> int:
    return _tokens(json.dumps(value, sort_keys=True))


async def _repair_of_a_failed_develop(named: tuple[str, ...], named_chars: int, modules: int):
    """The develop task naming ``named`` fails its acceptance having written them, and the
    executor's correction round composes its repair. Returns what the round produced."""
    tree = product_tree(named=named, named_chars=named_chars, modules=modules)
    cycle = increment_cycle()
    recall, store = await pinned_recall(cycle)
    vault, dispatcher = Vault(), Dispatcher()
    implementation = run("implementation")
    await seed_checkout_artifacts(
        cycle, implementation.run_id, vault=vault, repository=repository(tree), registry=projects()
    )
    built, registry = executor(vault, recall, dispatcher)
    [develop] = [
        e
        for e in generate_task_plan(
            cycle, implementation, squad(), plan=plan(*named), change_request=STORED
        )
        if e.task_type == "development.develop"
    ]
    enriched = await built._enrich_envelope(develop, {}, [], vault.refs())
    wrote = {path: module("total_line", named_chars) for path in named}
    result = failed(develop, wrote, [{"check": "acceptance:regex_match", "passed": False}])
    return tree, enriched, result, built, registry, dispatcher, store, cycle


async def test_a_repair_on_a_product_larger_than_its_window_binds_its_project_instruction(
    monkeypatch,
):
    """The budget is the window less what the repair's prompt shows, and the 1,330-token
    instruction is handed to the repair with no hold. Bug caught (#2810): the whole product tree
    counted as the prompt, so the budget read 0 and the run was held on an instruction that fits."""
    taken: list[int] = []
    budget = lesson_supply.prompt_budget
    monkeypatch.setattr(
        lesson_supply, "prompt_budget", lambda e: taken.append(budget(e)) or taken[-1]
    )
    (
        tree,
        enriched,
        result,
        built,
        registry,
        dispatcher,
        store,
        cycle,
    ) = await _repair_of_a_failed_develop((NAMED,), named_chars=8_000, modules=78)

    await correction_round(built, enriched, enriched, result, cycle)

    [repair] = [e for e in dispatcher.sent if e.task_type == _REPAIR]
    workspace = repair.inputs["acceptance_workspace_files"]
    spec = get_model_spec(MODEL)
    # The product is more than the window's worth, carried whole for the repair's evaluation.
    assert _json_tokens(workspace) > spec.context_window
    assert len(workspace) == len([p for p in tree if p.endswith((".py", ".toml"))])
    # What its prompt shows is the one file the failed task wrote, and the budget is the window
    # less that and the rest of the prompt.
    assert anchorable_files(repair.inputs) == [NAMED]
    shown = repair_prompt_contents(repair.inputs)
    assert shown["current_files"].startswith(f"`{NAMED}`:\n```\ndef total_line(ledger):")
    room = spec.context_window - system_prompt_tokens(_REPAIR) - template_prose_tokens(_REPAIR)
    room -= completion_reserve(_REPAIR, model_name=MODEL, agent_model=MODEL, agent_overrides={})
    rest = dataclasses.replace(
        repair,
        inputs={
            k: v
            for k, v in repair.inputs.items()
            if k not in REPAIR_BASE_INPUTS and k != PROJECT_INSTRUCTIONS_INPUT
        },
    )
    assert taken == [room - rendered_input_tokens(rest) - _json_tokens(shown)]
    assert taken[0] > INSTRUCTION_TOKENS
    # The whole tree would have left nothing, which is the hold the demonstration met.
    assert room - rendered_input_tokens(rest) - _json_tokens(workspace) < 0
    # The instruction binds: handed on the envelope the agent receives, disclosed as supplied.
    [handed] = repair.inputs[PROJECT_INSTRUCTIONS_INPUT]["instructions"]
    assert handed["record_id"] == INSTRUCTION_ID
    [exposure] = await store.list_exposures(run("implementation").run_id)
    assert exposure.task_id == repair.task_id
    assert exposure.project_instructions["disposition"] == "supplied"
    registry.record_binding_hold.assert_not_awaited()


async def test_a_repair_whose_shown_files_alone_exceed_the_window_is_still_held():
    """The control: the failed task wrote sixteen product files, each about 4,000 tokens, which
    its repair shows whole. The run is held on the instruction with why, as before. Bug caught:
    the scoping read as room the prompt doesn't have, so a binding is admitted into a prompt that
    overflows the window, which nothing after the composer checks for a repair."""
    named = tuple(f"tally/report_{i:02d}.py" for i in range(16))
    (
        _tree,
        enriched,
        result,
        built,
        registry,
        dispatcher,
        _store,
        cycle,
    ) = await _repair_of_a_failed_develop(named, named_chars=16_000, modules=10)

    with pytest.raises(_CancellationError):
        await correction_round(built, enriched, enriched, result, cycle)

    assert not [e for e in dispatcher.sent if e.task_type == _REPAIR]
    [call] = registry.record_binding_hold.await_args_list
    hold = call.args[1]
    assert hold.task_type == _REPAIR
    assert hold.unresolved == (
        (
            f"{INSTRUCTION_ID}@1",
            f"the project instructions take {INSTRUCTION_TOKENS} tokens and the prompt has 0",
            "input",
        ),
    )

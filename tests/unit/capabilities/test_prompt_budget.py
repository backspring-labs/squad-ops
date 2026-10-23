"""The composer's prompt budget and the guard's, from one reserve (#2681).

Bug classes guarded: the composer and the guard reserving different completion budgets, so the
composer admits a binding the guard refuses (#2681's second cause: the guard adds the thinking a
toggle model's reasoning buys, and the composer didn't); an authoring seam with no declaration of
what its prompt is made of, counted as if it rendered nothing but its inputs; and a model the
registry doesn't know read as room.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from squadops.capabilities.context_assembly import (
    CONTEXT_CONTRACTS,
    authoring_seam_of,
    prompt_contract_of,
)
from squadops.capabilities.prompt_budget import (
    completion_reserve,
    prompt_budget,
    prompt_without_memory_tokens,
)
from squadops.capabilities.reasoning_policy import REASONING_OVERRIDE_KEY
from squadops.cycles.task_plan import REPAIR_TASK_TYPES
from squadops.llm.model_registry import get_model_spec
from squadops.llm.models import ReasoningLevel

_TOGGLE = "qwen3.8:27b"


@pytest.mark.parametrize(
    "level",
    [ReasoningLevel.NONE, ReasoningLevel.LOW, ReasoningLevel.MEDIUM, ReasoningLevel.HIGH, None],
)
@pytest.mark.parametrize("task_type", ["development.develop", "qa.test"])
def test_the_composer_reserves_what_the_guard_reserves_at_every_reasoning_level(level, task_type):
    """Entered at the guard's own ``_resolve_model_budget`` on a toggle model, at each level an
    agent's overrides can set and at the capability's default (``None``). Bug caught: two reserves
    computed apart, so a new level or model spec splits them again."""
    from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
    from squadops.capabilities.handlers.cycle.qa_test import QATestHandler

    handler = {"development.develop": DevelopmentDevelopHandler, "qa.test": QATestHandler}[
        task_type
    ]()
    overrides = {} if level is None else {REASONING_OVERRIDE_KEY: level}
    inputs = {"agent_model": _TOGGLE, "agent_config_overrides": overrides}
    ceiling = get_model_spec(_TOGGLE).default_max_completion  # a capability at the model's limit

    _model, guards, _window = handler._resolve_model_budget(inputs, ceiling, "unused")
    composers = completion_reserve(
        task_type, model_name=_TOGGLE, agent_model=_TOGGLE, agent_overrides=overrides
    )

    assert composers == guards


def test_a_capability_below_the_models_limit_reserves_less_than_the_composer_counts():
    """The composer passes no ceiling, so it reserves the most any capability of the model can:
    never less than the guard, so it never admits what the guard refuses."""
    low = completion_reserve(
        "development.develop",
        model_name=_TOGGLE,
        agent_model=_TOGGLE,
        agent_overrides={},
        capability_max_tokens=1000,
    )
    composers = completion_reserve(
        "development.develop", model_name=_TOGGLE, agent_model=_TOGGLE, agent_overrides={}
    )

    assert low < composers


@pytest.mark.parametrize("model", ["no-such-model:1b", "qwen2.5:14b"])
def test_the_budget_is_the_window_less_the_reserve_and_the_rendered_prompt(model):
    """Bug caught: an unregistered model read as room (it is ``-1``, which holds a binding), or the
    budget computed from the inputs' JSON alone (#2681)."""
    envelope = SimpleNamespace(
        task_type="development.develop", inputs={"agent_model": model, "prd": "x" * 4000}
    )
    spec = get_model_spec(model)
    expected = (
        -1
        if spec is None
        else spec.context_window
        - spec.default_max_completion
        - prompt_without_memory_tokens(envelope)
    )

    assert prompt_budget(envelope) == expected


def test_memory_sections_and_declared_unrendered_inputs_are_not_counted_as_the_tasks_own():
    """Bug caught: a re-dispatch charging the instructions it already carries twice, or the
    acceptance tree a build author carries for its evaluation counted as prompt."""
    from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT

    base = {"agent_model": "qwen2.5:14b", "prd": "the PRD"}
    bare = SimpleNamespace(task_type="development.develop", inputs=base)
    carrying = SimpleNamespace(
        task_type="development.develop",
        inputs={
            **base,
            TASK_INSTRUCTIONS_INPUT: {"instructions": [{"text": "x" * 8000}]},
            "acceptance_workspace_files": {"a.py": "x" * 8000},
        },
    )

    assert prompt_without_memory_tokens(carrying) == prompt_without_memory_tokens(bare)


def test_every_authoring_seam_declares_what_its_prompt_is_made_of():
    """Bug caught: a new authoring seam with no template declared, so the composer counts its
    prompt as its inputs alone and admits bindings its guard refuses (#2681)."""
    seams = {t for t in {*CONTEXT_CONTRACTS, *REPAIR_TASK_TYPES} if authoring_seam_of(t)}
    assert len(seams) >= 12

    undeclared = sorted(t for t in seams if not prompt_contract_of(t).prompt_templates)

    assert undeclared == []

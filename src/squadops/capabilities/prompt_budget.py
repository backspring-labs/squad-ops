"""A task's prompt budget, counted as its handler renders the prompt (SIP-0110 Appendix A §3.6; #2681).

The composer decides whether a task's binding sections fit, and how much lesson text is left after
them. The handler then renders the prompt, and its guard (SIP-0073, ``prompt_guard``) refuses one
over the window. The two must agree, or a task the composer admitted is refused at the guard: #2681
measured a develop task's rendered prompt 1,244 tokens past what the composer had counted, because
the composer counted the envelope's inputs as JSON and nothing else.

So the composer counts what the handler renders, each part at an upper bound:

- **the completion reserve,** from the one function the guard takes its own from
  (:func:`completion_reserve`);
- **the system prompt,** read from the shipped fragments as the agent assembles it: the largest
  identity, the global constraints, the ``agent_start`` lifecycle and the task's own fragment, with
  the seam's supplement (a development or build profile's) at its largest;
- **every template the seam's handler may render,** each counted whole, since an appendix renders
  only with its input (``ContextAssemblyContract.prompt_templates``);
- **the raw text of each input the task carries,** except memory's own sections, which the
  composer measures itself, and the inputs the seam never renders
  (``ContextAssemblyContract.unrendered_inputs``). A handler that shows part of its
  ``artifact_contents`` has that part counted, through the function it shows it through
  (``ContextAssemblyContract.artifact_contents_rendering``, #2805).

Being upper bounds, they can only hold a task the guard would have passed, never the reverse. The
parity test (``tests/unit/memory/test_prompt_budget_parity.py``) renders each seam through its own
handler and holds the estimate at or above the rendered prompt.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Callable, Iterator, Mapping
from importlib import resources
from typing import TYPE_CHECKING, Any, overload

from squadops.capabilities.context_assembly import (
    CONTENTS_QA_TEST_PROMPT,
    SUPPLEMENT_BUILD_PROFILE,
    SUPPLEMENT_DEVELOPMENT_PROFILE,
    ContextAssemblyContract,
    prompt_contract_of,
)
from squadops.capabilities.handlers.build_profiles import BUILD_PROFILES
from squadops.capabilities.qa_prompt_contents import qa_test_prompt_contents
from squadops.capabilities.reasoning_policy import resolve_reasoning_level
from squadops.llm.model_registry import get_model_spec, thinking_headroom
from squadops.memory.lessons import _tokens
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.memory.recall import LESSONS_INPUT
from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT
from squadops.stacks.development_profiles import DEVELOPMENT_PROFILES

if TYPE_CHECKING:
    from squadops.tasks.models import TaskEnvelope

#: What memory supplies a dispatch. The composer measures these sections itself, framing included,
#: so they are never the task's own input.
SUPPLIED_INPUTS = frozenset({LESSONS_INPUT, TASK_INSTRUCTIONS_INPUT, PROJECT_INSTRUCTIONS_INPUT})


@overload
def completion_reserve(
    task_type: str,
    *,
    model_name: str | None,
    agent_model: str | None,
    agent_overrides: Mapping[str, Any],
    capability_max_tokens: int,
) -> int: ...


@overload
def completion_reserve(
    task_type: str,
    *,
    model_name: str | None,
    agent_model: str | None,
    agent_overrides: Mapping[str, Any],
    capability_max_tokens: None = None,
) -> int | None: ...


def completion_reserve(
    task_type: str,
    *,
    model_name: str | None,
    agent_model: str | None,
    agent_overrides: Mapping[str, Any],
    capability_max_tokens: int | None = None,
) -> int | None:
    """The completion tokens a task's call reserves of its window: its capability's ceiling, clamped
    to its model's default completion, plus the room its reasoning level buys (#1173). An explicit
    ``max_completion_tokens`` override wins.

    The guard passes its capability's ceiling. The composer passes none, which reads as no ceiling
    below the model's own, so its reserve is the largest any capability of the task's model takes:
    equal to the guard's wherever the capability's ceiling is at least the model's default, and
    larger where it isn't. ``None`` when nothing bounds it: no ceiling, and a model the registry
    doesn't know."""
    spec = get_model_spec(model_name) if model_name else None
    if capability_max_tokens is None:
        if spec is None:
            return None
        reserve = spec.default_max_completion
    else:
        reserve = capability_max_tokens
        if spec is not None:
            reserve = min(reserve, spec.default_max_completion)
    reserve += thinking_headroom(
        resolve_reasoning_level(task_type, agent_overrides=agent_overrides, model_name=agent_model),
        spec,
    )
    if "max_completion_tokens" in agent_overrides:
        reserve = agent_overrides["max_completion_tokens"]
    return reserve


def prompt_budget(envelope: TaskEnvelope) -> int:
    """§3.6's total prompt budget for memory's sections: the model's context window, less the
    completion reserve, the system prompt, the seam's templates and the task's own rendered inputs.
    A model the registry doesn't know has ``-1``, since an unknown never means room, apart from a
    known window the rest fills (``0``), so a hold says which."""
    inputs = envelope.inputs or {}
    model = str(inputs.get("agent_model") or "")
    spec = get_model_spec(model)
    reserve = completion_reserve(
        str(envelope.task_type),
        model_name=model,
        agent_model=model or None,
        agent_overrides=inputs.get("agent_config_overrides") or {},
    )
    if spec is None or reserve is None:
        return -1
    return max(0, spec.context_window - reserve - prompt_without_memory_tokens(envelope))


def prompt_without_memory_tokens(envelope: TaskEnvelope) -> int:
    """The prompt the handler renders for ``envelope``, memory's sections aside, at its largest:
    the system prompt, the seam's templates and the task's own rendered inputs."""
    task_type = str(envelope.task_type)
    return (
        system_prompt_tokens(task_type)
        + template_prose_tokens(task_type)
        + rendered_input_tokens(envelope)
    )


def rendered_input_tokens(envelope: TaskEnvelope) -> int:
    """The task's own inputs as its prompt can carry them: each one's raw text (a structure as its
    JSON, whose quoting and escapes cover the fences and headings a file is shown in), except
    memory's sections and the inputs the seam never renders. ``artifact_contents`` is the files
    the handler shows of it, where it shows a part (#2805)."""
    return sum(
        _tokens(value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str))
        for value in _shown_inputs(
            envelope.inputs or {}, prompt_contract_of(str(envelope.task_type))
        )
    )


#: #2805: each ``artifact_contents`` rendering a contract names, as the function its handler shows
#: the files through. A name with no function here fails, never counting the input as shown whole.
_CONTENTS_RENDERINGS: dict[str, Callable[[Mapping[str, Any]], dict[str, str]]] = {
    CONTENTS_QA_TEST_PROMPT: qa_test_prompt_contents,
}


def _shown_inputs(inputs: Mapping[str, Any], contract: ContextAssemblyContract) -> Iterator[Any]:
    """What the prompt shows of each input it carries: memory's sections and the inputs the seam
    never renders left out, ``artifact_contents`` through the contract's rendering when it names
    one, and every other input as it is."""
    rendering = contract.artifact_contents_rendering
    show = _CONTENTS_RENDERINGS[rendering] if rendering else None
    for key, value in inputs.items():
        if key in SUPPLIED_INPUTS or key in contract.unrendered_inputs:
            continue
        yield show(inputs) if show is not None and key == "artifact_contents" else value


def template_prose_tokens(task_type: str) -> int:
    """Every template the seam's handler may render, each whole with its variables taken out, and
    a set of alternatives at its largest."""
    contract = prompt_contract_of(task_type)
    declared = sum(
        max(_prose(t) for t in entry) if isinstance(entry, tuple) else _prose(entry)
        for entry in contract.prompt_templates
    )
    return declared + (_fill_only_prose() if contract.fill_only_appendix else 0)


@functools.cache
def _fill_only_prose() -> int:
    """The largest fill-only appendix a development profile names: the one a handler renders is
    its stack's, never named outside the profile (``DevelopmentProfile.fill_only_template``)."""
    return max(
        (
            _prose(p.fill_only_template)
            for p in DEVELOPMENT_PROFILES.values()
            if p.fill_only_template
        ),
        default=0,
    )


def system_prompt_tokens(task_type: str) -> int:
    """The system prompt the agent assembles for ``task_type``, at its largest: the largest identity
    (a generalist's process identity is not its step's role), the global constraints, the
    ``agent_start`` lifecycle and the task's own fragment, joined as the assembler joins them, with
    the seam's supplement at its largest."""
    parts = [
        # A role's own identity wins over the shared one (the assembler's search path): one of them.
        max(
            _fragment("shared/identity/identity.md"),
            *(_fragment(f"roles/{role}/identity.md") for role in _roles()),
        ),
        _fragment("shared/constraints/constraints.global.md"),
        _fragment("shared/lifecycle/lifecycle.agent_start.md"),
        _fragment(f"shared/task_type/task_type.{task_type}.md"),
        _supplement(prompt_contract_of(task_type).system_supplement),
    ]
    return sum(parts) + 2 * len(parts)


@functools.cache
def _prose(template_id: str) -> int:
    text = (
        resources.files("squadops.prompts") / "request_templates" / f"{template_id}.md"
    ).read_text(encoding="utf-8")
    body = text.split("---", 2)[2]
    return _tokens(re.sub(r"\{\{\w+\}\}", "", body).strip())


@functools.cache
def _fragment(path: str) -> int:
    """A fragment's text, its front matter taken out; 0 for one not shipped."""
    file = resources.files("squadops.prompts") / "fragments" / path
    if not file.is_file():
        return 0
    text = file.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return _tokens(text.strip())


@functools.cache
def _roles() -> tuple[str, ...]:
    roles = resources.files("squadops.prompts") / "fragments" / "roles"
    return tuple(sorted(r.name for r in roles.iterdir() if r.is_dir()))


@functools.cache
def _supplement(kind: str) -> int:
    """The largest supplement a seam's handler adds to the system prompt: a development profile's
    (develop) or a build profile's (the builder), across every profile shipped."""
    if kind == SUPPLEMENT_DEVELOPMENT_PROFILE:
        return max(_tokens(p.system_prompt_supplement) for p in DEVELOPMENT_PROFILES.values())
    if kind == SUPPLEMENT_BUILD_PROFILE:
        return max(_tokens(p.system_prompt_for_files(None)) for p in BUILD_PROFILES.values())
    return 0

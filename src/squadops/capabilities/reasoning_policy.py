"""How much reasoning each capability wants — declared once, resolved one way (#927).

**Reason where the output is an argument. Don't where the output is a transcription.**

Filling scaffold slots is derivation: shells, contract and envelope are all in the
prompt and the answer is a fixed format. Authoring an interface manifest from
behavioural prose is genuinely an argument: endpoints, statuses and error semantics
are being chosen, not restated. #924 measured the difference on the deployed qa
fill brief — 5,727 completion tokens with the channel on, 413 with it off, the
same eight fill fences — and the loop had been treating that as a budget problem.

The table is the capability's declaration. It lives here rather than on each
handler because the fact is *about the output shape*, not about the class that
produces it, and because a table can be read whole: every capability, one level,
no switch named for a mitigation (the #925 shape). When #922 gives cycle
capabilities a contract as data, the column moves there.

**No default.** A capability absent from the table raises: an undeclared level
would silently leave the channel on, which is the condition this module exists
to end. ``tests/unit/capabilities/test_reasoning_policy.py`` asserts every handler
in the package has an entry, so the gap is a CI failure, not a cycle finding.

Resolution is the chain every other generation knob already uses (SIP-0075 §3.2,
#1011): the capability's declaration, then the agent's ``config_overrides``, then
the model spec's clamp — a model with no reasoning channel gets no level at all,
because Ollama answers ``think: true`` for such a model with a 400 and the port says a level is a
request. A cycle-level (CRP) override is not wired here; the CRP applied-defaults
carry no per-agent LLM knobs today, and adding one is a contract-pack change.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.llm.model_registry import ReasoningControl, get_model_spec
from squadops.llm.models import ReasoningLevel
from squadops.tasks.task_types import TaskType

#: Per capability: the level its output wants. Grouped by the judgment behind it.
REASONING_BY_TASK_TYPE: dict[str, str] = {
    # --- transcription: the prompt determines the output; the model restates it ---
    TaskType.BUILDER_ASSEMBLE: ReasoningLevel.NONE,
    TaskType.BUILDER_ASSEMBLE_REPAIR: ReasoningLevel.NONE,
    TaskType.GOVERNANCE_CORRECTION_DECISION: ReasoningLevel.NONE,  # a verdict from evidence
    TaskType.QA_VALIDATE: ReasoningLevel.NONE,
    TaskType.QA_ASSESS_OUTCOMES: ReasoningLevel.NONE,
    TaskType.DATA_REPORT: ReasoningLevel.NONE,
    TaskType.DATA_GATHER_EVIDENCE: ReasoningLevel.NONE,
    TaskType.DATA_ANALYZE_VERIFICATION: ReasoningLevel.NONE,
    TaskType.DATA_CLASSIFY_UNRESOLVED: ReasoningLevel.NONE,
    TaskType.DATA_COLLECT_CYCLE_SNAPSHOT: ReasoningLevel.NONE,
    TaskType.DATA_COMPOSE_CYCLE_SUMMARY: ReasoningLevel.NONE,
    TaskType.DATA_PROFILE_CYCLE_METRICS: ReasoningLevel.NONE,
    TaskType.GOVERNANCE_PUBLISH_HANDOFF: ReasoningLevel.NONE,  # a stored report
    # --- implementation and revision: derivation with real choices inside it ---
    # #1268: qa's authoring pair moved here from transcription. #924 measured the qa FILL
    # BRIEF — 5,727 completion tokens with the channel on, 413 with it off, the same eight
    # fill fences — and filling declared slots is transcription, so the measurement was
    # right about what it measured. Authoring a suite from a PRD and a workspace is not:
    # it chooses what to assert, against which surface, in what order. With the channel off
    # the model returned a sentence of intent and stopped — five of seven 1.7.1 counted
    # rolls were shaped by it, fourteen attempts, zero in 1.6.6 (plan 1.7.2 §8a, measured
    # live: think:false 1 of 6 usable emissions, think:true 6 of 6, same prompt).
    TaskType.QA_TEST: ReasoningLevel.MEDIUM,
    TaskType.QA_TEST_REPAIR: ReasoningLevel.MEDIUM,
    TaskType.DEVELOPMENT_DEVELOP: ReasoningLevel.MEDIUM,
    TaskType.DEVELOPMENT_REPAIR: ReasoningLevel.MEDIUM,
    TaskType.DEVELOPMENT_CORRECTION_REPAIR: ReasoningLevel.MEDIUM,
    TaskType.GOVERNANCE_INCORPORATE_FEEDBACK: ReasoningLevel.MEDIUM,
    TaskType.QA_VALIDATE_REFINEMENT: ReasoningLevel.MEDIUM,
    TaskType.DATA_RESEARCH_CONTEXT: ReasoningLevel.MEDIUM,
    # --- argument: the output chooses; the design, the analysis, the plan ---
    TaskType.DEVELOPMENT_AUTHOR_MANIFEST: ReasoningLevel.HIGH,
    TaskType.STRATEGY_ANALYZE_PRD: ReasoningLevel.HIGH,
    TaskType.STRATEGY_FRAME_OBJECTIVE: ReasoningLevel.HIGH,
    TaskType.DEVELOPMENT_DESIGN: ReasoningLevel.HIGH,
    TaskType.DEVELOPMENT_DESIGN_PLAN: ReasoningLevel.HIGH,
    TaskType.QA_DEFINE_TEST_STRATEGY: ReasoningLevel.HIGH,
    TaskType.GOVERNANCE_PREPARE_PLAN_AUTHORING_BRIEF: ReasoningLevel.HIGH,
    TaskType.DEVELOPMENT_PROPOSE_PLAN_TASKS: ReasoningLevel.HIGH,
    TaskType.QA_PROPOSE_PLAN_TASKS: ReasoningLevel.HIGH,
    TaskType.STRATEGY_PROPOSE_PLAN_GUIDANCE: ReasoningLevel.HIGH,
    TaskType.GOVERNANCE_MERGE_PLAN: ReasoningLevel.HIGH,
    TaskType.GOVERNANCE_REVIEW_PLAN: ReasoningLevel.HIGH,
    TaskType.GOVERNANCE_REVIEW: ReasoningLevel.HIGH,
    TaskType.GOVERNANCE_DEFINE_DONE: ReasoningLevel.HIGH,
    TaskType.DATA_ANALYZE_FAILURE: ReasoningLevel.HIGH,
    TaskType.GOVERNANCE_ROOT_CAUSE_ANALYSIS: ReasoningLevel.HIGH,
    TaskType.STRATEGY_CORRECTIVE_PLAN: ReasoningLevel.HIGH,
    TaskType.GOVERNANCE_CLOSEOUT_DECISION: ReasoningLevel.HIGH,
}

#: A capability whose OUTPUT SHAPE differs by emission mode declares one level per shape.
#: #1285: `qa.test` is two output shapes under one id. In **fill mode** the shells, the
#: contract and the envelope are all in the prompt and the answer is a fixed format —
#: transcription, and #924 measured 5,727 completion tokens with the channel on against
#: 413 with it off for the same eight fill fences. In **authoring mode** the suite is
#: written from a PRD and a workspace, choosing what to assert, against which surface, in
#: what order — an argument, and with the channel off the model returned a sentence of
#: intent and stopped (fourteen attempts across the 1.7.1 counted rolls, five of seven
#: rolls shaped by it; live: 1 usable emission of 6 with `think: false`, 6 of 6 with it on).
#:
#: #1268 moved the capability to MEDIUM for the shape that was failing, which was right and
#: is why the authoring level below is unchanged. It also made fill mode pay for a channel
#: it does not use — so #1285 declared fill mode NONE.
#:
#: #1434 (1.7.5): NONE was a category error on this module's own definition. ``NONE`` is
#: the level for a transcription — an output the prompt already contains — and a fill is
#: synthesis under a scaffold: the model reads the shells and writes bodies. The 1.7.4
#: line measured the cost of the misdeclaration on the fill shape: three of five
#: fill-mode qa rolls produced a working suite in one emission at ~3,943 tokens, and two
#: produced a sentence of intent and nothing else (2 of 24 and 7 of 35 contentless
#: emissions), each recovered through correction rounds (1.7.4 record §3, Q1). ``LOW`` is
#: the minimum honest declaration for a shaped output; on Ollama's boolean wire it maps to
#: ``think: true`` — #1268's six-in-six — and on a provider with an effort dial it asks
#: for the cheapest reasoning rather than none. #924's token saving is given up on this
#: provider and kept as a declaration another provider can honour. Ruled by the owner
#: 2026-09-09 (1.7.5 plan §8, decision 2); the line's one live hypothesis reads whether a
#: contentless fill-mode first attempt recurs under the pinned configuration.
#:
#: This is deliberately NOT a second table keyed on a mitigation (the #925 shape this
#: module's docstring warns about). It is the same declaration the table above already
#: makes — *the level is about the output* — applied to a capability that has two outputs.
#: One row per shape, read whole, beside the single-shape rows.
REASONING_BY_OUTPUT_SHAPE: dict[tuple[str, str], str] = {
    (TaskType.QA_TEST, "fill"): ReasoningLevel.LOW,
    (TaskType.QA_TEST_REPAIR, "fill"): ReasoningLevel.LOW,
}

#: The ``config_overrides`` key an agent profile uses to override the declaration.
REASONING_OVERRIDE_KEY = "reasoning"


class UndeclaredReasoningLevel(LookupError):
    """A capability generates without declaring how much reasoning it wants."""


def default_reasoning_level(task_type: str, *, output_shape: str | None = None) -> str:
    """The level ``task_type`` declares for ``output_shape``. Raises when it declares none.

    ``output_shape`` is the capability's own name for which of its outputs this generation
    produces — ``"fill"`` for `qa.test` under a verification scaffold. Absent or unknown,
    the capability's single declaration applies, so every caller that has one output shape
    stays exactly as it was (#1285).
    """
    if output_shape is not None:
        shaped = REASONING_BY_OUTPUT_SHAPE.get((task_type, output_shape))
        if shaped is not None:
            return shaped
    try:
        return REASONING_BY_TASK_TYPE[task_type]
    except KeyError:
        raise UndeclaredReasoningLevel(
            f"capability {task_type!r} declares no reasoning level; "
            "add it to REASONING_BY_TASK_TYPE (squadops.capabilities.reasoning_policy)"
        ) from None


def resolve_reasoning_level(
    task_type: str,
    *,
    agent_overrides: Mapping[str, Any],
    model_name: str | None,
    output_shape: str | None = None,
) -> str | None:
    """The level to send for one generation, or ``None`` to send nothing.

    capability declaration → ``config_overrides.reasoning`` → the model's dial.
    ``None`` when the model is unknown to the registry or declares no reasoning
    channel: nothing is sent and the wire is what it was before #927. The
    override's value is validated where profiles are (``validate_agent_entries``),
    not re-checked here.
    """
    level = agent_overrides.get(
        REASONING_OVERRIDE_KEY, default_reasoning_level(task_type, output_shape=output_shape)
    )
    spec = get_model_spec(model_name) if model_name else None
    if spec is None or spec.reasoning_control == ReasoningControl.NONE:
        return None
    return level


def reasoning_kwargs(level: str | None) -> dict[str, str]:
    """The ``chat()`` kwargs for a resolved level — ``{}`` when nothing is to be sent.

    So a call site can ``chat_kwargs.update(reasoning_kwargs(level))`` and stay a
    straight line; the develop/qa/builder handlers build their kwargs by hand
    (the duplication #929 owns) and each would otherwise grow the same branch.
    """
    return {} if level is None else {"reasoning": level}

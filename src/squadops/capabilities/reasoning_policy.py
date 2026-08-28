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
because Ollama rejects ``think`` for such a model and the port says a level is a
request. A cycle-level (CRP) override is not wired here; the CRP applied-defaults
carry no per-agent LLM knobs today, and adding one is a contract-pack change.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.llm.model_registry import ReasoningControl, get_model_spec
from squadops.llm.models import ReasoningLevel

#: Per capability: the level its output wants. Grouped by the judgment behind it.
REASONING_BY_CAPABILITY: dict[str, str] = {
    # --- transcription: the prompt determines the output; the model restates it ---
    "qa.test": ReasoningLevel.NONE,  # fills scaffold slots (#924's measured case)
    "qa.test_repair": ReasoningLevel.NONE,
    "builder.assemble": ReasoningLevel.NONE,
    "builder.assemble_repair": ReasoningLevel.NONE,
    "governance.correction_decision": ReasoningLevel.NONE,  # a verdict from evidence
    "qa.validate": ReasoningLevel.NONE,
    "qa.assess_outcomes": ReasoningLevel.NONE,
    "data.report": ReasoningLevel.NONE,
    "data.gather_evidence": ReasoningLevel.NONE,
    "data.analyze_verification": ReasoningLevel.NONE,
    "data.classify_unresolved": ReasoningLevel.NONE,
    "data.collect_cycle_snapshot": ReasoningLevel.NONE,
    "data.compose_cycle_summary": ReasoningLevel.NONE,
    "data.profile_cycle_metrics": ReasoningLevel.NONE,
    "governance.publish_handoff": ReasoningLevel.NONE,  # a stored report
    # --- implementation and revision: derivation with real choices inside it ---
    "development.develop": ReasoningLevel.MEDIUM,
    "development.repair": ReasoningLevel.MEDIUM,
    "development.correction_repair": ReasoningLevel.MEDIUM,
    "governance.incorporate_feedback": ReasoningLevel.MEDIUM,
    "qa.validate_refinement": ReasoningLevel.MEDIUM,
    "data.research_context": ReasoningLevel.MEDIUM,
    # --- argument: the output chooses; the design, the analysis, the plan ---
    "development.author_manifest": ReasoningLevel.HIGH,
    "strategy.analyze_prd": ReasoningLevel.HIGH,
    "strategy.frame_objective": ReasoningLevel.HIGH,
    "development.design": ReasoningLevel.HIGH,
    "development.design_plan": ReasoningLevel.HIGH,
    "qa.define_test_strategy": ReasoningLevel.HIGH,
    "governance.prepare_plan_authoring_brief": ReasoningLevel.HIGH,
    "development.propose_plan_tasks": ReasoningLevel.HIGH,
    "qa.propose_plan_tasks": ReasoningLevel.HIGH,
    "strategy.propose_plan_guidance": ReasoningLevel.HIGH,
    "governance.merge_plan": ReasoningLevel.HIGH,
    "governance.review_plan": ReasoningLevel.HIGH,
    "governance.review": ReasoningLevel.HIGH,
    "governance.define_done": ReasoningLevel.HIGH,
    "data.analyze_failure": ReasoningLevel.HIGH,
    "governance.root_cause_analysis": ReasoningLevel.HIGH,
    "strategy.corrective_plan": ReasoningLevel.HIGH,
    "governance.closeout_decision": ReasoningLevel.HIGH,
}

#: The ``config_overrides`` key an agent profile uses to override the declaration.
REASONING_OVERRIDE_KEY = "reasoning"


class UndeclaredReasoningLevel(LookupError):
    """A capability generates without declaring how much reasoning it wants."""


def default_reasoning_level(capability_id: str) -> str:
    """The level ``capability_id`` declares. Raises for a capability that declares none."""
    try:
        return REASONING_BY_CAPABILITY[capability_id]
    except KeyError:
        raise UndeclaredReasoningLevel(
            f"capability {capability_id!r} declares no reasoning level; "
            "add it to REASONING_BY_CAPABILITY (squadops.capabilities.reasoning_policy)"
        ) from None


def resolve_reasoning_level(
    capability_id: str,
    *,
    agent_overrides: Mapping[str, Any],
    model_name: str | None,
) -> str | None:
    """The level to send for one generation, or ``None`` to send nothing.

    capability declaration → ``config_overrides.reasoning`` → the model's dial.
    ``None`` when the model is unknown to the registry or declares no reasoning
    channel: nothing is sent and the wire is what it was before #927. The
    override's value is validated where profiles are (``validate_agent_entries``),
    not re-checked here.
    """
    level = agent_overrides.get(REASONING_OVERRIDE_KEY, default_reasoning_level(capability_id))
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

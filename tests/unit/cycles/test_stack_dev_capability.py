"""A cycle declares its stack once, not twice (#832).

`build_profile` selects the expander, fill slots, criteria pack and probe profile.
`dev_capability` selects the dev agent's prompt text, `expected_extensions`, `source_filter`
and `test_framework`. The CRP set both to the same literal on adjacent lines, bound by
convention alone — nothing in code verified they agreed.

The failure that prevents is not a crash. The skeleton expands for one stack while the dev
agent is instructed to write another's files, so every emission lands **outside the fill
slots** and the cycle surfaces as "the plan claims no slots" — a symptom several layers from
its cause, a full framing workload after the mistake.

Bug classes guarded:

- **the two declarations disagreeing silently**, which is the defect;
- **a fullstack cycle falling back to `python_cli`** because `dev_capability` was merely
  absent — the pre-#832 default at five call sites, which would hand a scaffolded fullstack
  cycle CLI prompts;
- the fix reaching into free-form cycles. `python_cli`, `python_api` and `react_app` have no
  scaffold stack, and blocking or rewriting them would break a working configuration — the
  #762 lesson that a net which false-positives is worse than the gap it closes;
- **contradiction being silently resolved** rather than rejected. Picking a side hides the
  drift instead of ending it, and the operator never learns the profile is wrong;
- a stack registered without a capability, or naming one that does not exist — the same
  registry drift the other per-stack seams are pinned against.
"""

from __future__ import annotations

import pytest

from squadops.capabilities import scaffold
from squadops.capabilities.dev_capabilities import DEV_CAPABILITIES
from squadops.capabilities.scaffold import (
    ScaffoldStack,
    dev_capability_for,
    resolve_dev_capability,
)
from squadops.cycles.preflight import stack_dev_capability_decision

pytestmark = [pytest.mark.domain_contracts]

_STACK = "fullstack_fastapi_react"


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #


def test_a_scaffoldable_build_profile_derives_the_capability():
    """The pre-#832 default at five call sites was `python_cli`. A fullstack cycle that
    simply omitted `dev_capability` would have been handed CLI prompts — an omission, not a
    contradiction, and therefore invisible to any equality check."""
    assert resolve_dev_capability({"build_profile": _STACK}) == _STACK


def test_agreement_is_accepted_unchanged():
    assert resolve_dev_capability({"build_profile": _STACK, "dev_capability": _STACK}) == _STACK


def test_contradiction_resolves_to_none_rather_than_a_winner():
    """`None` is deliberately distinct from `""`: the caller is preflight, which must reject.
    Silently preferring either side would hide the drift instead of ending it."""
    assert resolve_dev_capability({"build_profile": _STACK, "dev_capability": "react_app"}) is None


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({"dev_capability": "python_cli"}, "python_cli"),
        ({"dev_capability": "react_app"}, "react_app"),
        ({"build_profile": "not_a_registered_stack", "dev_capability": "python_cli"}, "python_cli"),
        ({}, ""),
        (None, ""),
    ],
)
def test_a_cycle_with_no_scaffoldable_stack_is_untouched(config, expected):
    """Free-form generation cycles have no expander to disagree with. A net that
    false-positives on a working configuration is worse than the gap it closes (#762)."""
    assert resolve_dev_capability(config) == expected


# --------------------------------------------------------------------------- #
# The create-time block
# --------------------------------------------------------------------------- #


def test_a_contradicting_cycle_is_rejected_at_create():
    """Deterministic downstream failure, both inputs knowable at create — this module's
    block-vs-warn rule. Warning would spend a framing workload to reach a certain failure."""
    decision = stack_dev_capability_decision(
        {"build_profile": _STACK, "dev_capability": "react_app"}
    )

    assert decision.rejected
    assert decision.blocking[0].code == "stack_dev_capability_mismatch"


def test_the_rejection_names_both_values_and_the_fix():
    """A block that says only "mismatch" sends the operator into two registries to work out
    which value is wrong."""
    message = (
        stack_dev_capability_decision({"build_profile": _STACK, "dev_capability": "react_app"})
        .blocking[0]
        .message
    )

    assert _STACK in message and "react_app" in message
    assert "omit it" in message


@pytest.mark.parametrize(
    "config",
    [
        {"build_profile": _STACK, "dev_capability": _STACK},
        {"build_profile": _STACK},
        {"dev_capability": "python_cli"},
        {},
    ],
)
def test_valid_configurations_are_not_blocked(config):
    assert not stack_dev_capability_decision(config).rejected


# --------------------------------------------------------------------------- #
# Registry binding
# --------------------------------------------------------------------------- #


def test_every_registered_stack_names_a_capability_that_exists():
    """Fifth per-stack registry, same binding as the other four: forgetting must be an error
    rather than the plausible wrong answer S1 was written to eliminate."""
    for name, stack in scaffold._STACKS.items():
        assert stack.dev_capability, f"stack {name!r} declares no dev_capability"
        assert stack.dev_capability in DEV_CAPABILITIES, (
            f"stack {name!r} names dev_capability {stack.dev_capability!r}, which is not registered"
        )


def test_a_second_stack_does_not_inherit_the_first_stacks_capability(monkeypatch):
    """The inheritance trap S1 removed from `fill_slot_paths`, checked one registry over."""
    monkeypatch.setitem(
        scaffold._STACKS,
        "node_ts",
        ScaffoldStack(name="node_ts", expand=lambda m: [], fill_slots=lambda m: ()),
    )

    assert dev_capability_for("node_ts") == ""
    assert dev_capability_for(_STACK) == _STACK
    assert resolve_dev_capability({"build_profile": "node_ts", "dev_capability": "python_cli"}) == (
        "python_cli"
    ), "an undeclaring stack must not silently claim the config's value is wrong"

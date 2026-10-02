"""A campaign's increment cycle reaches its ruling (SIP-0109 §7.3, §9.2; #1705 step b).

The ``campaign-increment`` profile: proposal → ``progress_increment_ruling`` → framing →
``progress_plan_review`` → implementation. A campaign's increments launch from its policy's
proposal profile, so a profile that cannot reach the ruling is refused when the campaign is made.
"""

from __future__ import annotations

import copy

import pytest

from squadops.campaigns.gate import INCREMENT_RULING_GATE, increment_sequence_refusal
from squadops.contracts.cycle_request_profiles import load_profile

INCREMENT = load_profile("campaign-increment").defaults


def _with(**changes) -> dict:
    defaults = copy.deepcopy(INCREMENT)
    for key, value in changes.items():
        defaults[key] = value
    return defaults


def test_the_increment_profile_reaches_the_ruling_and_builds_on_its_approval():
    """Bug caught: the shipped profile drifting off the shape the campaign launches — a ruling
    gate the sequence never reaches, or an approval with nothing after it to build the change."""
    assert increment_sequence_refusal(INCREMENT) is None
    assert [(w["type"], w["gate"]) for w in INCREMENT["workload_sequence"]] == [
        ("proposal", INCREMENT_RULING_GATE),
        ("framing", "progress_plan_review"),
        ("implementation", None),
    ]


_RULING = {"name": INCREMENT_RULING_GATE, "description": "the ruling", "after_task_types": []}


@pytest.mark.parametrize(
    ("defaults", "refusal"),
    [
        # The proposal workload alone: its run ends with no ruling, and every increment escalates.
        (load_profile("campaign-proposal").defaults, "must open with the proposal workload"),
        # The ruling on the last workload: the sequence ends before that workload's gate.
        (
            _with(workload_sequence=[{"type": "proposal", "gate": INCREMENT_RULING_GATE}]),
            "a workload must follow",
        ),
        # Undeclared: the registry refuses a decision on a gate the policy does not name.
        (
            _with(task_flow_policy={"mode": "sequential", "gates": []}),
            "must declare the progress_increment_ruling gate",
        ),
        # A task boundary: the run pauses mid-flight on a proposal the campaign never received.
        (
            _with(
                task_flow_policy={
                    "mode": "sequential",
                    "gates": [{**_RULING, "after_task_types": ["strategy.propose_increment"]}],
                }
            ),
            "takes no after_task_types",
        ),
    ],
    ids=["proposal-alone", "ruling-on-the-last-workload", "undeclared", "task-boundary"],
)
def test_a_profile_that_cannot_reach_the_ruling_is_refused(defaults, refusal):
    assert refusal in (increment_sequence_refusal(defaults) or "")

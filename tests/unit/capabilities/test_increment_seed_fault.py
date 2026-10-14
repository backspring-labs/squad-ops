"""The increment-seed fault (#2279): the plan-review tier's timeout half, made reachable live.

Its wiring, from a declaring cycle's approval to the plan gate that stops for the question, is
in ``tests/unit/cycles/test_increment_gate_wiring.py``. These hold the fault's own contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadops.capabilities.handlers.fault_injection import (
    INCREMENT_SEED_SEAM,
    INJECTED_QUESTION,
    INJECTED_QUESTION_ID,
    UnknownFault,
    inject,
    seed,
    validate_declaration,
)
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.manifest_authoring import open_decisions
from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_capabilities]

_DECLARED = {"fault_injection": ["increment_design_asks"]}
_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "campaigns"
    / "manifest-cyc_39df987d4ba3-candidate.yaml"
).read_text()


def test_a_declaration_on_the_runtime_seam_is_accepted_and_an_unknown_one_is_not():
    """Bug caught: the seam missing from validation, so every diagnostic campaign's increments
    are refused at creation; or validation loosened to let any name through."""
    assert validate_declaration(_DECLARED) == ("increment_design_asks",)
    with pytest.raises(UnknownFault):
        validate_declaration({"fault_injection": ["increment_design_asks_twice"]})


@pytest.mark.parametrize(
    "task", [TaskType.DEVELOPMENT_DEVELOP, TaskType.QA_TEST, INCREMENT_SEED_SEAM]
)
def test_no_agent_emission_takes_a_seed_fault(task):
    """The fault is the runtime's, applied once where the manifest is built. Bug caught: an
    agent whose task id happened to end with the seam's name rewriting its own emission."""
    emission = "```yaml:interface_manifest.yaml\nversion: 1\n```"
    out = inject(
        emission, handler_name="h", task_id=f"task-run_x-m001-{task}", resolved_config=_DECLARED
    )
    assert out == emission


def test_seeding_asks_one_question_however_often_it_runs():
    """A bound retry or repair reuses the approved seed; a re-seed must not ask twice, or the
    escalation would name the same question twice and the late answer resolve only one."""
    once = seed(_MANIFEST, _DECLARED)
    twice = seed(once, _DECLARED)
    assert open_decisions(twice) == ((INJECTED_QUESTION_ID, INJECTED_QUESTION),)
    assert seed(_MANIFEST, {}) == _MANIFEST


def test_the_diagnostic_profile_is_campaign_increment_with_the_fault_and_nothing_else():
    """Bug caught: `campaign-increment` changing and its diagnostic copy not, so the timeout
    half is read on a cycle that differs from a real increment in more than the question."""
    plain = dict(load_profile("campaign-increment").defaults)
    asks = dict(load_profile("campaign-increment-asks").defaults)
    assert asks.pop("fault_injection") == ["increment_design_asks"]
    assert asks == plain
    assert yaml.safe_load(seed(_MANIFEST, asks)) == yaml.safe_load(_MANIFEST)  # no declaration left

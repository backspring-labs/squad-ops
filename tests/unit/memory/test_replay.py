"""The authoring replay's core (SIP-0110 §0.11–§0.12; slice 2, #2106): §0.15's replay fidelity,
temporal validity, claim kinds and experiment isolation rows, at the pure half.

What bugs would these catch? A lesson admitted by its unit's start rather than its evidence's time,
so it "teaches" a target from a failure that happened after the target authored; a lesson from the
target's own failure reported as transfer; a memory arm differing from the baseline by more than
the intervention, so a difference in outcome is not the lesson's; arms always run in one order.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.memory.recall import LESSONS_INPUT
from squadops.memory.replay import (
    Arm,
    CitedEvidence,
    ClaimKind,
    ReplayLesson,
    arm_inputs,
    manifest,
    schedule,
    temporal_validity,
    validity,
)

pytestmark = [pytest.mark.domain_memory]

CUTOFF = datetime(2026, 10, 8, 3, 0, tzinfo=UTC)


def _lesson(*cited: CitedEvidence) -> ReplayLesson:
    return ReplayLesson("pat_a@1", "Name the manifest element the criterion checks.", cited)


@pytest.mark.parametrize(
    ("cited", "valid", "claim"),
    [
        (
            (CitedEvidence("o1", CUTOFF - timedelta(hours=1), "cyc_other"),),
            True,
            ClaimKind.COUNTERFACTUAL,
        ),
        ((CitedEvidence("o1", CUTOFF, "cyc_other"),), False, None),
        (
            (CitedEvidence("o1", CUTOFF - timedelta(hours=1), "cyc_target"),),
            True,
            ClaimKind.ASSISTED_REPAIR,
        ),
        ((), False, None),
        # Two units at once: the source unit was admitted before the target (its first observation
        # predates the cutoff), and failed again after the target authored. Its later evidence is
        # excluded, whatever its admission time.
        (
            (
                CitedEvidence("o1", CUTOFF - timedelta(hours=2), "cyc_earlier"),
                CitedEvidence("o2", CUTOFF + timedelta(minutes=10), "cyc_earlier"),
            ),
            False,
            None,
        ),
    ],
)
def test_a_lesson_is_eligible_by_its_evidences_time_and_says_what_it_may_claim(cited, valid, claim):
    verdict = temporal_validity(_lesson(*cited), cutoff=CUTOFF, target_cycle_id="cyc_target")

    assert (verdict.valid, verdict.claim) == (valid, claim)


def test_the_arms_differ_only_by_the_intervention():
    """§0.15 replay fidelity. Bug caught: the baseline arm carrying a lesson an envelope was supplied
    live, so the comparison is memory against memory."""
    own = {"prd": "p", LESSONS_INPUT: {"snapshot": "snp_live", "lessons": [{"text": "live"}]}}

    baseline = arm_inputs(own, Arm.BASELINE, experiment_id="x")
    scoped = arm_inputs(own, Arm.SCOPED_MEMORY, experiment_id="x", lessons=[_lesson()])
    static = arm_inputs(own, Arm.STATIC_GUIDANCE, experiment_id="x", static_guidance="Check it.")

    assert baseline == {"prd": "p"}
    assert {k: v for k, v in scoped.items() if k != LESSONS_INPUT} == baseline
    assert scoped[LESSONS_INPUT]["lessons"] == [{"revision_id": "pat_a@1", "text": _lesson().text}]
    assert static[LESSONS_INPUT]["lessons"] == [{"revision_id": "static", "text": "Check it."}]
    with pytest.raises(ValueError, match="no guidance"):
        arm_inputs(own, Arm.STATIC_GUIDANCE, experiment_id="x")


SECTION = "\n\n## LESSONS FROM THIS PROJECT'S EARLIER CYCLES\n\n1. Name it.\n"


@pytest.mark.parametrize(
    ("memory", "expected"),
    [
        (
            [
                "sys",
                "Task.\n\n## LESSONS FROM THIS PROJECT'S EARLIER CYCLES\n\n1. Name it.\n\n### Out",
            ],
            True,
        ),
        (
            [
                "sys",
                "Task, edited.\n\n## LESSONS FROM THIS PROJECT'S EARLIER CYCLES\n\n1. Name it.\n\n### Out",
            ],
            False,
        ),
        (["sys", "Task.\n\n### Out"], False),  # the lessons never reached the prompt
    ],
)
def test_the_memory_arm_must_differ_from_the_baseline_by_its_section_alone(memory, expected):
    baseline = ["sys", "Task.\n\n### Out"]

    verdict = validity(baseline, baseline, baseline, memory, SECTION)

    assert verdict.baseline_exact is True
    assert verdict.memory_differs_only_by_its_section is expected
    assert verdict.valid is expected


def test_a_case_whose_reproduction_differs_is_never_valid():
    verdict = validity(["sys", "captured"], ["sys", "re-rendered"], ["sys", "re-rendered"])

    assert (verdict.baseline_exact, verdict.valid) == (False, False)


def test_the_schedule_pairs_every_case_with_every_arm_in_a_seeded_order():
    """§0.12: arm order randomized or balanced, inputs paired. Bug caught: the baseline always run
    first, so a drift in the model server reads as an arm effect."""
    arms = [Arm.BASELINE, Arm.SCOPED_MEMORY, Arm.STATIC_GUIDANCE]
    order = schedule(["c1", "c2", "c3", "c4"], arms, generations=3, seed=7)

    groups = [order[i : i + 3] for i in range(0, len(order), 3)]
    assert len(order) == 4 * 3 * 3
    assert all(
        {a for _, a, _ in g} == set(arms) and len({(c, n) for c, _, n in g}) == 1 for g in groups
    )
    assert len({g[0][1] for g in groups}) > 1
    assert schedule(["c1", "c2", "c3", "c4"], arms, generations=3, seed=7) == order


def test_an_experiments_identity_moves_with_its_inputs_and_not_with_its_clock():
    """§0.12 experiment manifest. Bug caught: a lesson's text edited between scored runs under the
    same experiment name, or every rerun reading as a new experiment."""
    envelope = {
        "envelope_id": "env_1",
        "task_type": "strategy.propose_increment",
        "seam": "proposal_writing",
        "messages_sha256": "abc",
        "captured_at": CUTOFF.isoformat(),
        "chat_kwargs": {"model": "qwen3.8:27b", "temperature": 0.2},
    }

    def build(text: str, at: datetime):
        return manifest(
            experiment_id="e",
            created_at=at,
            envelopes=[envelope],
            arms=[Arm.BASELINE, Arm.SCOPED_MEMORY],
            generations=3,
            seed=7,
            lessons=[ReplayLesson("pat_a@1", text, ())],
            static_guidance="",
            rubric="r@1",
            framework_git_sha="99d4a11e",
        )

    first = build("Name it.", CUTOFF)

    assert first.digest() == build("Name it.", CUTOFF + timedelta(days=1)).digest()
    assert first.digest() != build("Name it, edited.", CUTOFF).digest()
    assert first.to_dict()["model_settings"] == [{"model": "qwen3.8:27b", "temperature": 0.2}]

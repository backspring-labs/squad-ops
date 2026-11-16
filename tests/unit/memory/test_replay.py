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
    swapped_inputs,
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
            rubric_text=None,
            framework_git_sha="99d4a11e",
        )

    first = build("Name it.", CUTOFF)

    assert first.digest() == build("Name it.", CUTOFF + timedelta(days=1)).digest()
    assert first.digest() != build("Name it, edited.", CUTOFF).digest()
    assert first.to_dict()["model_settings"] == [{"model": "qwen3.8:27b", "temperature": 0.2}]


_SKILL = {"skillset": "fixture-dev", "skill": "gameplay", "digest": "d", "files": {"SKILL.md": "x"}}


def test_the_skills_arm_adds_its_equipment_and_nothing_else():
    """SIP-0116 §17p. Bug caught: the skills arm changing an input beside its equipment, so a
    difference in outcome isn't the skill's; or the equipment sharing state with the case's
    inputs, so one generation's handler changes what the next is handed."""
    own = {"prd": "p", "product_proposal": {"head": {"commit": "c"}}}
    vocabulary = {"reader": "fixture/1"}
    equipment = [(("skills",), [_SKILL]), (("product_proposal", "scenario_vocabulary"), vocabulary)]

    skills = arm_inputs(own, Arm.SKILLS, experiment_id="x", equipment=equipment)

    assert skills == {
        "prd": "p",
        "skills": [_SKILL],
        "product_proposal": {"head": {"commit": "c"}, "scenario_vocabulary": vocabulary},
    }
    assert own == {"prd": "p", "product_proposal": {"head": {"commit": "c"}}}
    skills["skills"][0]["files"]["SKILL.md"] = "changed"
    assert _SKILL["files"]["SKILL.md"] == "x"
    assert arm_inputs(own, Arm.BASELINE, experiment_id="x", equipment=equipment) == own


@pytest.mark.parametrize(
    ("own", "equipment", "says"),
    [
        ({"prd": "p"}, [], "no equipment to hand"),
        ({"prd": "p", "skills": [_SKILL]}, [(("skills",), [_SKILL])], "already hold skills"),
        (
            {"prd": "p"},
            [(("product_proposal", "scenario_vocabulary"), {})],
            "hold no product_proposal",
        ),
    ],
    ids=["none", "captured-with-it", "nowhere-to-put-it"],
)
def test_the_skills_arm_refuses_equipment_it_cant_hand_as_an_intervention(own, equipment, says):
    """Bug caught: a capture taken from a cycle that already had the skills replayed as their
    baseline (skills against skills), or a vocabulary dropped because its input isn't there."""
    with pytest.raises(ValueError, match=says):
        arm_inputs(own, Arm.SKILLS, experiment_id="x", equipment=equipment)


def test_a_swapped_case_changes_the_named_inputs_and_leaves_the_capture_as_it_was():
    own = {
        "config": {"objective": {"statement": "show the potions left"}},
        "tree": {"map": "- `tests/run.luau`\n- `src/A.luau`", "files": ["a", "b"]},
        "note": "n",
    }

    swapped = swapped_inputs(
        own,
        [
            {"path": ["config", "objective", "statement"], "value": "play a chime on pickup"},
            {"path": ["tree", "map"], "replace": ["- `tests/run.luau`\n", ""]},
            {"path": ["tree", "files", 0], "delete": True},
            {"path": ["note"], "delete": True},
        ],
    )

    assert swapped == {
        "config": {"objective": {"statement": "play a chime on pickup"}},
        "tree": {"map": "- `src/A.luau`", "files": ["b"]},
    }
    assert own["config"]["objective"]["statement"] == "show the potions left"


@pytest.mark.parametrize(
    ("swap", "says"),
    [
        ({"path": ["goal"], "value": "g"}, "already holds the value"),
        ({"path": ["absent"], "value": "g"}, "hold no absent to swap"),
        ({"path": ["tree", "absent", "x"], "value": "g"}, "hold no tree.absent"),
        ({"path": ["goal"], "replace": ["zzz", "y"]}, "holds no 'zzz' to replace"),
        ({"path": ["tree"], "replace": ["a", "b"]}, "holds no 'a' to replace"),
        ({"path": ["goal"], "value": "x", "delete": True}, "exactly one of"),
        ({"path": ["goal"]}, "exactly one of"),
        ({"path": ["goal"], "delete": "yes"}, "delete is true"),
        ({"path": [], "value": "x"}, "at least one key"),
    ],
    ids=[
        "changes-nothing",
        "absent",
        "absent-parent",
        "text-not-there",
        "not-text",
        "two-things",
        "nothing",
        "delete-not-true",
        "no-path",
    ],
)
def test_a_swap_that_cant_be_made_as_written_is_refused(swap, says):
    """Bug caught: a swap that silently changed nothing (a mistyped path, text that isn't
    there), leaving the capture's own task in front of the model under the case's name."""
    with pytest.raises(ValueError, match=says):
        swapped_inputs({"goal": "g", "tree": {"map": "m"}}, [swap])


def test_a_cases_notes_are_frozen_with_it_and_a_case_with_none_is_written_as_before():
    """Bug caught: a skills case's swaps or skill digests edited between scored runs under one
    experiment name; or the new notes changing an earlier experiment's manifest, which its own
    rerun would then be refused against."""
    envelope = {
        "envelope_id": "env_1",
        "task_type": "strategy.propose_increment",
        "seam": "proposal_writing",
        "messages_sha256": "abc",
        "captured_at": CUTOFF.isoformat(),
        "chat_kwargs": {"model": "m"},
    }

    def build(notes):
        return manifest(
            experiment_id="e",
            created_at=CUTOFF,
            envelopes=[envelope],
            arms=[Arm.BASELINE, Arm.SKILLS],
            generations=3,
            seed=7,
            lessons=[],
            static_guidance="",
            rubric="r@1",
            rubric_text=None,
            framework_git_sha="f3c1e81a",
            case_notes=notes,
        )

    plain = build(None)
    noted = build({"env_1": {"case": "strategy-unobservable", "skills": {"a/b": "d1"}}})

    assert plain.to_dict()["cases"] == [
        {
            "envelope_id": "env_1",
            "task_type": "strategy.propose_increment",
            "seam": "proposal_writing",
            "messages_sha256": "abc",
            "captured_at": CUTOFF.isoformat(),
        }
    ]
    assert noted.to_dict()["cases"][0]["skills"] == {"a/b": "d1"}
    assert noted.digest() != plain.digest()
    assert (
        noted.digest()
        != build({"env_1": {"case": "strategy-unobservable", "skills": {"a/b": "d2"}}}).digest()
    )

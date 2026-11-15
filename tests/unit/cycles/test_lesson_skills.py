"""Lessons and skillsets (SIP-0116 §10a; phase 6, part 1, #3038).

§14's proof for phase 6, entered at ``supply_the_dispatch``, the call the executor makes for each
dispatch, over the in-memory store as cross-cycle memory's own tests use it:

- a repository-backed cycle recalls under its development profile, and records that it did;
- a cycle with a ``build_profile`` recalls exactly as before;
- a lesson a skill the task loads supersedes is omitted, with its reason.

Part 2 (#3038): a lesson learned under another version of a skill the task loads is flagged, from
what its draft recorded it was learned under; and a skill promoted from lessons carries its review.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from squadops.capabilities.lesson_supply import StackSource, recall_stack, supply_the_dispatch
from squadops.capabilities.skillsets import SKILLS_INPUT, SkillsetError, load_skillset
from squadops.memory.approval import draft_revision
from squadops.memory.context import Disposition
from squadops.memory.exposures import RECALL_IDENTITY_RULE, Exposure
from squadops.memory.lessons import (
    SUPERSEDED_BY_SKILL,
    Applicability,
    Approval,
    PatternRevision,
    RecallDisposition,
    Recalled,
    pattern_id_for,
)
from squadops.memory.recall import LESSONS_INPUT, RecallQuery, UnitKind
from squadops.projects.source_context import parse_source_context
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.cycles.test_failure_recall import (
    _NOW,
    _framing_cycle,
    _pinned,
    _plan,
    _store_with,
)

pytestmark = [pytest.mark.domain_memory]

TEXT = "Name the manifest element each criterion checks."


def _where(stack: str) -> Applicability:
    return Applicability(
        project_id="group_run",
        task_types=("development.design_plan",),
        roles=("dev",),
        stacks=(stack,),
        model_families=("qwen3.8",),
    )


def _product_cycle():
    """A repository-backed cycle: no ``build_profile``, a pinned source and development profile."""
    return dataclasses.replace(
        _framing_cycle(),
        applied_defaults={"plan_authoring_contributors": ["development", "qa", "strategy"]},
        source_context=parse_source_context(recorded("project_source_context", "valid")),
        skillset_record={"development_profile": {"name": "product_neutral"}},
    )


def _design_task(*, skills=None):
    [design] = [e for e in _plan() if str(e.task_type) == "development.design_plan"]
    if skills is not None:
        design.inputs[SKILLS_INPUT] = skills
    return design


async def _dispatched(store, cycle, task) -> Exposure:
    from adapters.memory.recall import SnapshotRecall

    await supply_the_dispatch(
        [task], recall=SnapshotRecall(store), cycle=cycle, run_id="run_recall0001", now=_NOW
    )
    [exposure] = [
        x for x in await store.list_exposures("run_recall0001") if x.task_id == task.task_id
    ]
    return exposure


async def test_a_repository_backed_cycle_recalls_under_its_development_profile_and_says_so():
    """Bugs caught: a repository-backed cycle recalling with no stack, so it gets only lessons for
    any stack and never one for its own; or recall's identity unrecorded, so nobody reading the
    exposure can tell which lessons it could have been given."""
    store = await _store_with((TEXT, _where("product_neutral")))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")
    task = _design_task()

    exposure = await _dispatched(store, _product_cycle(), task)

    assert (exposure.query.stack, exposure.query.stack_source) == (
        "product_neutral",
        StackSource.DEVELOPMENT_PROFILE,
    )
    assert exposure.disposition == "supplied"
    assert exposure.to_dict()["identity"] == {
        "stack_source": "development_profile",
        "rule": RECALL_IDENTITY_RULE,
    }
    assert Exposure.from_dict(exposure.to_dict()).query.stack_source == "development_profile"
    assert LESSONS_INPUT in task.inputs


async def test_a_cycle_with_a_build_profile_recalls_exactly_as_before():
    """Bug caught: the development profile's name replacing the build profile's for a cycle that
    has one, so every lesson stored under ``fullstack_fastapi_react`` stops reaching it."""
    store = await _store_with((TEXT, _where("fullstack_fastapi_react")))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")

    exposure = await _dispatched(store, _framing_cycle(), _design_task())

    assert (exposure.query.stack, exposure.query.stack_source) == (
        "fullstack_fastapi_react",
        StackSource.BUILD_PROFILE,
    )
    assert exposure.disposition == "supplied"


async def test_a_lesson_a_loaded_skill_supersedes_is_omitted_with_its_reason():
    """Bugs caught: a lesson a skill replaces still handed beside it, so the task reads two
    guidances that may disagree; or omitted silently, so its absence reads as none eligible."""
    store = await _store_with((TEXT, _where("fullstack_fastapi_react")))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")
    pattern = pattern_id_for("group_run", TEXT, "development.design_plan")
    skill = {
        "skillset": "fixture-dev",
        "version": 2,
        "skill": "design",
        "digest": "d",
        "files": {
            "SKILL.md": f"---\nname: design\ndescription: d\nsupersedes: [{pattern}]\n---\nX.\n"
        },
    }
    task = _design_task(skills=[skill])

    exposure = await _dispatched(store, _framing_cycle(), task)

    assert exposure.disposition == "none_eligible"
    assert exposure.recalled["omitted"] == [
        {"revision_id": f"{pattern}@1", "reason": f"{SUPERSEDED_BY_SKILL}:fixture-dev/design"}
    ]
    assert LESSONS_INPUT not in task.inputs


@pytest.mark.parametrize(
    ("cycle", "expected"),
    [
        (lambda: _framing_cycle(), ("fullstack_fastapi_react", StackSource.BUILD_PROFILE)),
        (_product_cycle, ("product_neutral", StackSource.DEVELOPMENT_PROFILE)),
        # A sample application's cycle with no build_profile and no source: unscoped, as today.
        (
            lambda: dataclasses.replace(_framing_cycle(), applied_defaults={}),
            ("", StackSource.UNSCOPED),
        ),
        # Source-backed, created before skillset records: unscoped, never a guessed profile.
        (
            lambda: dataclasses.replace(_product_cycle(), skillset_record=None),
            ("", StackSource.UNSCOPED),
        ),
    ],
)
def test_the_recall_stack_falls_back_only_to_a_pinned_development_profile(cycle, expected):
    """Bug caught: a default development profile read for a cycle that pinned none, so it
    recalls lessons for a stack it never ran on."""
    assert recall_stack(cycle()) == expected


def test_a_skill_whose_supersedes_isnt_a_list_of_pattern_ids_refuses_its_skillset(tmp_path):
    """Bug caught: a malformed ``supersedes`` loaded, and a lesson it meant to replace kept, or
    one it didn't mean dropped."""
    import textwrap

    from tests.unit.capabilities.test_skillset_spec import CONTRACTS, SPEC

    skillset = tmp_path / "fixture-qa"
    (skillset / "skills" / "test-loader").mkdir(parents=True)
    (skillset / "skills" / "play-scenario").mkdir(parents=True)
    (tmp_path / "_shared" / "conventions").mkdir(parents=True)
    (skillset / "skillset.yaml").write_text(textwrap.dedent(SPEC))
    for path in ("skills/play-scenario", "skills/test-loader"):
        (skillset / path / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\nX.\n")
    (tmp_path / "_shared" / "conventions" / "SKILL.md").write_text(
        "---\nname: c\ndescription: d\nsupersedes: [the-old-lesson]\n---\nX.\n"
    )

    with pytest.raises(SkillsetError, match="supersedes is a list of lesson pattern ids"):
        load_skillset(skillset, contracts=CONTRACTS)


# ---------------------------------------------------------------- part 2: flagged, and promotion

DESIGN = "fixture-dev/design"


def _skill(digest: str, front: str = "") -> dict:
    return {
        "skillset": "fixture-dev",
        "version": 2,
        "skill": "design",
        "digest": digest,
        "files": {"SKILL.md": f"---\nname: design\ndescription: d\n{front}---\nX.\n"},
    }


async def _store_learned(learned) -> object:
    """A store holding one approved lesson whose revision records ``learned`` as learned under."""
    from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore

    store = InMemoryCrossCycleMemoryStore()
    where = _where("fullstack_fastapi_react")
    revision = PatternRevision(
        pattern_id=pattern_id_for("group_run", TEXT, "development.design_plan"),
        revision=1, target_behavior=TEXT, text=TEXT, applicability=where, template_id="lesson.t",
        template_version="1", drafter_model="auditor", drafter_version="1",
        cited_observations=("correction_round:x",), created_at=_NOW, learned_under=learned,
    )  # fmt: skip
    await store.record_revision(revision)
    await store.record_approval(Approval("apr_1", revision.revision_id, where, "owner", _NOW))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")
    return store


@pytest.mark.parametrize(
    ("learned", "flagged", "unrecorded"),
    [
        # Learned under the old version of the skill the task now loads: flagged, still supplied.
        (
            {DESIGN: ("d_old",)},
            [{"revision_id": "@1", "skill": DESIGN, "loaded": "d_new", "learned_under": ["d_old"]}],
            None,
        ),
        # Learned under this very version: nothing to review.
        ({DESIGN: ("d_old", "d_new")}, None, None),
        # Learned under no version of it: no earlier version shaped the lesson.
        ({"fixture-qa/test-loader": ("d_qa",)}, None, None),
        # Drafted before skills were recorded: it couldn't be checked, and says so.
        (None, None, ["@1"]),
    ],
    ids=["older version", "same version", "other skill", "unrecorded"],
)
async def test_a_lesson_learned_under_another_version_of_a_loaded_skill_is_flagged_and_supplied(
    learned, flagged, unrecorded
):
    """§10a's flagged record, entered at ``supply_the_dispatch``. Bugs caught: a lesson learned
    under a skill's earlier text supplied beside its new one with nothing for a reviewer to find;
    flagging read as omitting, so a version change alone drops the lesson; or a lesson that
    can't be checked passing as one that was."""
    store = await _store_learned(learned)
    task = _design_task(skills=[_skill("d_new")])

    exposure = await _dispatched(store, _framing_cycle(), task)

    pattern = pattern_id_for("group_run", TEXT, "development.design_plan")
    fill = lambda rows: [  # noqa: E731
        {**r, "revision_id": pattern + r["revision_id"]} if isinstance(r, dict) else pattern + r
        for r in rows
    ]
    assert exposure.disposition == "supplied"
    assert LESSONS_INPUT in task.inputs
    assert exposure.recalled.get("flagged") == (fill(flagged) if flagged else None)
    assert exposure.recalled.get("learned_under_unrecorded") == (
        fill(unrecorded) if unrecorded else None
    )
    assert exposure.to_dict()["skills"] == {DESIGN: "d_new"}
    assert Exposure.from_dict(exposure.to_dict()).query.loaded_skills == {DESIGN: "d_new"}


async def test_a_task_that_loads_no_skill_records_none_and_is_never_flagged():
    """Every existing stack's task. Bug caught: a task with no skill recorded as unknown, so every
    lesson drafted from it reads as unreadable; or flagged against skills it never loaded."""
    store = await _store_learned(None)

    exposure = await _dispatched(store, _framing_cycle(), _design_task())

    assert exposure.to_dict()["skills"] == {}
    assert "flagged" not in exposure.recalled
    assert "learned_under_unrecorded" not in exposure.recalled


def _observed(source_id: str, run_id=None, task_id=None):
    from squadops.memory.observations import (
        VOCABULARY_ATTRIBUTION,
        Classification,
        Observation,
        ObservationSource,
    )

    return Observation(
        source=ObservationSource.CORRECTION_ROUND, source_id=source_id, project_id="group_run",
        observed_at=_NOW, classification=Classification(VOCABULARY_ATTRIBUTION, ("x",)),
        run_id=run_id, task_id=task_id,
    )  # fmt: skip


def _exposure(task_id: str, attempt: int, loaded, *, held: bool = False) -> Exposure:
    query = RecallQuery("group_run", "development.design_plan", loaded_skills=loaded)
    return Exposure(
        "run_1", task_id, "cyc_1", "neo", "design", query,
        Recalled("snp_1", RecallDisposition.NONE_ELIGIBLE).exposure(), _NOW, attempt,
        task_instructions={"disposition": Disposition.INCOMPLETE.value} if held else None,
    )  # fmt: skip


def test_a_draft_records_the_skills_its_observations_dispatches_loaded_and_what_it_couldnt_read():
    """The other half of flagging: a revision knows what it was learned under. Bugs caught: a
    re-dispatch's skills lost, so a lesson learned across a skill's revision reads as learned
    under one; a held task's skills counted, though nothing reached the model; or an observation
    whose dispatch can't be read left out silently, so a partial record reads as whole."""
    cited = ["correction_round:a", "plan_review:b", "correction_round:c", "correction_round:d"]
    observations = [
        _observed(cited[0], "run_1", "t1"),
        _observed(cited[1], "run_1"),
        _observed(cited[2], "run_1", "t2"),
        _observed(cited[3], "run_1", "t3"),
    ]
    exposures = [
        _exposure("t1", 1, {DESIGN: "d1"}),
        _exposure("t1", 2, {DESIGN: "d2"}),
        _exposure("t1", 3, {DESIGN: "d9"}, held=True),
        _exposure("t2", 1, None),
    ]

    revision = draft_revision(
        target_behavior=TEXT, text=TEXT, applicability=_where("fullstack_fastapi_react"),
        template_id="lesson.t", template_version="1", drafter_model="m", drafter_version="1",
        cited_observations=cited, citable_observations=cited, revisions=(),
        observations=observations, exposures=exposures, now=_NOW,
    )  # fmt: skip

    assert revision.learned_under == {DESIGN: ("d1", "d2")}
    assert revision.learned_under_unread == (
        ("plan_review:b", "no_task"),
        ("correction_round:c", "skills_unrecorded"),
        ("correction_round:d", "no_exposure"),
    )
    stored = PatternRevision.from_dict(revision.to_dict())
    assert (stored.learned_under, stored.learned_under_unread) == (
        revision.learned_under,
        revision.learned_under_unread,
    )


def test_a_revision_from_before_is_stored_and_read_as_it_was():
    """Bug caught: every stored revision, and so every pinned snapshot holding one, gaining keys
    on its next write, or read back as learned under nothing rather than unrecorded."""
    revision = dataclasses.replace(
        PatternRevision.from_dict(
            {
                "pattern_id": "pat_0123456789abcdef", "revision": 1, "target_behavior": "t",
                "text": "t", "applicability": _where("*").to_dict(), "template_id": "l",
                "template_version": "1", "drafter_model": "m", "drafter_version": "1",
                "cited_observations": [], "created_at": _NOW.isoformat(),
            }
        )
    )  # fmt: skip

    assert revision.learned_under is None
    assert "learned_under" not in revision.to_dict()


PATTERN = "pat_0123456789abcdef"
REVIEW = (
    "promotion_review:\n  approved_by: owner\n  approved_at: '2026-11-14'\n"
    "  replay_check: {reference: replay/x, result: absent 5/6 vs 1/6}\n"
    "  generalization: holds on every product of the stack\n"
    "  distribution: names no product\n"
)


@pytest.mark.parametrize(
    ("front", "refused"),
    [
        (f"supersedes: [{PATTERN}]\npromoted_from: [{PATTERN}@2]\n{REVIEW}", None),
        (
            f"supersedes: [{PATTERN}]\npromoted_from: [{PATTERN}@2]\n",
            "carries its promotion_review",
        ),
        (f"supersedes: [{PATTERN}]\n{REVIEW}", "promotion_review is given with no promoted_from"),
        (f"promoted_from: [{PATTERN}@2]\n{REVIEW}", "supersedes lacks ['pat_0123456789abcdef']"),
        (f"supersedes: [{PATTERN}]\npromoted_from: [{PATTERN}]\n{REVIEW}", "revision ids"),
        (
            f"supersedes: [{PATTERN}]\npromoted_from: [{PATTERN}@2]\n"
            + REVIEW.replace("  distribution: names no product\n", "").replace(
                "result: absent 5/6 vs 1/6", "result: ''"
            ),
            "lacks distribution, replay_check (reference and result)",
        ),
    ],
    ids=["reviewed", "no review", "no lesson", "not superseded", "pattern not revision", "partial"],
)
def test_a_skill_promoted_from_lessons_loads_only_with_its_review(tmp_path, front, refused):
    """§10a's promotion review, at the skillset's load. Bugs caught: a lesson rewritten into a
    skill and handed to every project with no record of who approved it or what it was checked
    against; the lesson it came from still recalled beside it; or a review naming every field
    but one passing as complete."""
    import textwrap

    from tests.unit.capabilities.test_skillset_spec import CONTRACTS, SPEC

    skillset = tmp_path / "fixture-qa"
    (skillset / "skills" / "test-loader").mkdir(parents=True)
    (skillset / "skills" / "play-scenario").mkdir(parents=True)
    (tmp_path / "_shared" / "conventions").mkdir(parents=True)
    (skillset / "skillset.yaml").write_text(textwrap.dedent(SPEC))
    (skillset / "skills" / "test-loader" / "SKILL.md").write_text(
        f"---\nname: s\ndescription: d\n{front}---\nX.\n"
    )
    for path in ("skills/play-scenario", "../_shared/conventions"):
        (skillset / path / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\nX.\n")

    if refused is None:
        assert load_skillset(skillset, contracts=CONTRACTS).id == "fixture-qa"
        return
    with pytest.raises(SkillsetError, match=re.escape(refused)):
        load_skillset(skillset, contracts=CONTRACTS)

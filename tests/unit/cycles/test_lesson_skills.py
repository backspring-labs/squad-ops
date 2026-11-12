"""Lessons and skillsets (SIP-0116 §10a; phase 6, part 1, #3038).

§14's proof for phase 6, entered at ``supply_the_dispatch``, the call the executor makes for each
dispatch, over the in-memory store as cross-cycle memory's own tests use it:

- a repository-backed cycle recalls under its development profile, and records that it did;
- a cycle with a ``build_profile`` recalls exactly as before;
- a lesson a skill the task loads supersedes is omitted, with its reason.
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.capabilities.lesson_supply import StackSource, recall_stack, supply_the_dispatch
from squadops.capabilities.skillsets import SKILLS_INPUT, SkillsetError, load_skillset
from squadops.memory.exposures import RECALL_IDENTITY_RULE, Exposure
from squadops.memory.lessons import SUPERSEDED_BY_SKILL, Applicability, pattern_id_for
from squadops.memory.recall import LESSONS_INPUT, UnitKind
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

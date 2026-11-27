"""A task's skills as its prompt shows them (SIP-0116 §7; phase 3, part 2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from adapters.prompts.factory import create_prompt_asset_source
from squadops.capabilities.handlers.context_sections import context_sections
from squadops.capabilities.handlers.skills import skills_section
from squadops.capabilities.prompt_budget import _tokens, prompt_without_memory_tokens
from squadops.capabilities.skillsets import SKILLS_INPUT
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.memory.recall import LESSONS_INPUT
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_capabilities]

TEMPLATES = Path(__file__).resolve().parents[3] / "src/squadops/prompts/request_templates"
SLOT = "{{project_instructions_section}}{{skills_section}}{{cross_cycle_lessons_section}}"
HEADING = "## HOW THIS KIND OF WORK IS DONE ON THIS PLATFORM"

LOADER = {
    "skillset": "luau-qa",
    "version": 2,
    "skill": "test-loader",
    "digest": "d1",
    "files": {
        "SKILL.md": (
            "---\nname: Writing a spec\ndescription: Chosen by nobody here.\n---\n"
            "Name each spec `*.spec.luau`.\n\nRequire the module under test first.\n"
        ),
        "examples/door.spec.luau": "```luau\nreturn function() end\n```\n",
    },
}
CONVENTIONS = {
    "skillset": "luau-qa",
    "version": 2,
    "skill": "shared/conventions",
    "digest": "d2",
    "files": {"SKILL.md": "---\nname: Naming\ndescription: x\n---\nPascalCase for modules.\n"},
}


@pytest.fixture
def renderer():
    return RequestTemplateRenderer(create_prompt_asset_source("filesystem"))


async def test_each_skill_is_shown_whole_under_its_name_with_its_resources(renderer):
    """Bug caught: a skill's front matter shown as if it were guidance, a resource dropped,
    or a resource holding its own fenced block cut short by the fence it is shown in."""
    section = await skills_section(renderer, {SKILLS_INPUT: [LOADER, CONVENTIONS]})

    body = section.split("and before any lesson.\n\n", 1)[1]
    assert section.startswith(f"\n\n{HEADING}\n\n") and section.endswith("\n")
    assert body == (
        "### Skill: Writing a spec\n\n"
        "Name each spec `*.spec.luau`.\n\nRequire the module under test first.\n\n"
        "The skill's file `examples/door.spec.luau`:\n\n"
        "````\n```luau\nreturn function() end\n```\n````\n\n"
        "### Skill: Naming\n\n"
        "PascalCase for modules.\n"
    )
    assert "Chosen by nobody here" not in section


async def test_a_task_handed_none_shows_no_section(renderer):
    """The unchanged half. Bug caught: a heading with nothing under it in every prompt."""
    assert await skills_section(renderer, {}) == ""
    assert await skills_section(renderer, {SKILLS_INPUT: []}) == ""
    assert await skills_section(None, {}) == ""


@pytest.mark.parametrize(
    ("use_renderer", "skill", "says"),
    [
        (False, LOADER, "handed 1 skills and has no renderer to show them with"),
        (True, {**LOADER, "files": {"notes.md": "x"}}, "was handed with no SKILL.md"),
        (
            True,
            {**LOADER, "files": {"SKILL.md": "---\ndescription: x\n---\nBody.\n"}},
            "front matter gives no name",
        ),
    ],
    ids=["no-renderer", "no-skill-file", "no-name"],
)
async def test_skills_that_cant_be_shown_raise_and_are_never_left_out(
    renderer, use_renderer, skill, says
):
    """Bug caught: a prompt that goes out without the skills its task was handed, and reads
    afterwards as one that had them."""
    with pytest.raises(ValueError, match=says):
        await skills_section(renderer if use_renderer else None, {SKILLS_INPUT: [skill]})


async def test_the_skills_sit_after_the_projects_instructions_and_before_the_lessons(renderer):
    """§7's precedence, in the shared slots every authoring seam renders. Bug caught: skills
    shown after the lessons, or ahead of an instruction that overrides them."""
    sections = await context_sections(
        renderer,
        {
            SKILLS_INPUT: [CONVENTIONS],
            PROJECT_INSTRUCTIONS_INPUT: {
                "instructions": [
                    {"record_id": "m", "revision": 1, "text": "Ship small.", "references": []}
                ]
            },
            LESSONS_INPUT: {
                "snapshot": "s",
                "lessons": [{"revision_id": "p@1", "text": "Test it."}],
            },
        },
    )

    assert list(sections) == [
        "project_instructions_section",
        "skills_section",
        "cross_cycle_lessons_section",
    ]
    assert HEADING in sections["skills_section"]


def test_every_template_with_the_instruction_slots_has_the_skills_slot_between_them():
    """Bug caught: an authoring seam whose template never got the slot, so a task there is
    handed skills its prompt can't show; or the slot placed after the lessons."""
    slotted = [
        t for t in TEMPLATES.glob("*.md") if "{{project_instructions_section}}" in t.read_text()
    ]

    assert len(slotted) >= 13
    for path in slotted:
        text = path.read_text()
        assert text.count(SLOT) == 1, path.name
        assert "  - project_instructions_section\n  - skills_section\n" in text, path.name


async def test_every_slotted_template_renders_unchanged_with_no_skills():
    """The byte-identical half at the prompt. Bug caught: the skills' slot adding a line to a
    prompt whose task was handed none."""
    from tests.unit.memory.test_lesson_slots import _render

    for path in TEMPLATES.glob("*.md"):
        text = path.read_text().split("---", 2)[2]
        if "{{skills_section}}" not in text:
            continue
        names = set(re.findall(r"{{(\w+)}}", text))
        fill = {n: f"<{n}>" for n in names if n != "skills_section"}
        before = text.replace("{{skills_section}}", "")
        assert await _render(text, fill) == await _render(before, fill), path.name


async def test_an_author_shows_the_skills_it_is_handed_before_the_lessons():
    """Wiring, entered at the technical design's real ``handle()`` with the shipped assets.
    Bug caught: skills on the envelope and absent from the prompt, or shown after the
    lessons."""
    from squadops.capabilities.handlers.planning.framing import DevelopmentDesignPlanHandler
    from tests.unit.campaigns.test_prior_cycle import _rendered
    from tests.unit.memory.test_lesson_slots import _HEADING, _LESSONS

    base = {"prd": "the PRD", "resolved_config": {}}

    shown = await _rendered(
        DevelopmentDesignPlanHandler(),
        {**base, SKILLS_INPUT: [CONVENTIONS], LESSONS_INPUT: _LESSONS},
    )
    plain = await _rendered(DevelopmentDesignPlanHandler(), base)

    assert "### Skill: Naming\n\nPascalCase for modules." in shown
    assert shown.index(HEADING) < shown.index(_HEADING)
    assert HEADING not in plain and "Skill:" not in plain


def _envelope(**inputs) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="t", agent_id="neo", cycle_id="c", pulse_id="p", project_id="proj",
        task_type="development.develop", correlation_id="c", causation_id="c", trace_id="t",
        span_id="s", inputs={"prd": "the PRD", "agent_model": "qwen2.5:7b", **inputs},
    )  # fmt: skip


async def test_the_prompt_budget_counts_a_tasks_skills_at_least_as_they_render(renderer):
    """§7: the budget counts the skills a task loads before lessons are given space. Bug
    caught: skills left out of the measured prompt, so lessons are given room the skills
    already took and the prompt overruns the window."""
    shown = await skills_section(renderer, {SKILLS_INPUT: [LOADER, CONVENTIONS]})

    without = prompt_without_memory_tokens(_envelope())
    with_skills = prompt_without_memory_tokens(_envelope(**{SKILLS_INPUT: [LOADER, CONVENTIONS]}))

    assert with_skills - without >= _tokens(shown)


# --- #3240 (SIP-0116 §17aa): a declared stop outranks the task's own requirements -----------------

STOPPING = {
    "skillset": "luau-design",
    "version": 1,
    "skill": "scenario-authoring",
    "digest": "d3",
    "files": {
        "SKILL.md": (
            '---\nname: Authoring a scenario\ndescription: x\nstops: ["no scenario:"]\n---\n'
            "If the effect can't be observed, stop, and say in one line:\n"
            "`no scenario: <criterion> shows itself as <effect>, which can't be observed`.\n"
        )
    },
}
ORDERING = (
    "Where a skill disagrees with those, follow them, and say in your output which part of the\n"
    "skill you could not follow and why."
)
STOP_HEADING = "### When a skill above tells you to stop"


async def test_a_declared_stop_is_said_to_outrank_the_tasks_requirements(renderer):
    """Bug caught (#3240): the section ranking every part of a skill below the task's own
    requirements, so a model told to emit exactly one file resolves the skill's stop against
    the task and writes the artifact the stop exists to prevent."""
    section = await skills_section(renderer, {SKILLS_INPUT: [CONVENTIONS, STOPPING]})

    # Beside the ordering it is the exception to.
    flat = " ".join(section.split())
    assert (
        "you could not follow and why. The one exception is a stop a skill declares: it comes "
        "before this task's own requirements, as the end of this section says. They come before "
        "the general guidance"
    ) in flat
    # And where the section ends, after every skill, next to what the task is asked to emit.
    stops = section.split(f"{STOP_HEADING}\n\n", 1)[1]
    assert section.index("### Skill: Authoring a scenario") < section.index(STOP_HEADING)
    assert "From the skill Authoring a scenario:\n- `no scenario:`\n\n" in stops
    assert "A stop comes before this task's own requirements." in stops
    assert "does not apply to a task that stops: emit none" in stops
    assert stops.rstrip().endswith(
        "When no stop's condition holds, emit what this task asks for, exactly as it says."
    )
    # Only the skill that declares one is listed.
    assert "From the skill Naming" not in section


async def test_skills_that_declare_no_stop_render_the_section_they_rendered_before(renderer):
    """The unchanged half. Bug caught: every skill-carrying prompt told about stops none of
    its skills declares, and its bytes moved for nothing."""
    section = await skills_section(renderer, {SKILLS_INPUT: [LOADER, CONVENTIONS]})

    assert STOP_HEADING not in section and "one exception" not in section
    assert f"{ORDERING} They come before the general guidance for this stack" in section


async def test_the_sections_own_words_about_a_stop_are_never_read_as_one(renderer):
    """SIP-0116 §17u (#3154) holds for the new text. A model that quotes the section back, the
    list of openings included, hasn't stopped. Bug caught: an opening listed with words after
    it on its line, so the quote is read as the model's own stop and the task ends."""
    from squadops.capabilities.skill_stops import read_stop

    section = await skills_section(renderer, {SKILLS_INPUT: [STOPPING]})

    assert read_stop([STOPPING], section) is None
    assert read_stop([STOPPING], "- `no scenario:`") is None
    stopped = read_stop([STOPPING], "no scenario: the door's sound, which can't be observed")
    assert stopped is not None and stopped.opening == "no scenario:"


async def test_the_packaged_skills_stops_are_listed_under_their_own_names(renderer):
    """Entered with the skills the deployment ships. Bug caught: the list built from a field
    the packaged skills don't carry, so the two skills that declare a stop are told nothing."""
    from squadops.capabilities.skill_stops import read_stop
    from squadops.capabilities.skillsets import load_skillsets

    packaged = load_skillsets()
    handed = [
        {
            "skillset": skillset,
            "version": 1,
            "skill": skill,
            "digest": "d",
            "files": dict(packaged[skillset].skill_files[skill]),
        }
        for skillset, skill in (
            ("roblox-increment-design", "play-scenario-authoring"),
            ("roblox-luau-dev", "luau-gameplay"),
        )
    ]

    section = await skills_section(renderer, {SKILLS_INPUT: handed})

    stops = section.split(f"{STOP_HEADING}\n\n", 1)[1]
    assert "- `no scenario:`\n" in stops and "- `saved data:`\n" in stops
    assert stops.count("From the skill ") == 2
    assert read_stop(handed, section) is None


def test_the_budget_names_a_skill_whose_stops_it_cant_read():
    """From the MacBook lane's review. The budget reaches the list before any rendering does.
    Bug caught: a skill whose front matter can't be read skipped there, so the prompt is
    measured short and nothing says which skill."""
    broken = {**STOPPING, "files": {"SKILL.md": "no front matter at all\n"}}

    with pytest.raises(ValueError, match="skill luau-design/scenario-authoring: SKILL.md"):
        prompt_without_memory_tokens(_envelope(**{SKILLS_INPUT: [broken]}))


async def test_the_prompt_budget_counts_the_stops_text_at_least_as_it_renders(renderer):
    """Bug caught: the stop rule's text left out of the measured prompt, so a task near its
    window is given lesson room the section already took."""
    shown = await skills_section(renderer, {SKILLS_INPUT: [STOPPING]})

    without = prompt_without_memory_tokens(_envelope())
    with_skills = prompt_without_memory_tokens(_envelope(**{SKILLS_INPUT: [STOPPING]}))

    assert with_skills - without >= _tokens(shown)

"""A skill's declared stop, read from a model's answer (SIP-0116 §17o; #3041).

The packaged tests enter at the supply a cycle uses: the kept copy, ``skills_for`` and
``skills_input``, which is what a task's ``SKILLS_INPUT`` holds when a seam asks ``read_stop``.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.skill_stops import SkillStop, read_stop
from squadops.capabilities.skillsets import load_skillsets
from squadops.cycles.skillset_content import kept_document, skills_for, skills_input
from squadops.cycles.skillset_coverage import Assignment
from squadops.prompts.frontmatter import FrontmatterError

pytestmark = [pytest.mark.domain_capabilities]

_STOP_LINE = "no scenario: the chime shows itself as a sound, which fixture/1 can't observe"


def _handed(*stops: str, skill: str = "scenario-authoring") -> list[dict]:
    declared = f"stops: [{', '.join(repr(s) for s in stops)}]\n" if stops else ""
    body = "Write the scenario.\n" + "".join(f"Or say `{s} <why>`.\n" for s in stops)
    return [
        {
            "skillset": "fixture-design",
            "version": 1,
            "skill": skill,
            "digest": "0" * 64,
            "files": {"SKILL.md": f"---\nname: {skill}\ndescription: d\n{declared}---\n{body}"},
        }
    ]


@pytest.mark.parametrize(
    "answer",
    [
        _STOP_LINE,
        f"I can't write this one.\n\n`{_STOP_LINE}`\n",
        f"- **{_STOP_LINE}**",
        f"> {_STOP_LINE}",
        f"```\n{_STOP_LINE}\n```",
        f"`{_STOP_LINE}`.",
        "N" + _STOP_LINE[1:],
    ],
    ids=["bare", "inline-code", "bold-list-item", "quoted", "fenced", "sentence-end", "capital"],
)
def test_a_declared_stop_is_read_however_the_model_dresses_the_line(answer):
    """Bug caught: a stop the model wrote as it was shown (in inline code, in a list, with a
    capital) read as no stop, so the task is asked again to do what its skill refused."""
    stop = read_stop(_handed("no scenario:"), answer)

    assert stop is not None
    assert (stop.skillset, stop.skill, stop.opening) == (
        "fixture-design",
        "scenario-authoring",
        "no scenario:",
    )
    assert stop.line.casefold() == _STOP_LINE.casefold()
    assert stop.reason == _STOP_LINE[len("no scenario:") :].strip()
    assert stop.describe() == f"stopped by the skill fixture-design/scenario-authoring: {stop.line}"


@pytest.mark.parametrize(
    ("handed", "answer"),
    [
        (_handed("no scenario:"), "no scenario:"),
        (_handed("no scenario:"), "no scenario:   `"),
        (_handed("no scenario:"), "I considered answering no scenario: but the label is text."),
        (_handed("no scenario:"), "```yaml:change_request.yaml\nproposal_id: p1\n```"),
        (_handed(), _STOP_LINE),
        (None, _STOP_LINE),
        ([], _STOP_LINE),
        (_handed("no scenario:"), ""),
        (_handed("no scenario:"), None),
    ],
    ids=[
        "no-reason",
        "no-reason-decorated",
        "mid-line",
        "an-emission",
        "skill-declares-none",
        "handed-none",
        "handed-nothing",
        "empty-answer",
        "no-answer",
    ],
)
def test_an_answer_with_no_declared_stop_and_its_reason_reads_as_none(handed, answer):
    """Bug caught: a mention of the words, an opening with no reason, or another task's stop
    ending a run that should have been judged on its emission."""
    assert read_stop(handed, answer) is None


def test_the_first_stop_in_the_answer_is_the_one_read():
    handed = _handed("no scenario:", "no runner:")

    stop = read_stop(handed, "no runner: the tree has no tests/run\nno scenario: a sound")

    assert stop == SkillStop(
        "fixture-design", "scenario-authoring", "no runner:", "no runner: the tree has no tests/run"
    )


_TEMPLATE = "no scenario: <criterion> shows itself as <effect>, which fixture/1 can't observe"


def _handed_with_template() -> list[dict]:
    handed = _handed("no scenario:")
    handed[0]["files"]["SKILL.md"] += (
        f"Write no change request, and say in one line:\n`{_TEMPLATE}`.\n"
    )
    return handed


@pytest.mark.parametrize(
    "answer",
    [
        f"> Write no change request, and say in one line:\n> `{_TEMPLATE}`\n\n`{_STOP_LINE}`",
        f"`{_STOP_LINE}`\n\nThe skill's line is `{_TEMPLATE}`.\n{_TEMPLATE}",
        f"> `{_TEMPLATE[:52]}\n> {_TEMPLATE[52:]}`\n\n{_STOP_LINE}",
        f"{_TEMPLATE.upper()}\n{_STOP_LINE}",
    ],
    ids=["quoted-first", "quoted-after", "quote-wrapped", "quote-in-capitals"],
)
def test_the_skills_own_template_quoted_in_the_answer_is_passed_over(answer):
    """Bug caught (#3154): an answer that quotes its skill before stopping read as stopped by
    the template, so the reason the next proposal is shown was "<criterion> shows itself as
    <effect>"."""
    stop = read_stop(_handed_with_template(), answer)

    assert stop == SkillStop("fixture-design", "scenario-authoring", "no scenario:", _STOP_LINE)


@pytest.mark.parametrize(
    "answer",
    [f"`{_TEMPLATE}`", f"> {_TEMPLATE}\n\nSo I wrote a package criterion.", _TEMPLATE[:40]],
    ids=["template-alone", "quoted-then-overridden", "template-cut-short"],
)
def test_an_answer_holding_only_the_skills_template_holds_no_stop(answer):
    """Bug caught: an answer that quotes its skill's rule and goes round it reading as a stop,
    with the template for its reason."""
    assert read_stop(_handed_with_template(), answer) is None


def test_a_template_filled_in_part_is_the_models_line():
    """A line the skill doesn't show is the model's, placeholders and all: the reader passes
    over the skill's words and judges no others."""
    line = "no scenario: the chime shows itself as <effect>, which fixture/1 can't observe"

    stop = read_stop(_handed_with_template(), f"`{_TEMPLATE}`\n{line}")

    assert stop is not None
    assert stop.line == line


def test_a_handed_skill_whose_front_matter_cant_be_read_raises():
    """Bug caught: a kept copy changed after its load reading as a skill with no stops, so its
    stop is asked again and repaired instead of ending the run."""
    handed = _handed("no scenario:")
    handed[0]["files"]["SKILL.md"] = "no front matter here\n"

    with pytest.raises(FrontmatterError):
        read_stop(handed, _STOP_LINE)


@pytest.mark.parametrize(
    ("skillset", "role", "agent", "contract", "task_type", "line", "skill"),
    [
        (
            "roblox-increment-design",
            "strat",
            "nat",
            "game.increment_design",
            "strategy.propose_increment",
            "no scenario: the pickup chime shows itself as a sound, which roblox-studio/1 "
            "can't observe",
            "play-scenario-authoring",
        ),
        (
            "roblox-luau-dev",
            "dev",
            "neo",
            "game.gameplay_implementation",
            "development.develop",
            "saved data: coins would be renamed to gold",
            "luau-gameplay",
        ),
    ],
    ids=["strategy", "dev"],
)
def test_a_packaged_skills_own_stop_line_is_read_from_what_a_task_is_handed(
    skillset, role, agent, contract, task_type, line, skill
):
    """Entered at the supply a cycle uses. Bug caught: a packaged skill telling the model to
    stop with a line nothing reads (prompt standard rule 7), or declaring a stop under another
    spelling than the one its text shows."""
    catalog = load_skillsets()
    held = catalog[skillset]
    document = kept_document(
        [Assignment(role, agent, skillset, held.version, held.digest)], catalog
    )
    record = {
        "offered": [
            {"agent_id": agent, "contract": contract, "task_type": task_type, "skillset": skillset}
        ]
    }
    handed = skills_input(skills_for(document, record, task_type=task_type, agent_id=agent))

    opening = line.split(":")[0] + ":"
    templates = [
        shown
        for shown in held.skill_files[skill]["SKILL.md"].splitlines()
        if shown.startswith(f"`{opening}")
    ]

    stop = read_stop(handed, f"`{line}`")
    quoting = read_stop(handed, "".join(f"> {shown}\n" for shown in templates) + f"\n`{line}`")

    assert stop == SkillStop(skillset, skill, opening, line)
    assert len(templates) == 1, "the skill shows its stop's line once, on a line of its own"
    assert quoting == stop
    assert read_stop(handed, templates[0]) is None


def test_the_qa_skill_declares_no_stop_and_says_what_comes_first_instead():
    """``roblox-skills-v1`` (SIP-0116 §17r): the QA skill's stop asked for a tree with no runner,
    a state no cycle reaches, since a criterion's spec is placed only under a runner the product
    has. Bug caught: the stop coming back without a case that can reach it, or the skill left
    with nothing to say where the product's specs differ from it (prompt standard rule 7)."""
    from squadops.capabilities.skillsets import skill_stops

    md = load_skillsets()["roblox-studio-qa"].skill_files["luau-test-loader"]["SKILL.md"]

    assert skill_stops(md) == ()
    assert "**The product's own specs come first.**" in md

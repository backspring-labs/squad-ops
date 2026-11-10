"""Every packaged script's answers, through the handlers that will read them (#2892).

The soak's first dry run stopped at its first launch on an answer the proposal handler refused
(it authored the framework's derived fields), and the next refusal would have been found by the
next dry run, one rebuild at a time. This runs each answer through its handler's own parse and
validation (``scripts/dev/llm_script_check.py``) on every script the deploy will serve, so a
script that would be refused fails here instead.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest

from squadops.llm.script import AnswerKey, ScriptedAnswer, ScriptLibrary

pytestmark = [pytest.mark.domain_orchestration]

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def check():
    path = REPO / "scripts" / "dev" / "llm_script_check.py"
    spec = importlib.util.spec_from_file_location("llm_script_check", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_script_check"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ScriptLibrary.packaged().names())
def test_every_packaged_answer_passes_the_handler_that_reads_it(check, name):
    """Bug caught: a recorded answer its handler refuses (a derived field authored, a schema it
    doesn't meet, a brief id it doesn't cite), found by a dry run on a rebuilt deploy instead."""
    assert check.script_problems(ScriptLibrary.packaged().get(name)) == []


def _with_answer(script, key: AnswerKey, content: str):
    answers = {**script.answers, key: ScriptedAnswer(content=content)}
    return dataclasses.replace(script, answers=answers)


def _soak(name="shelfnote-soak-dry-c02"):
    return ScriptLibrary.packaged().get(name)


def test_a_proposal_that_authors_a_derived_field_is_refused(check):
    """The dry run's own failure, on the soak's own proposal: the answer with the framework's
    `content_hash` written back into it."""
    script = _soak()
    key = AnswerKey("strategy.propose_increment", 1, 1)
    content = script.answers[key].content.replace(
        "kind: feature", "content_hash: abc\nkind: feature"
    )

    problems = check.script_problems(_with_answer(script, key, content))

    assert len(problems) == 1
    assert "the framework derives content_hash" in problems[0]


def test_a_proposal_changed_after_its_ruling_is_refused_by_its_recorded_hash(check):
    """Bug caught: an answer that parses but isn't the proposal that was ruled on (a hand edit, a
    re-record against another run), so the replay builds a different increment."""
    script = _soak()
    key = AnswerKey("strategy.propose_increment", 1, 1)
    content = script.answers[key].content.replace("backlog_item: SN-7", "backlog_item: SN-8")

    problems = check.script_problems(_with_answer(script, key, content))

    assert problems and "does not match its hash" in problems[0]


def test_a_plan_proposal_citing_another_brief_is_named(check):
    """The plan proposers refuse a brief id other than their run's brief's."""
    script = _soak()
    key = AnswerKey("development.propose_plan_tasks", 1, 1)
    old = script.answers[key].content
    cited = next(line for line in old.splitlines() if line.startswith("source_brief_id:"))
    content = old.replace(cited, "source_brief_id: brief-elsewhere")

    problems = check.script_problems(_with_answer(script, key, content))

    assert problems == [
        f"{script.reference} {key}: cites brief 'brief-elsewhere', but the brief its run "
        f"writes is {cited.split(': ', 1)[1].strip()!r}"
    ]


def test_an_answer_refused_in_the_recording_too_is_allowed(check):
    """The edge: launch 11's qa answer was prose the handler couldn't extract, in the recording
    as at replay, and the task was asked again. Bug caught: the check refusing a faithful
    replay of a refusal, or allowing that refusal on any other answer."""
    script = _soak("shelfnote-soak-dry-c11")
    refused = AnswerKey("qa.test", 1, 2)
    prose = script.answers[refused].content
    other = AnswerKey("development.develop", 1, 1)

    assert check.script_problems(script) == []
    assert check.script_problems(_with_answer(script, other, prose)) == [
        f"{script.reference} {other}: no fenced file the handler would extract"
    ]

"""The scripted squad's script format and library (#2495).

A script is data an operator writes by hand or records from a run, so each rule the format
enforces is a hand-written mistake that would otherwise surface one task into a cycle, as an
answer at the wrong key or none at all.
"""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

import pytest

from squadops.llm.script import (
    AnswerKey,
    ScriptedAnswer,
    ScriptEntryMissingError,
    ScriptFormatError,
    ScriptLibrary,
    ScriptNotFoundError,
    ScriptReference,
    ScriptVersionMismatchError,
    parse_script,
    script_version,
)

pytestmark = [pytest.mark.domain_orchestration]

SCRIPT = textwrap.dedent(
    """\
    script: frame-twice
    description: a framing re-roll, then a good plan
    replay_latency: true
    answers:
      - task_type: strategy.analyze_prd
        occurrence: 1
        call: 1
        content: "not: [a plan"
        latency_seconds: 2.5
        completion_tokens: 40
      - task_type: strategy.analyze_prd
        occurrence: 2
        call: 1
        content: |
          # Analysis
          The plan.
        prompt_tokens: 900
        completion_tokens: 300
        reasoning_text: weighed two shapes
        termination: stop
    """
).encode()


def _write(directory: Path, name: str, raw: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.yaml"
    path.write_bytes(raw)
    return path


def test_a_script_parses_to_its_answers_by_key_with_every_figure_it_recorded():
    """Bug caught: a field read under the wrong name, so a recorded figure reached the handler as
    None (an unreported token count) or a deliberate bad answer reached the wrong key."""
    script = parse_script(SCRIPT, name="frame-twice")

    assert (script.name, script.version, script.replay_latency) == (
        "frame-twice",
        hashlib.sha256(SCRIPT).hexdigest()[:12],
        True,
    )
    assert dict(script.answers) == {
        AnswerKey("strategy.analyze_prd", 1, 1): ScriptedAnswer(
            content="not: [a plan", latency_seconds=2.5, completion_tokens=40
        ),
        AnswerKey("strategy.analyze_prd", 2, 1): ScriptedAnswer(
            content="# Analysis\nThe plan.\n",
            prompt_tokens=900,
            completion_tokens=300,
            reasoning_text="weighed two shapes",
            termination="stop",
        ),
    }


def test_a_missing_answer_names_the_key_it_looked_for_and_what_the_script_holds():
    """Bug caught: a miss reported without its key, so the operator could not tell which answer
    to add, or a miss answered with a neighbouring entry instead of failing."""
    script = parse_script(SCRIPT, name="frame-twice")

    with pytest.raises(ScriptEntryMissingError) as caught:
        script.answer_for(AnswerKey("strategy.analyze_prd", 2, 2))

    assert str(caught.value) == (
        f"script frame-twice@{script.version} has no answer for strategy.analyze_prd "
        "occurrence 2 call 2 (it holds, for strategy.analyze_prd: occurrence 1 call 1, "
        "occurrence 2 call 1). A scripted call is never answered by a model instead."
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("script: frame-twice", "script: other"), "declares script 'other'"),
        (("task_type: strategy.analyze_prd\n    occurrence: 2", "task_type: strategy.analyse\n    occurrence: 2"), "'strategy.analyse' is not a task type"),
        (("occurrence: 2", "occurrence: 1"), "holds two answers for strategy.analyze_prd occurrence 1 call 1"),
        (("occurrence: 2", "occurrence: 0"), "occurrence must be a whole number from 1"),
        (("termination: stop", "termination: done"), "termination must be one of"),
        (("latency_seconds: 2.5", "latency_seconds: -1"), "latency_seconds must be a non-negative number"),
        (("completion_tokens: 40", "completion_tokens: lots"), "completion_tokens must be a non-negative whole number"),
        (("replay_latency: true", "replay_latency: yes please"), "replay_latency must be true or false"),
        (("    content: \"not: [a plan\"\n", ""), "content must be a string"),
        (("description:", "descripton:"), "unknown keys ['descripton']"),
    ],
)
def test_each_hand_written_mistake_is_refused_naming_it(change, message):
    """Bugs caught: a typo'd task type or duplicate key accepted, leaving a key no call ever
    reaches (the cycle then fails one task in, on a miss that names the wrong cause)."""
    raw = SCRIPT.decode().replace(*change, 1).encode()
    assert raw != SCRIPT

    with pytest.raises(ScriptFormatError, match=message.replace("[", r"\[").replace("]", r"\]")):
        parse_script(raw, name="frame-twice")


def test_the_version_is_the_file_bytes_digest_so_any_edit_changes_it():
    """Bug caught: a version over the parsed answers, so an edit that kept them equal (or a
    reordering) left a cycle's pinned version naming bytes it never ran on."""
    edited = SCRIPT.replace(b"a good plan", b"a better plan")
    assert script_version(SCRIPT) != script_version(edited)
    assert script_version(SCRIPT) == hashlib.sha256(SCRIPT).hexdigest()[:12]


@pytest.mark.parametrize("value", ["frame-twice", "@abc", "frame@", "a@b@c", 7, None])
def test_a_reference_without_both_a_name_and_a_version_is_refused(value):
    with pytest.raises(ScriptFormatError, match="must be '<name>@<version>'"):
        ScriptReference.parse(value)


def test_the_library_resolves_only_the_version_it_holds(tmp_path):
    """Bug caught: an agent built from another tree answering a cycle pinned to a different
    version, so the record names answers the cycle did not run on."""
    _write(tmp_path, "frame-twice", SCRIPT)
    library = ScriptLibrary(tmp_path)
    held = script_version(SCRIPT)

    assert library.resolve(ScriptReference("frame-twice", held)).version == held
    with pytest.raises(ScriptVersionMismatchError, match=f"holds frame-twice@{held}"):
        library.resolve(ScriptReference("frame-twice", "0123456789ab"))


def test_the_library_refuses_a_name_it_does_not_hold_or_one_outside_its_directory(tmp_path):
    _write(tmp_path, "frame-twice", SCRIPT)
    library = ScriptLibrary(tmp_path)

    with pytest.raises(ScriptNotFoundError, match=r"holds \['frame-twice'\]"):
        library.get("frame-thrice")
    with pytest.raises(ScriptNotFoundError, match="is not a script name"):
        library.get("../frame-twice")


def test_an_absent_library_holds_nothing_and_its_digest_changes_with_any_script(tmp_path):
    """Bug caught: the deploy record's scripted digest unchanged when a script was edited, so two
    deploys answering differently read as the same."""
    library = ScriptLibrary(tmp_path / "none")
    assert library.names() == []
    empty = library.digest()

    _write(tmp_path / "none", "frame-twice", SCRIPT)
    one = library.digest()
    _write(tmp_path / "none", "frame-twice", SCRIPT + b"# edited\n")

    assert len({empty, one, library.digest()}) == 3

"""A skill's named stop, read from a model's answer (SIP-0116 §17o; prompt standard rule 7).

A skill may tell the model to refuse a task its equipment can't do honestly, and to say why in
one line: a criterion whose effect the scenario reader can't observe, a product with no test
runner. The skill declares that line's opening words in its front matter (``stops``), and this
is the one place an answer is read for them. A seam handed skills asks it when its own parser
found nothing to accept, so the reason reaches whoever reads the run and the model isn't asked
again to do what its skill told it to refuse.

Core holds no skill's words: it reads what the task's handed skills declare.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from squadops.capabilities.skillsets import SKILL_FILE, skill_stops
from squadops.llm.exceptions import LLMError

#: What a model puts around a line it was shown in inline code or a list: stripped from both
#: ends before the line is compared, and never from inside it.
_DECORATION = " \t>-*_`"

_INLINE_CODE = re.compile(r"`([^`\n]+)`")


@dataclass(frozen=True)
class SkillStop:
    """One declared stop found in an answer: the skill that declares it, and the line."""

    skillset: str
    skill: str
    #: The declared opening words, as the skill's front matter writes them.
    opening: str
    #: The whole line as the model wrote it, without the decoration around it.
    line: str

    @property
    def reason(self) -> str:
        """What follows the opening words."""
        return self.line[len(self.opening) :].strip()

    def describe(self) -> str:
        return describe_stop(self.to_dict())

    def to_dict(self) -> dict[str, str]:
        """The stop as a task's context and its result's evidence carry it."""
        return {
            "skillset": self.skillset,
            "skill": self.skill,
            "opening": self.opening,
            "line": self.line,
        }


def describe_stop(stop: Mapping[str, str]) -> str:
    """One sentence naming a carried stop (``SkillStop.to_dict``), for a task's or a run's
    failure reason."""
    return f"stopped by the skill {stop['skillset']}/{stop['skill']}: {stop['line']}"


class SkillStopped(LLMError):
    """The model answered with a stop one of the task's skills declares. Raised by
    ``_llm_call``, as a failed call is, so every seam's own ``except LLMError`` ends its task
    without parsing the answer or asking again."""

    def __init__(self, stop: SkillStop) -> None:
        super().__init__(stop.describe())
        self.stop = stop


def _bare(raw: str) -> str:
    """A line without the decoration around it."""
    line = raw.strip(_DECORATION)
    if line.endswith("`."):
        # The line quoted in inline code at the end of a sentence.
        line = line[:-2].rstrip(_DECORATION)
    return line


def _shown(skill_md: str, opening: str) -> tuple[str, ...]:
    """The skill's own showings of a stop it declares, casefolded: each line and each inline-code
    span of its text that opens with ``opening``. They are the skill's words (its template, with
    the placeholders the model is to fill), and a model that quotes its skill writes them too."""
    opens = opening.casefold()
    candidates = [_bare(line) for line in skill_md.splitlines()]
    candidates += [span.strip() for span in _INLINE_CODE.findall(skill_md)]
    return tuple({c.casefold() for c in candidates if c.casefold().startswith(opens)})


def read_stop(handed: Sequence[Mapping[str, Any]] | None, response: str | None) -> SkillStop | None:
    """The first line of ``response`` that opens with a stop one of the task's ``handed`` skills
    declares and is the model's own, or ``None``. ``handed`` is the task's ``SKILLS_INPUT``.

    A line is compared without the decoration around it and without regard to case, since a
    model shown the line in inline code may write it in a list or with a capital. An opening
    with nothing after it is no stop: the line exists to carry a reason.

    A line the skill itself shows is the skill quoted, whole or cut short where the quote
    wrapped, and it is passed over (#3154): a model quotes the rule before it applies it, and
    the template's placeholders are no reason. An answer whose only such line is the quote
    holds no stop.

    Raises:
        FrontmatterError: A handed skill's ``SKILL.md`` has no readable front matter. The
            skillset's load refused that, so a kept copy holding one was changed afterwards.
    """
    if not handed or not response:
        return None
    declared = [
        (str(skill["skillset"]), str(skill["skill"]), opening, _shown(text, opening))
        for skill in handed
        for text in (skill["files"][SKILL_FILE],)
        for opening in skill_stops(text)
    ]
    if not declared:
        return None
    for raw in response.splitlines():
        line = _bare(raw)
        folded = line.casefold()
        for skillset, skill, opening, shown in declared:
            if not folded.startswith(opening.casefold()) or not line[len(opening) :].strip():
                continue
            if any(quoted.startswith(folded) for quoted in shown):
                continue
            return SkillStop(skillset, skill, opening, line)
    return None

"""The skills replay's cases, and what each authoring is judged by (SIP-0116 §7, §17p; Q47).

A skill is tested on the models that will run it before any profile requires it. A case is a
captured task (by its type), the skillset whose skills it is handed, any swaps that put another
task in front of the same seam, and what the skills arm's answer is expected to be. The judgement
reads the handler's own verdict on the answer and the stop its skills declare: nothing here
parses an answer by a rule of its own.

Pure: the in-container runner authors, and the host runner reads the records.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import yaml

#: The cases file's first line names it and its version, as a rubric's does (#2313), so an
#: experiment's manifest pins the text it was run with.
_HEADER = re.compile(r"# Skill cases `(?P<name>[^`@]+)@(?P<version>[^`]+)`")
_CASE_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
_CASE_FIELDS = frozenset(
    {"id", "task_type", "skillset", "vocabulary_skillset", "swaps", "expect", "why"}
)
#: What a skills arm's answer may be expected to be. ``stop`` stands alone: a stopped task
#: emits nothing.
EXPECTATIONS = ("stop", "accepted", "emits", "scenario_criterion", "specs_pass")
CHANGE_REQUEST = "change_request.yaml"

MET = "met"
NOT_MET = "not_met"
#: An expectation nothing was run for (a spec run with no product checkout). Never a pass.
NOT_JUDGED = "not_judged"


class SkillCasesError(ValueError):
    """The cases file can't be read as written."""


@dataclass(frozen=True)
class SkillCase:
    id: str
    task_type: str
    skillset: str
    expect: Mapping[str, Any]
    vocabulary_skillset: str = ""
    swaps: tuple[Mapping[str, Any], ...] = ()
    #: What the case is there to show, for whoever reads the record.
    why: str = ""

    def notes(self) -> dict[str, Any]:
        """What an experiment's manifest freezes of the case."""
        return {
            "case": self.id,
            "skillset": self.skillset,
            "vocabulary_skillset": self.vocabulary_skillset,
            "swaps": [dict(s) for s in self.swaps],
            "expect": dict(self.expect),
        }


@dataclass(frozen=True)
class SkillCases:
    name: str
    version: str
    cases: tuple[SkillCase, ...] = field(default_factory=tuple)

    @property
    def id(self) -> str:
        return f"{self.name}@{self.version}"


def read_cases(text: str) -> SkillCases:
    """The cases ``text`` holds. Every defect is named: a case read with a field dropped would
    run as another case under its name."""
    header = _HEADER.fullmatch(text.partition("\n")[0].strip())
    if header is None:
        raise SkillCasesError("the first line is `# Skill cases `<name>@<version>``")
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SkillCasesError(f"not valid YAML: {exc}") from exc
    raw = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(raw, list) or not raw:
        raise SkillCasesError("`cases` is a list of at least one case")
    errors: list[str] = []
    cases = [_case(n, entry, errors) for n, entry in enumerate(raw, start=1)]
    ids = [c.id for c in cases if c is not None]
    errors.extend(f"case {i} is given twice" for i in sorted({i for i in ids if ids.count(i) > 1}))
    if errors:
        raise SkillCasesError("; ".join(errors))
    return SkillCases(header["name"], header["version"], tuple(c for c in cases if c is not None))


def _case(n: int, entry: Any, errors: list[str]) -> SkillCase | None:
    if not isinstance(entry, dict):
        errors.append(f"case {n} is a mapping")
        return None
    where = f"case {entry.get('id') or n}"
    before = len(errors)
    unknown = sorted(set(entry) - _CASE_FIELDS)
    if unknown:
        errors.append(f"{where}: unknown fields {', '.join(unknown)}")
    for key in ("id", "task_type", "skillset"):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            errors.append(f"{where}: {key} is a name")
    if isinstance(entry.get("id"), str) and not _CASE_ID.fullmatch(entry["id"]):
        errors.append(f"{where}: an id is lower-case letters, digits and hyphens")
    swaps = entry.get("swaps") or []
    if not isinstance(swaps, list) or not all(
        isinstance(s, dict) and isinstance(s.get("path"), list) for s in swaps
    ):
        errors.append(f"{where}: swaps is a list of mappings, each with a path")
    errors.extend(f"{where}: {e}" for e in expectation_errors(entry.get("expect")))
    if len(errors) > before:
        return None
    return SkillCase(
        id=entry["id"],
        task_type=entry["task_type"],
        skillset=entry["skillset"],
        expect=dict(entry["expect"]),
        vocabulary_skillset=str(entry.get("vocabulary_skillset") or ""),
        swaps=tuple(swaps),
        why=str(entry.get("why") or "").strip(),
    )


def expectation_errors(expect: Any) -> list[str]:
    """What is wrong with a case's ``expect`` as written, or ``[]``."""
    if not isinstance(expect, dict) or not expect:
        return [f"expect names at least one of {', '.join(EXPECTATIONS)}"]
    errors = [f"expect: unknown {k}" for k in sorted(set(expect) - set(EXPECTATIONS))]
    if "stop" in expect:
        if not isinstance(expect["stop"], str) or not expect["stop"].endswith(":"):
            errors.append("expect: stop is a declared stop's opening words, ending in a colon")
        if len(expect) > 1:
            errors.append("expect: stop stands alone, since a stopped task emits nothing")
    for key in ("accepted", "scenario_criterion", "specs_pass"):
        if key in expect and expect[key] is not True:
            errors.append(f"expect: {key} is true, or left out")
    if "emits" in expect and (
        not isinstance(expect["emits"], list)
        or not expect["emits"]
        or not all(isinstance(g, str) and g for g in expect["emits"])
    ):
        errors.append("expect: emits is a list of path patterns")
    return errors


def judge(
    expect: Mapping[str, Any],
    record: Mapping[str, Any],
    *,
    specs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One authoring record against its case's expectation: ``{"verdict", "findings"}``.

    ``record`` is the runner's: the handler's ``success``, its ``artifacts`` and the declared
    stop its model answered with (``skill_stop``). ``specs`` is the result of running the
    record's emitted specs on the product, where they were run: ``{"passed": [...], "failed":
    [...]}`` as the product's own reader read them.

    Every expectation is checked and every miss is named. One that nothing was run for makes
    the verdict ``not_judged``, never ``met``."""
    findings = _stop_findings(expect, record)
    unjudged: list[str] = []
    artifacts = [str(a.get("name") or "") for a in record.get("artifacts") or ()]
    if any(k in expect for k in ("accepted", "emits", "scenario_criterion", "specs_pass")):
        if not record.get("success"):
            findings.append(f"the handler refused the answer: {record.get('error')}")
    for pattern in expect.get("emits") or ():
        if not any(fnmatch.fnmatchcase(name, pattern) for name in artifacts):
            findings.append(
                f"no emitted file matches {pattern} (emitted: {', '.join(artifacts) or 'none'})"
            )
    if expect.get("scenario_criterion"):
        findings.extend(_scenario_findings(record))
    if expect.get("specs_pass"):
        if specs is None:
            unjudged.append("specs_pass: the emitted specs were not run on the product")
        else:
            findings.extend(_spec_findings(specs))
    verdict = NOT_MET if findings else NOT_JUDGED if unjudged else MET
    return {"verdict": verdict, "findings": findings + unjudged}


def _stop_findings(expect: Mapping[str, Any], record: Mapping[str, Any]) -> list[str]:
    """The declared stop the answer was, against the one expected, or against none."""
    stop = record.get("skill_stop")
    if "stop" not in expect:
        return [f"the task was stopped by its skill: {stop.get('line')}"] if stop else []
    if not stop:
        return [f"no declared stop was read; expected one opening {expect['stop']!r}"]
    if str(stop.get("opening")).casefold() != str(expect["stop"]).casefold():
        return [
            f"the stop read opens {stop.get('opening')!r}, not {expect['stop']!r}: "
            f"{stop.get('line')}"
        ]
    return []


def _spec_findings(specs: Mapping[str, Any]) -> list[str]:
    passed, failed = specs.get("passed") or (), specs.get("failed") or ()
    if failed or not passed:
        return [
            f"the emitted specs ran with {len(passed)} passing and {len(failed)} failing"
            + (": " + ", ".join(str(f) for f in failed) if failed else "")
        ]
    return []


def _scenario_findings(record: Mapping[str, Any]) -> list[str]:
    """The accepted change request holds a scenario criterion. The rails already read each one
    strictly against the vocabulary before the handler accepted it, so this only counts them."""
    document = next(
        (
            a.get("content")
            for a in record.get("artifacts") or ()
            if a.get("name") == CHANGE_REQUEST
        ),
        None,
    )
    if document is None:
        return [f"no {CHANGE_REQUEST} was accepted"]
    try:
        request = yaml.safe_load(document)
    except yaml.YAMLError as exc:
        return [f"the accepted {CHANGE_REQUEST} doesn't read as YAML: {exc}"]
    criteria: Sequence[Any] = request.get("criteria") or () if isinstance(request, dict) else ()
    kinds = [str(c.get("surface_kind")) for c in criteria if isinstance(c, dict)]
    if "scenario" not in kinds:
        return [f"no criterion is a scenario (kinds: {', '.join(kinds) or 'none'})"]
    return []

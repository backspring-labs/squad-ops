"""The skills replay's cases, and what each authoring is judged by (SIP-0116 §7, §17p; Q47).

A skill is tested on the models that will run it before any profile requires it. A case is a
captured task (by its type), the skillset whose skills it is handed, any swaps that put another
task in front of the same seam, and what the skills arm's answer is expected to be. The judgement
reads the handler's own verdict on the answer and the stop its skills declare. One expectation,
``scenario_rules`` (§17y), also reads the accepted change request by rules its case states before
the run: the gate's rules, which the handler doesn't hold.

Pure: the in-container runner authors, and the host runner reads the records.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import yaml

from squadops.campaigns.acceptance import DiscriminationReason
from squadops.campaigns.change_request import SurfaceKind
from squadops.remote_execution.scenario import ABSENT, Expectation, ExpectOp, expectation_met

#: The cases file's first line names it and its version, as a rubric's does (#2313), so an
#: experiment's manifest pins the text it was run with.
_HEADER = re.compile(r"# Skill cases `(?P<name>[^`@]+)@(?P<version>[^`]+)`")
_CASE_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
_CASE_FIELDS = frozenset(
    {"id", "task_type", "skillset", "vocabulary_skillset", "swaps", "expect", "why"}
)
#: What a skills arm's answer may be expected to be, by the cases file's key. A stop stands
#: alone: a stopped task emits nothing.
EXPECT_STOP = "stop"
EXPECT_ACCEPTED = "accepted"
EXPECT_EMITS = "emits"
EXPECT_EMITS_EXPECTED = "emits_expected"
EXPECT_SCENARIO_CRITERION = "scenario_criterion"
EXPECT_SPECS_PASS = "specs_pass"
EXPECT_DISCRIMINATES = "discriminates"
#: The fourth skills replay (#3199; the 2.8.1 plan's item 4): the gate's rules, read by rule from the
#: accepted change request against the facts its case states. Its value is those facts.
EXPECT_SCENARIO_RULES = "scenario_rules"
EXPECTATIONS = (
    EXPECT_STOP,
    EXPECT_ACCEPTED,
    EXPECT_EMITS,
    EXPECT_EMITS_EXPECTED,
    EXPECT_SCENARIO_CRITERION,
    EXPECT_SPECS_PASS,
    EXPECT_DISCRIMINATES,
    EXPECT_SCENARIO_RULES,
)
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
    if EXPECT_STOP in expect:
        if not isinstance(expect[EXPECT_STOP], str) or not expect[EXPECT_STOP].endswith(":"):
            errors.append("expect: stop is a declared stop's opening words, ending in a colon")
        if len(expect) > 1:
            errors.append("expect: stop stands alone, since a stopped task emits nothing")
    for key in (
        EXPECT_ACCEPTED,
        EXPECT_EMITS_EXPECTED,
        EXPECT_SCENARIO_CRITERION,
        EXPECT_SPECS_PASS,
        EXPECT_DISCRIMINATES,
    ):
        if key in expect and expect[key] is not True:
            errors.append(f"expect: {key} is true, or left out")
    if EXPECT_SCENARIO_RULES in expect:
        errors.extend(scenario_rules_errors(expect[EXPECT_SCENARIO_RULES]))
    if EXPECT_EMITS in expect and (
        not isinstance(expect[EXPECT_EMITS], list)
        or not expect[EXPECT_EMITS]
        or not all(isinstance(g, str) and g for g in expect[EXPECT_EMITS])
    ):
        errors.append("expect: emits is a list of path patterns")
    return errors


def judge(
    expect: Mapping[str, Any],
    record: Mapping[str, Any],
    *,
    specs: Mapping[str, Any] | None = None,
    baseline_attributes: Collection[str] | None = None,
) -> dict[str, Any]:
    """One authoring record against its case's expectation: ``{"verdict", "findings"}``.

    ``record`` is the runner's: the handler's ``success``, its ``artifacts``, the files its task
    expected (``expected_artifacts``, the task's own input), the declared stop its model answered
    with (``skill_stop``), and whether its suite was left to the product's own runner
    (``left_to_the_product_runner``). Such a task comes back unsuccessful with no verdict of its
    own, so its acceptance is what the product's runner reads of its specs. ``specs`` is the
    result of running the record's emitted specs on the product, where they were run: ``{"passed": [...], "failed":
    [...]}`` as the product's own reader read them. ``baseline_attributes`` are the attribute
    names the product's checkout sets, where one was given: a product's code stays in its own
    repository, so the cases file only says the rule applies.

    Every expectation is checked and every miss is named. One that nothing was run for makes
    the verdict ``not_judged``, never ``met``."""
    findings = _stop_findings(expect, record)
    unjudged: list[str] = []
    artifacts = [str(a.get("name") or "") for a in record.get("artifacts") or ()]
    handed_off = bool(record.get("left_to_the_product_runner"))
    if any(k in expect for k in EXPECTATIONS if k != EXPECT_STOP):
        if not record.get("success") and not handed_off:
            findings.append(f"the handler refused the answer: {record.get('error')}")
    for pattern in expect.get(EXPECT_EMITS) or ():
        if not any(fnmatch.fnmatchcase(name, pattern) for name in artifacts):
            findings.append(
                f"no emitted file matches {pattern} (emitted: {', '.join(artifacts) or 'none'})"
            )
    if expect.get(EXPECT_EMITS_EXPECTED):
        findings.extend(_expected_findings(record, artifacts))
    if expect.get(EXPECT_SCENARIO_CRITERION):
        findings.extend(_scenario_findings(record))
    if EXPECT_SCENARIO_RULES in expect:
        rules = expect[EXPECT_SCENARIO_RULES]
        findings.extend(scenario_rule_findings(rules, record, baseline_attributes))
        if rules.get(BASELINE_ATTRIBUTES) and baseline_attributes is None:
            unjudged.append(
                "scenario_rules: the baseline's attributes were not read (no product checkout)"
            )
    # What only the product's own runner can say. #3150: a suite the qa image left to that
    # runner (SIP-0112 H.26) has no verdict of its own, so its acceptance is read there too.
    for name, wanted, read in (
        (EXPECT_ACCEPTED, bool(expect.get(EXPECT_ACCEPTED)) and handed_off, _spec_findings),
        (EXPECT_SPECS_PASS, bool(expect.get(EXPECT_SPECS_PASS)), _spec_findings),
        (EXPECT_DISCRIMINATES, bool(expect.get(EXPECT_DISCRIMINATES)), _discrimination_findings),
    ):
        if not wanted:
            continue
        if specs is None:
            unjudged.append(f"{name}: the emitted specs were not run on the product")
        else:
            findings.extend(f for f in read(specs) if f not in findings)
    verdict = NOT_MET if findings else NOT_JUDGED if unjudged else MET
    return {"verdict": verdict, "findings": findings + unjudged}


def _stop_findings(expect: Mapping[str, Any], record: Mapping[str, Any]) -> list[str]:
    """The declared stop the answer was, against the one expected, or against none."""
    stop = record.get("skill_stop")
    if EXPECT_STOP not in expect:
        return [f"the task was stopped by its skill: {stop.get('line')}"] if stop else []
    wanted = str(expect[EXPECT_STOP])
    if not stop:
        return [f"no declared stop was read; expected one opening {wanted!r}"]
    if str(stop.get("opening")).casefold() != wanted.casefold():
        return [f"the stop read opens {stop.get('opening')!r}, not {wanted!r}: {stop.get('line')}"]
    return []


def _expected_findings(record: Mapping[str, Any], artifacts: Sequence[str]) -> list[str]:
    """Each file the task itself expected is among the files the handler accepted. A capture
    taken again brings another proposal and another plan, so a captured case names no file of
    its own. A task that expected none has nothing to be held to, and says so."""
    expected = [str(e) for e in record.get("expected_artifacts") or ()]
    if not expected:
        return ["the task expected no file, so there is none to hold its answer to"]
    return [
        f"the task expected {name}, and it was not emitted "
        f"(emitted: {', '.join(artifacts) or 'none'})"
        for name in expected
        if name not in artifacts
    ]


def _discrimination_findings(specs: Mapping[str, Any]) -> list[str]:
    """Each emitted spec proves its change by the Campaign's own rule: the reason
    ``discrimination_on_runner`` gave for it, run before the change and after. No spec judged is
    a finding, never a pass."""
    reasons = specs.get("discrimination") or {}
    if not reasons:
        return ["no emitted spec was run before and after its change"]
    return [
        f"{spec} doesn't prove its change: {reason}"
        for spec, reason in sorted(reasons.items())
        if reason != DiscriminationReason.DISCRIMINATES
    ]


def _spec_findings(specs: Mapping[str, Any]) -> list[str]:
    passed, failed = specs.get("passed") or (), specs.get("failed") or ()
    if failed or not passed:
        return [
            f"the emitted specs ran with {len(passed)} passing and {len(failed)} failing"
            + (": " + ", ".join(str(f) for f in failed) if failed else "")
        ]
    return []


def _accepted_request(record: Mapping[str, Any]) -> tuple[dict | None, str | None]:
    """The accepted change request as a mapping, or why there is none."""
    document = next(
        (
            a.get("content")
            for a in record.get("artifacts") or ()
            if a.get("name") == CHANGE_REQUEST
        ),
        None,
    )
    if document is None:
        return None, f"no {CHANGE_REQUEST} was accepted"
    try:
        request = yaml.safe_load(document)
    except yaml.YAMLError as exc:
        return None, f"the accepted {CHANGE_REQUEST} doesn't read as YAML: {exc}"
    if not isinstance(request, dict):
        return None, f"the accepted {CHANGE_REQUEST} isn't a mapping"
    return request, None


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
    if SurfaceKind.SCENARIO not in kinds:
        return [f"no criterion is a scenario (kinds: {', '.join(kinds) or 'none'})"]
    return []


# ---------------------------------------------------------------------------------------------
# The fourth skills replay: the gate's rules, by rule (#3199; the 2.8.1 plan's item 4)
#
# The revised scenario skill makes each criterion answer the gate's questions in fixed words, and
# the window's returns were each one of these mistakes. A case states what the rules are read
# against: the item's sentences, what the baseline sets, what no action reaches, which values
# change, and what the broken and correct builds show where the named check reads. Nothing here
# plays: a reading is the text or value a build shows at the named check's path, written in the
# case before the run. The plays on the case's candidates are the other half (by play).

_RULE_KEYS = frozenset(
    {"sentences", "headless_half", "unreachable", "baseline_attributes", "changing", "named"}
)
_MATCH_KEYS = frozenset({"kind", "path", "name", "state", "context"})
#: The fixed words each criterion's ``observable`` answers the gate in (the revised skill's
#: "Before you submit"). A package criterion is headless, every other kind is played.
PLAYED, HEADLESS, FAILS_ON, BAND, NOT_PLAYED = (
    "Played.",
    "Headless.",
    "Fails on:",
    "Band:",
    "Not played:",
)
BASELINE_ATTRIBUTES = "baseline_attributes"


def scenario_rules_errors(rules: Any) -> list[str]:
    """What is wrong with a case's ``scenario_rules`` as written, or ``[]``."""
    if not isinstance(rules, dict) or not rules:
        return ["expect: scenario_rules names the facts its rules are read against"]
    errors = [f"scenario_rules: unknown {k}" for k in sorted(set(rules) - _RULE_KEYS)]
    for n, sentence in enumerate(rules.get("sentences") or (), start=1):
        terms = sentence.get("read_by") if isinstance(sentence, dict) else None
        if (
            not isinstance(sentence, dict)
            or not isinstance(sentence.get("says"), str)
            or not (
                isinstance(terms, list) and terms and all(isinstance(t, str) and t for t in terms)
            )
        ):
            errors.append(f"scenario_rules: sentence {n} is {{says, read_by: [terms]}}")
    if "headless_half" in rules and rules["headless_half"] is not True:
        errors.append("scenario_rules: headless_half is true, or left out")
    for key in ("unreachable", "changing"):
        for n, match in enumerate(rules.get(key) or (), start=1):
            if not isinstance(match, dict) or not match or set(match) - _MATCH_KEYS:
                errors.append(
                    f"scenario_rules: {key} {n} matches by {', '.join(sorted(_MATCH_KEYS))}"
                )
    if BASELINE_ATTRIBUTES in rules and rules[BASELINE_ATTRIBUTES] is not True:
        errors.append(
            "scenario_rules: baseline_attributes is true, or left out: the names are read from "
            "the product's checkout, never written here"
        )
    for n, named in enumerate(rules.get("named") or (), start=1):
        errors.extend(f"scenario_rules: named {n} {e}" for e in _named_entry_errors(named))
    return errors


def _named_entry_errors(named: Any) -> list[str]:
    if not isinstance(named, dict) or not isinstance(named.get("match"), dict):
        return ["is {match, fails_on, passes_on}"]
    errors = []
    if set(named["match"]) - _MATCH_KEYS:
        errors.append(f"matches by {', '.join(sorted(_MATCH_KEYS))}")
    for key, what in (("fails_on", "broken"), ("passes_on", "correct")):
        if not isinstance(named.get(key), list) or not named[key]:
            errors.append(f"lists the readings {what} builds show ({key})")
    return errors


def _matches(match: Mapping[str, Any], observe: Mapping[str, Any]) -> bool:
    return all(
        fnmatch.fnmatchcase(str(observe.get(key)), str(pattern)) for key, pattern in match.items()
    )


def meets(expect: Mapping[str, Any], reading: Any) -> bool:
    """Whether ``reading`` meets ``expect`` by the scenario reader's own rule
    (``remote_execution.scenario.expectation_met``). A ``null`` reading is an absent value. An
    expectation the reader wouldn't read meets nothing."""
    try:
        expectation = Expectation(ExpectOp(str(expect.get("op"))), expect.get("value"))
    except ValueError:
        return False
    return expectation_met(expectation, ABSENT if reading is None else reading)


def _observations(scenario: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    """Every observation a scenario makes: its waits, in setup and steps, and its assertions."""
    found: list[tuple[str, Mapping[str, Any]]] = []
    for part in ("setup", "steps"):
        for n, action in enumerate(scenario.get(part) or (), start=1):
            if isinstance(action, dict) and isinstance(action.get("observe"), dict):
                found.append((f"{part} {n}", action["observe"]))
    for assertion in scenario.get("assertions") or ():
        if isinstance(assertion, dict) and isinstance(assertion.get("observe"), dict):
            found.append((f"assertion {assertion.get('id')}", assertion["observe"]))
    return found


def _named(scenario: Mapping[str, Any]) -> Mapping[str, Any] | None:
    wanted = scenario.get("named_assertion")
    return next(
        (
            a
            for a in scenario.get("assertions") or ()
            if isinstance(a, dict) and a.get("id") == wanted
        ),
        None,
    )


def scenario_rule_findings(
    rules: Mapping[str, Any],
    record: Mapping[str, Any],
    baseline_attributes: Collection[str] | None = None,
) -> list[str]:
    """Every rule the accepted change request breaks, against its case's facts. The attribute
    rule is read only where the baseline's attributes are given."""
    request, missing = _accepted_request(record)
    if request is None:
        return [str(missing)]
    criteria = [c for c in request.get("criteria") or () if isinstance(c, dict)]
    #: What the change says it adds, so an attribute it names isn't read as one nothing sets.
    said = yaml.safe_dump(request.get("prd_delta") or "").casefold()
    findings: list[str] = []
    for c in criteria:
        findings.extend(_word_findings(c))
        scenario = c.get("scenario") if isinstance(c.get("scenario"), dict) else None
        if scenario is not None:
            attrs = baseline_attributes if rules.get(BASELINE_ATTRIBUTES) else None
            findings.extend(_reach_findings(rules, c, scenario, said, attrs))
            findings.extend(_changing_findings(rules, c, scenario))
    findings.extend(_named_findings(rules, criteria))
    findings.extend(_coverage_findings(rules, criteria))
    if rules.get("headless_half") and not any(
        str(c.get("surface_kind")) == SurfaceKind.PACKAGE for c in criteria
    ):
        findings.append("no criterion is headless, and part of the item is a state no play reaches")
    return findings


def _observable(criterion: Mapping[str, Any]) -> str:
    return " ".join(str(criterion.get("observable") or "").split())


def _word_findings(c: Mapping[str, Any]) -> list[str]:
    """The criterion answers the gate in the skill's fixed words."""
    cid, kind, observable = c.get("id"), str(c.get("surface_kind")), _observable(c)
    opening = HEADLESS if kind == SurfaceKind.PACKAGE else PLAYED
    findings = []
    if not observable.startswith(opening):
        findings.append(f"{cid}: its observable doesn't open {opening!r}")
    if FAILS_ON not in observable:
        findings.append(f"{cid}: its observable names no broken build ({FAILS_ON!r})")
    if kind == SurfaceKind.PACKAGE and NOT_PLAYED not in observable:
        findings.append(f"{cid}: a headless criterion doesn't say what no play reached")
    return findings


def _reach_findings(
    rules: Mapping[str, Any],
    c: Mapping[str, Any],
    scenario: Mapping[str, Any],
    said: str,
    attrs: Collection[str] | None,
) -> list[str]:
    """No wait or observation names a state no action reaches, or a value nothing sets."""
    cid, findings = c.get("id"), []
    for where, observe in _observations(scenario):
        what = f"{observe.get('path')} {observe.get('name') or observe.get('state')}"
        if any(_matches(m, observe) for m in rules.get("unreachable") or ()):
            findings.append(f"{cid}: {where} reads {what}, which no action reaches")
        name = str(observe.get("name") or "")
        if (
            attrs is not None
            and observe.get("kind") == "attribute"
            and name not in attrs
            and name.casefold() not in said
        ):
            findings.append(
                f"{cid}: {where} reads the attribute {name}, which the baseline doesn't set and "
                "the change doesn't say it adds"
            )
    return findings


def _changing_findings(
    rules: Mapping[str, Any], c: Mapping[str, Any], scenario: Mapping[str, Any]
) -> list[str]:
    """A named check on a value that changes reads a band, and says where it starts."""
    named = _named(scenario)
    if named is None:
        return [f"{c.get('id')}: its named assertion isn't one of its assertions"]
    if not any(_matches(m, named.get("observe") or {}) for m in rules.get("changing") or ()):
        return []
    findings = []
    if (named.get("expect") or {}).get("op") == ExpectOp.EQUALS:
        findings.append(f"{c.get('id')}: its named check is an exact match on a value that changes")
    if BAND not in _observable(c):
        findings.append(
            f"{c.get('id')}: its named check reads a value that changes, with no {BAND!r}"
        )
    return findings


def _named_findings(rules: Mapping[str, Any], criteria: Sequence[Mapping[str, Any]]) -> list[str]:
    """Each named check the case states readings for rejects every broken reading and accepts a
    correct one; and some criterion's named check reads each such surface."""
    findings: list[str] = []
    for entry in rules.get("named") or ():
        readers = []
        for c in criteria:
            scenario = c.get("scenario") if isinstance(c.get("scenario"), dict) else None
            named = _named(scenario) if scenario else None
            if named and _matches(entry["match"], named.get("observe") or {}):
                readers.append((c.get("id"), named.get("expect") or {}))
        if not readers:
            findings.append(f"no criterion's named check reads {_described(entry['match'])}")
        for cid, expect in readers:
            passed = [r for r in entry["fails_on"] if meets(expect, r)]
            if passed:
                findings.append(
                    f"{cid}: its named check passes on a broken build reading "
                    + ", ".join("<absent>" if r is None else repr(r) for r in passed)
                )
            if not any(meets(expect, r) for r in entry["passes_on"]):
                findings.append(
                    f"{cid}: its named check passes on no reading a correct build shows"
                )
    return findings


def _coverage_findings(
    rules: Mapping[str, Any], criteria: Sequence[Mapping[str, Any]]
) -> list[str]:
    text = " ".join(
        f"{c.get('statement') or ''} {c.get('observable') or ''}" for c in criteria
    ).casefold()
    return [
        f"no criterion reads the item's sentence {s['says']!r}"
        for s in rules.get("sentences") or ()
        if not any(term.casefold() in text for term in s["read_by"])
    ]


def _described(match: Mapping[str, Any]) -> str:
    return " ".join(f"{k}={v}" for k, v in sorted(match.items()))

"""A suite's markers: the step values a held-out scenario must never be seen outside its store with
(SIP-0113 §4.1; the 2.4 window's P2 sweep; §10t ruling 3; §10ad).

A marker is a string a step sends (its ``json``, ``headers``, its path's segments and query string,
a browser step's typed ``value`` and the ``text`` it finds a control by) or a check expects
(``equals``, ``in``, ``contains``, ``where``, the literal text of a ``pattern``), at least
``MIN_LEN`` characters with a letter in it. The goal is not a marker: goals are visible by design
(D2(1)), and a proposal is shown them (§4.5).

Two things a suite writes are names, not values (§10ad; #2786):
- **A saved value's reference,** ``{name}`` (§10ab). A string that is one reference is no marker,
  wherever it is. A string that mixes text and references gives each run of its text between them,
  stripped, since the rendered value holds those runs and never the reference. A pattern's
  references are read the same way.
- **A declared route's words.** A step's path is read segment by segment. A segment at a literal
  word of a route the scenario's surfaces declare for the step (an ``http`` step's endpoints, a
  ``visit``'s pages) is public by design, when that route fits the path: as many segments, each of
  its words equal. A path no declared route fits is read whole, every segment that isn't a
  reference a value.

One definition for both readers: the P2 sweep (``scripts/dev/heldout_sweep.py``) searches the deploy
for every marker, and the proposal's evidence holds back a goal that contains one, since a goal that
quotes a step's value would carry it to the proposer (§10t ruling 3). The draft-time public check
and the pre-push scan read the sweep's.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from squadops.campaigns.increment_tree import route_param
from squadops.scenarios.models import Scenario, SurfaceKind
from squadops.scenarios.steps import PLACEHOLDER

#: A shorter value is too likely to be a word anyone would write.
MIN_LEN = 6


def forms(value: str) -> list[str]:
    """``value`` as each store writes it: as is, JSON-escaped (ASCII and not), and each of those
    with COPY's doubled backslashes. Distinct, in that order."""
    out: list[str] = []
    for form in (value, json.dumps(value)[1:-1], json.dumps(value, ensure_ascii=False)[1:-1]):
        for f in (form, form.replace("\\", "\\\\")):
            if f not in out:
                out.append(f)
    return out


def _strings(value: Any) -> Iterator[str]:
    """Every string leaf of ``value``. A mapping's keys are names (a concept, a field), not values."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list | tuple):
        for v in value:
            yield from _strings(v)


def _literals(text: str) -> list[str]:
    """The values in a string a step or a check renders: the string itself when it names no saved
    value, nothing when it is one name, and otherwise each run of its text between the names,
    stripped (§10ad)."""
    parts = PLACEHOLDER.split(text)
    if len(parts) == 1:
        return [text]
    return [run.strip() for run in parts[::2] if run.strip()]


def _texts(values: Iterable[Any]) -> list[str]:
    return [literal for value in values for text in _strings(value) for literal in _literals(text)]


#: The surfaces whose routes a step's path is read against, by the step's action.
_ROUTE_KINDS = {"http": SurfaceKind.HTTP_ENDPOINT, "visit": SurfaceKind.PAGE}


def _segments(path: str) -> list[str]:
    return [segment for segment in path.split("/") if segment]


def _routes(scenario: Scenario, action: Any) -> list[list[str]]:
    """The routes the scenario declares for a step of ``action``, each as its segments."""
    kind = _ROUTE_KINDS.get(action) if isinstance(action, str) else None
    return [_segments(s.path) for s in scenario.surfaces if s.kind is kind]


def _route_words(segments: list[str], routes: list[list[str]]) -> set[int]:
    """The positions in ``segments`` where a route that fits them has a literal word. A route fits
    a path with as many segments whose words, but not its parameters (``route_param``), are equal."""
    public: set[int] = set()
    for route in routes:
        if len(route) != len(segments):
            continue
        words = {i for i, word in enumerate(route) if route_param(word) is None}
        if all(route[i] == segments[i] for i in words):
            public |= words
    return public


def _path_values(path: Any, routes: list[list[str]]) -> list[str]:
    """A step path's values, decoded: each segment that isn't a fitting route's word, and each
    query value, read as ``_literals`` reads a string."""
    if not isinstance(path, str):
        return []
    split = urlsplit(path)
    segments = _segments(split.path)
    public = _route_words(segments, routes)
    values = [unquote(s) for i, s in enumerate(segments) if i not in public]
    values += [v for _, v in parse_qsl(split.query, keep_blank_values=False)]
    return [literal for value in values for literal in _literals(value)]


#: A pattern's characters that aren't literal text (SIP-0113 §10p ruling 9).
_PATTERN_SYNTAX = frozenset(".^$*+?()[]{}|")
_GROUP_PREFIX = re.compile(r"\(\?(?:[:=!]|<[=!])")


def _literal_runs(pattern: Any) -> list[str]:
    """The literal text inside a browser check's pattern, run by run: an escaped punctuation mark
    is its own character, and a class (``\\d``, ``\\s``) or any other syntax ends a run. So a run
    title a scenario looks for is a marker, and the pattern's syntax around it isn't. A saved
    value's reference ends a run too, and is none (§10ad): it's rendered as the value, escaped."""
    if not isinstance(pattern, str):
        return []
    return [run for piece in PLACEHOLDER.split(pattern)[::2] for run in _runs(piece)]


def _runs(pattern: str) -> list[str]:
    pattern = _GROUP_PREFIX.sub("(", pattern)  # (?: (?= (?! (?<= (?<! open a group, nothing else
    runs: list[str] = []
    run: list[str] = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            nxt = pattern[i + 1]
            if nxt.isalnum():
                runs.append("".join(run))
                run = []
            else:
                run.append(nxt)
            i += 2
            continue
        if c in _PATTERN_SYNTAX:
            runs.append("".join(run))
            run = []
        else:
            run.append(c)
        i += 1
    runs.append("".join(run))
    return [r.strip() for r in runs if r.strip()]


def _browser_values(item: Any) -> list[Any]:
    """What a browser step types (``value``), and the text a step or a check finds its control by
    (``text``, its ``near``'s included). Never a target's candidate names: they are drafted from the
    deliveries' own labels (§10p ruling 3), so a delivery holding one is no leak."""
    found: list[Any] = [item.get("value")]
    target = item.get("target")
    while isinstance(target, dict):
        found.append(target.get("text"))
        target = target.get("near")
    return found


def distinctive(value: str) -> bool:
    stripped = value.strip()
    return len(stripped) >= MIN_LEN and any(c.isalpha() for c in stripped)


def suite_markers(suite: Any) -> dict[str, tuple[str, str]]:
    """Each distinct marker of ``suite`` (a ``ScenarioSuite``), by its value: the first scenario
    and the step or check it was found in."""
    found: dict[str, tuple[str, str]] = {}
    for scenario in suite.scenarios:
        sources: list[tuple[str, list[str]]] = []
        for n, step in enumerate(scenario.steps, start=1):
            routes = _routes(scenario, step.get("action"))
            sent = [step.get("json"), step.get("headers"), *_browser_values(step)]
            sources += [
                (f"step {n}", _texts(sent)),
                (f"step {n}", _path_values(step.get("path"), routes)),
            ]
        for n, check in enumerate(scenario.checks, start=1):
            expected = [check.get(k) for k in ("equals", "in", "contains", "where")]
            patterns = [check.get("pattern"), *(check.get("patterns") or ())]
            sources += [
                (f"check {n}", _texts([*expected, *_browser_values(check)])),
                (f"check {n}", [run for p in patterns for run in _literal_runs(p)]),
            ]
        for where, texts in sources:
            for text in texts:
                if distinctive(text):
                    found.setdefault(text, (scenario.scenario_id, where))
    return found


def carries_a_marker(text: str, markers: Iterable[str]) -> bool:
    """Whether ``text`` holds any of ``markers`` in any form a store writes it in."""
    return any(form in text for marker in markers for form in forms(marker))

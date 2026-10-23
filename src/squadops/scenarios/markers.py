"""A suite's markers: the step values a held-out scenario must never be seen outside its store with
(SIP-0113 §4.1; the 2.4 window's P2 sweep; §10t ruling 3).

A marker is a string a step sends (its ``json``, ``headers`` and query string, a browser step's typed
``value`` and the ``text`` it finds a control by) or a check expects (``equals``, ``in``,
``contains``, ``where``, the literal text of a ``pattern``), at least ``MIN_LEN`` characters with a
letter in it. The goal is not a marker: goals are visible by design (D2(1)), and a proposal is shown
them (§4.5).

One definition for both readers: the P2 sweep (``scripts/dev/heldout_sweep.py``) searches the deploy
for every marker, and the proposal's evidence holds back a goal that contains one, since a goal that
quotes a step's value would carry it to the proposer (§10t ruling 3).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from typing import Any
from urllib.parse import parse_qsl, urlsplit

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


def _query_values(path: Any) -> list[str]:
    if not isinstance(path, str) or "?" not in path:
        return []
    return [v for _, v in parse_qsl(urlsplit(path).query, keep_blank_values=False)]


#: A pattern's characters that aren't literal text (SIP-0113 §10p ruling 9).
_PATTERN_SYNTAX = frozenset(".^$*+?()[]{}|")
_GROUP_PREFIX = re.compile(r"\(\?(?:[:=!]|<[=!])")


def _literal_runs(pattern: Any) -> list[str]:
    """The literal text inside a browser check's pattern, run by run: an escaped punctuation mark
    is its own character, and a class (``\\d``, ``\\s``) or any other syntax ends a run. So a run
    title a scenario looks for is a marker, and the pattern's syntax around it isn't."""
    if not isinstance(pattern, str):
        return []
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
        sources: list[tuple[str, Any]] = []
        for n, step in enumerate(scenario.steps, start=1):
            sources += [
                (f"step {n}", step.get("json")),
                (f"step {n}", step.get("headers")),
                (f"step {n}", _query_values(step.get("path"))),
                *((f"step {n}", v) for v in _browser_values(step)),
            ]
        for n, check in enumerate(scenario.checks, start=1):
            sources += [(f"check {n}", check.get(k)) for k in ("equals", "in", "contains", "where")]
            sources += [(f"check {n}", v) for v in _browser_values(check)]
            patterns = [check.get("pattern"), *(check.get("patterns") or ())]
            sources += [(f"check {n}", _literal_runs(p)) for p in patterns]
        for where, value in sources:
            for text in _strings(value):
                if distinctive(text):
                    found.setdefault(text, (scenario.scenario_id, where))
    return found


def carries_a_marker(text: str, markers: Iterable[str]) -> bool:
    """Whether ``text`` holds any of ``markers`` in any form a store writes it in."""
    return any(form in text for marker in markers for form in forms(marker))

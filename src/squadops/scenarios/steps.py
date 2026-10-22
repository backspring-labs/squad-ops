"""The runner's vocabulary: how a scenario's held-out steps and checks run over HTTP (SIP-0113
§4.1; #2414).

A scenario sets up its own data in its own steps: a step's response can ``save`` values under
names that later steps and checks use, as ``{name}`` in a path or a string. After its steps, its
checks read the responses. Pure: a scenario runs through a ``send`` the caller supplies, so the
runner's adapter owns the network and this owns what a result means.

**A step:** ``{"action": "http", "method": "POST", "path": "/runs/{run_id}/participants",
"json": {...}, "save": {"run_id": "id"}, "expect_status": 201}``. A transport failure, a status
other than its ``expect_status``, or a ``save`` its response can't answer fails the scenario at
that step.

**A check:** ``{"check": "status", "step": 3, "equals": 409}`` (or ``"in": [400, 422]``), or ``{"check": "json", "step": 4,
"path": "participants.0.name", "equals": "Ada"}`` (or ``"length": 1``, or ``"contains": ...``, or
``"where": {"title": "Riverside 10K"}``: some element of the list has every field named equal).
Steps are numbered from 1.

**A browser step** (§10k, §10p): ``{"action": "visit", "path": "/runs/{run_id}"}``,
``{"action": "fill", "target": {...}, "value": "Ada"}`` or ``{"action": "click", "target": {...}}``.
A target is found the way a user finds it: ``{"role": "button", "names": ["Join", "Join run"]}``,
the first candidate name that matches any element, exactly after case-folding; ``near`` names
another target the control must share a form with, and ``text`` a substring its text contains.
A maximal run of browser steps is one **segment**, which begins with ``visit`` and goes to
``browse`` whole, rendered with the values saved so far, with the checks that read its steps.
Values flow one way: a value substituted into a pattern is escaped, so it matches as written.

**A browser check** reads the page right after its step: ``{"check": "text", "step": 3,
"pattern": "2\\s*/\\s*5"}``, ``absent`` (the same, matching nothing), ``count`` (``target``,
``equals``), ``order`` (``target``, ``patterns``: elements matching each appear in that order) or
``control`` (``target``, ``is``: ``unavailable`` when absent, hidden or disabled, or ``enabled``).

A step the runner has no vocabulary for is ``blocked_unverified``: ``no_runner``, or for a
browser's action ``browser_unavailable`` when no browser runs (A2). A control none of a step's names
finds is ``control_absent``: the page's counterpart of ``surface_absent``, never failed (§10p
ruling 4). A malformed browser step is refused when a suite is drafted or approved
(``vocabulary_refusals``), never when it runs or is read.
"""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from squadops.scenarios.evaluation import ScenarioResult

_VAR = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
#: §10p ruling 10: ``page`` and ``browser`` were reserved for a browser and are no runner's.
_BROWSER_ACTIONS = frozenset({"visit", "fill", "click"})
_BROWSER_CHECKS = frozenset({"text", "absent", "count", "order", "control"})
_PATTERN_CHECKS = frozenset({"text", "absent"})
_HTTP_CHECKS = frozenset({"status", "json"})
CONTROL_STATES = ("unavailable", "enabled")
#: How the browser says a step ended (§10p ruling 1). ``done`` is the only one that carries on.
STEP_OUTCOMES = ("done", "not_found", "action_failed", "timeout", "page_broken")


@dataclass(frozen=True)
class HttpRequest:
    method: str
    path: str
    json: Any = None
    headers: Mapping[str, str] | None = None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: Any  # the parsed JSON, or the text when it isn't JSON


Send = Callable[[HttpRequest], Awaitable[HttpResponse]]


@dataclass(frozen=True)
class BrowseRequest:
    """One segment for the browser: its steps from ``first_step`` on, rendered, and the checks
    that read them, each by its index among the scenario's checks."""

    first_step: int
    steps: tuple[Mapping[str, Any], ...]
    checks: tuple[tuple[int, Mapping[str, Any]], ...] = ()


@dataclass(frozen=True)
class BrowseStep:
    """How one step ended: one of ``STEP_OUTCOMES``, what the browser saw when it didn't, and how
    long it took. The detail is the browser's own text, so it goes to the evidence only, never to
    a scenario's detail (§10p ruling 1)."""

    step: int
    outcome: str
    detail: str | None = None
    seconds: float = 0.0


@dataclass(frozen=True)
class BrowseCheck:
    """Whether one check held, by its index, and what the page showed when it didn't."""

    index: int
    holds: bool
    seen: str | None = None


@dataclass(frozen=True)
class BrowseAnswer:
    steps: tuple[BrowseStep, ...]
    checks: tuple[BrowseCheck, ...] = ()
    #: The runner that answered: the evaluator's tag and the browser's version (§10p ruling 6).
    browser: str | None = None
    #: The first failed or blocked step's or check's evidence, as the browser keeps it (§10p
    #: ruling 8; ``squadops.scenarios.evidence``): held out, so never in a detail.
    evidence: Mapping[str, Any] | None = None


class BrowserUnavailable(Exception):
    """No browser answered the segment: its container didn't start, ran out of time or wrote no
    answer. The scenario is ``browser_unavailable``, never failed."""


Browse = Callable[[BrowseRequest], Awaitable[BrowseAnswer]]


@dataclass(frozen=True)
class ScenarioRun:
    """How one scenario's run ended. ``result`` is ``passed``, ``failed`` or ``blocked_unverified``,
    the vocabulary ``squadops.scenarios.evaluation.ScenarioResult`` holds."""

    scenario_id: str
    result: str
    blocked_reason: str | None = None
    steps_taken: int = 0
    first_failing_step: int | None = None
    elapsed_seconds: float = 0.0
    detail: str | None = None
    #: §10p ruling 7: what ran the browser steps (the evaluator's tag and the browser's version),
    #: or ``None`` for a scenario with none, and each step's seconds, in step order.
    runner: str | None = None
    step_seconds: tuple[float, ...] = ()
    #: §10p ruling 8: a run that didn't pass carries its browser's evidence to the store, held out
    #: and capped by the sandbox (``squadops.scenarios.evidence.kept``). Never an outcome's.
    evidence: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "result": self.result,
            "blocked_reason": self.blocked_reason,
            "steps_taken": self.steps_taken,
            "first_failing_step": self.first_failing_step,
            "elapsed_seconds": self.elapsed_seconds,
            "detail": self.detail,
            "runner": self.runner,
            "step_seconds": list(self.step_seconds),
            "evidence": dict(self.evidence) if self.evidence is not None else None,
        }


class _Missing(Exception):
    pass


def _render(value: Any, names: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        whole = _VAR.fullmatch(value)
        if whole:  # a value that is one name keeps the saved value's own type
            return _lookup(names, whole.group(1))
        return _VAR.sub(lambda m: str(_lookup(names, m.group(1))), value)
    if isinstance(value, list):
        return [_render(v, names) for v in value]
    if isinstance(value, dict):
        return {k: _render(v, names) for k, v in value.items()}
    return value


def _render_pattern(pattern: Any, names: Mapping[str, Any]) -> Any:
    """A pattern with saved values in it, each escaped (§10p ruling 1): a saved title with ``(``
    or ``+`` in it matches as written, rather than breaking or widening the pattern."""
    if isinstance(pattern, str):
        return _VAR.sub(lambda m: re.escape(str(_lookup(names, m.group(1)))), pattern)
    if isinstance(pattern, list):
        return [_render_pattern(p, names) for p in pattern]
    return pattern


def _render_check(check: Mapping[str, Any], names: Mapping[str, Any]) -> dict[str, Any]:
    return {
        k: _render_pattern(v, names) if k in ("pattern", "patterns") else _render(v, names)
        for k, v in check.items()
    }


def _lookup(names: Mapping[str, Any], name: str) -> Any:
    if name not in names:
        raise _Missing(f"no saved value {name!r}")
    return names[name]


def extract(body: Any, path: str) -> Any:
    """A dotted path into a JSON body: ``participants.0.name``. ``""`` is the body itself."""
    value = body
    for part in [p for p in path.split(".") if p]:
        if isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise _Missing(f"the response has no {path!r}")
    return value


def _check(check: Mapping[str, Any], responses: Mapping[int, HttpResponse]) -> str | None:
    """None when the check holds, else what it saw. Raises LookupError for a check the runner
    can't read (an unknown kind, or a step that didn't run). ``responses`` are by step number, so
    a browser step between two HTTP steps shifts nothing."""
    kind, step = check.get("check"), check.get("step")
    if not isinstance(step, int) or step not in responses:
        raise LookupError(f"a check names step {step!r}, which didn't run")
    response = responses[step]
    if kind == "status":
        # ``in`` (#2464): the PRD says a request is "rejected" and each delivery's manifest picks
        # the status, 422 on the canonical stack and 400 on Next.js, so a check may accept several.
        allowed = check["in"] if "in" in check else [check.get("equals")]
        return (
            None
            if response.status in allowed
            else (f"step {step} answered {response.status}, not {' or '.join(map(str, allowed))}")
        )
    if kind != "json":
        raise LookupError(f"no runner for check {kind!r}")
    try:
        value = extract(response.body, str(check.get("path", "")))
    except _Missing as e:
        return f"step {step}: {e}"
    if "equals" in check:
        return None if value == check["equals"] else f"{check.get('path')!r} is {value!r}"
    if "length" in check:
        size = len(value) if isinstance(value, (list, str, dict)) else None
        return None if size == check["length"] else f"{check.get('path')!r} has length {size}"
    if "contains" in check:
        held = isinstance(value, (list, str)) and check["contains"] in value
        return None if held else f"{check.get('path')!r} doesn't contain {check['contains']!r}"
    if "where" in check:
        # #2464: "a created run appears in the list" names the run, not its place in the list,
        # and an element carries fields beyond the ones a scenario can know.
        wanted = check["where"]
        if not isinstance(wanted, Mapping) or not wanted:
            raise LookupError("a where check names the fields an element must have")
        held = isinstance(value, list) and any(
            isinstance(element, Mapping)
            and all(key in element and element[key] == want for key, want in wanted.items())
            for element in value
        )
        if held:
            return None
        size = len(value) if isinstance(value, list) else None
        return f"{check.get('path')!r} ({size} elements) has none with {dict(wanted)!r}"
    raise LookupError("a json check names equals, length, contains or where")


async def run_scenario(
    scenario: Mapping[str, Any], send: Send, browse: Browse | None = None
) -> ScenarioRun:
    """One scenario's steps, then its checks, against a started app. Each segment of browser steps
    goes to ``browse`` with the checks that read it (§10p rulings 1 and 2); with no ``browse``, a
    browser step is ``browser_unavailable``. Checks are reported in their order after every step
    has run, so a step's failure ends the scenario first."""
    run = _Run(scenario)
    steps = run.steps
    number = 1
    while number <= len(steps):
        if steps[number - 1].get("action") in _BROWSER_ACTIONS:
            last = number
            while last < len(steps) and steps[last].get("action") in _BROWSER_ACTIONS:
                last += 1
            ended = await run.segment(range(number, last + 1), browse)
            number = last + 1
        else:
            ended = await run.http(number, send)
            number += 1
        if ended is not None:
            return ended
    return run.checked()


class _Run:
    """One scenario's run in progress: the values its steps saved, the HTTP responses by step
    number, each browser check's reading by its index, and how many steps it took."""

    def __init__(self, scenario: Mapping[str, Any]) -> None:
        self.scenario_id = str(scenario["scenario_id"])
        self.steps = list(scenario["steps"])
        self.checks = list(scenario["checks"])
        self.started = time.monotonic()
        self.names: dict[str, Any] = {}
        self.responses: dict[int, HttpResponse] = {}
        #: A browser check's reading, by its index: ``None`` when it held, else what it saw.
        self.read: dict[int, str | None] = {}
        self.taken = 0
        self.seconds: list[float] = []
        self.runner: str | None = None
        self.evidence: Mapping[str, Any] | None = None

    def ended(self, result: str, **kw) -> ScenarioRun:
        return ScenarioRun(
            self.scenario_id,
            result,
            steps_taken=self.taken,
            elapsed_seconds=round(time.monotonic() - self.started, 3),
            runner=self.runner,
            step_seconds=tuple(self.seconds),
            evidence=None if result == ScenarioResult.PASSED else self.evidence,
            **kw,
        )

    def blocked(self, reason: str, detail: str) -> ScenarioRun:
        return self.ended("blocked_unverified", blocked_reason=reason, detail=detail)

    def failed(self, step: int, detail: str) -> ScenarioRun:
        return self.ended("failed", first_failing_step=step, detail=detail)

    async def http(self, number: int, send: Send) -> ScenarioRun | None:
        step = self.steps[number - 1]
        if step.get("action") != "http":
            return self.blocked("no_runner", f"step {number}")
        try:
            request = HttpRequest(
                method=str(step.get("method", "GET")).upper(),
                path=_render(str(step["path"]), self.names),
                json=_render(step.get("json"), self.names),
                headers=_render(step.get("headers"), self.names),
            )
        except (_Missing, KeyError) as e:
            return self.failed(number, f"step {number}: {e}")
        sent = time.monotonic()
        try:
            response = await send(request)
        except OSError as e:
            return self.failed(number, f"step {number}: {e}")
        finally:
            self.seconds.append(round(time.monotonic() - sent, 3))
        self.responses[number] = response
        self.taken += 1
        expected = step.get("expect_status")
        if expected is not None and response.status != expected:
            return self.failed(number, f"step {number} answered {response.status}, not {expected}")
        try:
            for name, path in (step.get("save") or {}).items():
                self.names[name] = extract(response.body, str(path))
        except _Missing as e:
            return self.failed(number, f"step {number} answered {response.status}: {e}")
        return None

    async def segment(self, segment: range, browse: Browse | None) -> ScenarioRun | None:
        if browse is None:
            return self.blocked("browser_unavailable", f"step {segment.start}")
        request = self._request(segment)
        if isinstance(request, ScenarioRun):
            return request
        try:
            answer = await browse(request)
        except BrowserUnavailable as e:
            return self.blocked("browser_unavailable", f"step {segment.start}: {e}")
        self.runner = self.runner or answer.browser
        self.evidence = self.evidence or answer.evidence
        outcomes = {o.step: o for o in answer.steps}
        for n in segment:
            outcome = outcomes.get(n)
            if outcome is None:
                return self.blocked(
                    "browser_unavailable", f"step {n}: the browser didn't answer it"
                )
            self.seconds.append(round(outcome.seconds, 3))
            if outcome.outcome == "not_found":
                return self.blocked("control_absent", f"step {n}")
            if outcome.outcome != "done":
                # The browser's own text stays in the evidence: it can quote the page (ruling 1).
                return self.failed(n, f"step {n} {outcome.outcome}")
            self.taken += 1
        for c in answer.checks:
            self.read[c.index] = None if c.holds else (c.seen or f"check {c.index + 1} didn't hold")
        return None

    def _request(self, segment: range) -> BrowseRequest | ScenarioRun:
        """The segment rendered with the values saved so far, and the checks that read it."""
        steps = []
        for n in segment:
            try:
                steps.append(_render(dict(self.steps[n - 1]), self.names))
            except _Missing as e:
                return self.failed(n, f"step {n}: {e}")
        reads = []
        for index, check in enumerate(self.checks):
            if check.get("check") in _BROWSER_CHECKS and check.get("step") in segment:
                try:
                    reads.append((index, _render_check(check, self.names)))
                except _Missing as e:
                    return self.failed(int(check["step"]), f"check {index + 1}: {e}")
        return BrowseRequest(segment.start, tuple(steps), tuple(reads))

    def checked(self) -> ScenarioRun:
        for index, check in enumerate(self.checks):
            if check.get("check") in _BROWSER_CHECKS:
                if index not in self.read:
                    return self.blocked("browser_unavailable", f"check {index + 1} wasn't read")
                seen = self.read[index]
            else:
                try:
                    seen = _check(check, self.responses)
                except LookupError as e:
                    return self.blocked("no_runner", str(e))
            if seen is not None:
                return self.failed(int(check["step"]), seen)
        return self.ended("passed")


def drives_a_browser(steps: Sequence[Mapping[str, Any]]) -> bool:
    """Whether a scenario has a browser step, so its page surfaces are checked against the
    delivery's routes before anything runs (§10p ruling 4)."""
    return any(step.get("action") in _BROWSER_ACTIONS for step in steps)


def vocabulary_refusals(
    steps: Sequence[Mapping[str, Any]], checks: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Every way a scenario's browser steps and its checks are malformed (§10p rulings 2, 3 and 9),
    each by its step or check and never by a value, since a value is held out. Read when a suite is
    drafted or approved, never when one runs or is read, so a rule added later can't make an
    approved suite unreadable."""
    actions = {n: step.get("action") for n, step in enumerate(steps, start=1)}
    return _step_refusals(steps, actions) + _check_refusals(checks, actions)


def _step_refusals(steps: Sequence[Mapping[str, Any]], actions: Mapping[int, Any]) -> list[str]:
    out: list[str] = []
    for n, step in enumerate(steps, start=1):
        action = actions[n]
        if action not in _BROWSER_ACTIONS:
            continue
        if action != "visit" and actions.get(n - 1) not in _BROWSER_ACTIONS:
            out.append(f"step {n}: a run of browser steps begins with visit")
        if action == "visit":
            path = step.get("path")
            if not isinstance(path, str) or not path.startswith("/"):
                out.append(f"step {n}: visit names a path from '/'")
            continue
        out += [f"step {n}: {why}" for why in _target_refusals(step.get("target"), named=True)]
        if action == "fill" and not isinstance(step.get("value"), str):
            out.append(f"step {n}: fill names the text it types")
    return out


def _check_refusals(checks: Sequence[Mapping[str, Any]], actions: Mapping[int, Any]) -> list[str]:
    out: list[str] = []
    for i, check in enumerate(checks, start=1):
        kind, raw = check.get("check"), check.get("step")
        step = (
            raw if isinstance(raw, int) and not isinstance(raw, bool) and raw in actions else None
        )
        if kind in _HTTP_CHECKS:
            # An HTTP check that names no step it can read stays as it was: blocked when it runs.
            if step is not None and actions[step] in _BROWSER_ACTIONS:
                out.append(
                    f"check {i}: a {kind} check reads an HTTP step, and step {step} isn't one"
                )
            continue
        if kind not in _BROWSER_CHECKS:
            continue  # a kind no runner reads is blocked when it runs, as before
        if step is None:
            out.append(f"check {i}: names a step the scenario has")
        elif actions[step] not in _BROWSER_ACTIONS:
            out.append(f"check {i}: a {kind} check reads a browser step, and step {step} isn't one")
        out += [f"check {i}: {why}" for why in _browser_check_refusals(kind, check)]
    return out


def _browser_check_refusals(kind: Any, check: Mapping[str, Any]) -> list[str]:
    if kind in _PATTERN_CHECKS:
        return _pattern_refusals(check.get("pattern"), "pattern")
    if kind == "count":
        equals = check.get("equals")
        size = isinstance(equals, int) and not isinstance(equals, bool) and equals >= 0
        return _target_refusals(check.get("target"), named=False) + (
            [] if size else ["count names how many elements it expects"]
        )
    if kind == "order":
        patterns = check.get("patterns")
        if not isinstance(patterns, list) or len(patterns) < 2:
            return ["order names two patterns or more"]
        return _target_refusals(check.get("target"), named=False) + [
            why for p in patterns for why in _pattern_refusals(p, "each of patterns")
        ]
    if kind == "control":
        state = [] if check.get("is") in CONTROL_STATES else [f"control is one of {CONTROL_STATES}"]
        return _target_refusals(check.get("target"), named=True) + state
    return []


def _target_refusals(target: Any, *, named: bool, inner: bool = False) -> list[str]:
    """A control is found by its role and the names a user reads (§10p ruling 3). An action's
    target names them; a check's may name only its role and a ``text``."""
    if not isinstance(target, Mapping):
        return ["a target is a mapping with a role"]
    out = []
    if not isinstance(target.get("role"), str) or not target["role"]:
        out.append("a target names its role")
    names = target.get("names")
    if names is not None or named:
        if not (isinstance(names, list) and names and all(isinstance(n, str) and n for n in names)):
            out.append("a target's names are a non-empty list of text")
    if "text" in target and not (isinstance(target["text"], str) and target["text"]):
        out.append("a target's text is non-empty text")
    if "near" in target:
        if inner:
            out.append("a near target has no near of its own")
        else:
            out += [
                f"its near {why}"
                for why in _target_refusals(target["near"], named=True, inner=True)
            ]
    return out


#: Python's syntax a browser's JavaScript pattern reads otherwise or not at all: named groups and
#: comments, ``\A`` and ``\Z`` (which JavaScript reads as the letters), and a leading flag group.
_NOT_JAVASCRIPT = re.compile(r"\(\?P[<=]|\(\?#|\\[AZ]|\(\?[aiLmsux]+\)")


def _pattern_refusals(pattern: Any, what: str) -> list[str]:
    """A pattern compiles here and reads the same in the browser, which runs it as JavaScript."""
    if not isinstance(pattern, str) or not pattern:
        return [f"{what} is non-empty text"]
    try:
        re.compile(_VAR.sub("x", pattern))
    except re.error:
        return [f"{what} isn't a pattern"]
    if _NOT_JAVASCRIPT.search(pattern):
        return [f"{what} uses Python's syntax, which the browser reads otherwise"]
    return []

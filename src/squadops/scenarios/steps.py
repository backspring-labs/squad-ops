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

A step the runner has no vocabulary for is ``blocked_unverified``: ``no_runner``, or for a
browser's action ``browser_unavailable`` until the evaluator's image runs pages (A2).
"""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

_VAR = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_BROWSER_ACTIONS = frozenset({"page", "browser", "click", "fill", "visit"})


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "result": self.result,
            "blocked_reason": self.blocked_reason,
            "steps_taken": self.steps_taken,
            "first_failing_step": self.first_failing_step,
            "elapsed_seconds": self.elapsed_seconds,
            "detail": self.detail,
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


def _check(check: Mapping[str, Any], responses: list[HttpResponse]) -> str | None:
    """None when the check holds, else what it saw. Raises LookupError for a check the runner
    can't read (an unknown kind, or a step that didn't run)."""
    kind, step = check.get("check"), check.get("step")
    if not isinstance(step, int) or not 1 <= step <= len(responses):
        raise LookupError(f"a check names step {step!r}, which didn't run")
    response = responses[step - 1]
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


async def run_scenario(scenario: Mapping[str, Any], send: Send) -> ScenarioRun:
    """One scenario's steps, then its checks, against a started app."""
    scenario_id = str(scenario["scenario_id"])
    started = time.monotonic()
    names: dict[str, Any] = {}
    responses: list[HttpResponse] = []

    def ended(result: str, **kw) -> ScenarioRun:
        return ScenarioRun(
            scenario_id,
            result,
            steps_taken=len(responses),
            elapsed_seconds=round(time.monotonic() - started, 3),
            **kw,
        )

    for number, step in enumerate(scenario["steps"], start=1):
        action = step.get("action")
        if action != "http":
            reason = "browser_unavailable" if action in _BROWSER_ACTIONS else "no_runner"
            return ended("blocked_unverified", blocked_reason=reason, detail=f"step {number}")
        try:
            request = HttpRequest(
                method=str(step.get("method", "GET")).upper(),
                path=_render(str(step["path"]), names),
                json=_render(step.get("json"), names),
                headers=_render(step.get("headers"), names),
            )
        except (_Missing, KeyError) as e:
            return ended("failed", first_failing_step=number, detail=f"step {number}: {e}")
        try:
            response = await send(request)
        except OSError as e:
            return ended("failed", first_failing_step=number, detail=f"step {number}: {e}")
        responses.append(response)
        expected = step.get("expect_status")
        if expected is not None and response.status != expected:
            return ended(
                "failed",
                first_failing_step=number,
                detail=f"step {number} answered {response.status}, not {expected}",
            )
        try:
            for name, path in (step.get("save") or {}).items():
                names[name] = extract(response.body, str(path))
        except _Missing as e:
            return ended(
                "failed",
                first_failing_step=number,
                detail=f"step {number} answered {response.status}: {e}",
            )
    for check in scenario["checks"]:
        try:
            seen = _check(check, responses)
        except LookupError as e:
            return ended("blocked_unverified", blocked_reason="no_runner", detail=str(e))
        if seen is not None:
            return ended("failed", first_failing_step=int(check["step"]), detail=seen)
    return ended("passed")

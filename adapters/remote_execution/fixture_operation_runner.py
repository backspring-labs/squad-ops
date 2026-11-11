"""The fixture provider: one operation that reads a declared scenario against a staged world
(SIP-0117 R5.5, R5.8; #3044).

It drives no tool. It is what a worker runs to prove the path from a queued operation to an
accepted result without an engine, and its results are real readings of the request:

- **``fixture/declared_scenario``** runs a frozen scenario under the ``fixture/1`` vocabulary
  (``VOCABULARY``: the same actions and observations as the Studio harness's, under its own
  reader). It refuses before anything runs, as ``not_executed``, a declaration whose text isn't
  the frozen one, is for another reader, or doesn't read under the vocabulary.
- **The world it observes** is the staged ``.fixture/world.json``: per context (``server``,
  ``client``), each instance path with its ``properties``, ``attributes``, ``gui`` states and
  ``value``. A path or a name the world doesn't hold observes ``absent``, which executes. A
  world that is missing or unreadable is ``not_executed``, with why.
- **The world is still.** Actions are recorded in the evidence and change nothing. A setup
  ``wait_until`` whose expectation isn't met means the scenario's world wasn't established, so
  every assertion reads ``setup_failed``.
- **A staged ``.fixture/hold_seconds``** makes the operation wait that many seconds first, so a
  rehearsal can watch a lease renew and a cancel arrive. A value that isn't a number of seconds
  is ``not_executed``, with the value.
"""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from squadops.ports.remote_execution import OperationRunnerPort
from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    EvidenceItem,
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.remote_execution.scenario import (
    ABSENT,
    Action,
    Expectation,
    ExpectOp,
    Observation,
    ScenarioDeclaration,
    ScenarioVocabulary,
    expectation_met,
    handed_scenario_defects,
)
from squadops.remote_execution.workers import ServedOperation
from squadops.runtime.models import RuntimeStatus

PROVIDER = "fixture"
OPERATION = "declared_scenario"
VERSION = "2"
HOLD_PATH = ".fixture/hold_seconds"
WORLD_PATH = ".fixture/world.json"
RUN_LOG_NAME = "declared_scenario_run.json"

#: The fixture's reader. A provider ships its vocabulary as data beside its code (R4.6).
VOCABULARY = ScenarioVocabulary.from_document(
    {
        "reader": "fixture/1",
        "contexts": ["server", "client"],
        "actions": {
            "click_gui": {"path": "text"},
            "hold_key": {"key": "text", "seconds": "seconds"},
            "move_to": {"point": "point", "deadline_s": "seconds"},
            "wait_until": {
                "observe": "observation",
                "expect": "expectation",
                "deadline_s": "seconds",
            },
        },
        "observations": {
            "property": {"path": "text", "name": "text"},
            "attribute": {"path": "text", "name": "text"},
            "gui_state": {"path": "text", "state": "text"},
            "value": {"path": "text"},
        },
    }
)

_WORLD_SECTIONS = {"property": "properties", "attribute": "attributes", "gui_state": "gui"}


class FixtureOperationRunner(OperationRunnerPort):
    def __init__(self, *, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._sleep = sleep

    def serves(self) -> tuple[ServedOperation, ...]:
        return (ServedOperation(PROVIDER, OPERATION),)

    async def tool_versions(self) -> Mapping[str, str]:
        return {PROVIDER: VERSION, "reader": VOCABULARY.reader}

    async def health(self) -> RuntimeStatus:
        return "online"

    async def reset(self) -> None:
        """Nothing to reset: the fixture keeps nothing between operations."""

    async def run(self, request: RemoteOperationRequest) -> RemoteOperationResult:
        if (request.provider, request.operation) != (PROVIDER, OPERATION):
            return self._not_executed(
                request,
                f"the fixture provider runs {PROVIDER}/{OPERATION}, and was asked for "
                f"{request.provider}/{request.operation}",
            )
        declaration, defects = handed_scenario_defects(request.scenario, VOCABULARY)
        if declaration is None:
            return self._not_executed(request, "the scenario can't be run: " + "; ".join(defects))
        try:
            world = _world(request.source_files)
        except ValueError as unreadable:
            return self._not_executed(request, str(unreadable))
        if HOLD_PATH in request.source_files:
            held = request.source_files[HOLD_PATH]
            try:
                seconds = float(held)
            except ValueError:
                seconds = math.nan
            if not math.isfinite(seconds) or seconds < 0:
                return self._not_executed(
                    request, f"{HOLD_PATH} is {held!r}, which isn't a number of seconds"
                )
            await self._sleep(seconds)
        records, log = _play(declaration, world)
        return RemoteOperationResult(
            status=OperationStatus.COMPLETED,
            records=records,
            evidence=(EvidenceItem(RUN_LOG_NAME, json.dumps(log, indent=2), "application/json"),),
            provider_version=f"{PROVIDER}@{VERSION}",
            ran_with={PROVIDER: VERSION, "reader": VOCABULARY.reader},
            dispatch_id=request.dispatch_id,
        )

    def _not_executed(self, request: RemoteOperationRequest, reason: str) -> RemoteOperationResult:
        return RemoteOperationResult(
            status=OperationStatus.NOT_EXECUTED,
            reason=reason,
            provider_version=f"{PROVIDER}@{VERSION}",
            dispatch_id=request.dispatch_id,
        )


def _world(files: Mapping[str, str]) -> dict[str, dict[str, Mapping[str, Any]]]:
    """The staged world, read strictly: a context the vocabulary doesn't read, or an instance
    that isn't an object, is refused rather than skipped."""
    if WORLD_PATH not in files:
        raise ValueError(f"no world is staged at {WORLD_PATH}, so there is nothing to observe")
    try:
        world = json.loads(files[WORLD_PATH])
    except json.JSONDecodeError as e:
        raise ValueError(f"{WORLD_PATH} isn't JSON: {e}") from e
    if not isinstance(world, dict) or not set(world) <= VOCABULARY.contexts:
        raise ValueError(
            f"{WORLD_PATH} is an object keyed by context, from {sorted(VOCABULARY.contexts)}"
        )
    for context, instances in world.items():
        if not isinstance(instances, dict) or not all(
            isinstance(i, dict) for i in instances.values()
        ):
            raise ValueError(f"{WORLD_PATH}: {context} maps each instance path to an object")
    return world


def _observe(observation: Observation, world: Mapping[str, Mapping[str, Any]]) -> Any:
    instance = world.get(observation.context, {}).get(observation.arguments["path"])
    if instance is None:
        return ABSENT
    if observation.kind == "value":
        return instance["value"] if "value" in instance else ABSENT
    section = instance.get(_WORLD_SECTIONS[observation.kind], {})
    key = observation.arguments["state" if observation.kind == "gui_state" else "name"]
    return section[key] if key in section else ABSENT


def _shown(value: Any) -> str:
    return repr(ABSENT) if value is ABSENT else json.dumps(value)


def _expected(expect: Expectation) -> str:
    return expect.op.value if expect.value is None else f"{expect.op.value} {_shown(expect.value)}"


def _waited(action: Action, world: Mapping[str, Mapping[str, Any]]) -> tuple[bool, Any]:
    observation = action.arguments["observe"]
    observed = _observe(
        Observation(
            observation["kind"],
            observation["context"],
            {k: v for k, v in observation.items() if k not in ("kind", "context")},
        ),
        world,
    )
    expect = action.arguments["expect"]
    # Read when the declaration was checked, so the op is one of ExpectOp's and ``absent`` alone
    # has no value.
    met = expectation_met(Expectation(ExpectOp(expect["op"]), expect.get("value")), observed)
    return met, observed


def _play(
    declaration: ScenarioDeclaration, world: Mapping[str, Mapping[str, Any]]
) -> tuple[tuple[AssertionRecord, ...], dict[str, Any]]:
    log: dict[str, Any] = {"reader": VOCABULARY.reader, "setup": [], "steps": []}
    established = True
    for phase, actions in (("setup", declaration.setup), ("steps", declaration.steps)):
        for action in actions:
            entry: dict[str, Any] = {"action": action.action}
            if action.action == "wait_until":
                met, observed = _waited(action, world)
                entry.update(met=met, observed=_shown(observed))
                if phase == "setup" and not met:
                    established = False
            log[phase].append(entry)
    if not established:
        return (
            tuple(
                AssertionRecord(
                    a.assertion_id,
                    AssertionOutcome.SETUP_FAILED,
                    expected=_expected(a.expect),
                    context=a.observe.context,
                )
                for a in declaration.assertions
            ),
            log,
        )
    records = []
    for declared in declaration.assertions:
        observed = _observe(declared.observe, world)
        records.append(
            AssertionRecord(
                declared.assertion_id,
                AssertionOutcome.PASSED
                if expectation_met(declared.expect, observed)
                else AssertionOutcome.FAILED,
                observed=_shown(observed),
                expected=_expected(declared.expect),
                context=declared.observe.context,
            )
        )
    return tuple(records), log

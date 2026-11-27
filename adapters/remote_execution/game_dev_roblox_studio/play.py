"""The scenario executor (SIP-0117 R3.7, R5.8; #3040): a frozen scenario's setup, steps and
assertions run in a play session under the ``roblox-studio/1`` vocabulary (``vocabulary``).

Each observation is the harness's ``observe`` program, read in the session's Server or Client
datamodel. Each action is Studio's own input, through its MCP tools:
- **``click_gui``** is the mouse moved to the object's path, then pressed and released in the
  same call. Studio's single-step click never answered, and the position doesn't carry across
  calls. The object must be visible first: a click on a hidden object would do nothing, and
  read as done.
- **``hold_key``** is a key down, a wait and a key up.
- **``move_to``** is the character navigated to the point, then waited on until it is within
  ``ARRIVED_STUDS``.
- **``wait_until``** polls its observation until its expectation is met.

Studio's input tools act only on a Studio in front of the Mac's desktop: with another app in
front, a click never answered (found live), so the runner refuses a scenario with any of
``STUDIO_INPUT_ACTIONS`` before it syncs anything, unless Studio is in front.

**One record per declared assertion,** whatever happened:
- A setup action that couldn't be done, or a setup ``wait_until`` that timed out, means the
  scenario's world wasn't established. Every assertion then reads ``setup_failed``.
- So does a step that couldn't be done (a missing or hidden object to click, a key Studio
  refuses), since the scenario didn't run as declared.
- A step's ``wait_until`` that times out doesn't stop the scenario: its assertions read what
  happened.
- An assertion's observation reads ``passed`` or ``failed`` against its expectation, and an
  absent instance executes like any value. It reads ``unsupported_input`` for an observation
  the harness doesn't read, ``missing`` when reading it failed, and ``wrong_context`` when the
  harness ran somewhere other than the context the assertion names.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from adapters.remote_execution.game_dev_roblox_studio.session import (
    StudioMcpSession,
    StudioSessionError,
)
from adapters.remote_execution.game_dev_roblox_studio.vocabulary import ARRIVED_STUDS, VOCABULARY
from squadops.remote_execution.models import AssertionOutcome, AssertionRecord
from squadops.remote_execution.scenario import (
    ABSENT,
    Action,
    Expectation,
    ExpectOp,
    Observation,
    ScenarioDeclaration,
    expectation_met,
)

#: The datamodel each of the vocabulary's contexts is read in.
DATAMODEL = {"server": "Server", "client": "Client"}
#: The actions done through Studio's input tools, which act only on a Studio in front.
STUDIO_INPUT_ACTIONS = frozenset({"click_gui", "hold_key", "move_to"})
#: What Studio's input tools answer when they did what was asked.
STUDIO_INPUT_DONE = "Success"
#: How often a wait polls its observation.
POLL_SECONDS = 0.25
#: How long the session's player may take to appear on the client before setup can run.
READY_SECONDS = 30.0
_NUMBER = r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?"
_POSITION = re.compile(rf"^\s*({_NUMBER}),\s*({_NUMBER}),\s*({_NUMBER})\s*$")


class ActionFailed(RuntimeError):
    """An action couldn't be done as declared; the message says why."""


@dataclass(frozen=True)
class Observed:
    """One observation's answer: a value (a JSON scalar or ``ABSENT``), or why there is none."""

    value: Any = None
    unsupported: str = ""
    unreadable: str = ""
    wrong_context: str = ""

    @property
    def read(self) -> bool:
        return not (self.unsupported or self.unreadable or self.wrong_context)


@dataclass
class PlayLog:
    """What the executor did, for the operation's evidence."""

    setup: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    stopped: str = ""

    #: This play session's id: each transaction's own, so a log is never read as another's.
    session_id: str = ""

    def to_document(self) -> dict[str, Any]:
        return {"reader": VOCABULARY.reader, "play_session": self.session_id,
                "setup": self.setup, "steps": self.steps, "stopped": self.stopped}  # fmt: skip


async def observe(session: StudioMcpSession, studio_id: str, observation: Observation) -> Observed:
    """One observation, read by the harness in its context's datamodel."""
    payload = {"kind": observation.kind, "context": observation.context, **observation.arguments}
    answer = await session.run_program(
        "observe", studio_id, payload, datamodel=DATAMODEL[observation.context]
    )
    if not isinstance(answer, dict):
        return Observed(unreadable=f"the observe program answered {answer!r:.200}")
    if answer.get("absent") is True:
        return Observed(ABSENT)
    if "unsupported" in answer:
        return Observed(unsupported=str(answer["unsupported"]))
    if "unreadable" in answer:
        return Observed(unreadable=str(answer["unreadable"]))
    if "wrong_context" in answer:
        return Observed(wrong_context=str(answer["wrong_context"]))
    if "value" in answer:
        return Observed(answer["value"])
    return Observed(unreadable=f"the observe program answered {answer!r:.200}")


async def run_scenario(
    session: StudioMcpSession,
    studio_id: str,
    declaration: ScenarioDeclaration,
    *,
    timed: Callable[[str, float], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[tuple[AssertionRecord, ...], PlayLog]:
    """The declaration run in the play session that is running now: its records and its log.
    ``timed`` is told each action's name and how long it took (#3250), whether it held or not."""
    log = PlayLog(session_id=uuid.uuid4().hex)
    stopped = await _ready(session, studio_id)
    for phase, actions in (("setup", declaration.setup), ("steps", declaration.steps)):
        if stopped:
            break
        for index, action in enumerate(actions):
            entry: dict[str, Any] = {"action": action.action}
            getattr(log, phase).append(entry)
            try:
                met = await _timed(session, studio_id, action, entry, timed, clock)
            except (ActionFailed, StudioSessionError) as e:
                entry["failed"] = str(e)
                stopped = f"{phase} {index + 1} ({action.action}) couldn't be done: {e}"
                break
            if phase == "setup" and met is False:
                stopped = f"setup {index + 1} (wait_until) wasn't met within its deadline"
                break
    if stopped:
        log.stopped = stopped
        return tuple(
            AssertionRecord(
                a.assertion_id,
                AssertionOutcome.SETUP_FAILED,
                observed=stopped,
                expected=_expected(a.expect),
                context=a.observe.context,
            )
            for a in declaration.assertions
        ), log
    records = []
    for declared in declaration.assertions:
        seen = await observe(session, studio_id, declared.observe)
        if seen.wrong_context:
            outcome, shown = AssertionOutcome.WRONG_CONTEXT, seen.wrong_context
        elif seen.unsupported:
            outcome, shown = AssertionOutcome.UNSUPPORTED_INPUT, seen.unsupported
        elif seen.unreadable:
            outcome, shown = AssertionOutcome.MISSING, seen.unreadable
        else:
            met = expectation_met(declared.expect, seen.value)
            outcome = AssertionOutcome.PASSED if met else AssertionOutcome.FAILED
            shown = _shown(seen.value)
        records.append(
            AssertionRecord(
                declared.assertion_id,
                outcome,
                observed=shown,
                expected=_expected(declared.expect),
                context=declared.observe.context,
            )
        )
    return tuple(records), log


async def _ready(session: StudioMcpSession, studio_id: str) -> str:
    """``""`` once the session's player is on the client with a character, or why not."""
    character = Observation("property", "client", {"path": "@player", "name": "Character"})
    deadline = asyncio.get_running_loop().time() + READY_SECONDS
    while True:
        seen = await observe(session, studio_id, character)
        if seen.read and seen.value is not ABSENT:
            return ""
        if asyncio.get_running_loop().time() >= deadline:
            return f"the session's player had no character on the client within {READY_SECONDS:g}s"
        await asyncio.sleep(POLL_SECONDS)


async def _do(
    session: StudioMcpSession, studio_id: str, action: Action, entry: dict[str, Any]
) -> bool | None:
    """Do one action. ``wait_until`` answers whether it was met; the others answer ``None``, or
    raise :class:`ActionFailed`."""
    args = action.arguments
    if action.action == "click_gui":
        path = args["path"]
        visible = await observe(
            session,
            studio_id,
            Observation("gui_state", "client", {"path": path, "state": "visible"}),
        )
        if not visible.read or visible.value is not True:
            raise ActionFailed(f"{path} isn't a visible GUI object ({why_not(visible)})")
        await _input(session, studio_id, "user_mouse_input", {"actions": [
            {"action": "moveTo", "instance_path": _studio_path(path)},
            {"action": "wait", "wait_time_ms": 200},
            {"action": "mouseButtonDown", "mouse_button": "left"},
            {"action": "wait", "wait_time_ms": 100},
            {"action": "mouseButtonUp", "mouse_button": "left"},
        ]})  # fmt: skip
        return None
    if action.action == "hold_key":
        held_ms = int(args["seconds"] * 1000)
        waits = [{"action": "wait", "wait_time_ms": min(10_000, held_ms - start)}
                 for start in range(0, held_ms, 10_000)]  # fmt: skip
        await _input(session, studio_id, "user_keyboard_input", {"actions": [
            {"action": "keyDown", "key_code": args["key"]}, *waits,
            {"action": "keyUp", "key_code": args["key"]},
        ]})  # fmt: skip
        return None
    if action.action == "move_to":
        x, y, z = args["point"]
        await _input(session, studio_id, "character_navigation", {"x": x, "y": y, "z": z})
        arrived = await _until(
            session,
            studio_id,
            Observation(
                "property",
                "client",
                {"path": "@player.Character.HumanoidRootPart", "name": "Position"},
            ),
            lambda value: _within(value, (x, y, z)),
            args["deadline_s"],
        )
        entry["arrived"] = arrived
        if not arrived:
            raise ActionFailed(
                f"the character didn't reach {list(args['point'])} within {args['deadline_s']:g}s"
            )
        return None
    if action.action == "wait_until":
        spec = args["observe"]
        observation = Observation(
            spec["kind"],
            spec["context"],
            {k: v for k, v in spec.items() if k not in ("kind", "context")},
        )
        expect = Expectation(ExpectOp(args["expect"]["op"]), args["expect"].get("value"))
        met = await _until(
            session,
            studio_id,
            observation,
            lambda value: expectation_met(expect, value),
            args["deadline_s"],
        )
        entry["met"] = met
        return met
    raise ActionFailed(f"the harness runs no action {action.action!r}")  # read declarations can't


async def _timed(
    session: StudioMcpSession,
    studio_id: str,
    action: Any,
    entry: dict[str, Any],
    timed: Callable[[str, float], None] | None,
    clock: Callable[[], float],
):
    """``_do``, with how long the action took told to ``timed``, whether it held or raised."""
    began = clock()
    try:
        return await _do(session, studio_id, action, entry)
    finally:
        if timed is not None:
            timed(action.action, clock() - began)


async def _until(
    session: StudioMcpSession, studio_id: str, observation: Observation, met, seconds: float
) -> bool:
    """Poll ``observation`` until ``met`` holds of its value, or ``seconds`` pass. An observation
    that can't be read fails the action rather than waiting it out."""
    deadline = asyncio.get_running_loop().time() + seconds
    while True:
        seen = await observe(session, studio_id, observation)
        if not seen.read:
            raise ActionFailed(
                f"{observation.arguments.get('path')} can't be observed ({why_not(seen)})"
            )
        if met(seen.value):
            return True
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await asyncio.sleep(POLL_SECONDS)


async def _input(session: StudioMcpSession, studio_id: str, tool: str, arguments: dict) -> None:
    answer = await session.call(
        tool, {"studio_id": studio_id, "datamodel_type": "Client", **arguments}
    )
    if answer.strip() != STUDIO_INPUT_DONE:
        raise ActionFailed(f"{tool} answered {answer!r:.200}")


def _studio_path(path: str) -> str:
    """A vocabulary path as Studio's input tools take it: ``@player`` is their ``LocalPlayer``,
    and a service path starts at ``game``."""
    if path == "@player" or path.startswith("@player."):
        return "LocalPlayer" + path[len("@player") :]
    return path if path.startswith("game.") else f"game.{path}"


def _within(value: Any, point: tuple[float, float, float]) -> bool:
    match = _POSITION.match(value) if isinstance(value, str) else None
    if match is None:
        return False
    return math.dist([float(g) for g in match.groups()], point) <= ARRIVED_STUDS


def why_not(seen: Observed) -> str:
    if not seen.read:
        return seen.unsupported or seen.unreadable or seen.wrong_context
    return "absent" if seen.value is ABSENT else f"it reads {_shown(seen.value)}"


def _shown(value: Any) -> str:
    return repr(ABSENT) if value is ABSENT else json.dumps(value)


def _expected(expect: Expectation) -> str:
    return expect.op.value if expect.value is None else f"{expect.op.value} {_shown(expect.value)}"

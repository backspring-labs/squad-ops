"""The script error a play's console names (SIP-0117 R5.32, #3200: the Studio provider's half).

A provider's fact, never an attribution: which staged script raised, at which line, and what
Studio said. Core attributes it (``remote_execution.setup_attribution``).

The console, as Studio's ``get_console_output`` answers it, writes an error with a stack as a
block of bare lines (read on 2026-11-26 from six stored consoles; none carries a level prefix):

    Visible is not a valid member of ScreenGui "TA_HUD"
    Stack Begin
    Script 'Players.<player>.PlayerScripts.Client.UI.Screens.HUD', Line 311 - function new
    Script 'Players.<player>.PlayerScripts.Client.Controllers.UIController', Line 444 - function Init
    Stack End

The first frame is the one that raised. What is reported (R5.32's "What a provider reports"):

- **an error with a stack,** and **one stackless kind: a staged script that fails to compile**
  (#3304). Studio writes a script that doesn't parse as one line in its own text,
  ``<script>:<line>: <message>``, with no stack, before the follow-ons below. An engine or network
  error has no stack either, but names no staged script, and isn't reported;
- **only one whose raising frame is a script of the staged tree.** One raised in Studio's own
  code, or in the command the provider's probe ran (``AssistantCommand``), isn't;
- **never a warning,** which the console writes as bare as an error. The one that carries a stack
  is the engine's ``Infinite yield possible on …``, for a wait that may never end;
- **never the follow-on a failed module load raises in each script that required it,**
  ``Requested module experienced an error while loading``: one per step up the require chain.
  The error is the module's own, which comes first;
- **only the first such block.** Later ones follow from it as often as not.

A frame names the script by where it runs. A client script runs as a copy under the player
(``Players.<player>.PlayerScripts.…``) of the one the place holds under
``StarterPlayer.StarterPlayerScripts.…``, so that prefix is read as the place's.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

STACK_BEGIN = "Stack Begin"
STACK_END = "Stack End"
#: The follow-on a failed module load raises in its requirer, once per step up the chain.
MODULE_LOAD_FOLLOW_ON = "Requested module experienced an error while loading"
#: The command a provider's probe runs through Studio's MCP. Its frames are never a script of
#: the staged tree.
PROBE_SCRIPT = "AssistantCommand"
#: An engine warning about a wait that may never end. It carries a stack, and it is a warning, not
#: an error raised, so it is never reported (ruled with the Spark lane, 2026-11-26).
INFINITE_YIELD = "Infinite yield possible on"
_FRAME = re.compile(r"^Script '(?P<script>[^']+)', Line (?P<line>\d+)(?: - .*)?$")
#: A script's own error line, ``<script>:<line>: <message>``: alone it is a compile error (#3304);
#: followed by ``Stack Begin`` it is a stacked block's message, read from its frame.
_SCRIPT_LINE = re.compile(r"^(?P<script>[^\s:]+):(?P<line>\d+): (?P<message>\S.*)$")
_PLAYER_SCRIPTS = re.compile(r"^Players\.[^.]+\.PlayerScripts\.")
_STARTER_PLAYER_SCRIPTS = "StarterPlayer.StarterPlayerScripts."


@dataclass(frozen=True)
class ConsoleError:
    """An error block whose raising frame is a script the place holds, by its place path."""

    script: str
    line: int
    message: str


def place_path(script: str) -> str:
    """The place's path of a script a frame names: a client script's player copy is read as
    the script under ``StarterPlayer.StarterPlayerScripts``."""
    return _PLAYER_SCRIPTS.sub(_STARTER_PLAYER_SCRIPTS, script, count=1)


def first_script_error(console: str, staged: Mapping[str, str]) -> ConsoleError | None:
    """The first error block raised in a staged script, or ``None``. ``staged`` maps each
    staged script's place path to its file in the request's tree; a frame in any other
    script is never reported."""
    lines = console.splitlines()
    for index, line in enumerate(lines):
        compiled = _compile_error(lines, index, staged)
        if compiled is not None:
            return compiled
        if line.strip() != STACK_BEGIN or index == 0:
            continue
        message = lines[index - 1].strip()
        frame = _first_frame(lines, index + 1)
        if frame is None or not message or MODULE_LOAD_FOLLOW_ON in message:
            continue
        if message.startswith(INFINITE_YIELD):
            continue
        script, at = frame
        if script == PROBE_SCRIPT or script.startswith(f"{PROBE_SCRIPT}."):
            continue
        if place_path(script) in staged:
            return ConsoleError(place_path(script), at, message)
    return None


def _compile_error(lines: list[str], index: int, staged: Mapping[str, str]) -> ConsoleError | None:
    """The line at ``index`` as a staged script's compile error: its own ``<script>:<line>:
    <message>`` with no stack after it, naming a staged script. ``None`` for anything else: a
    stacked block's message line (read from its frame), an engine line, or another script's."""
    text = lines[index].strip()
    matched = _SCRIPT_LINE.match(text)
    if matched is None or MODULE_LOAD_FOLLOW_ON in text:
        return None
    following = next((line.strip() for line in lines[index + 1 :] if line.strip()), "")
    if following == STACK_BEGIN:
        return None
    script = place_path(matched["script"])
    if script not in staged:
        return None
    return ConsoleError(script, int(matched["line"]), text)


def _first_frame(lines: list[str], start: int) -> tuple[str, int] | None:
    """The block's raising frame, or ``None`` for a block with none before its end."""
    for line in lines[start:]:
        text = line.strip()
        if text == STACK_END:
            return None
        matched = _FRAME.match(text)
        if matched:
            return matched["script"], int(matched["line"])
    return None


@dataclass(frozen=True)
class Window:
    """Which lines of the console are this play's, and how that was read: ``cleared`` (Studio
    cleared the console as play started), ``appended`` (it kept what it held and appended), or
    ``unestablished``, when this play's lines can't be told from an earlier play's."""

    kind: str
    lines: tuple[str, ...] | None


def this_plays_lines(before: str, early: str, after: str) -> Window:
    """The console lines this play wrote. Three reads of the console: just before play starts
    (``before``), just after it starts (``early``), and when the scenario has ended (``after``).
    Only exact prefixes are read: a play's console holds lines identical to an earlier play's, so
    matching runs of lines could cut a play's start, where its start-up errors are.

    Read on the Mac on 2026-11-26: Studio clears its console when play starts, and appends to
    it until the next start.

    - ``early`` starts with ``before``: the console wasn't cleared. This play's lines are what
      follows ``before`` in ``after``, when ``after`` starts with it.
    - Otherwise Studio cleared it as play started (an empty ``early`` is a cleared console).
      ``after`` is this play's whole console when it starts with ``early``.
    - Anything else, such as a console that rolled past this play's start, is unestablished.
      So is an ``early`` that begins with whole lines ``before`` ends with: a capped console that
      kept its tail and dropped its head reads like a cleared one, with an earlier play's lines
      at its start (the Spark lane's review, 2026-11-27).
    """
    if early.startswith(before):
        if after.startswith(before):
            return Window("appended", tuple(after[len(before) :].splitlines()))
        return Window("unestablished", None)
    if _kept_a_tail(before, early):
        return Window("unestablished", None)
    if after.startswith(early):
        return Window("cleared", tuple(after.splitlines()))
    return Window("unestablished", None)


def _kept_a_tail(before: str, early: str) -> bool:
    """Whether ``early`` begins with one or more whole lines ``before`` ends with. An empty
    ``early`` kept nothing: it is a cleared console with nothing yet written."""
    held, began = before.splitlines(), early.splitlines()
    return any(began[:n] == held[-n:] for n in range(1, min(len(held), len(began)) + 1))

"""``RobloxStudioRunner``: the ``roblox-studio`` provider behind ``OperationRunnerPort`` (#3039,
#3040).

It serves one operation, **``play_scenario``**: a frozen scenario played on the candidate, as one
transaction (R3.6), under the one lease the worker holds for the call:
1. The scenario is checked as frozen, under ``roblox-studio/1``, and Studio as the app in front.
2. Studio is held to what the operation was proved on: its version and its tool list (R2.4). The
   worker reads them, at each claim, from the newest passing qualification record (#3048), and a
   re-qualification holds Studio while it runs, so the two never use it at once.
3. The place's non-script baseline is held to its pin. A place that drifted is reset from its
   baseline file (R5.17) and the transaction begun again, once.
4. The candidate's scripts are synced, the place confirmed unpublished, and the scripts read back.
5. The synced scripts are checked for attributes and tags, and the non-script baseline is taken.
6. Play starts, the scenario runs (``play``), and play stops however it ends.
7. The baseline is taken again and held equal, and the scripts are read back again: one changed
   in Studio while the scenario ran fails the run (R3.6).

Sync, the console and the capture are steps of that transaction, never operations of their own:
every request carries a scenario. The rest stands beside it:
- ``health`` reads identity and the tool check;
- ``tool_versions`` registers the provider's version, Studio's version, the tool-schema digest,
  the harness's program digests and the vocabulary's reader (R4.6);
- ``reset`` restores the place from its read-only baseline file and reopens Studio (R5.17). A
  runner given no place files refuses to reset;
- ``read_back``, ``sync`` and ``play_round`` are the transaction's parts, run by hand from
  ``scripts/dev``.

**The player is a person's account.** A play session's player is whoever is signed in to Studio.
Its name and id are replaced by ``@player`` in every record, log and console line the operation
returns.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import os
import plistlib
import re
import shutil
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from adapters.remote_execution.game_dev_roblox_studio import harness, place, play
from adapters.remote_execution.game_dev_roblox_studio.session import (
    StudioMcpSession,
    StudioSessionError,
    ToolCheck,
)
from adapters.remote_execution.game_dev_roblox_studio.studio_app import (
    MacStudioApp,
    PlaceFiles,
    StudioApp,
)
from adapters.remote_execution.game_dev_roblox_studio.vocabulary import VOCABULARY
from squadops.ports.remote_execution import OperationRunnerPort
from squadops.remote_execution.models import (
    AssertionRecord,
    EvidenceItem,
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.remote_execution.scenario import (
    Observation,
    ScenarioDeclaration,
    handed_scenario_defects,
)
from squadops.remote_execution.workers import ServedOperation
from squadops.runtime.models import RuntimeStatus

PROVIDER = "roblox-studio"
#: This provider's version: what each operation's evidence records it ran with (R4.6).
PROVIDER_VERSION = "1"
OPERATION = "play_scenario"
RUN_LOG_NAME = "play_log.json"
CONSOLE_NAME = "console.txt"
#: The console's tail kept as evidence: the end is where a run's errors are.
CONSOLE_CHARS = 20_000


def studio_version(studio_mcp: Path) -> str:
    """The version of the Studio whose ``StudioMCP`` this is, from its app bundle's
    ``Info.plist`` (``…/RobloxStudio.app/Contents/MacOS/StudioMCP``). Raises when it can't be
    read: a worker that registered no Studio version couldn't be held to the one it was proved
    on."""
    info = studio_mcp.parent.parent / "Info.plist"
    try:
        with info.open("rb") as f:
            version = plistlib.load(f).get("CFBundleShortVersionString")
    except (OSError, plistlib.InvalidFileException) as e:
        raise ValueError(f"Studio's version can't be read from {info}: {e}") from e
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"{info} names no CFBundleShortVersionString")
    return version


@dataclass(frozen=True)
class ProvedOn:
    """What the operation was proved on (R2.4): Studio's version, and its tool list as
    ``<count>:<schema digest>``. A Studio that differs from either reads ``not_executed``."""

    studio_version: str
    studio_tools: str
    #: The digest of the qualification record these pins came from (#3048), recorded with
    #: every result. Empty only for pins handed in directly: a qualification's own runs.
    record: str = ""


class NotProved(RuntimeError):
    """The Studio a run would use isn't the one the operation was proved on, or nothing says
    what it was proved on."""


class StudioBusy(place.PlaceStateError):
    """Another process holds Studio: a re-qualification, or a worker's claim (#3048)."""


class Pins(Protocol):
    """Where a worker's pins come from (#3048): its qualification records."""

    def current(self) -> ProvedOn:
        """The pins of the newest passing record. Raises :class:`NotProved` naming why there
        are none."""

    def exclusive(self) -> AbstractContextManager[None]:
        """Studio, held for one transaction or reset. Raises :class:`StudioBusy` when another
        process holds it."""


class _Drifted(RuntimeError):
    """The place's non-script state isn't its pinned baseline."""


@dataclass(frozen=True)
class PlayRound:
    """A play round that held: the place's non-script baseline, equal before play and after
    stop."""

    baseline_digest: str
    instances: int


class RobloxStudioRunner(OperationRunnerPort):
    """The read side of the ``roblox-studio`` provider."""

    def __init__(
        self,
        studio_mcp: Path,
        *,
        session_factory: Callable[..., StudioMcpSession] | None = None,
        studio_version_of: Callable[[Path], str] = studio_version,
        discover_seconds: float = 20.0,
        place_files: PlaceFiles | None = None,
        proved_on: ProvedOn | Pins | None = None,
        app: StudioApp | None = None,
        quit_seconds: float = 20.0,
        reopen_seconds: float = 120.0,
    ) -> None:
        self._studio_mcp = studio_mcp
        self._files = place_files
        self._proved = proved_on
        # ``StudioMCP`` sits at ``…/RobloxStudio.app/Contents/MacOS/StudioMCP``.
        self._app = app or MacStudioApp(studio_mcp.parents[2])
        self._quit_seconds = quit_seconds
        self._reopen_seconds = reopen_seconds
        self._session = session_factory or (lambda **kw: StudioMcpSession([str(studio_mcp)], **kw))
        self._studio_version_of = studio_version_of
        self._discover_seconds = discover_seconds

    def serves(self) -> tuple[ServedOperation, ...]:
        return (ServedOperation(PROVIDER, OPERATION),)

    async def tool_versions(self) -> Mapping[str, str]:
        session = self._session()
        try:
            check = await session.open()
        finally:
            await session.close()
        return {
            PROVIDER: PROVIDER_VERSION,
            "studio": self._studio_version_of(self._studio_mcp),
            "studio_tools": f"{check.count}:{check.schema_digest}",
            "reader": VOCABULARY.reader,
            **{f"harness.{name}": digest[:16] for name, digest in harness.digests().items()},
        }

    async def health(self) -> RuntimeStatus:
        session = self._session()
        try:
            await session.open()
            await place.identity(session, discover_seconds=self._discover_seconds)
        except (StudioSessionError, place.PlaceReadError):
            return "offline"
        finally:
            await session.close()
        return "online"

    async def run(self, request: RemoteOperationRequest) -> RemoteOperationResult:
        """``play_scenario``, as one transaction. ``not_executed`` names why, for anything before
        play starts, for a place whose state play changed, and for a script changed in Studio
        while it ran. ``interrupted`` is for a session that failed after play began.
        ``completed`` carries one record per declared assertion.

        A place whose non-script state isn't its pinned baseline is reset (R5.17) and the
        transaction begun again, once."""
        if (request.provider, request.operation) != (PROVIDER, OPERATION):
            return self._ended(request, OperationStatus.NOT_EXECUTED,
                               f"{PROVIDER} runs {PROVIDER}/{OPERATION}, and was asked for "
                               f"{request.provider}/{request.operation}")  # fmt: skip
        declaration, defects = handed_scenario_defects(request.scenario, VOCABULARY)
        if declaration is None:
            return self._ended(request, OperationStatus.NOT_EXECUTED,
                               "the scenario can't be run: " + "; ".join(defects))  # fmt: skip
        manifest, unplaced = place.manifest_scripts(request.source_files)
        if unplaced:
            return self._ended(request, OperationStatus.NOT_EXECUTED, "nothing was run: " + "; ".join(
                f"{f} isn't a script {PROVIDER} places" for f in unplaced))  # fmt: skip
        files, pins = self._files, self._proved
        if files is None or pins is None:
            return self._ended(request, OperationStatus.NOT_EXECUTED,
                               f"nothing was run: {PROVIDER} was given no place files and "
                               "proved-on pins, so the place can't be confirmed as the one the "
                               "operation was proved on (R2.4)")  # fmt: skip
        if isinstance(pins, ProvedOn):
            return await self._played(request, declaration, manifest, files, pins)
        try:
            proved = pins.current()
            with pins.exclusive():
                return await self._played(request, declaration, manifest, files, proved)
        except (NotProved, StudioBusy) as e:
            return self._ended(request, OperationStatus.NOT_EXECUTED, f"nothing was run: {e}")

    async def _played(
        self,
        request: RemoteOperationRequest,
        declaration: ScenarioDeclaration,
        manifest: Mapping[str, place.ScriptText],
        files: PlaceFiles,
        proved: ProvedOn,
    ) -> RemoteOperationResult:
        """The transaction, begun again once after a reset when the place drifted."""
        try:
            return await self._transaction(request, declaration, manifest, files, proved)
        except _Drifted as drifted:
            try:
                await self._reset_held()
            except (place.PlaceStateError, place.PlaceReadError, StudioSessionError,
                    OSError) as e:  # fmt: skip
                return self._ended(request, OperationStatus.NOT_EXECUTED,
                                   f"nothing was run: {drifted}, and the reset failed: "
                                   f"{type(e).__name__}: {e}")  # fmt: skip
        try:
            return await self._transaction(request, declaration, manifest, files, proved)
        except _Drifted as drifted:
            return self._ended(request, OperationStatus.NOT_EXECUTED,
                               f"nothing was run: {drifted}, after a reset")  # fmt: skip

    async def _transaction(
        self,
        request: RemoteOperationRequest,
        declaration: ScenarioDeclaration,
        manifest: Mapping[str, place.ScriptText],
        files: PlaceFiles,
        proved: ProvedOn,
    ) -> RemoteOperationResult:
        """One attempt at the transaction. Raises :class:`_Drifted`, before anything is
        written, when the place isn't its pinned baseline."""
        if any(a.action in play.STUDIO_INPUT_ACTIONS for a in (*declaration.setup,
                                                                *declaration.steps)):  # fmt: skip
            behind = self._studio_behind()
            if behind:
                return self._ended(request, OperationStatus.NOT_EXECUTED,
                                   "nothing was run: the scenario acts through Studio's input, "
                                   f"which acts only on a Studio in front, and {behind}")  # fmt: skip
        session = self._session(harness=True)
        playing = False
        try:
            check = await session.open()
            self._held_to_proof(check, proved)
            studio = await place.identity(session, discover_seconds=self._discover_seconds)
            sid = studio.studio_id
            pinned = await place.baseline(session, sid)
            if pinned.digest != files.baseline_digest:
                raise _Drifted(
                    f"the place holds non-script baseline {pinned.digest[:16]}…, not the pinned "
                    f"{files.baseline_digest[:16]}…"
                )
            await place.sync(session, sid, manifest)
            marked = await place.marked_scripts(session, sid)
            if marked:
                raise place.PlaceStateError(
                    "synced scripts carry attributes or tags: " + "; ".join(marked)
                )
            before = await place.baseline(session, sid)
            await place.start_play(session, sid)
            playing = True
            try:
                records, log = await play.run_scenario(session, sid, declaration)
                player = await play.observe(
                    session,
                    sid,
                    Observation("property", "client", {"path": "@player", "name": "Name"}),
                )
                console = await place.console(session, sid)
            finally:
                await place.stop_play(session, sid)
            playing = False
            after = await place.baseline(session, sid)
            scripts_after = place.differences(await place.read_scripts(session, sid), manifest)
        except (place.PlaceReadError, place.PlaceSyncError, place.PlaceStateError,
                StudioSessionError, NotProved) as e:  # fmt: skip
            status = OperationStatus.INTERRUPTED if playing else OperationStatus.NOT_EXECUTED
            return self._ended(request, status, f"{type(e).__name__}: {e}")
        finally:
            await session.close()
        changes = place.baseline_changes(before, after)
        if changes:
            return self._ended(request, OperationStatus.NOT_EXECUTED,
                               "the place's non-script state changed through play, so the run "
                               "proves nothing: " + "; ".join(changes))  # fmt: skip
        if scripts_after:
            return self._ended(request, OperationStatus.NOT_EXECUTED,
                               "scripts changed in Studio while the scenario ran, so the run "
                               "proves nothing about the candidate: " + "; ".join(scripts_after))  # fmt: skip
        if not (player.read and isinstance(player.value, str) and player.value):
            return self._ended(request, OperationStatus.INTERRUPTED,
                               "the session's player name couldn't be read, so its records and "
                               "evidence can't be redacted, and none are returned "
                               f"({play.why_not(player)})")  # fmt: skip
        redact = _redactor(player.value)
        return RemoteOperationResult(
            status=OperationStatus.COMPLETED,
            records=tuple(_redacted_record(r, redact) for r in records),
            evidence=(
                EvidenceItem(
                    RUN_LOG_NAME,
                    redact(json.dumps(log.to_document(), indent=2)),
                    "application/json",
                ),
                EvidenceItem(CONSOLE_NAME, redact(console[-CONSOLE_CHARS:])),
            ),  # fmt: skip
            provider_version=f"{PROVIDER}@{PROVIDER_VERSION}",
            ran_with={
                **self._ran_with(before.digest, request.source_revision),
                "play_session": log.session_id,
                **({"qualified_by": proved.record[:16]} if proved.record else {}),
            },
            dispatch_id=request.dispatch_id,
        )

    def _held_to_proof(self, check: ToolCheck, proved: ProvedOn) -> None:
        """Raises :class:`NotProved` naming each way Studio differs from what the operation was
        proved on."""
        version = self._studio_version_of(self._studio_mcp)
        tools = f"{check.count}:{check.schema_digest}"
        differs = []
        if version != proved.studio_version:
            differs.append(f"Studio is {version}, and the operation was proved on "
                           f"{proved.studio_version}")  # fmt: skip
        if tools != proved.studio_tools:
            differs.append(f"Studio's tools read {tools[:24]}…, and the operation was proved on "
                           f"{proved.studio_tools[:24]}…")  # fmt: skip
        if differs:
            raise NotProved("; ".join(differs) + " (R2.4: a mode not proved reads not executed)")

    def _ran_with(self, baseline_digest: str, source_revision: str) -> dict[str, str]:
        return {
            PROVIDER: PROVIDER_VERSION,
            "reader": VOCABULARY.reader,
            "place_baseline": baseline_digest[:16],
            "source_revision": source_revision,
            **{f"harness.{name}": digest[:16] for name, digest in harness.digests().items()},
        }

    def _studio_behind(self) -> str:
        """``""`` when a Studio is the app in front, or what is in front instead."""
        try:
            front, studios = self._app.frontmost(), self._app.pids()
        except OSError as e:
            return f"which app is in front couldn't be read: {e}"
        if front is None:
            return "no app is in front"
        if front not in studios:
            return f"process {front} is in front, and Studio's are {studios or 'none'}"
        return ""

    def _ended(
        self, request: RemoteOperationRequest, status: OperationStatus, reason: str
    ) -> RemoteOperationResult:
        return RemoteOperationResult(
            status=status,
            reason=reason,
            provider_version=f"{PROVIDER}@{PROVIDER_VERSION}",
            dispatch_id=request.dispatch_id,
        )

    async def live_studio(self) -> tuple[str, ToolCheck]:
        """The running Studio's version and its live tool check, as a harness session reads it:
        what a re-qualification would pin (#3048)."""
        session = self._session(harness=True)
        try:
            check = await session.open()
        finally:
            await session.close()
        return self._studio_version_of(self._studio_mcp), check

    async def reset(self) -> None:
        """:meth:`_reset_held`, with Studio held against a re-qualification (#3048). Raises
        :class:`StudioBusy` while one runs, and the worker tries again at its next claim."""
        pins = self._proved
        if pins is None or isinstance(pins, ProvedOn):
            await self._reset_held()
            return
        with pins.exclusive():
            await self._reset_held()

    async def _reset_held(self) -> None:
        """Restore the place from its baseline file and reopen Studio on it (R3.6). Raises
        :class:`place.PlaceStateError`, naming why, when it can't do so safely, and then a person
        is needed:
        - before anything is touched, for a baseline file whose digest isn't the pinned one, more
          than one Studio, a Studio that doesn't answer, or one holding another file;
        - for a Studio that won't quit, or a lock a running Studio holds;
        - after reopening, for a place that doesn't come back unpublished, in Edit, holding the
          pinned non-script baseline."""
        files = self._files
        if files is None:
            raise place.PlaceStateError(
                f"{PROVIDER} was given no place files, so it has nothing to reset from"
            )
        held = hashlib.sha256(files.baseline.read_bytes()).hexdigest()
        if held != files.baseline_sha256:
            raise place.PlaceStateError(
                f"the baseline file {files.baseline} is {held[:16]}…, not the pinned "
                f"{files.baseline_sha256[:16]}…; nothing was touched"
            )
        await self._quit_studio(files)
        self._clear_lock(files)
        self._restore(files)
        self._app.open(files.place)
        await self._confirm_reopened(files)

    async def _quit_studio(self, files: PlaceFiles) -> None:
        """Quit the one Studio, which must hold the place file, asking first and killing only
        when it won't go (it ignores a quit while it asks to save)."""
        pids = self._app.pids()
        if not pids:
            return
        if len(pids) != 1:
            raise place.PlaceStateError(
                f"{len(pids)} Studio processes are running; a reset quits only its own"
            )
        session = self._session()
        try:
            await session.open()
            studios = await place.connected_studios(
                session, discover_seconds=self._discover_seconds
            )
        except (StudioSessionError, place.PlaceReadError) as e:
            raise place.PlaceStateError(
                f"Studio is running and its MCP server doesn't answer, so the reset can't confirm "
                f"which place it holds: {e}"
            ) from e
        finally:
            await session.close()
        files_held = [s.get("file") for s in studios]
        if files_held != [files.place.name]:
            raise place.PlaceStateError(
                f"the running Studio holds {files_held or 'no place it reports'}, not "
                f"{files.place.name}; the reset doesn't quit it"
            )
        [pid] = pids
        loop = asyncio.get_running_loop()
        for force, seconds in ((False, 3.0), (True, self._quit_seconds)):
            self._app.quit(pid, force=force)
            deadline = loop.time() + seconds
            while self._app.alive(pid) and loop.time() < deadline:
                await asyncio.sleep(0.25)
            if not self._app.alive(pid):
                return
        raise place.PlaceStateError(
            f"Studio (pid {pid}) didn't quit within {self._quit_seconds:g}s"
        )

    def _clear_lock(self, files: PlaceFiles) -> None:
        """Remove the lock a quit Studio left. One that names a running process, or can't be
        read, is refused: removing it could open the place twice."""
        lock = files.lock
        if not lock.exists():
            return
        first = lock.read_text(errors="replace").splitlines()[:1]
        if not first or not first[0].strip().isdigit():
            raise place.PlaceStateError(f"{lock} names no process id, so it isn't removed")
        pid = int(first[0])
        if self._app.alive(pid):
            raise place.PlaceStateError(f"{lock} is held by running process {pid}")
        lock.unlink()

    def _restore(self, files: PlaceFiles) -> None:
        """The baseline file in the place file's stead, written whole or not at all."""
        staged = files.place.with_name(files.place.name + ".squadops-reset")
        shutil.copyfile(files.baseline, staged)
        os.chmod(staged, 0o600)  # the baseline file is read-only; the place Studio saves isn't
        os.replace(staged, files.place)
        held = hashlib.sha256(files.place.read_bytes()).hexdigest()
        if held != files.baseline_sha256:
            raise place.PlaceStateError(f"{files.place} reads {held[:16]}… after the copy")

    async def _confirm_reopened(self, files: PlaceFiles) -> None:
        session = self._session(harness=True)
        try:
            await session.open()
            studio = await place.identity(session, discover_seconds=self._reopen_seconds)
            if studio.file != files.place.name:
                raise place.PlaceStateError(
                    f"Studio reopened on {studio.file!r}, not {files.place.name}"
                )
            await place.confirm_unpublished(session, studio.studio_id)
            reopened = await place.baseline(session, studio.studio_id)
        finally:
            await session.close()
        if reopened.digest != files.baseline_digest:
            raise place.PlaceStateError(
                f"the reopened place holds non-script baseline {reopened.digest[:16]}…, not the "
                f"pinned {files.baseline_digest[:16]}…"
            )

    async def read_back(self, source_files: Mapping[str, str]) -> list[str]:
        """Each way the place's three synced folders differ from ``source_files``, named; ``[]``
        when Studio holds exactly the manifest's scripts. A file under a synced folder that isn't
        a script this provider places is named too."""
        manifest, unplaced = place.manifest_scripts(source_files)
        session = self._session()
        try:
            await session.open()
            studio = await place.identity(session, discover_seconds=self._discover_seconds)
            read = await place.read_scripts(session, studio.studio_id)
        finally:
            await session.close()
        return [f"{f} isn't a script {PROVIDER} places" for f in unplaced] + place.differences(
            read, manifest
        )

    async def sync(self, source_files: Mapping[str, str]) -> place.SyncResult:
        """Write ``source_files``' scripts into the place's three synced folders and remove the
        rest, then read them back (D10). Raises :class:`place.PlaceSyncError`: before anything is
        written, for a file under a synced folder this provider can't place, or a place that
        isn't an unpublished local one; after, naming each difference the read-back finds."""
        manifest, unplaced = place.manifest_scripts(source_files)
        if unplaced:
            raise place.PlaceSyncError(
                "nothing was written: "
                + "; ".join(f"{f} isn't a script {PROVIDER} places" for f in unplaced)
            )
        session = self._session(harness=True)
        try:
            await session.open()
            studio = await place.identity(session, discover_seconds=self._discover_seconds)
            return await place.sync(session, studio.studio_id, manifest)
        finally:
            await session.close()

    async def play_round(self) -> PlayRound:
        """Play the place once and stop, holding its state (R3.6). Raises
        :class:`place.PlaceSyncError` for a place that isn't a local one in Edit, and
        :class:`place.PlaceStateError` before play for a synced script carrying attributes or
        tags, or after stop naming each instance whose state changed."""
        session = self._session(harness=True)
        try:
            await session.open()
            studio = await place.identity(session, discover_seconds=self._discover_seconds)
            await place.confirm_unpublished(session, studio.studio_id)
            marked = await place.marked_scripts(session, studio.studio_id)
            if marked:
                raise place.PlaceStateError(
                    "Script Sync's files can't carry attributes or tags, so these scripts are ones "
                    "the repository can't describe: " + "; ".join(marked)
                )
            before = await place.baseline(session, studio.studio_id)
            await place.start_play(session, studio.studio_id)
            # ``play_scenario`` will run its scenario here (#3040), inside a ``try`` whose
            # ``finally`` stops play.
            await place.stop_play(session, studio.studio_id)
            after = await place.baseline(session, studio.studio_id)
            changes = place.baseline_changes(before, after)
            if changes:
                raise place.PlaceStateError(
                    "the place's non-script state changed through play: " + "; ".join(changes)
                )
            return PlayRound(before.digest, len(before.lines))
        finally:
            await session.close()


def _redactor(name: str) -> Callable[[str], str]:
    """Replaces the session player's account name with ``@player``."""
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    return lambda text: pattern.sub("@player", text)


def _redacted_record(record: AssertionRecord, redact: Callable[[str], str]) -> AssertionRecord:
    return dataclasses.replace(
        record, observed=redact(record.observed), expected=redact(record.expected)
    )

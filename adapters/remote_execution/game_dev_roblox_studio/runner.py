"""``RobloxStudioRunner``: the ``roblox-studio`` provider behind ``OperationRunnerPort`` (#3039).

The first slice serves no operation. Each of the four (``sync_source``, ``play_scenario``,
``read_console``, ``capture``) is served once it is proved on the worker (SIP-0117 §R2.4: a mode
not proved reads not executed), so ``run`` answers ``not_executed`` and says so. What it does is
the read side the operations stand on:

- ``health`` reads identity and the tool check;
- ``tool_versions`` registers the provider's version, Studio's version and the tool-schema digest
  (R4.6);
- ``reset`` restores the place from its read-only baseline file and reopens Studio on it, with
  no person involved (R3.6): Studio quit, its stale lock cleared, the baseline copied in, Studio
  opened, and the reopened place confirmed unpublished and holding the pinned non-script baseline.
  A runner given no place files refuses to reset;
- ``read_back`` compares the place's three synced folders with a source manifest;
- ``sync`` writes a source manifest into those folders through the harness and reads it back
  (D10). It is the write side ``sync_source`` will stand on, and isn't served until the operation
  is proved on the worker, a Studio restart included;
- ``play_round`` is the transaction's frame around play: the synced scripts checked unmarked, the
  non-script baseline taken, play started and stopped, and the baseline taken again and held
  equal (R3.6). ``play_scenario`` will run its scenario inside it.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import plistlib
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.session import (
    StudioMcpSession,
    StudioSessionError,
)
from adapters.remote_execution.game_dev_roblox_studio.studio_app import (
    MacStudioApp,
    PlaceFiles,
    StudioApp,
)
from squadops.ports.remote_execution import OperationRunnerPort
from squadops.remote_execution.models import (
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.remote_execution.workers import ServedOperation
from squadops.runtime.models import RuntimeStatus

PROVIDER = "roblox-studio"
#: This provider's version: what each operation's evidence records it ran with (R4.6).
PROVIDER_VERSION = "1"


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
        app: StudioApp | None = None,
        quit_seconds: float = 20.0,
        reopen_seconds: float = 120.0,
    ) -> None:
        self._studio_mcp = studio_mcp
        self._files = place_files
        # ``StudioMCP`` sits at ``…/RobloxStudio.app/Contents/MacOS/StudioMCP``.
        self._app = app or MacStudioApp(studio_mcp.parents[2])
        self._quit_seconds = quit_seconds
        self._reopen_seconds = reopen_seconds
        self._session = session_factory or (lambda **kw: StudioMcpSession([str(studio_mcp)], **kw))
        self._studio_version_of = studio_version_of
        self._discover_seconds = discover_seconds

    def serves(self) -> tuple[ServedOperation, ...]:
        return ()

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
        return RemoteOperationResult(
            status=OperationStatus.NOT_EXECUTED,
            reason=(
                f"{PROVIDER} serves no operation yet: {request.operation!r} is served once it is "
                "proved on the worker (SIP-0117 R2.4)"
            ),
            dispatch_id=request.dispatch_id,
        )

    async def reset(self) -> None:
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

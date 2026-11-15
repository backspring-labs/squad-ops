"""``RobloxStudioRunner``: the ``roblox-studio`` provider behind ``OperationRunnerPort`` (#3039).

The first slice serves no operation. Each of the four (``sync_source``, ``play_scenario``,
``read_console``, ``capture``) is served once it is proved on the worker (SIP-0117 §R2.4: a mode
not proved reads not executed), so ``run`` answers ``not_executed`` and says so. What it does is
the read side the operations stand on:

- ``health`` reads identity and the tool check;
- ``tool_versions`` registers the provider's version, Studio's version and the tool-schema digest
  (R4.6);
- ``reset`` confirms identity, and raises when it can't. This slice writes nothing, so there is
  nothing to reset;
- ``read_back`` compares the place's three synced folders with a source manifest;
- ``sync`` writes a source manifest into those folders through the harness and reads it back
  (D10). It is the write side ``sync_source`` will stand on, and isn't served until the operation
  is proved on the worker, a Studio restart included;
- ``play_round`` is the transaction's frame around play: the synced scripts checked unmarked, the
  non-script baseline taken, play started and stopped, and the baseline taken again and held
  equal (R3.6). ``play_scenario`` will run its scenario inside it.
"""

from __future__ import annotations

import plistlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.session import (
    StudioMcpSession,
    StudioSessionError,
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
    ) -> None:
        self._studio_mcp = studio_mcp
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
        session = self._session()
        try:
            await session.open()
            await place.identity(session, discover_seconds=self._discover_seconds)
        finally:
            await session.close()

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

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
- ``read_back`` compares the place's three synced folders with a source manifest.
"""

from __future__ import annotations

import plistlib
from collections.abc import Callable, Mapping
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


class RobloxStudioRunner(OperationRunnerPort):
    """The read side of the ``roblox-studio`` provider."""

    def __init__(
        self,
        studio_mcp: Path,
        *,
        session_factory: Callable[[], StudioMcpSession] | None = None,
        studio_version_of: Callable[[Path], str] = studio_version,
        discover_seconds: float = 20.0,
    ) -> None:
        self._studio_mcp = studio_mcp
        self._session = session_factory or (lambda: StudioMcpSession([str(studio_mcp)]))
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

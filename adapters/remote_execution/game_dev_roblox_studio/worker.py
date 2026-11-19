"""The ``roblox-studio`` provider as a worker creates it (SIP-0117 R4.6; #3039).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

The worker's factory finds this module the way the runtime finds ``eligibility.AUTHORITY``, by
looking in each provider package, so the provider's name stays in this directory. The settings
are the worker's own ``roblox_studio_*`` fields, which its config requires for this provider.

What the operation was proved on is read from the qualifications directory at each claim, from
the newest passing re-qualification (#3048): ``scripts/dev/studio_requalify.py`` writes it.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio.qualification import Qualifications
from adapters.remote_execution.game_dev_roblox_studio.runner import (
    PROVIDER,
    NotProved,
    ProvedOn,
    RobloxStudioRunner,
    studio_version,
)
from adapters.remote_execution.game_dev_roblox_studio.studio_app import (
    MacStudioApp,
    PlaceFiles,
    StudioApp,
)
from squadops.remote_execution.workers import HostCheck

__all__ = ["PROVIDER", "SETTINGS", "create_qualifier", "create_runner", "host_checks"]

#: The settings the runner is created with.
SETTINGS = (
    "roblox_studio_mcp",
    "roblox_studio_place_file",
    "roblox_studio_baseline_file",
    "roblox_studio_baseline_sha256",
    "roblox_studio_baseline_digest",
    "roblox_studio_qualifications",
)


def create_runner(settings: Mapping[str, str]) -> RobloxStudioRunner:
    """The runner on this machine's Studio, pinned by its qualification records. Raises naming
    each setting that is missing or unknown, and each file or directory that isn't there: a
    worker that started on a wrong path would register as serving and fail every claim."""
    files, mcp = _place(settings)
    qualifications = Qualifications(Path(settings["roblox_studio_qualifications"]).expanduser())
    return RobloxStudioRunner(mcp, place_files=files, proved_on=qualifications)


def create_qualifier(
    settings: Mapping[str, str],
) -> tuple[Qualifications, Callable[[ProvedOn], RobloxStudioRunner]]:
    """What a re-qualification runs with: the worker's records, and a runner on the same Studio
    and place held to the pins under test."""
    files, mcp = _place(settings)
    qualifications = Qualifications(Path(settings["roblox_studio_qualifications"]).expanduser())
    return qualifications, lambda pins: RobloxStudioRunner(mcp, place_files=files, proved_on=pins)


def _place(settings: Mapping[str, str]) -> tuple[PlaceFiles, Path]:
    missing = [name for name in SETTINGS if not settings.get(name)]
    unknown = sorted(set(settings) - set(SETTINGS))
    if missing or unknown:
        raise ValueError(f"{PROVIDER}'s settings: missing {missing}, unknown {unknown}")
    paths = {
        name: Path(settings[name]).expanduser()
        for name in ("roblox_studio_mcp", "roblox_studio_place_file", "roblox_studio_baseline_file")
    }
    absent = [f"{name} ({path})" for name, path in paths.items() if not path.is_file()]
    if absent:
        raise ValueError(f"{PROVIDER}'s files aren't there: {'; '.join(absent)}")
    files = PlaceFiles(
        place=paths["roblox_studio_place_file"],
        baseline=paths["roblox_studio_baseline_file"],
        baseline_sha256=settings["roblox_studio_baseline_sha256"],
        baseline_digest=settings["roblox_studio_baseline_digest"],
    )
    return files, paths["roblox_studio_mcp"]


def host_checks(settings: Mapping[str, str], app: StudioApp | None = None) -> list[HostCheck]:
    """What ``squadops doctor`` checks of the Mac a Studio worker runs on (#3046). Reads only:
    nothing is opened, started or written. ``app`` is the Mac's Studio, for a test to stand
    in for.

    - **Studio:** installed where the settings say, with a version that can be read;
    - **StudioMCP:** the proxy present and executable;
    - **the place:** the place file there, and the baseline file there and equal to its pin;
    - **qualified:** a passing re-qualification of the Studio installed now (#3048), on the
      channel a running Studio is on (#3206). An update or a channel move that hasn't been
      re-qualified fails here before it fails a claim."""
    mcp = Path(settings.get("roblox_studio_mcp") or "").expanduser()
    checks = []
    try:
        version = studio_version(mcp)
    except ValueError as e:
        version = None
        checks.append(HostCheck("studio", False, str(e)))
    else:
        checks.append(HostCheck("studio", True, f"Studio {version} is installed"))
    runs = mcp.is_file() and os.access(mcp, os.X_OK)
    checks.append(
        HostCheck(
            "studio_mcp",
            runs,
            f"{mcp} is present" if runs else f"{mcp} isn't there, or can't be run",
        )
    )
    checks.append(_place_check(settings))
    if app is None and len(mcp.parents) > 2:
        # ``StudioMCP`` sits at ``…/RobloxStudio.app/Contents/MacOS/StudioMCP``.
        app = MacStudioApp(mcp.parents[2])
    checks.append(_qualified_check(settings, version, app))
    return checks


def _place_check(settings: Mapping[str, str]) -> HostCheck:
    place = Path(settings.get("roblox_studio_place_file") or "").expanduser()
    baseline = Path(settings.get("roblox_studio_baseline_file") or "").expanduser()
    missing = [str(p) for p in (place, baseline) if not p.is_file()]
    if missing:
        return HostCheck("place", False, f"not there: {', '.join(missing)}")
    held = hashlib.sha256(baseline.read_bytes()).hexdigest()
    pinned = settings.get("roblox_studio_baseline_sha256") or ""
    if held != pinned:
        return HostCheck(
            "place",
            False,
            f"the baseline file {baseline} is {held[:16]}…, not the pinned {pinned[:16]}…",
        )
    return HostCheck("place", True, f"{place.name}, and its baseline equal to its pin")


def _qualified_check(
    settings: Mapping[str, str], installed: str | None, app: StudioApp | None
) -> HostCheck:
    directory = Path(settings.get("roblox_studio_qualifications") or "").expanduser()
    try:
        pins = Qualifications(directory).current()
    except (ValueError, NotProved) as e:
        return HostCheck("qualified", False, str(e))
    if installed is not None and pins.studio_version != installed:
        return HostCheck(
            "qualified",
            False,
            f"Studio is {installed}, and the worker was qualified on {pins.studio_version}: "
            "re-qualify (scripts/dev/studio_requalify.py)",
        )
    qualified = (
        f"qualified on Studio {pins.studio_version}, channel {pins.studio_channel} "
        f"({pins.record[:16]}…)"
    )
    # A channel is a running Studio's (#3206): with none running there is none to compare,
    # and the next claim reads it.
    try:
        running = app.channel() if app is not None and app.pids() else None
    except OSError as e:
        return HostCheck(
            "qualified",
            False,
            f"the running Studio's channel can't be read ({e}), so every claim is refused: "
            f"the worker was {qualified}",
        )
    if running is None:
        return HostCheck("qualified", True, f"{qualified}; no Studio is running to compare")
    if running != pins.studio_channel:
        return HostCheck(
            "qualified",
            False,
            f"Studio is on channel {running}, and the worker was qualified on channel "
            f"{pins.studio_channel}: re-qualify (scripts/dev/studio_requalify.py)",
        )
    return HostCheck("qualified", True, qualified)

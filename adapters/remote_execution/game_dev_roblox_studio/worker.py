"""The ``roblox-studio`` provider as a worker creates it (SIP-0117 R4.6; #3039).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

The worker's factory finds this module the way the runtime finds ``eligibility.AUTHORITY``, by
looking in each provider package, so the provider's name stays in this directory. The settings
are the worker's own ``roblox_studio_*`` fields, which its config requires for this provider.

What the operation was proved on is read from the qualifications directory at each claim, from
the newest passing re-qualification (#3048): ``scripts/dev/studio_requalify.py`` writes it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio.qualification import Qualifications
from adapters.remote_execution.game_dev_roblox_studio.runner import (
    PROVIDER,
    ProvedOn,
    RobloxStudioRunner,
)
from adapters.remote_execution.game_dev_roblox_studio.studio_app import PlaceFiles

__all__ = ["PROVIDER", "SETTINGS", "create_runner", "create_qualifier"]

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

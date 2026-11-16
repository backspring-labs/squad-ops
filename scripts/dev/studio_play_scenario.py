#!/usr/bin/env python3
"""Play a frozen scenario on a repository's source in Roblox Studio, as ``play_scenario`` (#3040).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

The ``roblox-studio`` provider's one operation, run by hand, with the same request a worker
is handed:
- the scenario file is read and frozen under ``roblox-studio/1``;
- ``<repo>/src`` is the candidate;
- the transaction syncs it, holds the place's state, plays the scenario, and prints each
  assertion's record.

It writes the candidate's scripts into the place, never saves the place and never publishes.
The runner is created as the worker creates it, from the worker's own ``roblox-studio``
settings (``SQUADOPS__WORKER__ROBLOX_STUDIO_*``: StudioMCP, the place and baseline files, their
pins and the proved-on Studio), so a hand run and the worker are held to the same pins.

    python scripts/dev/studio_play_scenario.py ~/Code/z_tower-ascension scenario.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio import worker
from adapters.remote_execution.game_dev_roblox_studio.runner import OPERATION, PROVIDER
from adapters.remote_execution.game_dev_roblox_studio.vocabulary import VOCABULARY
from squadops.remote_execution.models import RemoteOperationRequest
from squadops.remote_execution.scenario import (
    ScenarioRefused,
    frozen_scenario,
    staged_revision,
)

_PREFIX = "SQUADOPS__WORKER__"


async def _main(repo: Path, scenario_file: Path) -> int:
    runner = worker.create_runner(
        {name: os.environ.get(_PREFIX + name.upper(), "") for name in worker.SETTINGS}
    )
    files = {
        p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted((repo / "src").rglob("*"))
        if p.is_file()
    }
    try:
        scenario = frozen_scenario(json.loads(scenario_file.read_text()), VOCABULARY)
    except ScenarioRefused as refused:
        print(f"refused before play, and Studio wasn't touched: {refused}")
        return 2
    request = RemoteOperationRequest(
        contract="game.scenario_verification", mode="play", provider=PROVIDER,
        operation=OPERATION, location="worker", source_revision=staged_revision(files),
        source_files=files, scenario=scenario, task_id="studio-play-scenario",
        dispatch_id="by-hand",
    )  # fmt: skip
    started = time.monotonic()
    result = await runner.run(request)
    print(f"{result.status.value} in {time.monotonic() - started:.1f}s {result.reason}")
    for record in result.records:
        print(f"  {record.assertion_id}: {record.outcome.value} ({record.context}) "
              f"observed {record.observed}, expected {record.expected}")  # fmt: skip
    for item in result.evidence:
        print(f"--- {item.name} ---\n{item.content[-1500:]}")
    return 0 if result.status.value == "completed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "repo", type=Path, help="the product repository whose src/ is the candidate"
    )
    parser.add_argument("scenario", type=Path, help="a squadops.scenario/1 declaration (JSON)")
    args = parser.parse_args()
    return asyncio.run(_main(args.repo.expanduser(), args.scenario))


if __name__ == "__main__":
    sys.exit(main())

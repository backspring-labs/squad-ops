#!/usr/bin/env python3
"""Re-qualify the Studio worker on the Studio this Mac runs now, and record the run (#3048).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

After Studio updates itself or moves release channel, every claim reads ``not_executed`` naming
the version, channel or tool list that changed (R2.4, R5.29). This run is the only way to move
the pin: the qualification scenario played,
the place reset (Studio quit, the place restored and Studio reopened), and the scenario played
again. The record is written to the worker's qualifications directory, passed or failed, and the
worker's next claim reads the newest passing one. A failed run leaves the pin where it was and
names the step that failed.

It reads the worker's own settings (``SQUADOPS__WORKER__ROBLOX_STUDIO_*``) and holds Studio for
the whole run, so a worker claim waits for it. Studio must be in front when the scenario clicks.

    python scripts/dev/studio_requalify.py ~/Code/z_tower-ascension scenario.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio import worker as studio_worker
from adapters.remote_execution.game_dev_roblox_studio.qualification import (
    QualificationRecord,
    requalify,
)
from adapters.remote_execution.game_dev_roblox_studio.runner import OPERATION, PROVIDER
from adapters.remote_execution.game_dev_roblox_studio.vocabulary import VOCABULARY
from squadops.remote_execution.models import RemoteOperationRequest
from squadops.remote_execution.scenario import frozen_scenario, staged_revision

_PREFIX = "SQUADOPS__WORKER__"


async def _main(repo: Path, scenario_file: Path) -> int:
    records, runner_for = studio_worker.create_qualifier(
        {name: os.environ.get(_PREFIX + name.upper(), "") for name in studio_worker.SETTINGS}
    )
    files = {
        p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted((repo / "src").rglob("*"))
        if p.is_file()
    }
    scenario = frozen_scenario(json.loads(scenario_file.read_text()), VOCABULARY)

    def request_for(name: str) -> RemoteOperationRequest:
        slug = name.replace(" ", "-")
        return RemoteOperationRequest(
            contract="game.scenario_verification", mode="play", provider=PROVIDER,
            operation=OPERATION, location="worker", source_revision=staged_revision(files),
            source_files=files, scenario=scenario, task_id=f"requalify-{slug}",
            dispatch_id=f"requalify-{slug}-1",
        )  # fmt: skip

    pinned = records.pinned()
    print("pinned before: " + (_studio(pinned) if pinned else "nothing"))
    record, path = await requalify(records, runner_for, request_for)
    print(f"{'passed' if record.passed else 'FAILED'}: Studio {_studio(record)}, "
          f"tools {record.studio_tools[:24]}…")  # fmt: skip
    changed = (
        "can't be said (the replaced record holds no per-tool digests)"
        if record.tools_changed is None
        else str(list(record.tools_changed))
    )
    print(
        f"  tools added {list(record.tools_added)}, removed {list(record.tools_removed)}, "
        f"changed {changed}"
    )
    for step in record.steps:
        print(f"  {step.name}: {step.status} {step.reason}".rstrip())
        for line in step.records:
            print(f"    {line}")
    if record.failing:
        print(f"  failing: {record.failing}")
    print(f"recorded: {path}")
    return 0 if record.passed else 1


def _studio(record: QualificationRecord) -> str:
    """A record's Studio: its version, and its channel or that it names none (#3206)."""
    channel = f"channel {record.studio_channel}" if record.studio_channel else "no channel named"
    return f"{record.studio_version or 'no version read'}, {channel}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo", type=Path, help="the product repository whose src/ is played")
    parser.add_argument("scenario", type=Path, help="the qualification scenario (JSON)")
    args = parser.parse_args()
    return asyncio.run(_main(args.repo.expanduser(), args.scenario))


if __name__ == "__main__":
    sys.exit(main())

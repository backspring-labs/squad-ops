#!/usr/bin/env python3
"""Play the place open in Roblox Studio once and stop, holding its state (#3039).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

The Studio adapter's frame around play (SIP-0117 R3.6), run by hand:
1. The place is confirmed as an unpublished local one in Edit.
2. The synced scripts are checked for attributes and tags.
3. The non-script baseline is taken.
4. Play is started, then stopped.
5. The baseline is taken again, and must be equal.

It writes nothing into the place, beyond what play itself does and stop throws away.

    python scripts/dev/studio_play_round.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.runner import RobloxStudioRunner

STUDIO_MCP = Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP")


async def _main(studio_mcp: Path) -> int:
    started = time.monotonic()
    try:
        held = await RobloxStudioRunner(studio_mcp).play_round()
    except (place.PlaceStateError, place.PlaceSyncError) as e:
        print(f"refused: {e}")
        return 1
    print(
        f"played and stopped; {held.instances} instances held, baseline "
        f"{held.baseline_digest[:16]}, in {time.monotonic() - started:.1f}s"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--studio-mcp", type=Path, default=STUDIO_MCP, help="StudioMCP's path")
    return asyncio.run(_main(parser.parse_args().studio_mcp))


if __name__ == "__main__":
    sys.exit(main())

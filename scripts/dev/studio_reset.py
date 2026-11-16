#!/usr/bin/env python3
"""Reset the place in Roblox Studio from its read-only baseline file, reopening Studio (#3039).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

The Studio adapter's reset (SIP-0117 R3.6), run by hand:
1. Studio is quit, by a kill if it won't go. Anything unsaved in it is lost.
2. Its lock is cleared, and the baseline file is copied over the place.
3. Studio is opened on the place again.
4. The reopened place must be an unpublished local one in Edit, holding the pinned non-script
   baseline.

The pins are given, never read from the files, so a changed baseline file is refused.

    python scripts/dev/studio_reset.py ~/Code/z_tower-ascension-place/ta-copy.rbxl \\
        ~/Code/z_tower-ascension-place/ta-copy.pristine.rbxl \\
        --baseline-sha256 <sha256 of the baseline file> --baseline-digest <its non-script baseline>
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.runner import RobloxStudioRunner
from adapters.remote_execution.game_dev_roblox_studio.studio_app import PlaceFiles

STUDIO_MCP = Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP")


async def _main(args: argparse.Namespace) -> int:
    files = PlaceFiles(
        place=args.place.expanduser(),
        baseline=args.baseline.expanduser(),
        baseline_sha256=args.baseline_sha256,
        baseline_digest=args.baseline_digest,
    )
    runner = RobloxStudioRunner(args.studio_mcp, place_files=files)
    started = time.monotonic()
    try:
        await runner.reset()
    except place.PlaceStateError as e:
        print(f"refused: {e}")
        return 1
    print(f"reset and reopened in {time.monotonic() - started:.1f}s, holding the pinned baseline")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("place", type=Path, help="the place file Studio opens")
    parser.add_argument("baseline", type=Path, help="the read-only baseline place file")
    parser.add_argument(
        "--baseline-sha256", required=True, help="the baseline file's pinned sha256"
    )
    parser.add_argument("--baseline-digest", required=True, help="its pinned non-script baseline")
    parser.add_argument("--studio-mcp", type=Path, default=STUDIO_MCP, help="StudioMCP's path")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())

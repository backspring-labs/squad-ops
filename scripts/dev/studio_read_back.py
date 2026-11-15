#!/usr/bin/env python3
"""Read the place open in Roblox Studio and compare it with a repository's source (#3039).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

The Studio adapter's read side, run by hand: what it registers (the provider's version, Studio's
version and the tool-schema digest), identity, and the read-back of the three synced folders
compared with ``<repo>/src``. It reads only: nothing is written into Studio, nothing is published.
Enable the server first: Studio's Assistant → … → Manage MCP Servers → Enable Studio as MCP server.

    python scripts/dev/studio_read_back.py ~/Code/z_tower-ascension
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.runner import RobloxStudioRunner
from adapters.remote_execution.game_dev_roblox_studio.session import StudioMcpSession

STUDIO_MCP = Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP")


async def _main(repo: Path, studio_mcp: Path) -> int:
    runner = RobloxStudioRunner(studio_mcp)
    print("registers:", dict(await runner.tool_versions()))
    session = StudioMcpSession([str(studio_mcp)])
    await session.open()
    try:
        studio = await place.identity(session)
        print(
            f"identity: one Studio in {studio.mode} mode, holding {studio.file}, not in the cloud"
        )
        started = time.monotonic()
        read = await place.read_scripts(session, studio.studio_id)
        print(f"read back {len(read)} scripts in {time.monotonic() - started:.1f}s")
    finally:
        await session.close()
    files = {
        p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted((repo / "src").rglob("*"))
        if p.is_file()
    }
    differences = await runner.read_back(files)
    print(f"compared with {len(files)} files under {repo / 'src'}: {len(differences)} differences")
    for difference in differences:
        print(f"  - {difference}")
    return 1 if differences else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo", type=Path, help="the product repository whose src/ is compared")
    parser.add_argument("--studio-mcp", type=Path, default=STUDIO_MCP, help="StudioMCP's path")
    args = parser.parse_args()
    args.repo = args.repo.expanduser()
    if not (args.repo / "src").is_dir():
        print(f"{args.repo} has no src/ directory", file=sys.stderr)
        return 2
    return asyncio.run(_main(args.repo, args.studio_mcp))


if __name__ == "__main__":
    sys.exit(main())

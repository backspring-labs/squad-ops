#!/usr/bin/env python3
"""Sync a repository's source into the place open in Roblox Studio, and read it back (#3039).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

The Studio adapter's sync (SIP-0117 D10), run by hand. It writes into the place open in Studio,
which must be an unpublished local place (``PlaceId`` 0): the harness refuses any other before it
writes. It never saves the place and never publishes, so closing Studio without saving discards it.

    python scripts/dev/studio_sync.py ~/Code/z_tower-ascension            # sync src/ as it is
    python scripts/dev/studio_sync.py ~/Code/z_tower-ascension --round-trip

``--round-trip`` proves a change and its undoing. It syncs ``src/`` with one script changed, one
added and one removed, then ``src/`` as it is, and each read-back must match its manifest.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio.runner import RobloxStudioRunner

STUDIO_MCP = Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP")
ADDED = "src/Shared/Modules/SquadOpsSyncProbe.luau"
ADDED_TEXT = (
    '-- Added by the sync round trip.\nlocal Probe = {}\nProbe.text = "é ]] \\\\"\nreturn Probe\n'
)


def _source(repo: Path) -> dict[str, str]:
    return {
        p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted((repo / "src").rglob("*"))
        if p.is_file()
    }


def _changed(files: dict[str, str]) -> dict[str, str]:
    """``files`` with its first Shared module changed, a module added and its last client file
    removed."""
    changed = dict(files)
    shared = next(p for p in sorted(files) if p.startswith("src/Shared/") and p.endswith(".luau"))
    client = next(p for p in sorted(files, reverse=True) if p.startswith("src/Client/"))
    changed[shared] = files[shared] + "\n-- changed by the sync round trip\n"
    changed[ADDED] = ADDED_TEXT
    del changed[client]
    print(f"  the change: {shared} edited, {ADDED} added, {client} removed")
    return changed


async def _sync(runner: RobloxStudioRunner, files: dict[str, str], what: str) -> None:
    started = time.monotonic()
    result = await runner.sync(files)
    print(
        f"{what}: wrote {len(result.written)}, removed {len(result.removed)}, read back and "
        f"matched in {time.monotonic() - started:.1f}s"
    )
    for path in (*result.written, *result.removed):
        print(f"  - {path}")


async def _main(repo: Path, studio_mcp: Path, round_trip: bool) -> int:
    runner = RobloxStudioRunner(studio_mcp)
    files = _source(repo)
    if round_trip:
        await _sync(runner, _changed(files), "the changed tree")
    await _sync(runner, files, f"{repo / 'src'} as it is")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo", type=Path, help="the product repository whose src/ is synced")
    parser.add_argument("--studio-mcp", type=Path, default=STUDIO_MCP, help="StudioMCP's path")
    parser.add_argument("--round-trip", action="store_true", help="sync a change, then undo it")
    args = parser.parse_args()
    args.repo = args.repo.expanduser()
    if not (args.repo / "src").is_dir():
        print(f"{args.repo} has no src/ directory", file=sys.stderr)
        return 2
    return asyncio.run(_main(args.repo, args.studio_mcp, args.round_trip))


if __name__ == "__main__":
    sys.exit(main())

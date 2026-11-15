"""What the read side reads from the place in Studio (SIP-0117 R3.6; the game plan §2.6; #3039).

- **Identity, as far as reading allows:** exactly one connected Studio, in Edit mode, holding a
  place never saved to the cloud. ``PlaceId`` 0 and the baseline digest take ``execute_luau``,
  which is the harness's (#3040).
- **Read-back** of every script in the three synced folders: its class, location and text, in
  pages each under 90,000 characters. A tree read that leaves part of the tree unexplored, or that
  fills its result limit, is refused rather than read as the whole tree.
- **The comparison** with a source manifest, file by file.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from adapters.remote_execution.game_dev_roblox_studio.session import (
    StudioMcpSession,
    StudioSessionError,
    StudioToolError,
)

#: The three synced folders: where each sits in Studio, and its directory in the repository.
SYNCED_FOLDERS = {
    "ServerScriptService.Server": "src/Server",
    "ReplicatedStorage.Shared": "src/Shared",
    "StarterPlayer.StarterPlayerScripts.Client": "src/Client",
}

#: A source file's suffix, and the script class it is in Studio. Longest first.
SCRIPT_SUFFIXES = (
    (".server.luau", "Script"),
    (".local.luau", "LocalScript"),
    (".luau", "ModuleScript"),
)
SCRIPT_CLASSES = frozenset(cls for _, cls in SCRIPT_SUFFIXES)

#: R3.6: a result is capped at 100,000 characters and reports success when truncated, so every
#: page stays under this.
PAGE_LIMIT = 90_000

#: Deep enough for the whole folder: ``search_game_tree``'s absolute maximum.
TREE_DEPTH = 10
#: A tree read that returns this many nodes may have been cut, and is refused.
TREE_LIMIT = 5_000

_LINE = re.compile(r"^ *(\d+)→(.*)$")
_PAST_END = re.compile(r"\nNote: Requested to read until line \d+, but file only has (\d+) lines$")
_STARTS_PAST_END = re.compile(r"exceeds file length \((\d+)\)")


class PlaceReadError(RuntimeError):
    """The place couldn't be read as the read side requires; the message says why."""


@dataclass(frozen=True)
class StudioIdentity:
    studio_id: str
    file: str
    mode: str


@dataclass(frozen=True)
class ScriptText:
    script_class: str
    text: str


async def identity(
    session: StudioMcpSession, *, discover_seconds: float = 20.0, poll_seconds: float = 0.5
) -> StudioIdentity:
    """The one connected Studio, in Edit mode, holding a place never saved to the cloud, or
    :class:`PlaceReadError` saying which of those fails. ``StudioMCP`` finds a running Studio a
    few seconds after it starts, so an empty list is asked again until ``discover_seconds``."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + discover_seconds
    while True:
        listed = _json(await session.call("list_roblox_studios", {}), "list_roblox_studios")
        studios = listed.get("studios") if isinstance(listed, dict) else None
        if not isinstance(studios, list):
            raise PlaceReadError(f"list_roblox_studios answered no list: {listed!r:.200}")
        if studios or loop.time() >= deadline:
            break
        await asyncio.sleep(poll_seconds)
    if len(studios) != 1:
        raise PlaceReadError(f"exactly one connected Studio is required; {len(studios)} are")
    [studio] = studios
    if studio.get("persistedToCloud") is not False:
        raise PlaceReadError(
            f"the place in Studio ({studio.get('file')!r}) is saved to the cloud, or doesn't say"
        )
    state = await session.call("get_studio_state", {"studio_id": studio["id"]})
    mode = re.search(r"Current Studio Mode: (\w+)", state)
    if mode is None:
        raise PlaceReadError(f"get_studio_state names no mode: {state!r:.200}")
    if mode.group(1) != "Edit":
        raise PlaceReadError(f"Studio is in {mode.group(1)} mode; the read side reads in Edit")
    return StudioIdentity(str(studio["id"]), str(studio.get("file") or ""), mode.group(1))


async def read_scripts(session: StudioMcpSession, studio_id: str) -> dict[str, ScriptText]:
    """Every script in the three synced folders, by its path in Studio."""
    scripts: dict[str, ScriptText] = {}
    for folder in SYNCED_FOLDERS:
        for node in await _tree(session, studio_id, folder):
            if node.get("className") not in SCRIPT_CLASSES:
                continue
            path = str(node["fullPath"])
            text = await read_script(session, studio_id, path)
            scripts[path] = ScriptText(str(node["className"]), text)
    return scripts


async def _tree(session: StudioMcpSession, studio_id: str, folder: str) -> list[dict]:
    nodes = _json(
        await session.call(
            "search_game_tree",
            {
                "datamodel_type": "Edit",
                "studio_id": studio_id,
                "path": folder,
                "max_depth": TREE_DEPTH,
                "head_limit": TREE_LIMIT,
            },
        ),
        f"search_game_tree {folder}",
    )
    if not isinstance(nodes, list) or not nodes:
        raise PlaceReadError(f"{folder} isn't in the place, or answered no tree: {nodes!r:.200}")
    if len(nodes) >= TREE_LIMIT:
        raise PlaceReadError(f"{folder} filled the {TREE_LIMIT}-node limit; it may be cut")
    unexplored = [str(n.get("fullPath")) for n in nodes if n.get("unexploredChildCount")]
    if unexplored:
        raise PlaceReadError(f"{folder} is deeper than {TREE_DEPTH} levels at {unexplored}")
    dotted = [
        str(n.get("fullPath"))
        for n in nodes
        if n.get("className") in SCRIPT_CLASSES and "." in str(n.get("name"))
    ]
    if dotted:
        raise PlaceReadError(f"a script's name holds a dot, so its path is ambiguous: {dotted}")
    return nodes


async def read_script(
    session: StudioMcpSession, studio_id: str, path: str, *, page_lines: int = 2_000
) -> str:
    """A script's whole text, in line ranges each under :data:`PAGE_LIMIT` characters. A page
    that reaches it is read again in halves; a single line that does is refused."""
    lines: list[str] = []
    start, size = 1, page_lines
    while True:
        end = start + size - 1
        try:
            page = await session.call(
                "script_read",
                {
                    "target_file": path,
                    "studio_id": studio_id,
                    "should_read_entire_file": False,
                    "start_line_one_indexed": start,
                    "end_line_one_indexed_inclusive": end,
                },
            )
        except StudioToolError as e:
            # A range that starts just past the last line ends a script that filled the last page.
            past = _STARTS_PAST_END.search(str(e))
            if past and int(past.group(1)) == start - 1 and start > 1:
                return "\n".join(lines)
            raise
        if len(page) >= PAGE_LIMIT:
            if size == 1:
                raise PlaceReadError(f"{path} line {start} alone reaches {PAGE_LIMIT} characters")
            size = max(1, size // 2)
            continue
        note = _PAST_END.search(page)
        body = page[: note.start()] if note else page
        read = _numbered(body, start, path)
        lines += read
        if note:
            total = int(note.group(1))
            if start + len(read) - 1 != total:
                raise PlaceReadError(f"{path} reads {start + len(read) - 1} of {total} lines")
            return "\n".join(lines)
        if len(read) != size:
            raise PlaceReadError(f"{path} gave {len(read)} lines for {start}–{end}, and no end")
        start = end + 1


def _numbered(body: str, start: int, path: str) -> list[str]:
    """The lines of one page, each checked to carry the next number."""
    out: list[str] = []
    for offset, raw in enumerate(body.split("\n")):
        match = _LINE.match(raw)
        if match is None or int(match.group(1)) != start + offset:
            raise PlaceReadError(f"{path} line {start + offset} doesn't read as numbered: {raw!r}")
        out.append(match.group(2))
    return out


def manifest_scripts(source_files: Mapping[str, str]) -> tuple[dict[str, ScriptText], list[str]]:
    """The scripts a source manifest places in the three folders, by their path in Studio, and
    each file under a synced folder that isn't a script this provider places."""
    placed: dict[str, ScriptText] = {}
    unplaced: list[str] = []
    for file_path, text in sorted(source_files.items()):
        folder = next((s for s, d in SYNCED_FOLDERS.items() if file_path.startswith(d + "/")), None)
        if folder is None:
            continue
        relative = file_path[len(SYNCED_FOLDERS[folder]) + 1 :]
        suffix = next(((s, c) for s, c in SCRIPT_SUFFIXES if relative.endswith(s)), None)
        if suffix is None or "." in relative[: -len(suffix[0])]:
            unplaced.append(file_path)
            continue
        name = relative[: -len(suffix[0])].replace("/", ".")
        placed[f"{folder}.{name}"] = ScriptText(suffix[1], text)
    return placed, unplaced


def differences(read: Mapping[str, ScriptText], manifest: Mapping[str, ScriptText]) -> list[str]:
    """Each way the place's scripts differ from the manifest's, named; ``[]`` when they match."""
    found: list[str] = []
    for path in sorted(set(manifest) - set(read)):
        found.append(f"{path} is in the manifest and not in the place")
    for path in sorted(set(read) - set(manifest)):
        found.append(f"{path} is in the place and not in the manifest")
    for path in sorted(set(read) & set(manifest)):
        held, wanted = read[path], manifest[path]
        if held.script_class != wanted.script_class:
            found.append(
                f"{path} is a {held.script_class}; the manifest's is a {wanted.script_class}"
            )
        elif held.text != wanted.text:
            found.append(f"{path}'s text differs from the manifest's")
    return found


async def console(session: StudioMcpSession, studio_id: str) -> str:
    """Studio's output log as ``get_console_output`` answers it."""
    return await session.call("get_console_output", {"studio_id": studio_id})


def _json(text: str, what: str) -> object:
    try:
        return json.loads(text)
    except ValueError:
        raise PlaceReadError(f"{what} answered something other than JSON: {text!r:.200}") from None


__all__ = [
    "PlaceReadError",
    "ScriptText",
    "StudioIdentity",
    "StudioSessionError",
    "console",
    "differences",
    "identity",
    "manifest_scripts",
    "read_script",
    "read_scripts",
]

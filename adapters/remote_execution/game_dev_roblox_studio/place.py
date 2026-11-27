"""What the read side reads from the place in Studio (SIP-0117 R3.6; the game plan §2.6; #3039).

- **Identity, as far as reading allows:** exactly one connected Studio, in Edit mode, holding a
  place never saved to the cloud. ``PlaceId`` 0 and the baseline digest take ``execute_luau``,
  which is the harness's (#3040).
- **Read-back** of every script in the three synced folders: its class, location and text, in
  pages each under 90,000 characters. A tree read that leaves part of the tree unexplored, or that
  fills its result limit, is refused rather than read as the whole tree.
- **The comparison** with a source manifest, file by file.
- **Sync** (D10): the manifest's scripts written into the three folders through the harness's
  sync program, the place's other scripts removed, and the result read back whole. Before it
  writes, the harness's identity program confirms ``PlaceId`` 0 and ``GameId`` 0: a place that
  isn't Roblox's is never written.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from collections.abc import Iterator, Mapping
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


class PlaceStateError(RuntimeError):
    """The place's state refuses a transaction: a synced script carrying attributes or tags, or
    a non-script baseline that changed through play. The message names each."""


class PlaceSyncError(RuntimeError):
    """A sync was refused before it wrote, or its read-back doesn't match the manifest. The
    message names why, or each difference."""


#: The most source text one sync call carries. A call's code is its payload in hex, twice the
#: bytes, and R3.6 found Studio's tools answer large results slowly; the bound keeps each call
#: well inside its deadline.
SYNC_BATCH_BYTES = 200_000


#: The most characters one baseline page asks for. A page is answered as JSON, which escapes the
#: lines' tabs and quotes, and R3.6 caps a result at 100,000 characters; this keeps it well under.
BASELINE_PAGE_CHARS = 40_000

#: How long Studio may take to change mode after it is asked to start or stop play.
PLAY_SECONDS = 60.0


@dataclass(frozen=True)
class PlaceBaseline:
    """The place's non-script state (the harness's baseline program): its sorted lines, and their
    digest."""

    digest: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class SyncResult:
    written: tuple[str, ...]
    removed: tuple[str, ...]


@dataclass(frozen=True)
class StudioIdentity:
    studio_id: str
    file: str
    mode: str


@dataclass(frozen=True)
class ScriptText:
    script_class: str
    text: str


async def connected_studios(
    session: StudioMcpSession, *, discover_seconds: float = 20.0, poll_seconds: float = 0.5
) -> list[dict]:
    """The connected Studios as ``list_roblox_studios`` answers them. ``StudioMCP`` finds a
    running Studio a few seconds after it starts, so an empty list is asked again until
    ``discover_seconds``: an empty answer is believed only then."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + discover_seconds
    while True:
        listed = _json(await session.call("list_roblox_studios", {}), "list_roblox_studios")
        studios = listed.get("studios") if isinstance(listed, dict) else None
        if not isinstance(studios, list):
            raise PlaceReadError(f"list_roblox_studios answered no list: {listed!r:.200}")
        if studios or loop.time() >= deadline:
            return studios
        await asyncio.sleep(poll_seconds)


async def identity(
    session: StudioMcpSession, *, discover_seconds: float = 20.0, poll_seconds: float = 0.5
) -> StudioIdentity:
    """The one connected Studio, in Edit mode, holding a place never saved to the cloud, or
    :class:`PlaceReadError` saying which of those fails. ``StudioMCP`` finds a running Studio a
    few seconds after it starts, so an empty list is asked again until ``discover_seconds``."""
    studios = await connected_studios(
        session, discover_seconds=discover_seconds, poll_seconds=poll_seconds
    )
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
    for file_path, path, script in _placements(source_files):
        if path is None or script is None:
            unplaced.append(file_path)
        else:
            placed[path] = script
    return placed, unplaced


def script_files(source_files: Mapping[str, str]) -> dict[str, str]:
    """Each script the manifest places, by its path in Studio, to the staged file it came from:
    how an error Studio names in a script is read back to the request's tree (R5.32, #3200)."""
    return {
        path: file_path
        for file_path, path, _script in _placements(source_files)
        if path is not None
    }


def _placements(
    source_files: Mapping[str, str],
) -> Iterator[tuple[str, str | None, ScriptText | None]]:
    """Each staged file under a synced folder: its path, and its script's path in Studio with its
    text, or ``None`` for both when this provider doesn't place it."""
    placed: set[str] = set()
    for file_path, text in sorted(source_files.items()):
        folder = next((s for s, d in SYNCED_FOLDERS.items() if file_path.startswith(d + "/")), None)
        if folder is None:
            continue
        relative = file_path[len(SYNCED_FOLDERS[folder]) + 1 :]
        suffix = next(((s, c) for s, c in SCRIPT_SUFFIXES if relative.endswith(s)), None)
        if suffix is None or "." in relative[: -len(suffix[0])]:
            yield file_path, None, None
            continue
        parts = relative[: -len(suffix[0])].split("/")
        if parts[-1] == "init":
            # Script Sync: ``X/init.luau`` is the script ``X``, its siblings in ``X/`` its children.
            parts = parts[:-1]
            if not parts:
                yield file_path, None, None  # an init file at a folder's root names no script
                continue
        path = f"{folder}.{'.'.join(parts)}"
        if path in placed:
            yield file_path, None, None  # ``X.luau`` beside ``X/init.luau``: two scripts, one name
            continue
        placed.add(path)
        yield file_path, path, ScriptText(suffix[1], text)


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


async def confirm_unpublished(session: StudioMcpSession, studio_id: str) -> None:
    """Raises :class:`PlaceSyncError` unless the harness's identity program reads ``PlaceId`` 0
    and ``GameId`` 0 in Edit, with no play running: a local place that was never published."""
    held = await session.run_program("identity", studio_id)
    if not isinstance(held, dict):
        raise PlaceSyncError(f"the identity program answered {held!r:.200}")
    wrong = [
        f"{key} is {held.get(key)!r}"
        for key, want in (("placeId", 0), ("gameId", 0), ("edit", True), ("running", False))
        if held.get(key) != want
    ]
    if wrong:
        raise PlaceSyncError(
            "the place in Studio isn't an unpublished local place in Edit, so nothing is written: "
            + "; ".join(wrong)
        )


async def sync(
    session: StudioMcpSession, studio_id: str, manifest: Mapping[str, ScriptText]
) -> SyncResult:
    """Make the three folders hold exactly ``manifest``'s scripts, and confirm it by reading
    them back. Only what differs is written: a missing or changed script, or one whose class
    changed. A script the manifest doesn't hold is removed, unless the manifest keeps a script
    inside it, which is refused before anything is written. Raises :class:`PlaceSyncError`
    naming each difference the read-back finds."""
    await confirm_unpublished(session, studio_id)
    held = await read_scripts(session, studio_id)
    writes = sorted(
        (path for path, script in manifest.items() if held.get(path) != script), key=_depth
    )
    removes = sorted(set(held) - set(manifest), key=_depth, reverse=True)
    kept_inside = [
        f"{gone} holds {kept}"
        for gone in removes
        for kept in manifest
        if kept.startswith(gone + ".")
    ]
    if kept_inside:
        raise PlaceSyncError(
            "the manifest drops a script it keeps a script inside, and removing it would remove "
            "both: " + "; ".join(kept_inside)
        )
    for batch in _batches(writes, manifest):
        await _run_sync(session, studio_id, writes=batch, removes=[])
    if removes:
        await _run_sync(session, studio_id, writes=[], removes=[_slashed(p) for p in removes])
    found = differences(await read_scripts(session, studio_id), manifest)
    if found:
        raise PlaceSyncError(
            "the read-back after sync differs from the manifest: " + "; ".join(found)
        )
    return SyncResult(tuple(writes), tuple(removes))


def _depth(path: str) -> tuple[int, str]:
    return (path.count("."), path)


def _slashed(path: str) -> str:
    """An instance path as the sync program takes it, from its service down. Names hold no dot
    (``_tree`` refuses one), so the dots are the separators."""
    return path.replace(".", "/")


def _batches(paths: list[str], manifest: Mapping[str, ScriptText]) -> list[list[dict]]:
    """The writes, in order, cut into calls of at most :data:`SYNC_BATCH_BYTES` of source. A
    script larger than that goes alone."""
    batches: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for path in paths:
        script = manifest[path]
        weight = len(script.text.encode())
        if current and size + weight > SYNC_BATCH_BYTES:
            batches.append(current)
            current, size = [], 0
        current.append(
            {"path": _slashed(path), "class": script.script_class, "source": script.text}
        )
        size += weight
    if current:
        batches.append(current)
    return batches


async def _run_sync(
    session: StudioMcpSession, studio_id: str, *, writes: list[dict], removes: list[str]
) -> None:
    answer = await session.run_program("sync", studio_id, {"writes": writes, "removes": removes})
    if not isinstance(answer, dict) or (answer.get("written"), answer.get("removed")) != (
        len(writes),
        len(removes),
    ):
        raise PlaceSyncError(
            f"the sync program answered {answer!r:.200} for {len(writes)} writes and "
            f"{len(removes)} removes"
        )


async def baseline(
    session: StudioMcpSession, studio_id: str, *, page_chars: int = BASELINE_PAGE_CHARS
) -> PlaceBaseline:
    """The place's non-script state, read in pages, or :class:`PlaceReadError` when the pages
    don't add up to the one snapshot: a total that changes between pages, or a page that doesn't
    advance. The snapshot kept in Studio is released, however the read ends."""
    snapshot = uuid.uuid4().hex
    lines: list[str] = []
    offset, total = 0, None
    try:
        while total is None or offset < total:
            page = await session.run_program(
                "baseline",
                studio_id,
                {"snapshot": snapshot, "offset": offset, "max_chars": page_chars, "release": False},
            )
            if not isinstance(page, dict) or not isinstance(page.get("lines"), list):
                raise PlaceReadError(f"a baseline page answered {page!r:.200}")
            if total is not None and page.get("total") != total:
                raise PlaceReadError(
                    f"the baseline's total moved from {total} to {page.get('total')} between pages"
                )
            total = int(page["total"])
            advanced = int(page["next"])
            if advanced <= offset and offset < total:
                raise PlaceReadError(f"a baseline page at {offset} of {total} didn't advance")
            lines += [str(line) for line in page["lines"]]
            offset = advanced
    finally:
        await session.run_program(
            "baseline",
            studio_id,
            {"snapshot": snapshot, "offset": 0, "max_chars": 1, "release": True},
        )
    if len(lines) != total:
        raise PlaceReadError(f"the baseline read {len(lines)} lines of {total}")
    text = "\n".join(lines)
    return PlaceBaseline(hashlib.sha256(text.encode()).hexdigest(), tuple(lines))


def baseline_changes(before: PlaceBaseline, after: PlaceBaseline) -> list[str]:
    """Each instance whose state differs between two baselines, named with what changed; ``[]``
    when the digests match."""
    if before.digest == after.digest:
        return []
    old, new = _by_path(before.lines), _by_path(after.lines)
    found: list[str] = []
    for path in sorted(set(old) | set(new)):
        if path not in new:
            found.append(f"{path} is gone")
        elif path not in old:
            found.append(f"{path} appeared ({new[path].get('', '?')})")
        elif old[path] != new[path]:
            fields = sorted(
                k for k in set(old[path]) | set(new[path]) if old[path].get(k) != new[path].get(k)
            )
            found.append(
                f"{path}: "
                + "; ".join(
                    f"{k or 'class'} {_short(old[path].get(k))} -> {_short(new[path].get(k))}"
                    for k in fields
                )
            )
    return found


def _by_path(lines: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """A baseline's lines by instance path: the class under ``""``, ``attributes`` and ``tags``
    whole, and each property by its name. A line is the path, the class, then tab-separated
    fields: ``attributes{…}``, ``tags{…}`` or ``Name=value``."""
    held: dict[str, dict[str, str]] = {}
    for line in lines:
        path, cls, *fields = line.split("\t")
        entry = {"": cls}
        for field in fields:
            group = next((g for g in ("attributes", "tags") if field.startswith(g + "{")), None)
            if group is not None:
                entry[group] = field
            else:
                key, _, value = field.partition("=")
                entry[key] = value
        held[path] = entry
    return held


def _short(value: str | None) -> str:
    if value is None:
        return "(none)"
    return value if len(value) <= 120 else value[:117] + "..."


async def marked_scripts(session: StudioMcpSession, studio_id: str) -> list[str]:
    """Each script in the three synced folders carrying attributes or tags, named with them
    (#3042's rule, placed at the worker); ``[]`` when none does."""
    answer = await session.run_program("script_marks", studio_id)
    marked = answer.get("marked") if isinstance(answer, dict) else None
    if not isinstance(marked, list):
        raise PlaceReadError(f"the script-marks program answered {answer!r:.200}")
    return [
        f"{m['path']} carries "
        + " and ".join(
            f"{what} {', '.join(m[what])}" for what in ("attributes", "tags") if m.get(what)
        )
        for m in marked
    ]


async def start_play(
    session: StudioMcpSession, studio_id: str, *, seconds: float | None = None
) -> None:
    """Start play and wait until Studio reports it, or :class:`PlaceReadError`."""
    await session.call("start_stop_play", {"studio_id": studio_id, "is_start": True})
    await _wait_for_mode(session, studio_id, "Play", PLAY_SECONDS if seconds is None else seconds)


async def stop_play(
    session: StudioMcpSession, studio_id: str, *, seconds: float | None = None
) -> None:
    """Stop play and wait until Studio is back in Edit, or :class:`PlaceReadError`."""
    await session.call("start_stop_play", {"studio_id": studio_id, "is_start": False})
    await _wait_for_mode(session, studio_id, "Edit", PLAY_SECONDS if seconds is None else seconds)


async def _wait_for_mode(
    session: StudioMcpSession, studio_id: str, want: str, seconds: float, poll: float = 0.5
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while True:
        state = await session.call("get_studio_state", {"studio_id": studio_id})
        mode = re.search(r"Current Studio Mode: (\w+)", state)
        if mode and mode.group(1) == want:
            return
        if loop.time() >= deadline:
            held = mode.group(1) if mode else "no mode"
            raise PlaceReadError(f"Studio didn't reach {want} within {seconds:g}s; it reads {held}")
        await asyncio.sleep(poll)


async def console(session: StudioMcpSession, studio_id: str) -> str:
    """Studio's output log as ``get_console_output`` answers it."""
    return await session.call("get_console_output", {"studio_id": studio_id})


def _json(text: str, what: str) -> object:
    try:
        return json.loads(text)
    except ValueError:
        raise PlaceReadError(f"{what} answered something other than JSON: {text!r:.200}") from None


__all__ = [
    "connected_studios",
    "PlaceStateError",
    "PlaceBaseline",
    "baseline",
    "baseline_changes",
    "marked_scripts",
    "start_play",
    "stop_play",
    "PlaceReadError",
    "PlaceSyncError",
    "SyncResult",
    "confirm_unpublished",
    "sync",
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

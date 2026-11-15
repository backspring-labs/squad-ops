"""A stand-in for Studio's ``StudioMCP`` (#3039): JSON-RPC over stdio, answering as the real one
did on Studio 0.747 (2026-11-14), from a world file given as ``argv[1]``.

The world holds ``tools``, ``studios``, ``state``, ``trees`` (folder to nodes), ``scripts`` (path
to text), optional ``silent`` (tools that never answer), ``errors_as_success`` (tools that answer
``Error: …`` with ``isError`` false), ``page_cap`` (a page at least this long is answered as cut)
and ``log`` (a file each tools/call name is appended to).

``execute_luau`` runs only the harness's programs, matched by their exact text with hex where the
payload token is, as the adapter's ``harness`` builds them: ``identity`` answers the world's
``identity``, and ``sync`` applies its payload to ``scripts`` and ``trees``, dropping writes to the
paths in ``ignore_writes``, and saves the world back to its file. Each program run is logged as
``execute_luau:<name>``, and its code appended to ``code_log`` when the world names one. Any other
code is refused, as a program the harness doesn't hold.

``baseline`` pages the world's ``baseline`` lines (``baseline_after_play`` once play has stopped,
when given); ``baseline_stall`` answers a page that doesn't advance. ``script_marks`` answers the
world's ``marked``. ``start_stop_play`` moves the world's ``mode`` between Play and Edit, unless
``stuck`` holds it, and ``get_studio_state`` reports ``mode`` when the world has one.
"""

import json
import re
import sys
from pathlib import Path

WORLD = sys.argv[1]
world = json.load(open(WORLD))
HARNESS = (
    Path(__file__).resolve().parents[3] / "adapters/remote_execution/game_dev_roblox_studio/harness"
)
TOKEN = "{{PAYLOAD}}"
IDENTITY = {"placeId": 0, "gameId": 0, "edit": True, "running": False}
SYNCED = (
    "ServerScriptService.Server",
    "ReplicatedStorage.Shared",
    "StarterPlayer.StarterPlayerScripts.Client",
)


def reply(message_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": message_id, "result": result}) + "\n")
    sys.stdout.flush()


def text(body, error=False):
    return {"content": [{"type": "text", "text": body}], "isError": error}


def script_read(args):
    lines = world["scripts"][args["target_file"]].split("\n")
    start = args["start_line_one_indexed"]
    end = args["end_line_one_indexed_inclusive"]
    if start > len(lines):
        return text(f"ReadFileTool:99: `start_line_one_indexed` ({start}) exceeds file length "
                    f"({len(lines)})", error=True)  # fmt: skip
    body = "\n".join(f"{n:6d}→{lines[n - 1]}" for n in range(start, min(end, len(lines)) + 1))
    if end > len(lines):
        body += f"\nNote: Requested to read until line {end}, but file only has {len(lines)} lines"
    return text(body[: world.get("page_cap", 10**9)])


def program_of(code):
    """The harness program ``code`` is, and its decoded payload, or None."""
    for path in sorted(HARNESS.glob("*.luau")):
        text = path.read_text()
        if TOKEN not in text:
            if code == text:
                return path.stem, None
            continue
        head, tail = text.split(TOKEN)
        if code.startswith(head) and code.endswith(tail):
            middle = code[len(head) : len(code) - len(tail)]
            if re.fullmatch(r"[0-9a-f]*", middle):
                return path.stem, json.loads(bytes.fromhex(middle).decode())
    return None


def sync(job):
    nodes = world["trees"]
    for write in job["writes"]:
        dotted = write["path"].replace("/", ".")
        if dotted in world.get("ignore_writes", ()):
            continue
        world["scripts"][dotted] = write["source"]
        folder = next(f for f in SYNCED if dotted.startswith(f + "."))
        tree = nodes.setdefault(
            folder, [{"fullPath": folder, "name": folder.split(".")[-1], "className": "Folder"}]
        )
        parts = dotted[len(folder) + 1 :].split(".")
        for depth in range(1, len(parts) + 1):
            path = folder + "." + ".".join(parts[:depth])
            node = next((n for n in tree if n["fullPath"] == path), None)
            if node is None:
                node = {"fullPath": path, "name": parts[depth - 1], "className": "Folder"}
                tree.append(node)
            if depth == len(parts):
                node["className"] = write["class"]
    removed = 0
    for path in job["removes"]:
        dotted = path.replace("/", ".")
        if world["scripts"].pop(dotted, None) is not None:
            removed += 1
        for folder, tree in nodes.items():
            nodes[folder] = [
                n
                for n in tree
                if n["fullPath"] != dotted and not n["fullPath"].startswith(dotted + ".")
            ]
    with open(WORLD, "w") as f:
        json.dump(world, f)
    return {"written": len(job["writes"]), "replaced": 0, "removed": removed}


def baseline_page(job):
    played = world.get("played") and "baseline_after_play" in world
    lines = world["baseline_after_play"] if played else world.get("baseline", [])
    if job["release"]:
        return {"total": len(lines), "next": 0, "lines": []}
    out, used, index = [], 0, job["offset"]
    while index < len(lines):
        size = len(lines[index]) + 1
        if out and used + size > job["max_chars"]:
            break
        out.append(lines[index])
        used += size
        index += 1
    if world.get("baseline_stall"):
        index = job["offset"]
    return {"total": len(lines), "next": index, "lines": out}


def start_stop_play(args):
    if not world.get("stuck"):
        world["mode"] = "Play" if args["is_start"] else "Edit"
        if not args["is_start"]:
            world["played"] = True
    return text("Game Started" if args["is_start"] else "Game Stopped")


def execute_luau(args):
    found = program_of(args["code"])
    if found is None:
        return text("this code is not a harness program", error=True)
    name, payload = found
    if "log" in world:
        with open(world["log"], "a") as f:
            f.write(f"execute_luau:{name}\n")
    if "code_log" in world:
        with open(world["code_log"], "a") as f:
            f.write(json.dumps(args["code"]) + "\n")
    if name == "identity":
        return text(json.dumps(world.get("identity", IDENTITY)))
    if name == "baseline":
        return text(json.dumps(baseline_page(payload)))
    if name == "script_marks":
        return text(json.dumps({"marked": world.get("marked", [])}))
    return text(json.dumps(sync(payload)))


def call(name, args):
    if name in world.get("errors_as_success", ()):
        return text("Error: Could not find any instances at path 'x'")
    if name == "list_roblox_studios":
        return text(json.dumps({"studios": world["studios"]}))
    if name == "get_studio_state":
        if "mode" in world:
            return text(f"- Current Studio Mode: {world['mode']}")
        return text(world["state"])
    if name == "start_stop_play":
        return start_stop_play(args)
    if name == "search_game_tree":
        return text(json.dumps(world["trees"].get(args["path"], [])))
    if name == "script_read":
        return script_read(args)
    if name == "execute_luau":
        return execute_luau(args)
    if name == "get_console_output":
        return text(world.get("console", ""))
    return text(f"unknown tool {name}", error=True)


for line in sys.stdin:
    message = json.loads(line)
    method, message_id = message.get("method"), message.get("id")
    if method == "initialize":
        reply(message_id, {"protocolVersion": "2025-06-18", "serverInfo": {"name": "RobloxStudio"}})
    elif method == "tools/list":
        reply(message_id, {"tools": world["tools"]})
    elif method == "tools/call":
        name = message["params"]["name"]
        if "log" in world:
            with open(world["log"], "a") as f:
                f.write(name + "\n")
        if name not in world.get("silent", ()):
            reply(message_id, call(name, message["params"]["arguments"]))

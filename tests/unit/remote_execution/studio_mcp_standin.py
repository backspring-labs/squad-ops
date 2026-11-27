"""A stand-in for Studio's ``StudioMCP`` (#3039): JSON-RPC over stdio, answering as the real one
did on Studio 0.747 (2026-11-14), from a world file given as ``argv[1]``.

The world holds ``tools``, ``studios``, ``state``, ``trees`` (folder to nodes), ``scripts`` (path
to text), optional ``silent`` (tools that never answer; ``silent_in_play`` while play runs),
``errors_as_success`` (tools that answer
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
``stuck`` holds it, and ``get_studio_state`` reports ``mode`` when the world has one. Stopping
play applies ``scripts_after_play`` (path to text) to ``scripts``: an edit made in Studio while
the scenario ran.
``studios_late`` lists no Studio for that many of a session's first ``list_roblox_studios``.

A play session (#3040): ``play`` holds, per context (``server``, ``client``), each instance path
with its ``properties``, ``attributes``, ``gui`` states and ``value``, or ``unsupported`` /
``unreadable`` reasons; ``observe`` reads it as the harness's program answers. ``clicks`` maps a
clicked path to the instances it changes (``{context: {path: instance}}``, ``null`` removing
one); ``character_navigation`` puts the character at its point; ``input_errors`` lists the input
tools that answer an error; ``console`` is the output log. ``console_edit``, when given, is what
the log holds in edit mode: Studio clears its console when play starts (read 2026-11-26).
``console_reads_in_play`` answers successive reads in play, the last thereafter. Each input call's arguments are
appended to ``input_log`` when the world names one.
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
            world["scripts"].update(world.get("scripts_after_play", {}))
    return text("Game Started" if args["is_start"] else "Game Stopped")


CONTEXTS = {"Server": "server", "Client": "client"}


def observe(job, datamodel):
    instances = world.get("play", {}).get(CONTEXTS[datamodel], {})
    instance = instances.get(job["path"])
    if instance is None:
        return {"absent": True}
    for why in ("unsupported", "unreadable", "wrong_context"):
        if why in instance:
            return {why: instance[why]}
    if job["kind"] == "value":
        return {"value": instance["value"]} if "value" in instance else {"absent": True}
    section = {"property": "properties", "attribute": "attributes", "gui_state": "gui"}[job["kind"]]
    key = job["state"] if job["kind"] == "gui_state" else job["name"]
    held = instance.get(section, {})
    return {"value": held[key]} if key in held else {"absent": True}


def play_input(name, args):
    if "input_log" in world:
        with open(world["input_log"], "a") as f:
            f.write(json.dumps({"tool": name, **args}) + "\n")
    if name in world.get("input_errors", ()):
        return text(f"{name}: the game view isn't ready", error=True)
    if name == "user_mouse_input":
        moved = next(a["instance_path"] for a in args["actions"] if a["action"] == "moveTo")
        path = "@player" + moved[len("LocalPlayer") :] if moved.startswith("LocalPlayer") else moved
        for context, changes in world.get("clicks", {}).get(path, {}).items():
            for changed, instance in changes.items():
                held = world.setdefault("play", {}).setdefault(context, {})
                if instance is None:
                    held.pop(changed, None)
                else:
                    held[changed] = instance
    if name == "character_navigation":
        root = "@player.Character.HumanoidRootPart"
        world.setdefault("play", {}).setdefault("client", {})[root] = {
            "properties": {"Position": f"{args['x']}, {args['y']}, {args['z']}"}
        }
    return text("Success")


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
    if name == "observe":
        return text(json.dumps(observe(payload, args["datamodel_type"])))
    return text(json.dumps(sync(payload)))


def console():
    """The output log as it reads now: ``console_edit`` in edit mode when given, since Studio
    clears its console when play starts; in play, each of ``console_reads_in_play`` in turn and
    the last thereafter (a console that rolls); otherwise ``console``."""
    if world.get("mode") == "Edit" and "console_edit" in world:
        return world["console_edit"]
    reads = world.get("console_reads_in_play")
    if world.get("mode") == "Play" and reads:
        return reads.pop(0) if len(reads) > 1 else reads[0]
    return world.get("console", "")


def call(name, args):
    if name in world.get("errors_as_success", ()):
        return text("Error: Could not find any instances at path 'x'")
    if name == "list_roblox_studios":
        # ``studios_late``: StudioMCP finds a running Studio a few seconds after it starts, so
        # the first answers of a new session list none.
        late = world.get("studios_late", 0)
        world["studios_late"] = late - 1
        return text(json.dumps({"studios": [] if late > 0 else world["studios"]}))
    if name == "get_studio_state":
        if "mode" in world:
            return text(f"- Current Studio Mode: {world['mode']}")
        return text(world["state"])
    if name == "start_stop_play":
        return start_stop_play(args)
    if name in ("user_mouse_input", "user_keyboard_input", "character_navigation"):
        return play_input(name, args)
    if name == "search_game_tree":
        return text(json.dumps(world["trees"].get(args["path"], [])))
    if name == "script_read":
        return script_read(args)
    if name == "execute_luau":
        return execute_luau(args)
    if name == "get_console_output":
        return text(console())
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
        playing = world.get("mode") == "Play"
        if name not in world.get("silent", ()) and not (
            playing and name in world.get("silent_in_play", ())
        ):
            reply(message_id, call(name, message["params"]["arguments"]))

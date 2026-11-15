"""A stand-in for Studio's ``StudioMCP`` (#3039): JSON-RPC over stdio, answering as the real one
did on Studio 0.747 (2026-11-14), from a world file given as ``argv[1]``.

The world holds ``tools``, ``studios``, ``state``, ``trees`` (folder to nodes), ``scripts`` (path
to text), optional ``silent`` (tools that never answer), ``errors_as_success`` (tools that answer
``Error: …`` with ``isError`` false), ``page_cap`` (a page at least this long is answered as cut)
and ``log`` (a file each tools/call name is appended to).
"""

import json
import sys

world = json.load(open(sys.argv[1]))


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


def call(name, args):
    if name in world.get("errors_as_success", ()):
        return text("Error: Could not find any instances at path 'x'")
    if name == "list_roblox_studios":
        return text(json.dumps({"studios": world["studios"]}))
    if name == "get_studio_state":
        return text(world["state"])
    if name == "search_game_tree":
        return text(json.dumps(world["trees"].get(args["path"], [])))
    if name == "script_read":
        return script_read(args)
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

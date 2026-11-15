"""A session with Studio's own MCP server, ``StudioMCP``, over stdio (SIP-0117 R3.6, #3039).

JSON-RPC, one request per line. Every call has a deadline, and a tool outside the allow-list is
refused before it is sent (deny by default). Studio answers some errors as a successful result
(``isError`` false, text ``Error: …``), so an answer is an error whichever way it is marked.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

#: The read-only slice's allow-list (#3039): what the read side calls, and nothing else. Each must
#: be in the live ``tools/list`` and marked read-only there. ``http_get`` and ``search_asset`` are
#: marked read-only too, and reach outside Studio, so the allow-list is named, never derived.
READ_ONLY_TOOLS = frozenset(
    {
        "list_roblox_studios",
        "get_studio_state",
        "search_game_tree",
        "script_read",
        "get_console_output",
    }
)

#: The MCP protocol version this session speaks.
PROTOCOL_VERSION = "2025-06-18"

#: A reply line can carry a whole script tree; asyncio's default line limit is 64 KiB.
_LINE_LIMIT = 32 * 1024 * 1024


class StudioSessionError(RuntimeError):
    """The session couldn't do what was asked: the server didn't answer in time, closed, or
    answered with something that isn't a reply."""


class ToolDenied(StudioSessionError):
    """A tool outside the allow-list was asked for. Nothing was sent."""


class StudioToolError(StudioSessionError):
    """A tool answered with an error, marked as one or not."""


@dataclass(frozen=True)
class ToolCheck:
    """The live ``tools/list``, as the worker registers it (R4.6): how many tools, and the digest
    of their schemas, so an operation can read ``not_executed`` when Studio changed under it."""

    count: int
    schema_digest: str


def tool_check(tools: Sequence[Mapping[str, Any]], allowed: frozenset[str]) -> ToolCheck:
    """The check of a live ``tools/list`` against ``allowed``, or :class:`StudioSessionError`
    naming every allowed tool that is missing or isn't marked read-only."""
    by_name = {str(t.get("name")): t for t in tools}
    problems = [
        f"{name} is not offered" if name not in by_name else f"{name} is not marked read-only"
        for name in sorted(allowed)
        if name not in by_name
        or (by_name[name].get("annotations") or {}).get("readOnlyHint") is not True
    ]
    if problems:
        raise StudioSessionError("Studio's tool list fails the allow-list: " + "; ".join(problems))
    canonical = json.dumps(sorted(tools, key=lambda t: str(t.get("name"))), sort_keys=True)
    return ToolCheck(len(tools), hashlib.sha256(canonical.encode()).hexdigest())


class StudioMcpSession:
    """One connection to ``StudioMCP``: started by :meth:`open`, ended by :meth:`close`."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        allowed: frozenset[str] = READ_ONLY_TOOLS,
        call_seconds: float = 60.0,
        start_seconds: float = 20.0,
    ) -> None:
        if not command:
            raise ValueError("the StudioMCP command is empty")
        self._command = tuple(command)
        self._allowed = allowed
        self._call_seconds = call_seconds
        self._start_seconds = start_seconds
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self.tools: ToolCheck | None = None

    async def open(self) -> ToolCheck:
        """Start the server, initialize, and check its live tool list."""
        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=_LINE_LIMIT,
        )
        await self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "squadops-worker", "version": "1"},
            },
            self._start_seconds,
        )
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        listed = await self._request("tools/list", {}, self._start_seconds)
        tools = listed.get("tools")
        if not isinstance(tools, list):
            raise StudioSessionError(f"tools/list answered no tool list: {listed!r:.200}")
        self.tools = tool_check(tools, self._allowed)
        return self.tools

    async def close(self) -> None:
        process, self._process = self._process, None
        if process is None or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError:
            process.kill()
            await process.wait()

    async def call(self, tool: str, arguments: Mapping[str, Any]) -> str:
        """The text ``tool`` answered with, or :class:`StudioToolError`. A tool outside the
        allow-list raises :class:`ToolDenied` before anything is sent."""
        if tool not in self._allowed:
            raise ToolDenied(f"{tool} is not on the allow-list; it was not sent")
        result = await self._request(
            "tools/call", {"name": tool, "arguments": dict(arguments)}, self._call_seconds
        )
        content = result.get("content")
        if not isinstance(content, list):
            raise StudioSessionError(f"{tool} answered no content: {result!r:.200}")
        text = "".join(str(c.get("text", "")) for c in content if c.get("type") == "text")
        if result.get("isError") is True or text.startswith("Error:"):
            raise StudioToolError(f"{tool}: {text}")
        return text

    async def _send(self, message: Mapping[str, Any]) -> None:
        process = self._open_process()
        assert process.stdin is not None
        process.stdin.write((json.dumps(message) + "\n").encode())
        await process.stdin.drain()

    async def _request(self, method: str, params: Mapping[str, Any], seconds: float) -> dict:
        request_id, self._next_id = self._next_id, self._next_id + 1
        await self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        try:
            reply = await asyncio.wait_for(self._reply(request_id), seconds)
        except TimeoutError:
            raise StudioSessionError(f"{method} had no answer within {seconds:g}s") from None
        if "error" in reply:
            raise StudioSessionError(f"{method} was refused: {reply['error']!r:.300}")
        result = reply.get("result")
        if not isinstance(result, dict):
            raise StudioSessionError(f"{method} answered no result: {reply!r:.200}")
        return result

    async def _reply(self, request_id: int) -> dict:
        """The reply to ``request_id``. Notifications and other lines are passed over."""
        process = self._open_process()
        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                raise StudioSessionError("StudioMCP closed its output")
            with contextlib.suppress(ValueError):
                message = json.loads(line)
                if isinstance(message, dict) and message.get("id") == request_id:
                    return message

    def _open_process(self) -> asyncio.subprocess.Process:
        if self._process is None:
            raise StudioSessionError("the session isn't open")
        return self._process

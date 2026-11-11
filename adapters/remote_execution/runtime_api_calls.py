"""One caller's HTTP calls to the runtime API, and the strict reading of its answers
(SIP-0117 R5.5, R5.6).

The worker and the requester each call the runtime API with a service client's token, and each
keeps three ways a call fails apart:

- **unreachable**: no answer, or a server failure. ``RuntimeUnreachable``; the caller may try
  again;
- **refused**: the identity provider or the runtime will not serve the caller. The caller's
  own exception, built by ``refused``; trying again changes nothing;
- **unreadable**: an answer that isn't the document this version reads.
  ``RuntimeAnswerUnreadable``.

None is turned into an empty answer. The reading helpers raise ``RuntimeAnswerUnreadable`` with
what was received.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from typing import Any

import httpx

from squadops.remote_execution.workers import RuntimeAnswerUnreadable, RuntimeUnreachable

#: A call that takes longer than this got no answer. Well inside a lease, so a renewal that
#: hangs is tried again before the lease runs out.
TIMEOUT_SECONDS = 10.0


class RuntimeApiCalls:
    def __init__(
        self,
        base_url: str,
        token: Callable[[], Awaitable[str]] | None,
        *,
        caller: str,
        refused: Callable[[str], Exception],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """``token`` returns the caller's bearer token. ``None`` sends none, which only a
        runtime with authentication disabled accepts; any other refuses the call, and that is
        raised. ``caller`` names whose credentials they are, in a refusal's words."""
        self._token = token
        self._caller = caller
        self._refused = refused
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=TIMEOUT_SECONDS, transport=transport
        )

    async def post(self, path: str, body: Mapping[str, Any] | None) -> tuple[int, Any]:
        """The status and the JSON body."""
        return await self._call("POST", path, body)

    async def get(self, path: str) -> tuple[int, Any]:
        """The status and the JSON body."""
        return await self._call("GET", path, None)

    def refusal(self, status: int, body: Any, path: str) -> Exception:
        """The caller's refusal for a status no route of its own explains."""
        return self._refused(f"HTTP {status} from {path}: {body!r}")

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(
        self, method: str, path: str, body: Mapping[str, Any] | None
    ) -> tuple[int, Any]:
        headers = await self._headers()
        try:
            reply = await self._client.request(method, path, json=body, headers=headers)
        except httpx.TransportError as e:
            raise RuntimeUnreachable(f"no answer from {path}: {type(e).__name__}: {e}") from e
        if reply.status_code >= 500:
            raise RuntimeUnreachable(f"HTTP {reply.status_code} from {path}: {reply.text[:300]}")
        try:
            return reply.status_code, reply.json()
        except ValueError as e:
            raise RuntimeAnswerUnreadable(
                f"HTTP {reply.status_code} from {path} with a body that isn't JSON: "
                f"{reply.text[:300]!r}"
            ) from e

    async def _headers(self) -> dict[str, str]:
        if self._token is None:
            return {}
        try:
            return {"Authorization": f"Bearer {await self._token()}"}
        except httpx.TransportError as e:
            raise RuntimeUnreachable(
                f"no answer from the identity provider: {type(e).__name__}: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status >= 500:
                raise RuntimeUnreachable(f"HTTP {status} from the identity provider") from e
            raise self._refused(
                f"the identity provider refused {self._caller} client credentials "
                f"(HTTP {status}): {e.response.text[:300]}"
            ) from e


def error(body: Any) -> Mapping[str, Any]:
    """The standard error envelope's ``error`` object (``squadops.api.errors``)."""
    return as_object(field(as_object(field(body, "detail"), "detail"), "error"), "detail.error")


def error_code(body: Any) -> str | None:
    """The envelope's code, or ``None`` when the body isn't the envelope: a 404 from an address
    that isn't the runtime API has none, and is then no route's "not found"."""
    try:
        return text(error(body), "code")
    except RuntimeAnswerUnreadable:
        return None


def as_object(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeAnswerUnreadable(f"{where} is {value!r}, and an object was expected")
    return value


def field(body: Any, key: str) -> Any:
    body = as_object(body, "the answer")
    if key not in body:
        raise RuntimeAnswerUnreadable(f"the answer has no {key!r}: {dict(body)!r}")
    return body[key]


def text(body: Any, key: str) -> str:
    value = field(body, key)
    if not isinstance(value, str) or not value:
        raise RuntimeAnswerUnreadable(f"{key} is {value!r}, and text was expected")
    return value


def seconds(body: Any, key: str) -> float:
    value = field(body, key)
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise RuntimeAnswerUnreadable(f"{key} is {value!r}, and a number of seconds was expected")
    return float(value)


def instant(value: Any, where: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as e:
        raise RuntimeAnswerUnreadable(f"{where} is {value!r}, and a time was expected") from e
    if parsed.tzinfo is None:
        raise RuntimeAnswerUnreadable(f"{where} is {value!r}, which names no time zone")
    return parsed

"""Does the delivered UI actually reach its own API? (measured 2026-08-15)

Every verification layer in the pipeline exercises the API *directly*: contract probes
issue HTTP against declared endpoint paths, SIP-0104's scaffold shells import route
handlers and invoke them in-process, ``frontend_build`` compiles, and the sandbox audit
probes the contract. **Nothing follows the path the UI itself takes.**

SIP-0104 window roll 1 (`cyc_04d36309d793`) shipped the consequence: all five page data
calls used unprefixed paths (``api('/runs')``) against routes mounted at ``/api/runs``,
so every list, create, detail, join and leave 404'd — in a deliverable that passed 36/36
checks, all five probes, ``tests_pass``, ``frontend_build``, and the boot audit. A user
opening it sees a page that never loads.

This module extracts the request paths the UI's own source will issue and resolves them
the way that stack's client seam would, so the audit can put those exact paths to the
running app. The check it enables is narrow and unambiguous: **does the app serve a route
where the UI asks?** — not whether the response is semantically right, which is the
contract probes' job.

Deliberately no headless browser. The defect is a wiring fact, decidable from the source
plus one HTTP round trip per distinct path; a browser would add a runtime dependency to
answer a question that does not need one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Placeholder substituted for a template expression (``${runId}``) so a concrete path
#: can be requested. Deliberately inert: a correct app answers a request for an unknown
#: id with its own error envelope, which still proves the ROUTE exists.
SAMPLE_SEGMENT = "ui-probe-sample"

#: How each stack's scaffold-owned client seam turns a call argument into a request path.
#: Stack #1's `apiFetch` prepends `/api`; stack #2's `api` fetches verbatim. Encoding the
#: difference here is the point — assuming one stack's convention for the other is the
#: defect this module exists to catch.
_SEAM_PREFIX: dict[str, str] = {
    "fullstack_fastapi_react": "/api",
    "nextjs_ts": "",
}

#: Files whose calls are the UI's. Route handlers legitimately talk to the store, not HTTP.
_UI_SUFFIXES = (".tsx", ".jsx")

_CALL_RE = re.compile(
    r"\b(?P<fn>api|apiFetch|fetch)\s*(?:<[^>()]*>)?\s*\(\s*(?P<quote>['\"`])(?P<path>[^'\"`]*)(?P=quote)"
)
_TEMPLATE_EXPR_RE = re.compile(r"\$\{[^}]*\}")


@dataclass(frozen=True)
class UiCall:
    """One data call the UI source will make, resolved to a requestable path."""

    file: str
    line: int
    fn: str
    #: The argument exactly as written, for a message that points at real source.
    written: str
    #: What the client seam will actually request.
    request_path: str

    def location(self) -> str:
        return f"{self.file}:{self.line}"


def extract_ui_calls(files: dict[str, str], stack: str) -> list[UiCall]:
    """Every data call the UI makes, with the path its seam will request.

    Absolute URLs are returned as written (``http://…``): those are the #877
    live-server class, a different defect, and silently normalizing them would hide it.
    An unknown stack yields nothing rather than guessing a prefix — a wrong prefix
    would invent failures in an app that works.
    """
    prefix = _SEAM_PREFIX.get(stack)
    if prefix is None:
        return []
    calls: list[UiCall] = []
    for path, content in sorted(files.items()):
        if not path.endswith(_UI_SUFFIXES):
            continue
        for lineno, line in enumerate(content.split("\n"), start=1):
            for match in _CALL_RE.finditer(line):
                written = match.group("path")
                if not written:
                    continue
                concrete = _TEMPLATE_EXPR_RE.sub(SAMPLE_SEGMENT, written)
                if concrete.startswith(("http://", "https://")):
                    request_path = concrete
                elif match.group("fn") == "fetch":
                    # A raw fetch bypasses the seam, so no prefix is applied to it.
                    request_path = concrete
                else:
                    request_path = prefix + concrete
                calls.append(
                    UiCall(
                        file=path,
                        line=lineno,
                        fn=match.group("fn"),
                        written=written,
                        request_path=request_path,
                    )
                )
    return calls


#: Verdicts for one probed UI path.
SERVED = "served"
ROUTE_MISSING = "route_missing"
PAGE_NOT_API = "page_not_api"
LIVE_SERVER = "live_server"

#: Call sites that parse the response as JSON unconditionally — the scaffold-owned
#: seams. Their own contract is "this returns JSON", so any non-JSON answer is a broken
#: call whatever its status. A raw ``fetch`` makes no such promise and is judged only on
#: whether a route exists at all.
_JSON_SEAM_FUNCTIONS = frozenset({"api", "apiFetch"})


def classify_ui_response(
    request_path: str, status: int, content_type: str, *, via_seam: bool = True
) -> str:
    """Did the UI's data call reach an API route?

    Two failure shapes, and this stack invites both because App Router serves pages and
    API handlers from ONE routing tree (#859):

    - ``ROUTE_MISSING`` — a 404 the framework produced (its 404 page is HTML, while an
      app answering through the scaffold's frozen ``errorResponse`` returns JSON). So a
      legitimate "no such run" — 404 WITH the envelope — reads as SERVED, because the
      route did answer. That distinction keeps correct apps passing.
    - ``PAGE_NOT_API`` — a 200 carrying HTML. The call landed on a *page* whose URL
      happens to match, so it never 404s: the seam's ``res.json()`` fails, its
      ``.catch(() => ({}))`` yields an empty object, and the view renders blank with no
      error anywhere. Roll 1 shipped exactly this on its detail route, and a
      404-only rule (this function's first version) called it served.
    """
    if request_path.startswith(("http://", "https://")):
        return LIVE_SERVER
    is_json = "json" in content_type.lower()
    if status == 404 and not is_json:
        return ROUTE_MISSING
    if via_seam and not is_json:
        return PAGE_NOT_API
    return SERVED


def expects_json(fn: str) -> bool:
    """Whether this call site parses the response as JSON by construction."""
    return fn in _JSON_SEAM_FUNCTIONS


def describe_failure(call: UiCall, verdict: str) -> str:
    if verdict == LIVE_SERVER:
        return (
            f"{call.location()}: {call.fn}({call.written!r}) targets a live server — the "
            f"UI must call its own app's paths (#877)"
        )
    if verdict == PAGE_NOT_API:
        return (
            f"{call.location()}: {call.fn}({call.written!r}) requests "
            f"{call.request_path!r}, which serves a PAGE, not the API — the response is "
            f"HTML, so the parsed body is empty and the view renders blank with no error"
        )
    return (
        f"{call.location()}: {call.fn}({call.written!r}) requests {call.request_path!r}, "
        f"which the app serves no route for — this call 404s for every user"
    )

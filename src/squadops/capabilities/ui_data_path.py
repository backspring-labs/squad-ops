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

#: Matched against whole file content, not line by line — a call argument that wraps to the
#: next line is still one call, and scanning per line silently dropped it (#952). The two
#: character classes exclude newlines deliberately: a type parameter and a request path each
#: live on one line, and letting either span lines lets an unbalanced quote swallow the rest
#: of the file. Only the whitespace between ``(`` and the opening quote may cross a line,
#: which is exactly the wrap this expression exists to tolerate.
_CALL_RE = re.compile(
    r"\b(?P<fn>api|apiFetch|fetch)\s*(?:<[^>()\n]*>)?\s*"
    r"\(\s*(?P<quote>['\"`])(?P<path>[^'\"`\n]*)(?P=quote)"
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

    Scans whole file content. The first version scanned line by line, so a call written
    across two lines — ``await api<Run>(`` then the path beneath it, which is what a
    formatter produces once the call carries a second argument — matched nothing and was
    never probed (#952). That silence is the worst possible failure for this module: it
    does not weaken the check, it removes it, and the roll still reads as audited. Roll 1
    of the SIP-0104 P6 window passed with its join and leave call sites extracted as zero.
    """
    prefix = _SEAM_PREFIX.get(stack)
    if prefix is None:
        return []
    calls: list[UiCall] = []
    for path, content in sorted(files.items()):
        if not path.endswith(_UI_SUFFIXES):
            continue
        for match in _CALL_RE.finditer(content):
            written = match.group("path")
            if not written:
                continue
            # The call site is where the failure message must point, so the line is the
            # one the call OPENS on, not the one its path happens to land on.
            lineno = content.count("\n", 0, match.start()) + 1
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


#: The probe is a GET whatever verb the UI uses, because sending the real verb would mutate
#: the app under audit. A route that exists but rejects GET therefore answers 405, and that
#: answer proves the route is mounted — see ``classify_ui_response`` (#953).
METHOD_NOT_ALLOWED = 405

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

    **405 is SERVED, whatever it carries** (#953). The audit probes every call site with a
    GET regardless of the verb the UI uses, because sending the real verb would mutate the
    application being audited — a POST probe would create a record, and the audit must be
    able to run twice. So a POST-only route answers the probe with 405, and Next produces
    that from the router with no content type. Read as "not JSON", it fell to
    ``PAGE_NOT_API`` and failed correct applications: P6 rolls 3 and 4 were both failed on
    join and leave routes that a human then verified by hand. This inverts the evidence.
    **A 405 is the strongest signal the route exists** — the router matched the path and
    rejected only the method, which is precisely the question this check asks. A page never
    answers 405; it answers 200 with HTML, and that case is untouched.
    """
    if request_path.startswith(("http://", "https://")):
        return LIVE_SERVER
    is_json = "json" in content_type.lower()
    if status == 404 and not is_json:
        return ROUTE_MISSING
    if status == METHOD_NOT_ALLOWED:
        return SERVED
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

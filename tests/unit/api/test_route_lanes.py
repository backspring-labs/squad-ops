"""#218: every route the runtime API registers sits in a lane, and the lanes are what the
standard says they are.

The surface had accreted four URL-prefix conventions with no owning rule — `/api/v1`,
unversioned `/api/chat` + `/api/agents`, `/health`, `/auth` — each chosen per SIP in
isolation, and nothing failed. The standard is `docs/architecture/api-route-lanes.md`;
this test enumerates the routers `main.py` registers (by importing the route modules, not
the app, so no config or services are needed) and holds the surface to it.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
from fastapi import APIRouter

pytestmark = [pytest.mark.domain_api]

_REPO = Path(__file__).resolve().parents[3]
_MAIN = _REPO / "src" / "squadops" / "api" / "runtime" / "main.py"

#: The lanes, by prefix — the standard's table.
RESOURCE = "/api/v1/"
PROBE = "/health"
IDENTITY = "/auth"

#: Routes off every lane, each keyed to the issue that moves it. An entry here is a
#: deviation on record, not a permission: the test fails a route off-lane that is NOT
#: listed, and fails a listed prefix that no longer has any route (the entry is stale).
KNOWN_DEVIATIONS: dict[str, str] = {}


def _registered_routers() -> list[tuple[str, APIRouter]]:
    """The routers main.py includes — read from its own AST: every `app.include_router(x)`
    resolved through the `from squadops.api.routes... import ...` that bound `x`."""
    tree = ast.parse(_MAIN.read_text(encoding="utf-8"), filename=str(_MAIN))
    bound: dict[str, tuple[str, str]] = {}
    names: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("squadops.api.routes")
        ):
            for alias in node.names:
                bound[alias.asname or alias.name] = (node.module, alias.name)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            names.append(node.args[0].id)
    assert names, "main.py registers no routers — the enumeration is broken"
    routers: list[tuple[str, APIRouter]] = []
    for name in names:
        assert name in bound, f"{name} is registered but not imported from squadops.api.routes"
        module, attr = bound[name]
        router = getattr(importlib.import_module(module), attr)
        assert isinstance(router, APIRouter), name
        routers.append((name, router))
    return routers


def _routes() -> list[tuple[str, str, frozenset[str]]]:
    """(router name, full path, methods) for every route registered."""
    out = []
    for name, router in _registered_routers():
        for route in router.routes:
            methods = frozenset(getattr(route, "methods", None) or ())
            out.append((name, route.path, methods))
    assert len(out) >= 20, f"only {len(out)} routes enumerated — the enumeration is broken"
    return out


def _lane(path: str) -> str | None:
    if path.startswith(RESOURCE):
        return "resource"
    if path == PROBE or path.startswith(PROBE + "/"):
        return "probe"
    if path == IDENTITY or path.startswith(IDENTITY + "/"):
        return "identity"
    return None


def test_every_route_is_in_a_lane_or_a_recorded_deviation():
    """Bug caught: a fifth convention. A new router with its own prefix — `/api/foo`,
    `/v1/...`, `/internal/...` — that a neighbourhood decision found reasonable."""
    off_lane = [
        f"{name}: {path}"
        for name, path, _ in _routes()
        if _lane(path) is None and not any(path.startswith(p) for p in KNOWN_DEVIATIONS)
    ]
    assert not off_lane, (
        "routes off every lane and not recorded as a deviation "
        "(docs/architecture/api-route-lanes.md):\n  " + "\n  ".join(off_lane)
    )


def test_no_api_v2():
    """Rule 2: extend v1 — the API is versioned by getting v1 right, not by prefix."""
    assert not [p for _, p, _ in _routes() if p.startswith("/api/v2")]


def test_the_probe_lane_is_read_only():
    """Rule 3: `/health` is the only unauthenticated lane, so a write there is a security
    regression — #326 moved the agent-status ingest to `/api/v1/agents` for this reason."""
    writes = [
        f"{name}: {sorted(methods)} {path}"
        for name, path, methods in _routes()
        if _lane(path) == "probe" and methods - {"GET", "HEAD", "OPTIONS"}
    ]
    assert not writes, "writable routes under /health:\n  " + "\n  ".join(writes)


def test_the_middleware_allowlists_exactly_the_probe_lane():
    """The auth boundary matches the lane table: GET/HEAD under `/health` without a
    token, nothing else — read from the middleware's own declaration."""
    from squadops.api.middleware import auth

    assert auth._ALWAYS_ALLOWLISTED_PREFIXES == (PROBE,)
    assert auth._DOCS_PATHS == {"/docs", "/openapi.json", "/redoc"}


def test_recorded_deviations_still_exist():
    """The other side: an entry that outlives its routes would quietly license the next
    one under that prefix. Empty since #219 moved the chat routes onto /api/v1 — the last
    deviation the standard recorded."""
    paths = [p for _, p, _ in _routes()]
    stale = [prefix for prefix in KNOWN_DEVIATIONS if not any(p.startswith(prefix) for p in paths)]
    assert not stale, f"deviations recorded for routes that no longer exist: {stale}"


def test_the_standard_names_every_lane_and_the_deviation():
    """The document is the owning standard; its table must agree with this test's."""
    doc = (_REPO / "docs" / "architecture" / "api-route-lanes.md").read_text(encoding="utf-8")
    for token in ("/api/v1/<resource>", "/health/*", "/auth/*", "No `/api/v2`", "#219"):
        assert token in doc, token


def _plain_error_bodies(path: Path, root: Path = _REPO) -> list[str]:
    """Each error body in ``path`` written as a bare string, an f-string or a ``str(...)``."""

    def plain(node: ast.expr | None) -> bool:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return True
        if isinstance(node, ast.JoinedStr | ast.BoolOp):
            return True
        return isinstance(node, ast.Call) and getattr(node.func, "id", None) == "str"

    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", getattr(node.func, "attr", None))
        kwargs = {k.arg: k.value for k in node.keywords}
        if name == "HTTPException":
            detail = kwargs.get("detail", node.args[1] if len(node.args) > 1 else None)
            if plain(detail):
                found.append(f"{path.relative_to(root)}:{node.lineno}")
        if name == "JSONResponse" and isinstance(kwargs.get("content"), ast.Dict):
            content = kwargs["content"]
            for key, value in zip(content.keys, content.values, strict=True):
                if isinstance(key, ast.Constant) and key.value == "detail" and plain(value):
                    found.append(f"{path.relative_to(root)}:{node.lineno}")
    return found


def test_no_route_or_middleware_answers_an_error_with_a_plain_string():
    """#1976, the standard's rule 5. Bug caught: an error body a client can't read as
    ``{"error": {"code", "message", "details"}}``. 24 were left on the auth middleware and the
    health, agent-status, auth, model, project and profile routes, and some 500s carried the
    exception's text on unauthenticated routes. ``squadops.api.errors`` builds the body."""
    found = [
        hit
        for path in sorted((_REPO / "src" / "squadops" / "api").rglob("*.py"))
        for hit in _plain_error_bodies(path)
    ]
    assert found == []


def test_the_scan_finds_each_plain_form(tmp_path):
    source = tmp_path / "routes.py"
    source.write_text(
        "raise HTTPException(404, 'gone')\n"
        "raise HTTPException(status_code=500, detail=f'failed: {e}')\n"
        "raise HTTPException(status_code=422, detail=str(e))\n"
        "raise HTTPException(status_code=403, detail=reason or 'Forbidden')\n"
        "return JSONResponse(content={'detail': 'Authentication service unavailable'})\n"
        "raise HTTPException(status_code=404, detail=error_body('X', 'gone'))\n"
    )
    assert _plain_error_bodies(source, tmp_path) == [f"routes.py:{n}" for n in (1, 2, 3, 4, 5)]

"""The FastAPI + React walking skeleton — stack #1, in its own module (#1131).

Stack #2 (``stack_nextjs_ts.py``) was written as a module from the start; stack #1 lived
inline in ``scaffold.py`` from the Phase-0.5 spike until this move, which is why "generic"
scaffold code was stack #1 and a stack-shaped predicate written into a shared module could
discard a green React suite unnoticed (#1126, the 1.6.5 set). This module is the seam's
view of stack #1: the frozen templates, the expander, the fill slots and how a suite invokes
the application. ``scaffold.py`` registers it through ``ScaffoldStack`` exactly as it
registers stack #2.

**A pure move.** Every template byte is unchanged. The proof is the reference contract:
``tests/fixtures/reference_contract/contract_v11_harness_cleanup_1127.yaml`` pins the
sha256 of every frozen file this expander emits, and
``tests/unit/capabilities/test_contract_derivation_reference.py`` reproduces the contract
byte-for-byte — a moved template that changes one byte fails there. ``GENERATOR_VERSION``
does not participate for this stack (it gates only the SIP-0104 emitter, which stack #1 does
not opt into).

**The rationale behind these templates was harvested before the move** (#1149):
SIP-0105, "Design decisions harvested from the stack #1 expander", entries 1–23. The
comments below are the same decisions in place; the register is the durable record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadops.capabilities.app_invocation import NETWORK_SEAM_FETCH_STUB, AppInvocation
from squadops.capabilities.success_status import derived_success_status
from squadops.capabilities.type_tokens import base_type_name

if TYPE_CHECKING:  # pragma: no cover - annotations only, avoids a scaffold import cycle
    from squadops.capabilities.scaffold import Endpoint, InterfaceManifest, Route

STACK_NAME = "fullstack_fastapi_react"

#: #1126: a React SPA reaches the app by rendering a real component or ``App``; the
#: network is a seam UNDER it, so a global ``fetch`` stub or a mock of the app's own
#: ``api.js`` client is legitimate when a component is rendered and self-mocking when
#: nothing is. Mocking a view or ``App`` module itself is mocking the subject.
APP_INVOCATION = AppInvocation(
    invocation_import=(
        r"""^\s*(?:import\b[^\n]*?from\s*|.*\brequire\s*\(\s*)['"`][^'"`]*"""
        r"""(?:/App|/views/[A-Za-z0-9_]+)(?:\.[jt]sx?)?['"`]"""
    ),
    subject_mock=r"""(?:vi|jest)\s*\.\s*mock\s*\(\s*['"`][^'"`]*(?:/App|/views/)""",
    network_seam_mock=(
        NETWORK_SEAM_FETCH_STUB
        + r"""    | (?:vi|jest)\s*\.\s*mock\s*\(\s*['"`][^'"`]*/api(?:\.[jt]sx?)?['"`]"""
    ),
)

_PY_PRIMITIVES = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}


def _py_type(type_str: str) -> str:
    """Map a manifest type token onto a Python annotation.

    ``string`` -> ``str``; ``list[X]`` -> ``list[X]``; an entity name passes through
    as the class name (models are emitted in manifest order, referenced entities
    first, and routes import the classes they reference — so no forward refs).
    """
    t = type_str.strip()
    if t.startswith("list[") and t.endswith("]"):
        inner = t[len("list[") : -1].strip()
        return f"list[{_py_type(inner)}]"
    return _PY_PRIMITIVES.get(t, t)


def _model_source(manifest: InterfaceManifest) -> str:
    lines = [
        '"""Pydantic models — scaffold-owned interface (entities + request shapes).',
        "",
        "Field bodies (validators, computed defaults) are fill-only; the class",
        "surface here is fixed by the interface manifest.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Annotated",
        "",
        "from pydantic import BaseModel, Field, StringConstraints",
        "",
        "# #593: required request fields reject blank/whitespace-only input at the",
        "# model layer — the contract pins validation_error → 422 for it, and the",
        "# blank-input probe enforces it against the running app. Whitespace is",
        "# stripped before the length check, so '  ' is as blank as ''.",
        "NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]",
        "",
    ]
    for entity in manifest.entities:
        lines.append(f"class {entity.name}(BaseModel):")
        if not entity.fields:
            lines.append("    pass")
        for f in entity.fields:
            ann = _py_type(f.type)
            if f.required and not f.has_default:
                lines.append(f"    {f.name}: {ann}")
            elif f.has_default and isinstance(f.default, list):
                lines.append(f"    {f.name}: {ann} = Field(default_factory=list)")
            elif f.has_default and f.default is not None:
                lines.append(f"    {f.name}: {ann} = {f.default!r}")
            else:
                # #1125: a declared ``default: null`` and an optional field with no default
                # mean the same thing — the value may be absent — and both freeze nullable.
                # ``default: null`` used to take the branch above and emit ``str = None``:
                # a non-nullable annotation with a None default, which pydantic v2 rejects
                # (``string_type``) the moment a route forwards the request's None into the
                # model. Five of six 1.6.5 FastAPI+React rolls paid that as a round-0 500.
                lines.append(f"    {f.name}: {ann} | None = None")
        lines.append("")

    for shape in manifest.api.request_shapes:
        lines.append(f"class {shape.name}(BaseModel):")
        if not shape.required and not shape.optional:
            lines.append("    pass")
        for name in shape.required:
            lines.append(f"    {name}: NonBlankStr")
        for name in shape.optional:
            lines.append(f"    {name}: str | None = None")
        lines.append("")

    lines.extend(_entity_body_model_lines(manifest))
    return "\n".join(lines)


def _entity_body_model_lines(manifest: InterfaceManifest) -> list[str]:
    """#1128: an entity used as an endpoint's ``request:`` gets a request model of its own.

    Shaped by the same resolver the contract's probe bodies use — required, non-generated,
    undefaulted fields as ``NonBlankStr`` (so the blank-input probe applies as it does to a
    declared shape), every other non-generated field optional. The entity class itself
    requires its generated ``id`` and could never accept the body the contract sends.
    """
    lines: list[str] = []
    for entity_name in manifest.entity_typed_requests():
        entity = next(e for e in manifest.entities if e.name == entity_name)
        required = manifest.request_body_fields(entity_name)
        optional = [f.name for f in entity.fields if not f.generated and f.name not in required]
        lines.append(f"class {manifest.request_model_name(entity_name)}(BaseModel):")
        if not required and not optional:
            lines.append("    pass")
        for name in required:
            lines.append(f"    {name}: NonBlankStr")
        for name in optional:
            lines.append(f"    {name}: str | None = None")
        lines.append("")
    return lines


def _route_func_name(ep: Endpoint) -> str:
    slug = ep.path.strip("/").replace("{", "").replace("}", "").replace("/", "_")
    slug = slug.replace("-", "_") or "root"
    return f"{ep.method.lower()}_{slug}"


def _routes_source(manifest: InterfaceManifest) -> str:
    known_models = {e.name for e in manifest.entities} | {
        s.name for s in manifest.api.request_shapes
    }
    referenced: set[str] = set()
    for ep in manifest.api.endpoints:
        request_model = manifest.request_model_name(ep.request)
        if request_model:
            referenced.add(request_model)
        if ep.response:
            base = base_type_name(ep.response)
            if base in known_models:
                referenced.add(base)
    import_line = f"from .models import {', '.join(sorted(referenced))}" if referenced else ""
    # The fill raises ApiError for the declared error codes, so the seam import is wired
    # into the frozen stub — that makes import_present(ApiError) a valid *interface*
    # criterion (it must pass on the bare skeleton, SIP-0098 §6.2), and the fill dev just
    # calls the already-imported symbol.
    errors_import = "from .errors import ApiError" if manifest.api.error_contract else ""
    # #603: the state container is scaffold-owned, so wire its import into the frozen
    # stub exactly as the error seam is. The fill then USES the store instead of
    # inventing a module for it — which is what pf-40 did, with a broken import.
    store_names = [f"{_snake(e.name)}_store" for e in manifest.entities]
    store_import = f"from .store import {', '.join(store_names)}" if store_names else ""
    import_block = "\n".join(
        ln
        for ln in (
            "from fastapi import APIRouter, HTTPException",
            import_line,
            errors_import,
            store_import,
        )
        if ln
    )
    error_codes = [
        c.code for c in (manifest.api.error_contract.codes if manifest.api.error_contract else ())
    ]
    codes_hint = (
        f"On failure raise ApiError(code, message) from .errors — codes: {', '.join(error_codes)}."
        if error_codes
        else "On failure raise ApiError(code, message) from .errors."
    )
    lines = [
        '"""API route stubs — scaffold-owned signatures, fill-only bodies.',
        "",
        "Every endpoint the interface manifest declares is wired here with its",
        "correct path, method, and response model. Bodies raise 501 until filled;",
        "the app imports and boots regardless.",
        "",
        "The router takes NO prefix. The frontend calls /api/... and the proxy strips",
        "that prefix before the request reaches this app, so these paths are already",
        "the full backend paths. Adding prefix= to APIRouter puts every route behind a",
        "second /api and the app answers 404 to its own contract (pf-41).",
        "",
        codes_hint,
        '"""',
        "",
        import_block,
        "",
        "router = APIRouter()",
        "",
    ]
    for ep in manifest.api.endpoints:
        fn = _route_func_name(ep)
        path_args = [p[1:-1] for p in ep.path.split("/") if p.startswith("{") and p.endswith("}")]
        params = [f"{a}: str" for a in path_args]
        if ep.request:
            params.append(f"payload: {manifest.request_model_name(ep.request) or ep.request}")
        sig = ", ".join(params)
        decorator = f'@router.{ep.method.lower()}("{ep.path}"'
        if ep.response:
            decorator += f", response_model={_py_type(ep.response)}"
        # The success status is *interface*, not implementation — it belongs to the
        # scaffold-owned decorator so the fill dev cannot drop it (pf-39). #772: an
        # UNDECLARED status is pinned too, to the same default the contract asserts —
        # an omitted kwarg meant FastAPI's 200 against the deriver's 201, unwinnable.
        pinned = (
            ep.success_status
            if ep.success_status is not None
            else derived_success_status(ep.method, ep.path)
        )
        if pinned is not None:
            decorator += f", status_code={pinned}"
        decorator += ")"
        lines.append(decorator)
        lines.append(f"def {fn}({sig}):")
        summary = ep.summary or fn
        lines.append(f'    """{summary} — TODO: implement (scaffold stub)."""')
        lines.append('    raise HTTPException(status_code=501, detail="not implemented")')
        lines.append("")
    return "\n".join(lines)


_ERRORS_PY = '''"""Error contract rendering — scaffold-owned interface wiring.

The interface manifest pins one error envelope shape and a code->status map. Both
the ApiError exception (raise ApiError(code, message) from a route body) and the
request-validation handler render that exact shape, so a fill-only dev conforms
the contract by raising ApiError — never by hand-rendering JSON, and never by
editing this file. FastAPI's default validation error ({"detail": [...]}) fires
before any route body, so this handler is the only place it can be conformed.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# code -> HTTP status, generated from the manifest error_contract.
_ERROR_STATUS: dict[str, int] = __STATUS_MAP__


class ApiError(Exception):
    """Raise from a route body to emit the pinned {"error": {...}} envelope."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = _ERROR_STATUS.get(code, 400)


def _envelope(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code, exc.message))


async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=_ERROR_STATUS.get("validation_error", 422),
        content=_envelope("validation_error", "request validation failed"),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
'''


def _errors_source(manifest: InterfaceManifest) -> str:
    ec = manifest.api.error_contract
    codes = ec.codes if ec else ()
    if codes:
        entries = "\n".join(f'    "{c.code}": {c.http},' for c in codes)
        status_map = "{\n" + entries + "\n}"
    else:
        status_map = "{}"
    return _ERRORS_PY.replace("__STATUS_MAP__", status_map)


_MAIN_PY = '''"""FastAPI application entry point — scaffold-owned invariant bootstrap.

CORS origins come from the CORS_ORIGINS env var (comma-separated); the health
endpoint is the deterministic readiness probe. Error handlers render the pinned
error envelope. Business routes live in routes.py.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .errors import register_error_handlers
from .routes import router

app = FastAPI(title="{project_id}")

_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    return {{"status": "ok"}}


app.include_router(router)
'''

_REQUIREMENTS_TXT = """fastapi>=0.115,<0.200
uvicorn[standard]>=0.30,<0.40
pydantic>=2.7,<3
"""

_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{project_id}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""

_PACKAGE_JSON = """{{
  "name": "{project_id}-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  }},
  "dependencies": {{
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  }},
  "devDependencies": {{
    "@testing-library/dom": "^10.4.0",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^25.0.1",
    "vite": "^5.4.2",
    "vitest": "^2.1.9"
  }}
}}
"""

_VITE_CONFIG = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The /api proxy is dev-only; production serves the built assets behind a
// reverse proxy. Backend host/port are blueprint-owned, not interface.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\\/api/, ''),
      },
    },
  },
  // #627: the frontend test harness is scaffold-owned, mirroring the backend
  // conftest. vitest reads this key; `vite build` ignores it.
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test-setup.js'],
  },
})
"""

# Scaffold-owned vitest setup (frozen) — registers jest-dom matchers for every
# suite. The frontend mirror of the conftest ``client`` fixture: harness wiring
# is a workspace invariant, never a per-suite guess (#627 / pf-53: with no
# seeded harness, qa either refused to test or invented one that could not run).
_TEST_SETUP_JS = """// The /vitest entry registers jest-dom matchers on vitest's expect — the
// bare entry assumes a GLOBAL expect and crashes collection under vitest's
// default globals:false (caught on the real toolchain, not in review).
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// #1127: Testing Library only auto-registers cleanup when a GLOBAL afterEach
// exists, and under globals:false there is none — so nothing unmounts between
// tests and a suite that renders in more than one `it` fails "Found multiple
// elements". Registering it here is the workspace invariant, not a per-suite
// guess.
afterEach(cleanup)
"""

# Scaffold-owned harness proof (frozen). Renders the app shell at a path no
# route claims, so it passes on the bare skeleton AND after any fill — it
# asserts harness wiring (vitest + jsdom + Testing Library + router), never
# app behavior. Doubles as the in-workspace example of the testing idiom.
_HARNESS_TEST_JSX = """// Scaffold-owned harness proof (frozen): vitest + jsdom + Testing Library +
// router wiring all work in this workspace. Write real UI tests in NEW files
// beside this one (e.g. views.test.jsx) — render with MemoryRouter exactly as
// below; jest-dom matchers are already registered via src/test-setup.js.
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App.jsx'

describe('frontend test harness', () => {
  it('renders the app shell under a memory router', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/__harness__']}>
        <App />
      </MemoryRouter>,
    )
    expect(container.querySelector('.app')).toBeInTheDocument()
  })
})
"""

_MAIN_JSX = """import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
"""

_API_JS = """// Scaffold-owned API client — the /api base path and error-envelope unwrapping
// are interface wiring, fixed here. Views call apiFetch('/path'); the /api prefix
// routes through the Vite dev proxy to the backend. A response carrying the pinned
// {"error": {code, message}} envelope is thrown as ApiError.
export class ApiError extends Error {
  constructor(code, message, status) {
    super(message)
    this.code = code
    this.status = status
  }
}

export async function apiFetch(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!response.ok) {
    let body = null
    try {
      body = await response.json()
    } catch {
      // non-JSON error body
    }
    const err = (body && body.error) || {}
    throw new ApiError(err.code || 'error', err.message || response.statusText, response.status)
  }
  if (response.status === 204) return null
  return response.json()
}
"""


def _app_jsx(manifest: InterfaceManifest) -> str:
    routes = manifest.frontend.routes
    imports = "\n".join(f"import {r.view} from './views/{r.view}.jsx'" for r in routes)
    route_els = "\n".join(
        f'        <Route path="{r.path}" element={{<{r.view} />}} />' for r in routes
    )
    return (
        "import { Routes, Route } from 'react-router-dom'\n"
        + imports
        + "\n\n"
        + "// App wiring is scaffold-owned: routes and their component imports are\n"
        + "// fixed by the interface manifest. Add a route by amending the manifest\n"
        + "// and re-expanding, never by editing this file by hand.\n"
        + "export default function App() {\n"
        + "  return (\n"
        + '    <div className="app">\n'
        + "      <Routes>\n"
        + route_els
        + "\n      </Routes>\n"
        + "    </div>\n"
        + "  )\n"
        + "}\n"
    )


def _view_stub(route: Route) -> str:
    purpose = route.purpose or route.view
    # #659: the root anchor is stamped on the stub container so it exists from
    # the bare skeleton onward; the fill inherits it in place. The full anchor
    # inventory rides as a comment because the stub has no other elements yet —
    # the dev prompt (testid surface appendix) carries the binding instruction.
    root_attr = f' data-testid="{route.testids[0]}"' if route.testids else ""
    anchor_comment = (
        f"  // DOM anchors (manifest-pinned, keep every one): {', '.join(route.testids)}\n"
        if route.testids
        else ""
    )
    return (
        "// Scaffold-owned slot: fill this component's body. The default export\n"
        "// name and file path are fixed by the interface manifest. Fetch backend\n"
        "// data via apiFetch from '../api.js' (handles the /api prefix + errors).\n"
        f"export default function {route.view}() {{\n"
        f"  // TODO: {purpose}\n"
        f"{anchor_comment}"
        f"  return <div{root_attr}>{route.view}</div>\n"
        "}\n"
    )


# Scaffold-owned pytest anchor (frozen) — the SINGLE source of the test import root.
# Puts the workspace root on sys.path so ``import backend`` resolves regardless of
# pytest's CWD, and owns the app import behind a ``client`` fixture. Suites fill bodies
# against ``client`` and never author ``from <root>.main import app`` themselves — so the
# package root is a scaffold invariant, not a per-suite guess (the pf-26 divergence:
# files under backend/ but the qa test invented ``from app.main import app``).
_CONFTEST_PY = '''"""Scaffold-owned pytest anchor (frozen) — the single source of the import root.

Puts the workspace root on sys.path so ``import backend`` resolves regardless of the
working directory pytest runs from, and exposes ``client`` as the ONE place the app is
imported. Test suites fill bodies against ``client``; they never author the app import.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app  # noqa: E402  -- after the sys.path anchor above


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
'''


def _snake(name: str) -> str:
    """``RunEvent`` → ``run_event``. Deterministic, so the store's names are stable."""
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _store_source(manifest: InterfaceManifest) -> str:
    """The in-memory state container (#603).

    The manifest declares ``persistence: in_memory`` and the skeleton used to emit
    nothing that held the data. The planner therefore invented a module on every roll
    — reasonable engineering given an incomplete skeleton, but an invented file is
    outside every safety net: nothing freezes it, no contract criterion names it, and
    its imports are guessed fresh each time. pf-40 died exactly there, on a
    ``from models import ...`` that was missing the leading dot, so the app never
    started and the behavioural probe could not run at all.

    Emitting it makes the imports correct by construction and brings the file under
    scaffold ownership. One dict per declared entity, keyed by the entity's id.
    """
    entities = [e.name for e in manifest.entities]
    lines = [
        '"""In-memory state — scaffold-owned (frozen).',
        "",
        "The manifest declares in-memory persistence, so this module owns it: one store",
        "per declared entity, keyed by the entity's id. Fill route bodies against these",
        "names; do not define a second store elsewhere and do not edit this file.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
    ]
    if entities:
        lines.append(f"from .models import {', '.join(sorted(entities))}")
        lines.append("")
    for name in entities:
        lines.append(f"{_snake(name)}_store: dict[str, {name}] = {{}}")
    if entities:
        lines.append("")
    lines.append("")
    lines.append("def reset() -> None:")
    lines.append('    """Clear every store — for test isolation between cases."""')
    if entities:
        for name in entities:
            lines.append(f"    {_snake(name)}_store.clear()")
    else:
        lines.append("    return None")
    lines.append("")
    return "\n".join(lines)


def expand_fullstack_fastapi_react(manifest: InterfaceManifest) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []

    # ---- backend (FastAPI, in-memory) ----
    files.append({"name": "backend/__init__.py", "content": ""})
    files.append(
        {"name": "backend/main.py", "content": _MAIN_PY.format(project_id=manifest.project_id)}
    )
    files.append({"name": "backend/models.py", "content": _model_source(manifest)})
    files.append({"name": "backend/store.py", "content": _store_source(manifest)})
    files.append({"name": "backend/errors.py", "content": _errors_source(manifest)})
    files.append({"name": "backend/routes.py", "content": _routes_source(manifest)})
    files.append({"name": "backend/requirements.txt", "content": _REQUIREMENTS_TXT})
    # Frozen pytest anchor: pins the import root so suites don't each guess it.
    files.append({"name": "conftest.py", "content": _CONFTEST_PY})

    # ---- frontend (React + Vite) ----
    files.append(
        {
            "name": "frontend/index.html",
            "content": _INDEX_HTML.format(project_id=manifest.project_id),
        }
    )
    files.append(
        {
            "name": "frontend/package.json",
            "content": _PACKAGE_JSON.format(project_id=manifest.project_id),
        }
    )
    files.append({"name": "frontend/vite.config.js", "content": _VITE_CONFIG})
    files.append({"name": "frontend/src/test-setup.js", "content": _TEST_SETUP_JS})
    files.append({"name": "frontend/src/__tests__/harness.test.jsx", "content": _HARNESS_TEST_JSX})
    files.append({"name": "frontend/src/main.jsx", "content": _MAIN_JSX})
    files.append({"name": "frontend/src/api.js", "content": _API_JS})
    files.append({"name": "frontend/src/App.jsx", "content": _app_jsx(manifest)})
    for route in manifest.frontend.routes:
        files.append({"name": f"frontend/src/views/{route.view}.jsx", "content": _view_stub(route)})

    return files


def fill_slots_fullstack_fastapi_react(manifest: InterfaceManifest) -> tuple[str, ...]:
    """The route bodies, plus one component per declared route."""
    views = tuple(f"frontend/src/views/{r.view}.jsx" for r in manifest.frontend.routes)
    return ("backend/routes.py", *dict.fromkeys(views))


def store_brief_lines(manifest: InterfaceManifest) -> list[str]:
    """What the developer's model-surface brief says about this stack's frozen store.

    pf-45's dev re-declared local store dicts in the fill slot, shadowing
    ``backend/store.py`` — the scaffold's ``reset()`` then cleared the unused stores and
    test isolation silently broke. The stores are named by the same rule ``store.py``
    defines them (``_snake``), so the brief and the module cannot disagree. Declared here
    because the text is this stack's: ``backend/store.py``, ``from .store import`` and
    ``<entity>_store`` describe nothing on a Next.js tree — and were being said to one.
    """
    if manifest.persistence != "in_memory":
        return []
    stores = ", ".join(f"`{_snake(e.name)}_store`" for e in manifest.entities)
    return [
        f"`backend/store.py` is scaffold-frozen and already defines the in-memory "
        f"stores: {stores} (plus `reset()` for test isolation). Import them "
        "(`from .store import ...`); do NOT declare your own store dicts — a shadow "
        "store is invisible to `reset()`, so state leaks between tests and the suite "
        "fails on isolation"
    ]

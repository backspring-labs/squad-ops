"""Contract-first build scaffolding — the deterministic walking-skeleton expander.

Per ``sips/proposed/SIP-Contract-First-Build-Scaffolding.md``: framing emits a typed
*interface manifest* (entities / endpoints / routes); this module deterministically
materializes a **walking skeleton** from it — a wired application that already builds
and boots — into which the dev agent fills bodies at fixed, scaffold-owned slots.

The dividing line between deterministic and generative work is *interface vs.
implementation*: everything identical regardless of what the app does (entry files,
config, bootstrap, cross-file wiring) is scaffolded here; only the endpoint/component
*bodies* are left for the model.

This is pure logic (``manifest -> list[{name, content}]``) — no port, no NoOp, no
factory, sibling to ``build_profiles.py``/``dev_capabilities.py``. The output shape
(``{"name", "content"}``) matches ``patch_verification.materialize_artifacts`` so the
expanded files ride the existing artifact-seeding rail with no new adapter.

Phase-0.5 spike scope: the ``fullstack_fastapi_react`` stack only; standalone parse
(not yet wired into ``ImplementationPlan.from_yaml`` or the executor seam — that is the
post-verdict integration). The emitted skeleton is deliberately *empty*: routes and
components exist, wire together, build, and boot, but their bodies are stubs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import yaml

# Schema v1 is frozen (SIP-0099 phase 99.1): the shape below is the canonical
# interface-manifest contract the fullstack_fastapi_react expander was proven against
# in the Phase-0.5 spike. A manifest declaring any other version/kind is rejected at
# parse time rather than silently mis-expanded — a future v2 gets its own expander.
INTERFACE_MANIFEST_VERSION = 1
INTERFACE_MANIFEST_KIND = "interface_manifest"

# --------------------------------------------------------------------------- schema


@dataclass(frozen=True)
class ManifestField:
    """A field on an entity (``entities[].fields[]``)."""

    name: str
    type: str
    required: bool = True
    generated: bool = False
    default: Any = None
    has_default: bool = False


@dataclass(frozen=True)
class Entity:
    name: str
    fields: tuple[ManifestField, ...] = ()


@dataclass(frozen=True)
class RequestShape:
    """A request body shape (``api.request_shapes``) — a projection of entity fields."""

    name: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    summary: str = ""
    request: str | None = None  # names a RequestShape
    response: str | None = None  # e.g. "RunEvent" or "list[RunEvent]"
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ErrorCode:
    code: str
    http: int


@dataclass(frozen=True)
class ErrorContract:
    shape: str = ""
    codes: tuple[ErrorCode, ...] = ()


@dataclass(frozen=True)
class Api:
    base_path: str = ""
    request_shapes: tuple[RequestShape, ...] = ()
    endpoints: tuple[Endpoint, ...] = ()
    error_contract: ErrorContract | None = None


@dataclass(frozen=True)
class Route:
    path: str
    view: str
    purpose: str = ""


@dataclass(frozen=True)
class Frontend:
    framework: str = "react_vite"
    language: str = "javascript"
    api_client: str = "fetch"
    routes: tuple[Route, ...] = ()


@dataclass(frozen=True)
class InterfaceManifest:
    """The typed interface contract framing emits and the expander consumes."""

    version: int
    kind: str
    project_id: str
    stack: str
    source_prd: str = ""
    scope: str = ""
    entities: tuple[Entity, ...] = ()
    api: Api = field(default_factory=Api)
    frontend: Frontend = field(default_factory=Frontend)
    persistence: str = "in_memory"

    @classmethod
    def from_yaml(cls, content: str) -> InterfaceManifest:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ValueError("interface manifest must be a YAML mapping")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InterfaceManifest:
        required_keys = ("version", "kind", "project_id", "stack")
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise ValueError(f"interface manifest missing required keys: {missing}")

        version = int(data["version"])
        if version != INTERFACE_MANIFEST_VERSION:
            raise ValueError(
                f"unsupported interface manifest version {version}; "
                f"this expander is schema v{INTERFACE_MANIFEST_VERSION}"
            )
        kind = str(data["kind"])
        if kind != INTERFACE_MANIFEST_KIND:
            raise ValueError(
                f"interface manifest kind must be {INTERFACE_MANIFEST_KIND!r}, got {kind!r}"
            )

        entities = tuple(_parse_entity(e) for e in data.get("entities", []))
        api = _parse_api(data.get("api", {}) or {})
        frontend = _parse_frontend(data.get("frontend", {}) or {})
        return cls(
            version=version,
            kind=kind,
            project_id=str(data["project_id"]),
            stack=str(data["stack"]),
            source_prd=str(data.get("source_prd", "")),
            scope=str(data.get("scope", "")),
            entities=entities,
            api=api,
            frontend=frontend,
            persistence=str(data.get("persistence", "in_memory")),
        )

    def _canonical(self) -> dict[str, Any]:
        """Deterministic structural projection for hashing — every field the expander
        reads to produce the skeleton, and nothing else. Provenance (``source_prd``,
        ``scope``) is excluded: the expander ignores it, so a provenance-only edit must
        not spuriously move the hash and invalidate the verification contract bound to
        it (SIP-0098 §10 drift). ``project_id`` IS included — it is substituted into the
        emitted package name and app title, so it changes the skeleton."""
        return {
            "version": self.version,
            "kind": self.kind,
            "project_id": self.project_id,
            "stack": self.stack,
            "persistence": self.persistence,
            "entities": [
                {
                    "name": e.name,
                    "fields": [
                        {
                            "name": f.name,
                            "type": f.type,
                            "required": f.required,
                            "generated": f.generated,
                            "default": f.default,
                            "has_default": f.has_default,
                        }
                        for f in e.fields
                    ],
                }
                for e in self.entities
            ],
            "api": {
                "base_path": self.api.base_path,
                "request_shapes": [
                    {"name": s.name, "required": list(s.required), "optional": list(s.optional)}
                    for s in self.api.request_shapes
                ],
                "endpoints": [
                    {
                        "method": ep.method,
                        "path": ep.path,
                        "summary": ep.summary,
                        "request": ep.request,
                        "response": ep.response,
                        "errors": list(ep.errors),
                    }
                    for ep in self.api.endpoints
                ],
                "error_contract": (
                    {
                        "shape": self.api.error_contract.shape,
                        "codes": [
                            {"code": c.code, "http": c.http} for c in self.api.error_contract.codes
                        ],
                    }
                    if self.api.error_contract
                    else None
                ),
            },
            "frontend": {
                "framework": self.frontend.framework,
                "language": self.frontend.language,
                "api_client": self.frontend.api_client,
                "routes": [
                    {"path": r.path, "view": r.view, "purpose": r.purpose}
                    for r in self.frontend.routes
                ],
            },
        }

    def content_hash(self) -> str:
        """Stable sha256 identifying the skeleton this manifest expands to. SIP-0098's
        verification contract binds ``skeleton.interface_manifest_hash`` to this value,
        so drift between a contract and the skeleton it verifies becomes detectable."""
        canonical = json.dumps(self._canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_entity(raw: dict[str, Any]) -> Entity:
    fields = []
    for f in raw.get("fields", []):
        has_default = "default" in f
        fields.append(
            ManifestField(
                name=str(f["name"]),
                type=str(f["type"]),
                required=bool(f.get("required", True)),
                generated=bool(f.get("generated", False)),
                default=f.get("default"),
                has_default=has_default,
            )
        )
    return Entity(name=str(raw["name"]), fields=tuple(fields))


def _parse_api(raw: dict[str, Any]) -> Api:
    shapes = tuple(
        RequestShape(
            name=str(name),
            required=tuple(str(x) for x in (spec or {}).get("required", [])),
            optional=tuple(str(x) for x in (spec or {}).get("optional", [])),
        )
        for name, spec in (raw.get("request_shapes", {}) or {}).items()
    )
    endpoints = tuple(
        Endpoint(
            method=str(ep["method"]).upper(),
            path=str(ep["path"]),
            summary=str(ep.get("summary", "")),
            request=(str(ep["request"]) if ep.get("request") else None),
            response=(str(ep["response"]) if ep.get("response") else None),
            errors=tuple(str(x) for x in ep.get("errors", [])),
        )
        for ep in raw.get("endpoints", [])
    )
    ec_raw = raw.get("error_contract")
    error_contract = None
    if ec_raw:
        codes = tuple(
            ErrorCode(code=str(code), http=int((spec or {}).get("http", 400)))
            for code, spec in (ec_raw.get("codes", {}) or {}).items()
        )
        error_contract = ErrorContract(shape=str(ec_raw.get("shape", "")), codes=codes)
    return Api(
        base_path=str(raw.get("base_path", "")),
        request_shapes=shapes,
        endpoints=endpoints,
        error_contract=error_contract,
    )


def _parse_frontend(raw: dict[str, Any]) -> Frontend:
    routes = tuple(
        Route(
            path=str(r["path"]),
            view=str(r["view"]),
            purpose=str(r.get("purpose", "")),
        )
        for r in raw.get("routes", [])
    )
    return Frontend(
        framework=str(raw.get("framework", "react_vite")),
        language=str(raw.get("language", "javascript")),
        api_client=str(raw.get("api_client", "fetch")),
        routes=routes,
    )


# ------------------------------------------------------------------------- expander


def expand(manifest: InterfaceManifest) -> list[dict[str, str]]:
    """Materialize the walking skeleton for ``manifest.stack``.

    Returns a list of ``{"name": <workspace-relative path>, "content": <str>}`` —
    the shape ``patch_verification.materialize_artifacts`` writes to disk.
    """
    expander = _EXPANDERS.get(manifest.stack)
    if expander is None:
        raise ValueError(
            f"no scaffold expander for stack {manifest.stack!r}; available: {sorted(_EXPANDERS)}"
        )
    return expander(manifest)


def fill_slot_paths(manifest: InterfaceManifest) -> tuple[str, ...]:
    """Workspace-relative paths of the *fill slots* — the files the dev agent fills
    bodies into. Everything else ``expand`` emits is frozen (scaffold-owned): the
    SIP-0098 verification contract pins those by hash and hangs per-file criteria only
    on these slots. Same stack dispatch as ``expand``; raises for an unknown stack.

    (fullstack_fastapi_react: the route bodies + one component per declared route. As
    more stacks land in 99.4 they carry their own slot map alongside their expander.)
    """
    if manifest.stack not in _EXPANDERS:
        raise ValueError(
            f"no scaffold expander for stack {manifest.stack!r}; available: {sorted(_EXPANDERS)}"
        )
    views = tuple(f"frontend/src/views/{r.view}.jsx" for r in manifest.frontend.routes)
    return ("backend/routes.py", *dict.fromkeys(views))


# ------------------------------------------------- fullstack_fastapi_react templates

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


def _base_type_name(type_str: str) -> str:
    """The bare entity/model name inside a type token (``list[RunEvent]`` -> ``RunEvent``)."""
    t = type_str.strip()
    if t.startswith("list[") and t.endswith("]"):
        return _base_type_name(t[len("list[") : -1])
    return t


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
        "from pydantic import BaseModel, Field",
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
            elif f.has_default:
                lines.append(f"    {f.name}: {ann} = {f.default!r}")
            else:
                lines.append(f"    {f.name}: {ann} | None = None")
        lines.append("")

    for shape in manifest.api.request_shapes:
        lines.append(f"class {shape.name}(BaseModel):")
        if not shape.required and not shape.optional:
            lines.append("    pass")
        for name in shape.required:
            lines.append(f"    {name}: str")
        for name in shape.optional:
            lines.append(f"    {name}: str | None = None")
        lines.append("")
    return "\n".join(lines)


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
        if ep.request and ep.request in known_models:
            referenced.add(ep.request)
        if ep.response:
            base = _base_type_name(ep.response)
            if base in known_models:
                referenced.add(base)
    import_line = f"from .models import {', '.join(sorted(referenced))}" if referenced else ""
    # The fill raises ApiError for the declared error codes, so the seam import is wired
    # into the frozen stub — that makes import_present(ApiError) a valid *interface*
    # criterion (it must pass on the bare skeleton, SIP-0098 §6.2), and the fill dev just
    # calls the already-imported symbol.
    errors_import = "from .errors import ApiError" if manifest.api.error_contract else ""
    import_block = "\n".join(
        ln
        for ln in ("from fastapi import APIRouter, HTTPException", import_line, errors_import)
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
            params.append(f"payload: {ep.request}")
        sig = ", ".join(params)
        decorator = f'@router.{ep.method.lower()}("{ep.path}"'
        if ep.response:
            decorator += f", response_model={_py_type(ep.response)}"
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
    "preview": "vite preview"
  }},
  "dependencies": {{
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  }},
  "devDependencies": {{
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.2"
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
// are interface wiring, fixed here. Views call apiFetch('/runs'); the /api prefix
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
    return (
        "// Scaffold-owned slot: fill this component's body. The default export\n"
        "// name and file path are fixed by the interface manifest. Fetch backend\n"
        "// data via apiFetch from '../api.js' (handles the /api prefix + errors).\n"
        f"export default function {route.view}() {{\n"
        f"  // TODO: {purpose}\n"
        f"  return <div>{route.view}</div>\n"
        "}\n"
    )


def _expand_fullstack_fastapi_react(manifest: InterfaceManifest) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []

    # ---- backend (FastAPI, in-memory) ----
    files.append({"name": "backend/__init__.py", "content": ""})
    files.append(
        {"name": "backend/main.py", "content": _MAIN_PY.format(project_id=manifest.project_id)}
    )
    files.append({"name": "backend/models.py", "content": _model_source(manifest)})
    files.append({"name": "backend/errors.py", "content": _errors_source(manifest)})
    files.append({"name": "backend/routes.py", "content": _routes_source(manifest)})
    files.append({"name": "backend/requirements.txt", "content": _REQUIREMENTS_TXT})

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
    files.append({"name": "frontend/src/main.jsx", "content": _MAIN_JSX})
    files.append({"name": "frontend/src/api.js", "content": _API_JS})
    files.append({"name": "frontend/src/App.jsx", "content": _app_jsx(manifest)})
    for route in manifest.frontend.routes:
        files.append({"name": f"frontend/src/views/{route.view}.jsx", "content": _view_stub(route)})

    return files


_EXPANDERS = {
    "fullstack_fastapi_react": _expand_fullstack_fastapi_react,
}

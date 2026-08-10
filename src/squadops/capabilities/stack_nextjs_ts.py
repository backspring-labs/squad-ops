"""The Next.js + TypeScript walking skeleton — stack #2 (#822, Stage 1c).

Its purpose is not "support another language". It is the **acceptance gate for the Stack
Blueprint SIP**, which declines its own acceptance until a second real stack exists because
*"generalising from one instance produces the FastAPI contract with generic field names —
worse than no contract, because it looks authoritative and the second stack will quietly bend
itself to fit rather than reveal the mismatch."* Every bend recorded below is S3's evidence.

**Parity of ambition with stack #1, deliberately** (#822 gate decision 1): the same seams —
models, store, errors, an app entry, a client helper, a test harness, routes and views — no
more and no fewer, with the same frozen/fill split. Writing a *better* skeleton would make
VS-vs-V5 uninterpretable, because a yield difference would be ambiguous between "the blueprint
schema generalises" and "stack #2's skeleton is better".

**Why this is a module and stack #1's expander is not.** Stack #1's lives inline in
``scaffold.py``. A second one there would push that file past 2000 lines and interleave two
stacks' source templates. Extracting stack #1 to match is a follow-up refactor, deliberately
not bundled — it would move bytes the reference contract is pinned to.

### Bends

Recorded in **`docs/plans/stack-2-bend-register.md`**, not here. S3 evaluates "zero unexplained
bends" against that document, and a second copy in this docstring would be the release's own
recurring failure — a claim maintained in two places, drifting the moment one is edited.

Read it before changing the partition, the path translation, or what a fill slot is: four of
its six entries are about exactly those, and one of them (`frontend.routes[].view`) is an open
strain on the manifest schema rather than a settled decision.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - annotations only, avoids a scaffold import cycle
    from squadops.capabilities.scaffold import InterfaceManifest

STACK_NAME = "nextjs_ts"

_TS_TYPES = {
    "str": "string",
    "string": "string",
    "text": "string",
    "int": "number",
    "integer": "number",
    "float": "number",
    "number": "number",
    "decimal": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "datetime": "string",
    "date": "string",
    "time": "string",
}


def _ts_type(raw: str) -> str:
    """Manifest field type → TypeScript. Unknown types become ``string`` rather than ``any``:
    ``any`` would silently disable the type checking that is stack #2's entire hygiene tier."""
    t = (raw or "").strip().lower()
    inner = re.fullmatch(r"(?:list|array)\[(.+)\]", t)
    if inner:
        return f"{_ts_type(inner.group(1))}[]"
    return _TS_TYPES.get(t, "string")


def _segments(path: str) -> str:
    """``/runs/{run_id}/join`` → ``runs/[run_id]/join`` (bend 2). Frontend routes arrive in
    ``:id`` form, so both parameter syntaxes translate to Next's bracket directory."""
    out = []
    for seg in path.strip("/").split("/"):
        if not seg:
            continue
        if seg.startswith("{") and seg.endswith("}"):
            out.append(f"[{seg[1:-1]}]")
        elif seg.startswith(":"):
            out.append(f"[{seg[1:]}]")
        else:
            out.append(seg)
    return "/".join(out)


def _route_groups(manifest: Any) -> dict[str, list[Any]]:
    """Endpoints grouped by the file that will own them — **bend 1**.

    Insertion-ordered so the emitted file list is deterministic, which the contract's frozen
    hashes and the golden benchmark both depend on.
    """
    groups: dict[str, list[Any]] = {}
    for ep in manifest.api.endpoints:
        path = f"app/api/{_segments(ep.path)}/route.ts".replace("//", "/")
        groups.setdefault(path, []).append(ep)
    return groups


def _page_path(route: Any) -> str:
    segs = _segments(getattr(route, "path", "/") or "/")
    return f"app/{segs}/page.tsx" if segs else "app/page.tsx"


# --------------------------------------------------------------------------- #
# Frozen sources
# --------------------------------------------------------------------------- #


def _package_json(manifest: Any) -> str:
    return (
        json.dumps(
            {
                "name": str(getattr(manifest, "project_id", "app")).replace("_", "-"),
                "private": True,
                "scripts": {
                    "dev": "next dev",
                    "build": "next build",
                    "start": "next start",
                    "test": "vitest run",
                },
                "dependencies": {"next": "14.2.5", "react": "18.3.1", "react-dom": "18.3.1"},
                "devDependencies": {
                    "@types/node": "20.14.10",
                    "@types/react": "18.3.3",
                    "typescript": "5.5.3",
                    "vitest": "1.6.0",
                },
            },
            indent=2,
        )
        + "\n"
    )


_TSCONFIG = """{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "ES2022"],
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "paths": { "@/*": ["./*"] },
    "plugins": [{ "name": "next" }]
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
"""

_NEXT_CONFIG = """/** @type {import('next').NextConfig} */
// Type errors fail the build deliberately: `next build` runs tsc, and it is stack #2's
// entire hygiene tier — the nine AST checks parse Python only. Disabling this would leave
// the API route slots with no static coverage at all (#822 bend 6).
const nextConfig = { typescript: { ignoreBuildErrors: false } }
export default nextConfig
"""

_VITEST_CONFIG = """import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: { environment: 'node', include: ['**/__tests__/**/*.test.ts'] },
})
"""

_HARNESS_TEST = """// Scaffold-owned harness (SIP-0100). QA suites consume the seams this proves, and must
// not reach past them into the app entry — the boundary that killed pf-25/26 on stack #1.
import { describe, it, expect } from 'vitest'
import { reset, insert, all } from '@/lib/store'

describe('scaffold harness', () => {
  it('provides an isolated store per test', () => {
    reset()
    expect(all('__probe')).toHaveLength(0)
    insert('__probe', { id: 'x' })
    expect(all('__probe')).toHaveLength(1)
    reset()
    expect(all('__probe')).toHaveLength(0)
  })
})
"""

_STORE = """// In-memory persistence, scaffold-owned and frozen. Module-level state reset per test via
// `reset()` — the coverage expectation the contract states for every stack.
const tables: Record<string, Record<string, unknown>[]> = {}

export function reset(): void {
  for (const key of Object.keys(tables)) delete tables[key]
}

export function all(table: string): Record<string, unknown>[] {
  return tables[table] ?? []
}

export function insert(table: string, row: Record<string, unknown>): Record<string, unknown> {
  ;(tables[table] ??= []).push(row)
  return row
}

export function find(table: string, id: string): Record<string, unknown> | undefined {
  return (tables[table] ?? []).find((r) => r.id === id)
}

export function nextId(): string {
  return Math.random().toString(36).slice(2, 10)
}
"""

_API_CLIENT = """// Client fetch helper, scaffold-owned. Views consume this rather than calling fetch
// directly, so the error envelope is parsed in exactly one place.
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body?.error?.code ?? `http_${res.status}`)
  return body as T
}
"""

_LAYOUT = """export const metadata = { title: 'app' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
"""


def _models_source(manifest: Any) -> str:
    lines = [
        "// Entity types, derived from the interface manifest. Scaffold-owned and frozen:",
        "// the fill slots import these rather than restating field names (#822).",
        "",
    ]
    for entity in getattr(manifest, "entities", ()) or ():
        lines.append(f"export interface {entity.name} {{")
        for field in entity.fields:
            optional = "" if getattr(field, "required", True) else "?"
            lines.append(f"  {field.name}{optional}: {_ts_type(getattr(field, 'type', 'str'))}")
        lines.append("}")
        lines.append("")
    for shape in getattr(manifest.api, "request_shapes", ()) or ():
        lines.append(f"export interface {shape.name} {{")
        for name in shape.required:
            lines.append(f"  {name}: string")
        for name in getattr(shape, "optional", ()) or ():
            lines.append(f"  {name}?: string")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def _errors_source(manifest: Any) -> str:
    contract = getattr(manifest.api, "error_contract", None)
    codes = list(getattr(contract, "codes", ()) or ()) if contract else []
    mapping = ",\n".join(f"  {c.code}: {c.http}" for c in codes)
    return f"""// Error envelope and code→status map, derived from the manifest's error contract.
// Frozen: a route that invents its own envelope breaks every probe that asserts on it.
export const ERROR_STATUS: Record<string, number> = {{
{mapping}
}}

export class ApiError extends Error {{
  constructor(
    public code: string,
    public detail: string = '',
  ) {{
    super(code)
  }}
}}

export function errorResponse(err: unknown): Response {{
  const code = err instanceof ApiError ? err.code : 'internal_error'
  const status = ERROR_STATUS[code] ?? 500
  const detail = err instanceof ApiError ? err.detail : ''
  return Response.json({{ error: {{ code, detail }} }}, {{ status }})
}}
"""


# --------------------------------------------------------------------------- #
# Fill slots — stubs that FAIL, by construction
# --------------------------------------------------------------------------- #


def _route_stub(path: str, endpoints: list[Any]) -> str:
    """A route file exporting one handler per declared method.

    Stubs throw rather than return: the bare skeleton must fail its probes, or the
    behavioral gate would measure the scaffold instead of the fill (SIP-0098 §7).
    """
    head = [
        "// FILL SLOT. Implement each exported handler against the declared contract.",
        "// The scaffold owns the signatures, the error envelope and the store; fill bodies only.",
        "import { ApiError, errorResponse } from '@/lib/errors'",
        "import * as store from '@/lib/store'",
        "",
        f"// Declared here: {', '.join(f'{e.method} {e.path}' for e in endpoints)}",
        "",
    ]
    body = []
    for ep in endpoints:
        status = getattr(ep, "success_status", None) or 200
        body += [
            f"export async function {ep.method.upper()}(request: Request) {{",
            "  try {",
            f"    // TODO: implement {ep.method} {ep.path} — respond {status}",
            f"    throw new ApiError('not_implemented', '{ep.method} {ep.path}')",
            "  } catch (err) {",
            "    return errorResponse(err)",
            "  }",
            "}",
            "",
        ]
    return "\n".join(head + body)


def _page_stub(route: Any) -> str:
    view = getattr(route, "view", None) or "Page"
    testids = list(getattr(route, "testids", ()) or ())
    anchors = "\n".join(f"      {{/* required anchor: {t} */}}" for t in testids)
    return f"""// FILL SLOT. Render this route's view. Every declared testid below must appear as a
// `data-testid` on the element it names — the QA suite queries them and nothing else.
'use client'

import {{ api }} from '@/lib/api'

export default function {view}() {{
  // TODO: implement. Declared anchors: {", ".join(testids) or "none"}
  return (
    <main>
{anchors}
    </main>
  )
}}
"""


# --------------------------------------------------------------------------- #
# The expander
# --------------------------------------------------------------------------- #


def expand_nextjs_ts(manifest: InterfaceManifest) -> list[dict[str, str]]:
    """Manifest → the Next.js walking skeleton, frozen files and fill slots together."""
    files: list[dict[str, str]] = [
        {"name": "package.json", "content": _package_json(manifest)},
        {"name": "tsconfig.json", "content": _TSCONFIG},
        {"name": "next.config.mjs", "content": _NEXT_CONFIG},
        {"name": "vitest.config.ts", "content": _VITEST_CONFIG},
        {"name": "lib/models.ts", "content": _models_source(manifest)},
        {"name": "lib/store.ts", "content": _STORE},
        {"name": "lib/errors.ts", "content": _errors_source(manifest)},
        {"name": "lib/api.ts", "content": _API_CLIENT},
        {"name": "app/layout.tsx", "content": _LAYOUT},
        {"name": "__tests__/harness.test.ts", "content": _HARNESS_TEST},
    ]
    for path, endpoints in _route_groups(manifest).items():
        files.append({"name": path, "content": _route_stub(path, endpoints)})
    for route in getattr(manifest.frontend, "routes", ()) or ():
        files.append({"name": _page_path(route), "content": _page_stub(route)})
    return files


def fill_slots_nextjs_ts(manifest: InterfaceManifest) -> tuple[str, ...]:
    """The files a dev fills bodies into: every route handler and every page.

    **Bend 1 lives here.** Stack #1 returns one routes file plus its views; this returns *n*
    route files, because Next derives the URL from the directory and an API with five
    endpoints across four paths is four files whether or not the blueprint expected it.
    """
    routes = tuple(_route_groups(manifest))
    pages = tuple(
        dict.fromkeys(_page_path(r) for r in (getattr(manifest.frontend, "routes", ()) or ()))
    )
    return routes + pages

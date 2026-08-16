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


def _dir_shape(directory: str) -> str:
    """``app/runs/[run_id]`` → ``app/runs/[]``. Two paths sharing a shape occupy the same
    position in Next's routing tree, whatever their slug names are called."""
    return "/".join("[]" if s.startswith("[") else s for s in directory.split("/"))


def _assert_routing_tree_is_coherent(routes: dict[str, list[Any]], pages: tuple[str, ...]) -> None:
    """Refuse a manifest whose API and page paths cannot coexist in one App Router tree (#859).

    **This is the other half of dropping the ``app/api/`` prefix.** That prefix used to keep
    API handlers and pages in disjoint subtrees, so a collision was structurally impossible
    and nobody had to think about it. Deriving the file from the declared URL is correct —
    ``/api/runs`` now yields ``app/api/runs/route.ts``, which serves ``/api/runs`` — but it
    puts both kinds of file in one tree, where Next has rules we must not silently violate:

    - a directory cannot hold both ``route.ts`` and ``page.tsx``;
    - two paths cannot use different slug names at the same dynamic position
      (``app/runs/[run_id]`` beside ``app/runs/[id]``).

    Raising rather than repairing is deliberate. The manifest states what the app serves, and
    two declarations that cannot both be served is a design defect the author must resolve —
    silently relocating one would produce an app that answers different URLs than its own
    contract probes, which is exactly the failure this change exists to end (roll 6 burned a
    full 7200s budget on it). M3's ``PROOF_EXPANDS`` turns this into a framing rejection, so
    it costs a free re-roll rather than an implementation run.

    The reference manifest fails this check by design of its own paths — its API is ``/runs``
    and its page is ``/runs/:id`` — which is why declaring API endpoints under ``/api`` is now
    a stated requirement of this stack rather than a convention the expander supplied.
    """
    route_dirs = {p.rsplit("/", 1)[0]: p for p in routes}
    page_dirs = {p.rsplit("/", 1)[0]: p for p in pages}

    both = sorted(set(route_dirs) & set(page_dirs))
    if both:
        raise ValueError(
            f"directory {both[0]!r} would hold both a route handler and a page — Next serves "
            f"one path from one file, so an API endpoint and a frontend route cannot share a "
            f"path on this stack. Declare the API under a distinct prefix (conventionally "
            f"`/api/...`) so the two occupy separate directories."
        )

    by_shape: dict[str, str] = {}
    for directory in list(route_dirs) + list(page_dirs):
        shape = _dir_shape(directory)
        clash = by_shape.setdefault(shape, directory)
        if clash != directory:
            raise ValueError(
                f"{clash!r} and {directory!r} occupy the same position in the routing tree "
                f"with different parameter names — Next requires one slug name per dynamic "
                f"segment. Use the same parameter name in both paths, or declare the API "
                f"under a distinct prefix (conventionally `/api/...`)."
            )


def _route_groups(manifest: Any) -> dict[str, list[Any]]:
    """Endpoints grouped by the file that will own them — **bend 1**.

    Insertion-ordered so the emitted file list is deterministic, which the contract's frozen
    hashes and the golden benchmark both depend on.

    **The path is derived from the declared URL, with no ``app/api/`` prefix (#859).** It used
    to prefix unconditionally, so a manifest declaring the true Next URL — ``/api/runs``, which
    is what an App Router author writes and what the frontend fetches — produced
    ``app/api/api/runs/route.ts``. That file serves ``/api/api/runs`` while the contract's
    probes request ``/api/runs``, so the application could never answer its own verification.
    Every gate passed it and roll 6's correction chain looped until the time budget ended it.

    ``path`` now means the same thing on every stack: the URL the app serves. Where the file
    lives is the stack's business, and here it is a direct function of that URL.
    """
    groups: dict[str, list[Any]] = {}
    for ep in manifest.api.endpoints:
        path = f"app/{_segments(ep.path)}/route.ts".replace("//", "/")
        groups.setdefault(path, []).append(ep)
    _assert_routing_tree_is_coherent(
        groups,
        tuple(_page_path(r) for r in (getattr(manifest.frontend, "routes", ()) or ())),
    )
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

_VITEST_CONFIG = """// The `@` alias is declared twice by necessity: tsconfig.json `paths` covers `tsc` and
// `next build`, but vitest resolves through vite, which does not read tsconfig paths —
// without this block every suite importing app code the way this stack teaches it
// (`@/lib/store`) fails collection with "Failed to load url", including the scaffold's
// own harness test. The two declarations must agree; a test pins them together.
import { defineConfig } from 'vitest/config'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  resolve: { alias: { '@': root } },
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

_LAYOUT = """import './globals.css'

export const metadata = { title: 'app' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
"""

#: The baseline stylesheet. Scaffold-owned, frozen, and never a fill slot.
#:
#: Delivered apps rendered with browser default styles, because the skeleton shipped no
#: stylesheet at all — nothing chose that look, it was simply absent. This supplies a floor.
#:
#: **Every rule is element-scoped on purpose.** A class-based stylesheet is a vocabulary the
#: fill author has to be taught, remember, and apply — which is a per-roll lottery, a new way
#: for a roll to fail, and a prompt surface to maintain. Selecting on elements instead means
#: the sheet styles whatever markup the author happens to write, with zero coordination: no
#: prompt change, nothing to learn, nothing to get wrong. The author never needs to know it
#: exists. That is the difference between a styling *capability* and a styling *floor*, and
#: only the floor is free.
#:
#: Consequences accepted deliberately:
#: - **Best-effort by construction.** A page built from semantic elements gets styled; a page
#:   built from a pile of `<div>`s gets the container and type treatment and little else.
#:   Improving that means teaching a vocabulary, which is the trade this rule exists to refuse.
#: - **Light only, no `prefers-color-scheme` block.** A dark scheme here would invert the page
#:   ground while any inline or component-level color the author wrote stays light, so the
#:   failure mode is a half-dark page that looks broken. A predictable floor beats a
#:   conditional one.
#: - **No reset.** Normalizing every element is a larger surface for no benefit at this scope.
_GLOBALS_CSS = """/* Baseline presentation. Scaffold-owned and frozen — do not edit.
   Element-scoped on purpose: it styles the markup you write without you doing anything. */

:root {
  --ink: #1c1e21;
  --muted: #61656b;
  --line: #e3e5e8;
  --accent: #2d6cdf;
  --surface: #ffffff;
  --ground: #f6f7f9;
  --radius: 8px;
}

* { box-sizing: border-box; }

body {
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
  max-width: 56rem;
  font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial,
    sans-serif;
  font-size: 16px;
  line-height: 1.55;
  color: var(--ink);
  background: var(--ground);
}

h1, h2, h3 { line-height: 1.25; margin: 0 0 0.5rem; font-weight: 650; }
h1 { font-size: 1.75rem; margin-top: 0.5rem; }
h2 { font-size: 1.25rem; margin-top: 2rem; }
h3 { font-size: 1.05rem; margin-top: 1.5rem; }
p { margin: 0 0 1rem; }
small { color: var(--muted); }

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

ul, ol { padding-left: 1.25rem; margin: 0 0 1rem; }
li { margin: 0.25rem 0; }

/* An unadorned list of records is the most common shape these apps render. */
ul li { list-style: none; }
ul {
  padding-left: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
ul li {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
}

table { width: 100%; border-collapse: collapse; margin: 0 0 1.5rem; background: var(--surface); }
th, td { text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--line); }
th { font-weight: 600; color: var(--muted); font-size: 0.85rem; text-transform: uppercase;
  letter-spacing: 0.03em; }
tr:last-child td { border-bottom: none; }

form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin: 0 0 1.5rem;
}

label { font-size: 0.9rem; font-weight: 550; color: var(--muted); }

input, select, textarea {
  font: inherit;
  color: inherit;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  width: 100%;
}
input:focus, select:focus, textarea:focus {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
  border-color: var(--accent);
}

button {
  font: inherit;
  font-weight: 550;
  padding: 0.55rem 1.1rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  align-self: flex-start;
}
button:hover { filter: brightness(1.08); }
button:disabled { opacity: 0.55; cursor: not-allowed; }

code, pre {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em;
}
pre {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1rem;
  overflow-x: auto;
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
        {"name": "app/globals.css", "content": _GLOBALS_CSS},
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

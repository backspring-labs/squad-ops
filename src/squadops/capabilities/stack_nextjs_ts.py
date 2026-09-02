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
from collections.abc import Collection
from typing import TYPE_CHECKING, Any

from squadops.capabilities.app_invocation import AppInvocation
from squadops.capabilities.success_status import success_status_for

if TYPE_CHECKING:  # pragma: no cover - annotations only, avoids a scaffold import cycle
    from squadops.capabilities.scaffold import InterfaceManifest

STACK_NAME = "nextjs_ts"

#: #1126: how a suite on this stack invokes the application. Under the in-process model
#: (#877) a suite reaches the app by importing its ``app/api/`` route handler — required as
#: an import *statement*, so a ``vi.mock('@/app/api/...')`` string cannot satisfy it — so
#: there is no ``fetch`` for a correct suite to stub, and mocking the route module under
#: test is unconditionally self-mocking. These three patterns used to live in the shared
#: detector as if they were every stack's; they are this stack's.
APP_INVOCATION = AppInvocation(
    invocation_import=r"""^\s*(?:import\b[^\n]*?from\s*|.*\brequire\s*\(\s*)['"`][^'"`]*app/api/""",
    subject_mock=r"""(?:vi|jest)\s*\.\s*mock\s*\(\s*['"`][^'"`]*app/api/""",
    invocation_description=(
        "an import of an `app/api/**/route` handler module, called directly with a "
        "`new Request(...)` — the in-process model; `@/lib/api` is the browser client and "
        "reaches no server under vitest"
    ),
)

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


def _ts_type(raw: str, declared: Collection[str] = ()) -> str:
    """Manifest field type → TypeScript. Unknown types become ``string`` rather than ``any``:
    ``any`` would silently disable the type checking that is stack #2's entire hygiene tier.

    ``declared`` is the set of entity and request-shape names the manifest defines. A token
    naming one passes through **case-preserved**, so ``list[Participant]`` renders
    ``Participant[]`` — the interface the same file declares three lines up.

    **#1096, and why this parameter exists.** Before it, every entity reference took the
    unknown-type path: the token was lower-cased (so the name was already gone), missed
    ``_TS_TYPES``, and became ``string``. The frozen ``lib/models.ts`` then declared
    ``Run.participants: string[]`` under a ``Participant`` interface it had just defined,
    the FROZEN FILES surface repeated it to the developer with the word *authoritative*
    attached, and the response floor — derived from the same manifest — demanded objects
    carrying ``name``. On every ``nextjs_ts`` roll of the 1.6.3 set the developers who
    obeyed the frozen file were rejected and the ones who ignored it were accepted. The
    Python expander's ``_py_type`` always passed entity names through; this is stack #2
    catching up to stack #1.
    """
    t = (raw or "").strip()
    inner = re.fullmatch(r"(?:list|array)\[(.+)\]", t, re.IGNORECASE)
    if inner:
        return f"{_ts_type(inner.group(1), declared)}[]"
    if t in declared:
        return t
    return _TS_TYPES.get(t.lower(), "string")


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

_HARNESS_TEST_HEAD = """// Scaffold-owned harness (SIP-0100). QA suites consume the seams this proves, and must
// not reach past them into the app entry — the boundary that killed pf-25/26 on stack #1.
import { describe, it, expect } from 'vitest'
import { reset, insert, all, TABLES } from '@/lib/store'
"""

_HARNESS_TEST_NO_ENTITIES = """// Scaffold-owned harness (SIP-0100). QA suites consume the seams this proves, and must
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


def _harness_test_source(manifest: Any) -> str:
    """The isolation harness, addressing a real table rather than a magic literal (#967).

    It used `'__probe'`, which a typed `Table` union rejects. Reserving a member for it was
    the tempting alternative and is exactly the untyped escape hatch #967 removes — a
    reserved name is a legal string the app could also pick. So the harness uses the first
    declared table via `TABLES`, which additionally demonstrates the accessor the fill briefs
    point authors at.
    """
    from squadops.capabilities.scaffold import root_persisted_entities

    # #1087: the first ROOT-PERSISTED table, not the first declared entity. On
    # ``group_run`` the first declared entity is ``Participant`` — an embedded shape —
    # so every roll's frozen harness demonstrated inserting into a table no correct
    # application writes, right above the fill the qa author was about to write.
    entities = (
        list(root_persisted_entities(manifest)) if getattr(manifest, "entities", None) else []
    )
    if not entities:
        return _HARNESS_TEST_NO_ENTITIES
    ref = f"TABLES.{entities[0]}"
    return (
        _HARNESS_TEST_HEAD
        + f"""
describe('scaffold harness', () => {{
  it('provides an isolated store per test', () => {{
    reset()
    expect(all({ref})).toHaveLength(0)
    insert({ref}, {{ id: 'x' }})
    expect(all({ref})).toHaveLength(1)
    reset()
    expect(all({ref})).toHaveLength(0)
  }})
}})
"""
    )


_STORE_HEADER = """// In-memory persistence, scaffold-owned and frozen. Module-level state reset per test via
// `reset()` — the coverage expectation the contract states for every stack.
//
// Table names are DERIVED FROM THE MANIFEST'S ENTITIES and typed (#967). Before this the
// table was a free `string`: the application named one, its test suite named another, and
// the disagreement surfaced as an empty array at assertion time — indistinguishable from a
// handler that never persisted at all. SIP-0104 window roll 6 was rejected that way with an
// application that worked. A name the two sides disagree about is now a COMPILE error
// listing the legal values, and `next build` runs tsc with errors fatal, so it fails before
// the suite ever runs."""

_STORE_BODY = """

export function reset(): void {
  for (const key of Object.keys(tables)) delete tables[key as Table]
}

export function all(table: Table): Record<string, unknown>[] {
  return tables[table] ?? []
}

export function insert(table: Table, row: Record<string, unknown>): Record<string, unknown> {
  ;(tables[table] ??= []).push(row)
  return row
}

// Persist a change to an existing row. Upsert by `id`: replaces the stored row when one
// matches, appends when none does.
//
// This exists because it did not (#1055). The store's only write verb was `insert`, which
// is `push`, so "save my change" had no correct form — the working answer was to mutate the
// object `find` returned and never call a write verb at all, which is non-obvious, while the
// natural-looking answer silently stored a duplicate. Two independent authorings on two
// different models both reached for `insert`, and both times only in the handlers that
// UPDATE rather than create (join and leave), which is what makes it an API gap rather than
// an authoring defect.
export function update(table: Table, row: Record<string, unknown>): Record<string, unknown> {
  const rows = (tables[table] ??= [])
  const index = rows.findIndex((r) => r.id === row.id)
  if (index >= 0) rows[index] = row
  else rows.push(row)
  return row
}

export function find(table: Table, id: string): Record<string, unknown> | undefined {
  return (tables[table] ?? []).find((r) => r.id === id)
}

export function nextId(): string {
  return Math.random().toString(36).slice(2, 10)
}
"""


def _table_name(entity_name: str) -> str:
    """``RunEvent`` → ``run_event``. The derivation, in one place.

    Exists as a function rather than inline so the tests can pin it and the authoring briefs
    can render the same values the store exports. The point of #967 is that nobody
    reproduces this rule by hand — ``TABLES`` is the answer and the type is the enforcement.
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", entity_name).lower()


def _store_source(manifest: Any) -> str:
    """The store, with its table names typed from the manifest's entities (#967).

    **Only the root-persisted ones (#1087).** ``TABLES`` used to carry every declared
    entity, including embedded shapes and response projections no correct application
    writes; a qa fill asserting on one of those rejected a working app, twice in eight
    rolls. The handle now exists only for what a correct app stores, so a fill reaching
    for ``TABLES.Participant`` fails at the fill gate with the real tables named — and
    under ``next build``'s type check — instead of at runtime with an empty array that
    reads exactly like a handler that never saved anything.

    A manifest declaring no entities keeps an open signature: there is no union to derive,
    and ``never`` would make the store unusable rather than safe.
    """
    from squadops.capabilities.scaffold import root_persisted_entities

    entities = (
        list(root_persisted_entities(manifest)) if getattr(manifest, "entities", None) else []
    )
    if not entities:
        return (
            _STORE_HEADER
            + "\n//\n// No entities are declared, so there is no table union to derive and the"
            + " signature\n// stays open. There is also nothing for two authors to disagree"
            + " about.\nexport type Table = string\n"
            + "const tables: Record<string, Record<string, unknown>[]> = {}"
            + _STORE_BODY
        )
    lines = [
        _STORE_HEADER,
        "",
        "export const TABLES = {",
        *(f"  {name}: '{_table_name(name)}'," for name in entities),
        "} as const",
        "",
        "export type Table = (typeof TABLES)[keyof typeof TABLES]",
        "",
        "const tables: Partial<Record<Table, Record<string, unknown>[]>> = {}",
    ]
    return "\n".join(lines) + _STORE_BODY


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
    entities = tuple(getattr(manifest, "entities", ()) or ())
    shapes = tuple(getattr(manifest.api, "request_shapes", ()) or ())
    # The names a field type may reference (#1096): an entity-typed field renders the
    # interface this file declares for it, never ``string``.
    declared = frozenset([e.name for e in entities] + [s.name for s in shapes])
    for entity in entities:
        lines.append(f"export interface {entity.name} {{")
        for field in entity.fields:
            optional = "" if getattr(field, "required", True) else "?"
            ts = _ts_type(getattr(field, "type", "str"), declared)
            lines.append(f"  {field.name}{optional}: {ts}")
        lines.append("}")
        lines.append("")
    for shape in shapes:
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
    message: string = '',
  ) {{
    super(message)
  }}
}}

export function errorResponse(err: unknown): Response {{
  const code = err instanceof ApiError ? err.code : 'internal_error'
  const status = ERROR_STATUS[code] ?? 500
  const message = err instanceof ApiError ? err.message : ''
  return Response.json({{ error: {{ code, message }} }}, {{ status }})
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
        status = success_status_for(ep)
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
        {"name": "lib/store.ts", "content": _store_source(manifest)},
        {"name": "lib/errors.ts", "content": _errors_source(manifest)},
        {"name": "lib/api.ts", "content": _API_CLIENT},
        {"name": "app/layout.tsx", "content": _LAYOUT},
        {"name": "__tests__/harness.test.ts", "content": _harness_test_source(manifest)},
    ]
    for path, endpoints in _route_groups(manifest).items():
        files.append({"name": path, "content": _route_stub(path, endpoints)})
    for route in getattr(manifest.frontend, "routes", ()) or ():
        files.append({"name": _page_path(route), "content": _page_stub(route)})
    return files


def endpoint_owners_nextjs_ts(manifest: InterfaceManifest) -> dict[str, list[str]]:
    """``route file → ["METHOD /path", …]`` — which fill slot serves which endpoint (#1015).

    Stack #1 states this relation through the ``endpoint_defined`` criterion its pack
    attaches to ``backend/routes.py``; this stack's pack has no Python AST check to hang
    it on, so until now the contract said nothing and ``endpoint_owners()`` came back
    empty — which is why the 1.6.3 set's repair target was the whole application in 18
    of 18 rounds: the #688 chain from a failing probe to the file that owns its endpoint
    had no map to walk on this stack. The relation is bend 1's own output
    (``_route_groups``), so the contract now carries it as data.
    """
    return {
        path: [f"{ep.method} {ep.path}" for ep in endpoints]
        for path, endpoints in _route_groups(manifest).items()
    }


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

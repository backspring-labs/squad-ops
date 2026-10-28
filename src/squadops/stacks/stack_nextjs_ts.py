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
from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Any

from squadops.stacks.app_invocation import JS_MODULE_LOAD, NETWORK_SEAM_FETCH_STUB, AppInvocation
from squadops.stacks.baseline_stylesheet import BASELINE_CSS
from squadops.stacks.client_surface import KIND_FUNCTION, ClientExport, ClientSurface
from squadops.stacks.rendered_packaging import render_packaging
from squadops.stacks.route_paths import path_segments
from squadops.stacks.success_status import success_status_for

if TYPE_CHECKING:  # pragma: no cover - annotations only, avoids a scaffold import cycle
    from squadops.stacks.scaffold import InterfaceManifest

STACK_NAME = "nextjs_ts"

#: #1126: how a suite on this stack invokes the application. Under the in-process model
#: (#877) an API suite reaches the app by loading its ``app/api/`` route handler — an import
#: statement, a ``require``, or a dynamic ``import(`` (``JS_MODULE_LOAD``, #1533), never a
#: ``vi.mock('@/app/api/...')`` string — and calls it directly. A page suite (#2534) reaches it
#: by rendering a real ``app/**/page`` module or a ``components/`` component, as stack #1's
#: suites render ``App`` or a view: the network is a seam UNDER the page, so a ``fetch`` stub
#: or a mock of the frozen ``@/lib/api`` client is legitimate beneath a rendered page and
#: self-mocking when nothing is rendered. A page criterion about structure fetches nothing,
#: so requiring a handler import refused a correct page test (#2547). Mocking a route module
#: or a page module itself is mocking the subject. These patterns used to live in the shared
#: detector as if they were every stack's; they are this stack's.
APP_INVOCATION = AppInvocation(
    invocation_import=(
        JS_MODULE_LOAD
        + r"""['"`][^'"`]*(?:app/api/|app/(?:[^'"`]*/)?page(?:\.tsx?)?['"`]|components/"""
        # #2577: the frozen route caller loads and calls the route module itself, and #2602's
        # frozen page loader loads the page module.
        + r"""|vitest\.(?:routes|pages)(?:\.ts)?['"`])"""
    ),
    subject_mock=(
        r"""(?:vi|jest)\s*\.\s*mock\s*\(\s*['"`][^'"`]*"""
        r"""(?:app/api/|app/(?:[^'"`]*/)?page(?:\.tsx?)?['"`]|vitest\.(?:routes|pages)(?:\.ts)?['"`])"""
    ),
    network_seam_mock=(
        NETWORK_SEAM_FETCH_STUB
        + r"""    | (?:vi|jest)\s*\.\s*mock\s*\(\s*['"`][^'"`]*lib/api(?:\.tsx?)?['"`]"""
    ),
    invocation_description=(
        "an import of an `app/api/**/route` handler module, called directly with a "
        "`new Request(...)` — the in-process model — or a route called through the frozen "
        "`callRoute` from `@/vitest.routes`, or, for a page, rendering the real "
        "`app/**/page` (or one loaded through the frozen `loadPage` from `@/vitest.pages`, or a "
        "`components/` component) with `fetch` or the frozen `@/lib/api` "
        "client stubbed beneath it; `@/lib/api` alone is the browser client and reaches no "
        "server under vitest"
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
    """``/runs/{run_id}/join`` → ``runs/[run_id]/join`` (bend 2). A parameter in either of the
    manifest's spellings (``route_paths``) becomes Next's bracket directory."""
    return "/".join(f"[{s.name}]" if s.param else s.name for s in path_segments(path))


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
                # #2534: a page suite renders in a DOM with Testing Library, as stack #1's do.
                "devDependencies": {
                    "@testing-library/dom": "10.4.0",
                    "@testing-library/jest-dom": "6.5.0",
                    "@testing-library/react": "16.0.1",
                    "@types/node": "20.14.10",
                    "@types/react": "18.3.3",
                    "jsdom": "25.0.1",
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

#: The files this stack's test runner collects — rendered into the scaffold's vitest config
#: below and read by plan validation and patch acceptance through the development profile's
#: ``test_file_patterns`` (#1534). Stated once because it was stated three times and they
#: disagreed: the config collected ``__tests__/**/*.test.ts`` while the profile declared
#: ``.tsx`` and ``.spec`` forms and the plan-authoring rules said vitest discovers ``.tsx``.
#: Six stored plans named a qa suite the runner never collects; on 1.8.0 deploy A's Next.js
#: checkpoint (``cyc_79f70a0bbac1``) the qa author spent a self-eval pass writing one.
#: ``.test.tsx`` is collected too (#2531): a suite that renders a page writes JSX, which a ``.ts``
#: file can't hold, so a planner testing a page named ``.tsx`` and plan review refused the plan,
#: in two of the 2.4 shakeout's three framings that planned one. ``esbuild.jsx`` below compiles it.
VITEST_SUITE_GLOBS = ("**/__tests__/**/*.test.ts", "**/__tests__/**/*.test.tsx")

#: ``esbuild.jsx`` (#2394): without it vite compiled each page's JSX as ``React.createElement``,
#: and a Next.js page does not import React, so a suite that rendered one failed "React is not
#: defined" inside the page module, where no repair either role may make reaches it. The 2.3.1
#: regression pair's Next.js roll (``cyc_31a49b2cdde6``) ended there, and so did a qa.test on
#: 1.8.1 (``cyc_4d9602ce0a66``).
_VITEST_CONFIG = (
    """// The `@` alias is declared twice by necessity: tsconfig.json `paths` covers `tsc` and
// `next build`, but vitest resolves through vite, which does not read tsconfig paths —
// without this block every suite importing app code the way this stack teaches it
// (`@/lib/store`) fails collection with "Failed to load url", including the scaffold's
// own harness test. The two declarations must agree; a test pins them together.
// `esbuild.jsx` is set here for the same reason: tsconfig.json's `"jsx": "preserve"` leaves
// JSX to `next build`, and vite would otherwise compile a page's JSX for a React import the
// page does not have.
import { defineConfig } from 'vitest/config'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { '@': root } },
  test: {
    environment: 'node',
    // A page suite renders a page, so it runs in a DOM (#2534); an API suite stays in node,
    // the environment the route handlers run in.
    environmentMatchGlobs: [['**/__tests__/**/*.test.tsx', 'jsdom']],
    setupFiles: ['vitest.setup.ts'],
    include: ['"""
    + "', '".join(VITEST_SUITE_GLOBS)
    + """'],
  },
})
"""
)

#: Scaffold-owned setup (frozen, #2534), stack #1's ``test-setup.js`` for this stack: jest-dom's
#: matchers on vitest's ``expect``, and Testing Library's cleanup after each test that rendered,
#: since under ``globals: false`` it registers none itself (#1127). It runs for API suites too,
#: in node, where there is no document and nothing to clean up.
_VITEST_SETUP = """// Scaffold-owned (frozen): jest-dom's matchers, and Testing Library's cleanup after each
// test, so one test's render never leaks into the next (a suite that renders in more than one
// `it` would otherwise fail "Found multiple elements").
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

afterEach(async () => {
  if (typeof document === 'undefined') return
  const { cleanup } = await import('@testing-library/react')
  cleanup()
})
"""

#: Scaffold-owned harness proof (frozen, #2534): a ``.test.tsx`` suite renders in a DOM and
#: Testing Library finds a test id in it. It imports no page, so it passes on the bare skeleton
#: and after any fill, and an install that lost the DOM fails here, by name.
_HARNESS_DOM_TEST = """// Scaffold-owned harness proof (frozen): a page suite (`.test.tsx`) runs in a DOM, with
// Testing Library and jest-dom's matchers. Write page suites in NEW files beside this one,
// rendering the page as below and mocking what it fetches.
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

describe('page test harness', () => {
  it('renders into a DOM where a test id is found', async () => {
    render(<main data-testid="harness-root">ready</main>)
    expect(await screen.findByTestId('harness-root')).toHaveTextContent('ready')
  })
})
"""

#: Where the scaffold's route caller lives, and how a criterion test imports it. A test-config
#: file beside ``vitest.setup.ts`` (``ScaffoldStack.test_config_files``), outside the qa
#: namespace, which holds suites only: so every criterion's verifier bundle carries it, and the
#: bundle is what runs on the accepted tree, which may predate this file (SIP-0109 §7.4).
ROUTE_CALLER_PATH = "vitest.routes.ts"
ROUTE_CALLER_IMPORT = "@/vitest.routes"

#: The App Router's resolution, written once and emitted into both the route caller and the page
#: loader (#2602), so the two never route one path differently. Each emitted file carries its own
#: copy: a criterion's bundle carries the test-config files, and a stored bundle's caller is the
#: one it was frozen with, so neither file may import the other.
_NODE_IMPORTS = """import { existsSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
"""

_APP_DIR = """// As vitest.config.ts finds the root: a literal `new URL(..., import.meta.url)` is rewritten to an
// http URL in a DOM suite, and `fileURLToPath` refuses it.
const APP = path.join(path.dirname(fileURLToPath(import.meta.url)), 'app')
"""

_SEGMENT_MATCH = """function match(segments: string[], parts: string[]): Record<string, string> | null {
  if (segments.length !== parts.length) return null
  const params: Record<string, string> = {}
  for (let i = 0; i < segments.length; i++) {
    const segment = segments[i]
    if (segment.startsWith('[') && segment.endsWith(']')) params[segment.slice(1, -1)] = parts[i]
    else if (segment !== parts[i]) return null
  }
  return params
}

function specificity(segments: string[]): string {
  return segments.map((s) => (s.startsWith('[') ? '1' : '0')).join('')
}
"""


def _app_tree_walk(function: str, is_entry: str) -> str:
    """The walk of ``app/`` that lists each file ``is_entry`` accepts with its URL segments: a
    ``_private`` folder is skipped and a ``(group)`` folder adds no segment, as the App Router
    routes them."""
    return f"""function {function}(dir: string, segments: string[] = []): {{ file: string; segments: string[] }}[] {{
  if (!existsSync(dir)) return []
  const found: {{ file: string; segments: string[] }}[] = []
  for (const entry of readdirSync(dir, {{ withFileTypes: true }})) {{
    if (entry.isDirectory()) {{
      if (entry.name.startsWith('_')) continue
      const group = entry.name.startsWith('(') && entry.name.endsWith(')')
      found.push(...{function}(path.join(dir, entry.name), group ? segments : [...segments, entry.name]))
    }} else if ({is_entry}) {{
      found.push({{ file: path.join(dir, entry.name), segments }})
    }}
  }}
  return found
}}
"""


#: Scaffold-owned route caller (frozen, #2577), the counterpart of stack #1's ``client`` fixture.
#: A criterion's test runs on the accepted application, where it must fail, and on the change,
#: where it must pass (SIP-0109 §8.2). This stack's tests import a route's module, and a route the
#: change adds has no module on the accepted tree, so the file failed at collection: a setup
#: failure, never counted as the criterion failing, and the 2.4 window's campaign 2 seed increment
#: was rejected however correct its build. Through ``callRoute`` the route is found when the call
#: is made, as the App Router finds it, and a path no route serves answers 404.
_ROUTE_CALLER = (
    """// Scaffold-owned (frozen): call a route handler by method and path, as a client calls the
// running application. The route is found when the call is made, the way the App Router finds
// it: a static folder wins over a [param] folder, segment by segment; a (group) folder adds no
// segment and a _private folder routes nothing. A path no route serves answers 404, a method its
// route does not export 405, HEAD is served by GET, OPTIONS answers 204 with Allow, and a path
// with a trailing slash is redirected (308), as `next start` does.
//
// A criterion's test calls its route here, never by importing the route module: on the
// application before the change that module may not exist, and an import of it fails the file
// before any assertion runs.
"""
    + _NODE_IMPORTS
    + """
type Handler = (
  request: Request,
  context: { params: Record<string, string> },
) => Response | Promise<Response>

const METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
"""
    + _APP_DIR
    + "\n"
    + _app_tree_walk("routes", "entry.name === 'route.ts'")
    + "\n"
    + _SEGMENT_MATCH
    + """
export async function callRoute(method: string, url: string, init: RequestInit = {}): Promise<Response> {
  const target = new URL(url, 'http://localhost')
  if (target.pathname.length > 1 && target.pathname.endsWith('/')) {
    const location = target.pathname.replace(/\\/+$/, '') + target.search
    return new Response(null, { status: 308, headers: { location } })
  }
  let parts: string[]
  try {
    parts = target.pathname.split('/').filter(Boolean).map(decodeURIComponent)
  } catch {
    return new Response(null, { status: 400 })
  }
  const candidates = routes(APP)
    .map((r) => ({ ...r, params: match(r.segments, parts) }))
    .filter((c): c is { file: string; segments: string[]; params: Record<string, string> } => c.params !== null)
    .sort((a, b) => specificity(a.segments).localeCompare(specificity(b.segments)))
  const chosen = candidates[0]
  if (chosen === undefined) return new Response(null, { status: 404 })
  const handlers = (await import(/* @vite-ignore */ chosen.file)) as Record<string, Handler | undefined>
  const verb = method.toUpperCase()
  const exported = METHODS.filter((m) => typeof handlers[m] === 'function')
  const handler = handlers[verb] ?? (verb === 'HEAD' ? handlers.GET : undefined)
  if (handler === undefined) {
    if (verb === 'OPTIONS') return new Response(null, { status: 204, headers: { allow: exported.join(', ') } })
    return new Response(null, { status: 405, headers: { allow: exported.join(', ') } })
  }
  const response = await handler(new Request(target, { ...init, method: verb }), { params: chosen.params })
  return verb === 'HEAD' && handlers.HEAD === undefined
    ? new Response(null, { status: response.status, headers: response.headers })
    : response
}
"""
)

#: Where the scaffold's page loader lives, and how a criterion test imports it (#2602): the page
#: counterpart of the route caller, a test-config file beside it for the same reason.
PAGE_LOADER_PATH = "vitest.pages.ts"
PAGE_LOADER_IMPORT = "@/vitest.pages"

#: Scaffold-owned page loader (frozen, #2602), the page half of ``_ROUTE_CALLER``. A page
#: criterion's test (``client_route``) renders its page. A page the change adds has no
#: ``app/**/page`` module on the accepted tree, so a test that imports it failed at collection,
#: a setup failure §8.2 never counts, and the increment was refused however correct its build.
#: Through ``loadPage`` the page is found when the test runs, by the route caller's own
#: resolution, and a path no page serves renders a not-found page: the test fails at its anchor's
#: assertion, as §8.2 counts "a missing view rendering without its declared test ids". No JSX, so
#: the file is ``.ts`` like the caller and needs no compile setting of its own.
_PAGE_LOADER = (
    """// Scaffold-owned (frozen): load the page the App Router serves for a path, to render it in a
// page suite (`.test.tsx`). The page is found when the test runs, as vitest.routes.ts finds a
// route: a static folder wins over a [param] folder, segment by segment; a (group) folder adds no
// segment and a _private folder routes nothing. The page is rendered with its `params` and
// `searchParams` props, as the App Router passes them. A path no page serves renders a not-found
// page instead, as `next start` answers it.
//
// A criterion's test loads its page here, never by importing the page module: on the application
// before the change that module may not exist, and an import of it fails the file before any
// assertion runs.
"""
    + _NODE_IMPORTS
    + """import { createElement, type ComponentType } from 'react'

type PageProps = { params: Record<string, string>; searchParams: Record<string, string> }

const PAGE_FILES = ['page.tsx', 'page.ts', 'page.jsx', 'page.js']
"""
    + _APP_DIR
    + "\n"
    + _app_tree_walk("pages", "PAGE_FILES.includes(entry.name)")
    + "\n"
    + _SEGMENT_MATCH
    + """
function NotFound() {
  return createElement(
    'main',
    null,
    createElement('h1', null, '404'),
    createElement('p', null, 'This page could not be found.'),
  )
}

export async function loadPage(url: string): Promise<ComponentType> {
  const target = new URL(url, 'http://localhost')
  let parts: string[]
  try {
    parts = target.pathname.split('/').filter(Boolean).map(decodeURIComponent)
  } catch {
    return NotFound
  }
  const candidates = pages(APP)
    .map((p) => ({ ...p, params: match(p.segments, parts) }))
    .filter((c): c is { file: string; segments: string[]; params: Record<string, string> } => c.params !== null)
    .sort((a, b) => specificity(a.segments).localeCompare(specificity(b.segments)))
  const chosen = candidates[0]
  if (chosen === undefined) return NotFound
  const loaded = (await import(/* @vite-ignore */ chosen.file)) as { default?: ComponentType<PageProps> }
  const Page = loaded.default
  if (Page === undefined) throw new Error(`${chosen.file} has no default-exported page component`)
  const props: PageProps = { params: chosen.params, searchParams: Object.fromEntries(target.searchParams) }
  return function LoadedPage() {
    return createElement(Page, props)
  }
}
"""
)

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
    # deferred (cycle): stacks.scaffold loads this module
    from squadops.stacks.scaffold import root_persisted_entities

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

// Delete a stored row by its `id`. Returns whether a row was removed.
//
// This exists because it did not (#2363), the same gap `update` closed for changes. With only
// `insert`, `update` and `find`, a DELETE over an entity stored as rows of its own had no
// correct form: the leave handler could take a participant out of its run's list, but the
// participant's own row stayed, and a suite asserting that table failed a working application
// on every repair (cyc_0758d771a1dc, three rounds).
export function remove(table: Table, id: string): boolean {
  const rows = tables[table] ?? []
  const index = rows.findIndex((r) => r.id === id)
  if (index < 0) return false
  rows.splice(index, 1)
  return true
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
    # deferred (cycle): stacks.scaffold loads this module
    from squadops.stacks.scaffold import root_persisted_entities

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
    # #2205 gap 3: a declared message is the contract's, rendered whatever the throw passes. A
    # contract that declares none emits the module byte for byte as before.
    messages = {c.code: c.message for c in codes if getattr(c, "message", None) is not None}
    message_map = ""
    message = "err instanceof ApiError ? err.message : ''"
    if messages:
        entries = ",\n".join(f"  {code}: {json.dumps(text)}" for code, text in messages.items())
        message_map = (
            "\n// code→message, declared in the manifest's error contract: rendered word for word.\n"
            "export const ERROR_MESSAGE: Record<string, string> = {\n" + entries + "\n}\n"
        )
        message = f"ERROR_MESSAGE[code] ?? ({message})"
    return f"""// Error envelope and code→status map, derived from the manifest's error contract.
// Frozen: a route that invents its own envelope breaks every probe that asserts on it.
export const ERROR_STATUS: Record<string, number> = {{
{mapping}
}}
{message_map}
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
  const message = {message}
  return Response.json({{ error: {{ code, message }} }}, {{ status }})
}}
"""


# --------------------------------------------------------------------------- #
# Fill slots — stubs that FAIL, by construction
# --------------------------------------------------------------------------- #


def _route_stub(
    path: str, endpoints: list[Any], shapes: Mapping[str, Any], entities: Mapping[str, Any]
) -> str:
    """A route file exporting one handler per declared method.

    Stubs throw rather than return: the bare skeleton must fail its probes, or the
    behavioral gate would measure the scaffold instead of the fill (SIP-0098 §7).

    Each handler states its contract where it is written: the request shape's fields, the
    response entity's fields and the declared errors. A route file is one endpoint's, not every
    endpoint's as FastAPI's ``routes.py`` is, so without them a change to an endpoint's request,
    response or errors left its file's skeleton unchanged. An increment's footprint is the files whose skeleton the delta
    changes (``change_request.derive_footprint``), so the route a capacity increment must
    implement fell outside it, and every edit to it was dropped as another producer's slot
    (Next.js shakeout round 2, cyc_0df8d7215ef2).
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
        # #2202: a declared order is stated where the handler is written.
        order = [f"    // {ep.order.instruction()}"] if ep.order is not None else []
        body += [
            f"export async function {ep.method.upper()}(request: Request) {{",
            "  try {",
            f"    // TODO: implement {ep.method} {ep.path} — respond {status}",
            *_contract_lines(ep, shapes, entities=entities),
            *order,
            f"    throw new ApiError('not_implemented', '{ep.method} {ep.path}')",
            "  } catch (err) {",
            "    return errorResponse(err)",
            "  }",
            "}",
            "",
        ]
    return "\n".join(head + body)


def _contract_lines(
    ep: Any, shapes: Mapping[str, Any], *, entities: Mapping[str, Any]
) -> list[str]:
    """The endpoint's request fields, response fields and declared errors, as comment lines in
    its handler.

    The response line is #2522's request line for what the handler returns: a field added to the
    entity changes every route that returns it, so those routes join the increment's footprint. A
    handler that lists the fields it returns could otherwise never add one (Next.js shakeout
    round 5, ``cyc_311e2117c21d``: the detail route returned a run without ``capacity``)."""
    lines = []
    shape = shapes.get(ep.request) if ep.request else None
    if shape is not None:
        optional = f"; optional {', '.join(shape.optional)}" if shape.optional else ""
        lines.append(
            f"    // request {shape.name}: {', '.join(shape.required) or 'no required field'}{optional}"
        )
    response = str(ep.response or "")
    listed = response.startswith("list[") and response.endswith("]")
    entity = entities.get(response[5:-1] if listed else response)
    if entity is not None:
        always = [f.name for f in entity.fields if f.required]
        sometimes = [f.name for f in entity.fields if not f.required]
        rest = f"; optional {', '.join(sometimes)}" if sometimes else ""
        lines.append(
            f"    // response {response}: {', '.join(always) or 'no required field'}{rest}"
        )
    if ep.errors:
        lines.append(f"    // errors: {', '.join(ep.errors)}")
    if ep.query:
        # #2378: the inputs it reads from ``new URL(request.url).searchParams``.
        lines.append(f"    // query: {', '.join(q.placeholder() for q in ep.query)}")
    return lines


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
        {"name": "vitest.setup.ts", "content": _VITEST_SETUP},
        {"name": "lib/models.ts", "content": _models_source(manifest)},
        {"name": "lib/store.ts", "content": _store_source(manifest)},
        {"name": "lib/errors.ts", "content": _errors_source(manifest)},
        {"name": "lib/api.ts", "content": _API_CLIENT},
        {"name": "app/layout.tsx", "content": _LAYOUT},
        {"name": "app/globals.css", "content": BASELINE_CSS},
        {"name": "__tests__/harness.test.ts", "content": _harness_test_source(manifest)},
        {"name": "__tests__/harness-dom.test.tsx", "content": _HARNESS_DOM_TEST},
        {"name": ROUTE_CALLER_PATH, "content": _ROUTE_CALLER},
        {"name": PAGE_LOADER_PATH, "content": _PAGE_LOADER},
        # #598: rendered from the environment contract and frozen, not builder-authored.
        *render_packaging("nextjs_ts"),
    ]
    shapes = {s.name: s for s in getattr(manifest.api, "request_shapes", ()) or ()}
    entities = {e.name: e for e in getattr(manifest, "entities", ()) or ()}
    for path, endpoints in _route_groups(manifest).items():
        files.append({"name": path, "content": _route_stub(path, endpoints, shapes, entities)})
    for route in getattr(manifest.frontend, "routes", ()) or ():
        files.append({"name": _page_path(route), "content": _page_stub(route)})
    return files


#: The frozen ``lib/api.ts`` client's call surface (#668), as the registry carries it and the
#: ``client_mock_surface`` check judges by. Declared here rather than read off the template, which is
#: TypeScript (``api<T>(path: string, init?: RequestInit)``); a test holds the two together. Its page
#: suites mock or stub beneath it since they render pages in a DOM (#2534): the 2.4 Next.js shakeout's
#: round 6 mocked it with React's prefix-less paths (``/runs``), which this client never receives, so
#: every page call missed the mock and no page rendered its data.
CLIENT_SURFACE = ClientSurface(
    path="lib/api.ts",
    # Suites import it by the stack's alias, or relatively from __tests__/ and its subdirectories.
    module_specifier=r"(?:@/|(?:\.\./)+)lib/api(?:\.ts)?",
    exports=(ClientExport("api", KIND_FUNCTION, ("path", "init")),),
    path_prefix="",
    error_envelope_key="error",
    default_export=None,
)


def client_surface_lines_nextjs_ts(manifest: InterfaceManifest) -> list[str]:
    """The frozen client's call surface as the page suite's author reads it (#668), one line per
    export, from ``CLIENT_SURFACE``; the prose around them is the appendix asset's."""
    del manifest
    return [
        f"`{export.name}(path, init?)` exported from `{CLIENT_SURFACE.path}` (import it as "
        "`@/lib/api`) — fetches the path it is given verbatim, with no prefix, so a page calls it "
        "with the endpoint's full declared path (`/api/runs`, `/api/runs/{run_id}/join`); sends "
        "JSON headers, returns the parsed JSON body, and on a non-2xx response throws an `Error` "
        f"whose message is the `{CLIENT_SURFACE.error_envelope_key}.code` of the body's envelope"
        for export in CLIENT_SURFACE.call_exports
    ]


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

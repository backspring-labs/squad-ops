---
fragment_id: task_type.qa.test
layer: task_type
version: "0.9.24"
roles: ["qa"]
---
# Task: Generate and Execute Tests (qa.test)

You are generating test files that will be executed immediately, as-is, in the
workspace they are written for. Your tests are themselves a deliverable that
can fail the build — a test suite that cannot load is a failed check, not a
neutral outcome.

## Execution Environment (hard rule)

Your suite runs in the test runner's own process — pytest or vitest, exactly
as the workspace's dependency manifests declare. **No application server is
running during test execution, on any stack, and nothing you write can start
one.** A test that opens a network connection to the application — `fetch` or
an HTTP client against `localhost` or any URL — fails unconditionally: there
is nothing listening. Exercise the application IN-PROCESS instead:

- Python/FastAPI workspaces: `fastapi.testclient.TestClient` or
  `httpx.AsyncClient` bound to the app object — in-process, no server.
- Next.js workspaces: route handlers are plain exported functions. Import
  them and invoke them directly with a `Request`, e.g.
  `import { POST } from '@/app/api/runs/route'` then
  `const res = await POST(new Request('http://test/api/runs', {method: 'POST', body: ...}))`
  and assert on the returned `Response`. Drive shared state through the
  scaffold's store seam, as the frozen harness demonstrates.

## Discovery Contract (hard rule)

When the workspace declares Python dependency manifests (`requirements.txt`),
backend tests MUST be Python pytest files whose names match pytest discovery:
`test_*.py` (e.g. `tests/test_api.py`). The suite is executed with `pytest .`
from the workspace root — a JavaScript file, a shell script, or a Python file
named any other way is invisible to the runner: pytest collects zero tests,
the required `tests_pass` check fails, and the whole run is rejected. Never
write backend smoke tests in JavaScript. Frontend test files are only
generated when the frontend manifest declares a test runner (see Scope
Discipline), and they never satisfy the backend suite requirement.

When the workspace is a single TypeScript application (no Python manifests —
e.g. a Next.js project rooted at the workspace), there is no pytest suite:
the whole suite is the declared JS runner's (`vitest run`), and its discovery
convention is the one the workspace's config declares (scaffolded Next.js
workspaces collect `__tests__/**/*.test.ts`).

## Dependency Constraint (hard rule)

Generated tests may ONLY import packages that appear in the workspace's
dependency manifests shown in the source files (`requirements.txt`,
`package.json`). Never introduce a new dependency in a test file — a suite
that fails to import fails the whole `tests_pass` check. If a test would need
an unavailable library, cover that behavior from the other side of the stack
(e.g. backend API tests) or omit it.

## Test Isolation (hard rule)

- Every test must be order-independent: never rely on state created,
  mutated, or left behind by another test.
- Application state that lives at module level (in-memory stores, caches,
  registries) persists across all tests in a session. Reset it in a fixture
  that runs before each test (e.g. an autouse fixture clearing the store) —
  a test asserting "empty" must establish empty, not hope to run first.

## Frontend Tests (when the workspace declares a runner)

When `frontend/package.json` declares a `test` script (scaffolded workspaces
declare vitest), frontend UI tests are real deliverables:

- Files are `*.test.jsx` under `frontend/src/__tests__/`, executed with
  `vitest run` in a jsdom environment.
- The workspace seeds a frozen harness proof (`harness.test.jsx`) and setup
  file (`src/test-setup.js`, registers jest-dom matchers). Follow the harness
  example exactly: render components inside a `MemoryRouter`; never edit the
  frozen harness files — write NEW test files beside them.
- Component tests must not depend on a running backend: jsdom has no server.
  Mock the workspace's `apiFetch` (from `frontend/src/api.js`) instead of
  calling `fetch` against real URLs.

## Scope Discipline

- Test the deliverable that exists, against the interfaces it actually
  exposes — do not test aspirational behavior the PRD excludes.
- If the frontend dependency manifest declares no test runner and no `test`
  script, generate no frontend test files; the frontend build check covers
  compile-level integrity.
- Prefer fewer tests that exercise real code paths over many shallow ones.

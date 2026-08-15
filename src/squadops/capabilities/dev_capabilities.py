"""Development capability registry (SIP-0072).

Typed development capabilities that control handler behavior: prompt
supplements, file structure guidance, source filtering, and test framework
selection.  V1 capabilities are code-defined frozen dataclass instances.

Mirrors the BuildProfile registry pattern in build_profiles.py.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Test framework constants (D5)
# ---------------------------------------------------------------------------

TEST_FRAMEWORK_PYTEST = "pytest"
TEST_FRAMEWORK_VITEST = "vitest"
TEST_FRAMEWORK_BOTH = "both"


# ---------------------------------------------------------------------------
# DevelopmentCapability dataclass (D1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DevelopmentCapability:
    """Typed development capability definition (SIP-0072 §5.1).

    Handlers must not mutate capability fields; treat get_capability() return
    as read-only.
    """

    name: str
    system_prompt_supplement: str
    file_structure_guidance: str
    example_structure: str
    expected_extensions: tuple[str, ...]
    test_framework: str
    test_prompt_supplement: str
    source_filter: tuple[str, ...]
    test_file_patterns: tuple[str, ...]
    max_completion_tokens: int = 4000
    test_timeout_seconds: int = 60
    # Config/entry files (by basename) needed to *build/test* the deliverable but
    # excluded by ``source_filter`` (e.g. package.json, vite.config.js, index.html).
    # Materialized into the QA build/test workspace so the frontend build check
    # (#290) and vitest actually run instead of skipping on "no package.json" (#296).
    build_support_files: tuple[str, ...] = ()
    #: The managed asset carrying this stack's fill-only instruction — which files hold
    #: the slots, and what the scaffold-owned seams mean. Per stack because the answer
    #: IS the stack: one asset served both, so a `nextjs_ts` author was told to fill
    #: `backend/routes.py` and `frontend/src/views/*.jsx` and that `apiFetch` "prefixes
    #: `/api`" — none of which exist here. It wrote `api('/runs')` against a helper that
    #: prefixes nothing, and every UI call 404'd in a deliverable that passed every gate
    #: (SIP-0104 window roll 1, cyc_04d36309d793, measured 2026-08-15).
    #:
    #: Empty means NO fill-only appendix rather than another stack's — wrong guidance is
    #: worse than none (#818's asymmetric-default rule; this defect is the proof).
    fill_only_template: str = ""


# ---------------------------------------------------------------------------
# V1 capability registry
# ---------------------------------------------------------------------------

DEV_CAPABILITIES: dict[str, DevelopmentCapability] = {
    # ── python_cli ────────────────────────────────────────────────────────
    # Reproduces current hardcoded behavior exactly (D2).
    "python_cli": DevelopmentCapability(
        name="python_cli",
        system_prompt_supplement=(
            "You are generating source code as a Python package. "
            "Emit each file as a fenced code block: ```<lang>:<path>\n"
            "Use relative imports within the package (from .module import X). "
            "Paths must be clean relative paths with no colons or spaces."
        ),
        file_structure_guidance=(
            "\n\nGenerate complete, runnable source files as a Python package. "
            "Use tagged fenced code blocks with the language and path "
            "separated by a colon, for example:\n"
            "```python:my_project/main.py\n<content>\n```\n\n"
            "IMPORTANT rules for file paths and imports:\n"
            "- Use the project name as the top-level package directory "
            "(e.g., play_game/main.py, play_game/board.py).\n"
            "- Always include a __init__.py for the package.\n"
            "- Use RELATIVE imports within the package "
            "(e.g., `from .board import Board`, NOT `from board import Board`).\n"
            "- File paths must use forward slashes, no colons, no spaces.\n"
            "- Include a requirements.txt at the project root if external "
            "dependencies are needed.\n"
            "- The main entry point should be runnable via "
            "`python -m <package_name>` (use __main__.py) or as a script.\n\n"
            "Example of a correctly structured package:\n"
            "```python:my_app/__init__.py\n```\n"
            "```python:my_app/__main__.py\n"
            "from .main import main\n"
            "if __name__ == '__main__':\n"
            "    main()\n```\n"
            "```python:my_app/main.py\n"
            "import random\n"
            "from .board import Board\n```\n\n"
            "Before emitting each file, verify:\n"
            "- All stdlib and third-party imports are present (import random, etc.)\n"
            "- All intra-package imports use relative form (from .module import X)\n"
            "- __main__.py uses relative imports, not absolute"
        ),
        example_structure=(
            "<package_name>/\n"
            "  __init__.py\n"
            "  __main__.py\n"
            "  main.py\n"
            "  <module>.py\n"
            "requirements.txt"
        ),
        expected_extensions=(".py",),
        test_framework=TEST_FRAMEWORK_PYTEST,
        test_prompt_supplement=(
            "You are generating pytest test files. "
            "Emit each file as a fenced code block: ```python:<path>\n"
            "Paths must be clean relative paths like tests/test_module.py — "
            "no colons, no spaces, no extra metadata after the path."
        ),
        source_filter=(".py",),
        test_file_patterns=("test_*.py", "*_test.py"),
        # max_completion_tokens=4000 (default)
        # test_timeout_seconds=60 (default)
    ),
    # ── python_api ────────────────────────────────────────────────────────
    # FastAPI-specific guidance replacing CLI packaging conventions.
    "python_api": DevelopmentCapability(
        name="python_api",
        system_prompt_supplement=(
            "You are generating source code for a FastAPI web application. "
            "Emit each file as a fenced code block: ```<lang>:<path>\n"
            "Paths must be clean relative paths with no colons or spaces."
        ),
        file_structure_guidance=(
            "\n\nGenerate complete, runnable source files for a FastAPI application. "
            "Use tagged fenced code blocks with the language and path "
            "separated by a colon, for example:\n"
            "```python:my_api/main.py\n<content>\n```\n\n"
            "IMPORTANT rules for file paths and imports:\n"
            "- Use a flat or shallow directory structure rooted at the project name "
            "(e.g., my_api/main.py, my_api/models.py, my_api/routes.py).\n"
            "- The main entry point should be in main.py with `app = FastAPI()`.\n"
            "- Start the server with `uvicorn main:app` or "
            "`uvicorn <package>.main:app`.\n"
            "- File paths must use forward slashes, no colons, no spaces.\n"
            "- Include a requirements.txt listing fastapi, uvicorn, and any "
            "other dependencies.\n"
            "- Use standard Python imports (absolute or relative as appropriate).\n\n"
            "Before emitting each file, verify:\n"
            "- All stdlib and third-party imports are present\n"
            "- FastAPI route decorators use correct HTTP methods\n"
            "- requirements.txt includes all dependencies"
        ),
        example_structure=(
            "<project_name>/\n  main.py\n  models.py\n  routes.py\nrequirements.txt"
        ),
        expected_extensions=(".py",),
        test_framework=TEST_FRAMEWORK_PYTEST,
        test_prompt_supplement=(
            "You are generating pytest test files for a FastAPI application. "
            "Use httpx.AsyncClient or fastapi.testclient.TestClient for endpoint tests. "
            "Emit each file as a fenced code block: ```python:<path>\n"
            "Paths must be clean relative paths like tests/test_api.py — "
            "no colons, no spaces, no extra metadata after the path."
        ),
        source_filter=(".py",),
        test_file_patterns=("test_*.py", "*_test.py"),
        max_completion_tokens=6000,
    ),
    # ── react_app ─────────────────────────────────────────────────────────
    "react_app": DevelopmentCapability(
        name="react_app",
        system_prompt_supplement=(
            "You are generating source code for a React application using Vite. "
            "Emit each file as a fenced code block: ```<lang>:<path>\n"
            "Paths must be clean relative paths with no colons or spaces."
        ),
        file_structure_guidance=(
            "\n\nGenerate complete, runnable source files for a React (Vite) application. "
            "Use tagged fenced code blocks with the language and path "
            "separated by a colon, for example:\n"
            "```javascript:src/App.jsx\n<content>\n```\n\n"
            "IMPORTANT rules for file paths and imports:\n"
            "- Use ES module imports (import/export), not CommonJS (require).\n"
            "- Include package.json with react, react-dom, vite, and "
            "@vitejs/plugin-react as dependencies.\n"
            "- Include vite.config.js with the React plugin.\n"
            "- Include index.html as the Vite entry HTML.\n"
            "- Place source files under src/ (e.g., src/main.jsx, src/App.jsx).\n"
            "- File paths must use forward slashes, no colons, no spaces.\n"
            "- Use .jsx extension for files containing JSX.\n\n"
            "Before emitting each file, verify:\n"
            "- All imports reference correct relative paths\n"
            "- package.json includes all required dependencies\n"
            "- vite.config.js imports and uses @vitejs/plugin-react"
        ),
        example_structure=("index.html\npackage.json\nvite.config.js\nsrc/\n  main.jsx\n  App.jsx"),
        expected_extensions=(".js", ".jsx", ".html", ".css"),
        test_framework=TEST_FRAMEWORK_VITEST,
        test_prompt_supplement=(
            "You are generating vitest test files for a React application. "
            "Use @testing-library/react for component tests. "
            "Emit each file as a fenced code block: ```javascript:<path>\n"
            "Paths must be clean relative paths like src/__tests__/App.test.jsx — "
            "no colons, no spaces, no extra metadata after the path."
        ),
        source_filter=(".js", ".jsx"),
        test_file_patterns=(
            "*.test.js",
            "*.test.jsx",
            "*.spec.js",
            "*.spec.jsx",
        ),
        build_support_files=(
            "package.json",
            "vite.config.js",
            "vite.config.ts",
            "index.html",
            "tsconfig.json",
            "tsconfig.node.json",
        ),
        max_completion_tokens=8000,
        test_timeout_seconds=120,
    ),
    # ── fullstack_fastapi_react ───────────────────────────────────────────
    "fullstack_fastapi_react": DevelopmentCapability(
        name="fullstack_fastapi_react",
        system_prompt_supplement=(
            "You are generating source code for a fullstack application with a "
            "FastAPI backend and a React (Vite) frontend. "
            "Emit each file as a fenced code block with the language and path "
            "separated by a colon. Examples:\n"
            "```python:backend/main.py\n"
            "```javascript:frontend/src/App.jsx\n\n"
            "All backend files go under backend/, all frontend files under frontend/. "
            "Paths must be clean relative paths with no colons in the path or spaces."
        ),
        file_structure_guidance=(
            "\n\nGenerate complete, runnable source files for a fullstack application "
            "with a FastAPI backend and a React (Vite) frontend. "
            "Use tagged fenced code blocks with the language and path "
            "separated by a colon, for example:\n"
            "```python:backend/main.py\n<content>\n```\n"
            "```javascript:frontend/src/App.jsx\n<content>\n```\n\n"
            "IMPORTANT rules for file paths and imports:\n\n"
            "### Backend (backend/)\n"
            "- The FastAPI app lives in backend/main.py with `app = FastAPI()`.\n"
            "- Start with `cd backend && uvicorn main:app --port 8000`.\n"
            "- Include backend/requirements.txt listing fastapi, uvicorn, and any "
            "other dependencies.\n"
            "- Configure CORS origins from configuration, NOT hardcoded: read an "
            "env var (e.g. `CORS_ORIGINS`, comma-separated) with a dev default of "
            "`http://localhost:5173`. Never bake a single origin as the only allowed "
            "one — that breaks the moment the app is served over LAN/tailnet.\n\n"
            "### Frontend (frontend/)\n"
            "- Use ES module imports (import/export), not CommonJS (require).\n"
            "- Include frontend/package.json with react, react-dom, vite, and "
            "@vitejs/plugin-react as dependencies.\n"
            "- Include frontend/vite.config.js with the React plugin.\n"
            "- Include frontend/index.html as the Vite entry HTML.\n"
            "- Do NOT hardcode the backend URL. Read the API base from "
            "`import.meta.env.VITE_API_BASE` with a RELATIVE default of `/api` "
            "(e.g. `const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'`).\n"
            "- In frontend/vite.config.js add a dev `server.proxy` mapping `/api` "
            "to the backend, e.g. `server: { proxy: { '/api': 'http://localhost:8000' } }`, "
            "so the relative `/api` base is same-origin in dev (no CORS needed).\n"
            "- Place source files under frontend/src/ "
            "(e.g., frontend/src/main.jsx, frontend/src/App.jsx).\n"
            "- Use .jsx extension for files containing JSX.\n\n"
            "### General\n"
            "- File paths must use forward slashes, no colons, no spaces.\n"
            "- All paths are relative to the project root.\n\n"
            "### Portable integration (NON-NEGOTIABLE)\n"
            "The app must run unchanged on localhost AND when served from another "
            "host (LAN/tailnet) with no source edits. Achieve this with: a relative "
            "`/api` API base (env-overridable via `VITE_API_BASE`), a Vite dev proxy "
            "for `/api`, and config-driven backend CORS. Never hardcode "
            "`http://localhost:8000` in the frontend or a single CORS origin in the backend.\n\n"
            "Before emitting each file, verify:\n"
            "- Backend: all imports present, CORS origins config-driven (not a single "
            "hardcoded origin), requirements.txt complete\n"
            "- Frontend: API base is relative/env-driven (no hardcoded "
            "http://localhost:8000), vite.config.js has the `/api` dev proxy, all "
            "imports reference correct paths, package.json complete\n"
            "- No cross-stack imports (frontend does not import from backend or vice versa)"
        ),
        example_structure=(
            "backend/\n"
            "  main.py\n"
            "  requirements.txt\n"
            "frontend/\n"
            "  index.html\n"
            "  package.json\n"
            "  vite.config.js\n"
            "  src/\n"
            "    main.jsx\n"
            "    App.jsx"
        ),
        expected_extensions=(".py", ".js", ".jsx", ".html", ".css"),
        test_framework=TEST_FRAMEWORK_BOTH,
        test_prompt_supplement=(
            "You are generating test files for a fullstack application.\n\n"
            "For backend (Python/FastAPI): generate pytest test files. "
            "Use httpx.AsyncClient or fastapi.testclient.TestClient for endpoint tests. "
            "Place tests in backend/tests/ (e.g., backend/tests/test_api.py).\n\n"
            "For frontend (React/Vite): generate vitest test files ONLY if "
            "`vitest` appears in the frontend package.json devDependencies. "
            "Use component-test libraries (e.g. @testing-library/react) ONLY "
            "if they are already declared there — NEVER import a package the "
            "manifest does not ship (#448: suites that fail to load fail the "
            "whole tests_pass check). If no frontend test runner is declared, "
            "generate no frontend test files — the frontend build check covers "
            "compile-level integrity. When generated, place tests in "
            "frontend/src/__tests__/ (e.g., frontend/src/__tests__/App.test.jsx).\n\n"
            "Emit each file as a fenced code block with the language and path "
            "separated by a colon. Examples:\n"
            "```python:backend/tests/test_api.py\n"
            "```javascript:frontend/src/__tests__/App.test.jsx\n\n"
            "Paths must be clean relative paths — no colons in the path, "
            "no spaces, no extra metadata after the path."
        ),
        source_filter=(".py", ".js", ".jsx"),
        test_file_patterns=(
            "test_*.py",
            "*_test.py",
            "*.test.js",
            "*.test.jsx",
            "*.spec.js",
            "*.spec.jsx",
        ),
        build_support_files=(
            "package.json",
            "vite.config.js",
            "vite.config.ts",
            "index.html",
            "tsconfig.json",
            "tsconfig.node.json",
        ),
        max_completion_tokens=12000,
        test_timeout_seconds=180,
        fill_only_template="request.development_develop_fill_only_appendix",
    ),
    # #822 stack #2. Bound to the scaffold stack of the same name by
    # ``ScaffoldStack.dev_capability`` (#832), so the two registries can no longer disagree
    # about which stack a cycle is building.
    "nextjs_ts": DevelopmentCapability(
        name="nextjs_ts",
        system_prompt_supplement=(
            "You are generating source code for a Next.js (App Router) application in "
            "TypeScript. One project at the repository root — there is no separate backend "
            "or frontend tree.\n"
            "Emit each file as a fenced code block with the language and path separated by "
            "a colon. Examples:\n"
            "```typescript:app/api/runs/route.ts\n"
            "```tsx:app/runs/page.tsx\n\n"
            "Paths must be clean relative paths with no colons in the path or spaces."
        ),
        file_structure_guidance=(
            "\n\nGenerate complete, runnable source for a Next.js App Router application in "
            "TypeScript.\n\n"
            "### Routing\n"
            "- Server endpoints are ROUTE HANDLERS at app/api/<path>/route.ts, exporting one "
            "async function per HTTP method (`export async function GET(request: Request)`).\n"
            "- Do NOT use server actions for endpoints the design declares: they have no "
            "stable URL, so nothing can address them over HTTP.\n"
            "- A path parameter is a DIRECTORY in brackets: `/runs/{run_id}` is "
            "app/api/runs/[run_id]/route.ts. Read it from the second handler argument, "
            "`{ params }`.\n"
            "- Pages are app/<path>/page.tsx with a default-exported component. The URL comes "
            "from the directory; the filename is always page.tsx.\n\n"
            "### Conventions\n"
            "- Server-first. Add `'use client'` only to a component that genuinely needs "
            "browser interactivity — anything rendered on the client is absent from the "
            "initial HTML.\n"
            "- Import through the `@/` alias (`@/lib/store`), not long relative chains.\n"
            "- Return errors through the scaffold-owned envelope in lib/errors.ts. Never "
            "invent a second error shape.\n"
            "- Every declared testid must appear as a `data-testid` attribute on the element "
            "it names.\n"
            "- TypeScript is strict and `next build` fails on type errors; it is the only "
            "static check this stack has.\n\n"
            "### General\n"
            "- Forward slashes, no colons, no spaces; paths relative to the project root."
        ),
        example_structure=(
            "package.json\n"
            "tsconfig.json\n"
            "app/\n"
            "  layout.tsx\n"
            "  page.tsx\n"
            "  api/\n"
            "    runs/\n"
            "      route.ts\n"
            "lib/\n"
            "  models.ts\n"
            "  store.ts"
        ),
        expected_extensions=(".ts", ".tsx", ".json", ".css"),
        test_framework=TEST_FRAMEWORK_VITEST,
        test_prompt_supplement=(
            "You are generating vitest test files for a Next.js TypeScript application.\n\n"
            "EXECUTION MODEL (#877): the suite runs with `vitest run` in a plain Node "
            "process. NO server is running and none can be started — a test that calls "
            "`fetch` against localhost or any live URL fails unconditionally. Route "
            "handlers are plain exported functions: import them and invoke them directly "
            "with a `Request`, then assert on the returned `Response`. Example:\n"
            "```typescript\n"
            "import { POST } from '@/app/api/runs/route'\n"
            "const res = await POST(\n"
            "  new Request('http://test/api/runs', {\n"
            "    method: 'POST',\n"
            "    headers: { 'content-type': 'application/json' },\n"
            "    body: JSON.stringify({ name: 'x' }),\n"
            "  })\n"
            ")\n"
            "expect(res.status).toBe(201)\n"
            "```\n"
            "For a parameterized route, pass the params argument the handler signature "
            "declares: `GET(request, { params: { run_id: 'r1' } })`.\n\n"
            "Import ONLY packages the shipped package.json declares — a suite that fails to "
            "load fails the whole tests_pass check (#448).\n"
            "Consume the scaffold-owned store seam (`reset`, `insert`, `all` from "
            "@/lib/store) rather than reaching into the app entry.\n"
            "Place tests in __tests__/ with a .test.ts suffix, e.g. "
            "__tests__/runs.test.ts.\n\n"
            "Emit each file as a fenced code block with the language and path separated by a "
            "colon:\n"
            "```typescript:__tests__/runs.test.ts\n\n"
            "Paths must be clean relative paths — no colons, no spaces."
        ),
        source_filter=(".ts", ".tsx"),
        test_file_patterns=("*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx"),
        build_support_files=(
            "package.json",
            "tsconfig.json",
            "next.config.mjs",
            "vitest.config.ts",
        ),
        max_completion_tokens=12000,
        test_timeout_seconds=180,
        fill_only_template="request.development_develop_fill_only_appendix_nextjs_ts",
    ),
}


def get_capability(name: str) -> DevelopmentCapability:
    """Resolve development capability by name.

    Args:
        name: Capability name to look up.

    Returns:
        The matching DevelopmentCapability.

    Raises:
        ValueError: If name is not a registered capability.
    """
    capability = DEV_CAPABILITIES.get(name)
    if capability is None:
        available = sorted(DEV_CAPABILITIES.keys())
        raise ValueError(
            f"Unknown development capability {name!r}. Available capabilities: {available}"
        )
    return capability


#: What a cycle that names no capability gets: free-form Python generation, the
#: pre-SIP-0072 behavior. Named because the literal was written out at six call sites
#: as ``resolve_dev_capability(cfg) or "python_cli"`` (#846).
DEFAULT_DEV_CAPABILITY = "python_cli"


def effective_capability_name(resolved_config: Mapping[str, Any] | None) -> str:
    """The capability a cycle actually runs under, defaulted.

    ``scaffold.resolve_dev_capability`` answers "what does this config *declare*", and
    returns ``None`` for a contradiction so preflight can reject rather than silently pick
    a side. This wraps it with the fallback every consumer applied by hand, so "which
    capability is in force" has one answer instead of six copies of one expression.

    A contradiction resolves to the default here rather than raising: the callers are
    validators and prompt builders that must not crash on a config preflight already
    refuses, and picking the conservative Python capability is what they did before.
    """
    from squadops.capabilities.scaffold import resolve_dev_capability

    return resolve_dev_capability(resolved_config) or DEFAULT_DEV_CAPABILITY


def matches_test_file_patterns(path: str, patterns: tuple[str, ...]) -> bool:
    """True when ``path``'s basename matches any of the stack's test-file conventions.

    Basename globbing only — deliberately narrower than
    ``handlers.cycle.validation._is_test_file``, which additionally treats anything under
    ``__tests__/`` as a test file. That generosity is right for *excluding* files from a
    source set, and wrong for asking "will the runner discover this?": ``__tests__/
    helpers.py`` is not collected by pytest, and counting it would weaken #715's guard for
    Python stacks. One matcher, two callers, each with its own answer about directories.
    """
    from fnmatch import fnmatch
    from pathlib import PurePosixPath

    name = PurePosixPath(path).name
    return any(fnmatch(name, pat) for pat in patterns)


def test_file_patterns_for(resolved_config: Mapping[str, Any] | None) -> tuple[str, ...]:
    """The test-file conventions a cycle's stack actually uses (#846).

    ``pytest``'s ``test_*.py``/``*_test.py`` was hardcoded into plan validation, so a
    correct vitest suite (``__tests__/store.test.ts``) was rejected for containing no
    pytest-discoverable file — and the remedy the error suggested, "include a test_*.py",
    would have been wrong. The stack has always declared this; nothing asked it.
    """
    return get_capability(effective_capability_name(resolved_config)).test_file_patterns

"""Development capability registry (SIP-0072).

Typed development capabilities that control handler behavior: prompt
supplements, file structure guidance, source filtering, and test framework
selection.  V1 capabilities are code-defined frozen dataclass instances.

Mirrors the BuildProfile registry pattern in build_profiles.py.
"""
from __future__ import annotations

from dataclasses import dataclass


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
            "<project_name>/\n"
            "  main.py\n"
            "  models.py\n"
            "  routes.py\n"
            "requirements.txt"
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
        example_structure=(
            "index.html\n"
            "package.json\n"
            "vite.config.js\n"
            "src/\n"
            "  main.jsx\n"
            "  App.jsx"
        ),
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
            "*.test.js", "*.test.jsx", "*.spec.js", "*.spec.jsx",
        ),
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
            "- Configure CORS to allow requests from http://localhost:5173 "
            "(Vite dev server default).\n\n"
            "### Frontend (frontend/)\n"
            "- Use ES module imports (import/export), not CommonJS (require).\n"
            "- Include frontend/package.json with react, react-dom, vite, and "
            "@vitejs/plugin-react as dependencies.\n"
            "- Include frontend/vite.config.js with the React plugin.\n"
            "- Include frontend/index.html as the Vite entry HTML.\n"
            "- Place source files under frontend/src/ "
            "(e.g., frontend/src/main.jsx, frontend/src/App.jsx).\n"
            "- Use .jsx extension for files containing JSX.\n\n"
            "### General\n"
            "- File paths must use forward slashes, no colons, no spaces.\n"
            "- All paths are relative to the project root.\n\n"
            "Before emitting each file, verify:\n"
            "- Backend: all imports present, CORS configured, requirements.txt complete\n"
            "- Frontend: all imports reference correct paths, package.json complete\n"
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
            "For frontend (React/Vite): generate vitest test files. "
            "Use @testing-library/react for component tests. "
            "Place tests in frontend/src/__tests__/ "
            "(e.g., frontend/src/__tests__/App.test.jsx).\n\n"
            "Emit each file as a fenced code block with the language and path "
            "separated by a colon. Examples:\n"
            "```python:backend/tests/test_api.py\n"
            "```javascript:frontend/src/__tests__/App.test.jsx\n\n"
            "Paths must be clean relative paths — no colons in the path, "
            "no spaces, no extra metadata after the path."
        ),
        source_filter=(".py", ".js", ".jsx"),
        test_file_patterns=(
            "test_*.py", "*_test.py",
            "*.test.js", "*.test.jsx", "*.spec.js", "*.spec.jsx",
        ),
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
            f"Unknown development capability {name!r}. "
            f"Available capabilities: {available}"
        )
    return capability

"""The tree a sample application's ``qa.test`` suite runs against, characterized before #2815.

#2815 gives a repository-backed product's suite the product's tree (``qa_run_tree``). A sample
application's suite keeps the tree it has always had: the stack's source and build-support files
(``qa_prompt_contents.source_files``). That half is a no-change, and these cases pin it.

Each case drives the real ``handle()`` of ``qa.test`` on one stack's development profile, on the
focused path, the monolithic path and the execute-only retest, over one invented workspace that
holds every kind of file a stack's filter decides on: source by each extension, build-support files,
tests by each stack's patterns, ``__tests__/`` helpers, ``conftest.py``, data, config and documents.
What reaches the suite runner (``run_build_validation``) and the lint reading, path and content,
is compared with a golden captured from the code before #2815 (``origin/main`` at ``6b9ee472``).

Bug caught: the product's run tree reaching a sample application, by a marker read wrongly or a
selection widened for every cycle: a data file, a document or a test materialized beside a sample
application's suite, or a source file dropped from it, on any stack or path.

Regenerate (only for a DELIBERATE behaviour change, in the PR that makes it):
    UPDATE_RUN_TREE_GOLDENS=1 pytest tests/unit/capabilities/handlers/test_sample_run_tree_characterization.py
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.llm.models import ChatMessage

pytestmark = [pytest.mark.domain_capabilities]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "sample_run_tree_characterization.json"

_STACKS = ("python_cli", "python_api", "react_app", "fullstack_fastapi_react", "nextjs_ts")
_PATHS = ("focused", "monolithic", "retest")

#: One invented workspace, every kind of file a stack's filter decides on.
_WORKSPACE = {
    "lantern/__init__.py": "",
    "lantern/main.py": "def start():\n    return 'lit'\n",
    "lantern/store.py": "ROWS: list[str] = []\n",
    "tests/__init__.py": "",
    "tests/conftest.py": "import pytest\n",
    "tests/test_lantern.py": "def test_start():\n    assert True\n",
    "tests/lantern_test.py": "def test_store():\n    assert True\n",
    "tests/fixtures/rows.json": '["a", "b"]\n',
    "__tests__/helpers.py": "def helper():\n    return 1\n",
    "frontend/package.json": '{"name": "lantern-ui"}\n',
    "frontend/vite.config.js": "export default {};\n",
    "frontend/vite.config.ts": "export default {};\n",
    "frontend/index.html": "<div id='root'></div>\n",
    "frontend/tsconfig.json": "{}\n",
    "frontend/tsconfig.node.json": "{}\n",
    "frontend/src/index.css": "body { margin: 0; }\n",
    "frontend/src/theme.css": ".lit { color: gold; }\n",
    "frontend/src/App.jsx": "export const App = () => null;\n",
    "frontend/src/App.test.jsx": "test('app', () => {});\n",
    "frontend/src/App.spec.js": "test('spec', () => {});\n",
    "frontend/src/main.tsx": "export const main = 1;\n",
    "frontend/src/view.test.ts": "test('view', () => {});\n",
    "frontend/src/__tests__/render.jsx": "export const render = () => null;\n",
    "app/page.tsx": "export default function Page() { return null; }\n",
    "app/globals.css": "html { color: black; }\n",
    "lib/api.ts": "export const api = (p: string) => p;\n",
    "__tests__/page.test.tsx": "test('page', () => {});\n",
    "next.config.mjs": "export default {};\n",
    "vitest.config.ts": "export default {};\n",
    "scripts/build.mjs": "console.log('built');\n",
    "plugins/clock/manifest.toml": 'id = "clock"\ntitle = "Clock"\n',
    "config/settings.yaml": "lamps: 3\n",
    "requirements.txt": "fastapi\n",
    "pyproject.toml": '[project]\nname = "lantern"\n',
    "README.md": "# Lantern\n",
    "plans/validation_plan.md": "Check that the lantern starts.\n",
}

_SUITE_PATH = "tests/test_probe.py"
_SUITE = "def test_probe():\n    assert True\n"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _inputs(stack: str, path: str) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "prd": "Lantern lights lamps.",
        "resolved_config": {"development_profile": stack},
        "artifact_contents": dict(_WORKSPACE),
        "acceptance_workspace_files": dict(_WORKSPACE),
    }
    if path in ("focused", "retest"):
        inputs |= {"subtask_focus": "the lantern suite", "expected_artifacts": [_SUITE_PATH]}
    if path == "retest":
        inputs["retest_files"] = [{"filename": _SUITE_PATH, "content": _SUITE}]
    return inputs


def _context() -> MagicMock:
    ctx = MagicMock()
    assembled = MagicMock()
    assembled.content = "System prompt"
    assembled.assembly_hash = "sha256:test"
    ctx.ports.prompt_service.get_system_prompt.return_value = assembled
    ctx.ports.prompt_service.assemble.return_value = assembled
    ctx.ports.request_renderer = None
    ctx.ports.llm.default_model = "test-model"

    async def _answer(messages, **kwargs):
        return ChatMessage(
            role="assistant",
            content=f"```python:{_SUITE_PATH}\n{_SUITE}```\n",
            prompt_tokens=11,
            completion_tokens=7,
        )

    ctx.ports.llm.chat_stream_with_usage = _answer
    ctx.correlation_context = None
    ctx.disputed_checks = []
    return ctx


async def _observed(stack: str, path: str, monkeypatch) -> dict[str, Any]:
    """What reached the suite runner and the lint reading on ``stack``'s ``path``."""
    ran_on: list[list[list[str]]] = []
    linted: list[list[list[str]]] = []

    async def _runner(framework, sources, tests, timeout_seconds=None):
        ran_on.append([[s["path"], _sha(s["content"])] for s in sources])
        return RunTestsResult(executed=True, exit_code=0, stdout="1 passed", runner="pytest")

    def _lint(tree):
        linted.append([[p, _sha(str(c))] for p, c in tree.items()])
        return {"version": 1}

    monkeypatch.setattr(
        "squadops.capabilities.handlers.cycle.qa_test.run_build_validation", _runner
    )
    monkeypatch.setattr("squadops.capabilities.handlers.cycle.qa_test.lint_delivered", _lint)

    result = await QATestHandler().handle(_context(), _inputs(stack, path))

    assert result.success, result.error
    return {"suite_sources": ran_on, "lint_tree": linted}


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("stack", _STACKS)
async def test_a_sample_applications_suite_runs_on_the_tree_it_ran_on_before_2815(
    stack, path, monkeypatch
):
    """Entered at ``QATestHandler.handle``, the live caller, on each stack and path."""
    observed = await _observed(stack, path, monkeypatch)
    key = f"{stack}/{path}"

    if os.environ.get("UPDATE_RUN_TREE_GOLDENS"):
        golden = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else {}
        golden[key] = observed
        _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN_PATH.write_text(json.dumps(golden, indent=1, sort_keys=True) + "\n")
        pytest.skip("golden regenerated")

    assert observed == json.loads(_GOLDEN_PATH.read_text())[key]


def test_the_golden_holds_no_file_a_sample_application_never_ran_on():
    """Guards the golden itself, in case a regeneration captured the product's tree: on no stack
    did a sample application's suite run beside a document, a data file or another suite.
    Bug caught: a golden regenerated after a regression, which would then pin the regression."""
    golden = json.loads(_GOLDEN_PATH.read_text())
    never = {
        "README.md",
        "plans/validation_plan.md",
        "plugins/clock/manifest.toml",
        "config/settings.yaml",
        "tests/fixtures/rows.json",
        "tests/test_lantern.py",
        "tests/lantern_test.py",
    }

    assert set(golden) == {f"{s}/{p}" for s in _STACKS for p in _PATHS}
    for key, observed in golden.items():
        [ran_on] = observed["suite_sources"]
        assert never.isdisjoint(p for p, _sha in ran_on), key
        assert ran_on, key

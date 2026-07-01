"""QA source-artifact materialization incl. build-support files (#296).

Bug this guards: package.json / index.html / vite.config.js were excluded from
the QA build/test workspace (``source_filter`` is only .py/.js/.jsx), so the
frontend build check (#290) and vitest skipped on "no package.json" and a
non-runnable frontend shipped undetected (cyc_8617e0975ed5).
"""

from __future__ import annotations

import pytest

from squadops.capabilities.dev_capabilities import (
    DEV_CAPABILITIES,
    TEST_FRAMEWORK_BOTH,
    TEST_FRAMEWORK_VITEST,
    get_capability,
)
from squadops.capabilities.handlers.cycle_tasks import QATestHandler

pytestmark = [pytest.mark.domain_capabilities]

_CONTENTS = {
    "backend/main.py": "app = 1",
    "frontend/src/main.jsx": "import App from './App'",
    "frontend/package.json": "{}",
    "frontend/vite.config.js": "export default {}",
    "frontend/index.html": "<div id='root'></div>",
    "frontend/tsconfig.json": "{}",
    "backend/tests/test_api.py": "def test_x(): pass",  # test file -> excluded
    "frontend/src/__tests__/App.test.jsx": "test('a', () => {})",  # test file -> excluded
    "qa_handoff.md": "# doc",  # non-source doc -> excluded
}


def _inputs(dev_capability: str) -> dict:
    return {
        "resolved_config": {"dev_capability": dev_capability},
        "artifact_contents": dict(_CONTENTS),
    }


class TestSourceArtifactMaterialization:
    def test_build_support_files_materialized(self):
        sources = QATestHandler()._get_source_artifacts(_inputs("fullstack_fastapi_react"))
        for f in (
            "frontend/package.json",
            "frontend/vite.config.js",
            "frontend/index.html",
            "frontend/tsconfig.json",
        ):
            assert f in sources, f"{f} must be materialized so the build check can run (#296)"

    def test_source_files_still_included(self):
        sources = QATestHandler()._get_source_artifacts(_inputs("fullstack_fastapi_react"))
        assert "backend/main.py" in sources
        assert "frontend/src/main.jsx" in sources

    def test_test_and_doc_files_excluded(self):
        sources = QATestHandler()._get_source_artifacts(_inputs("fullstack_fastapi_react"))
        assert "backend/tests/test_api.py" not in sources
        assert "frontend/src/__tests__/App.test.jsx" not in sources
        assert "qa_handoff.md" not in sources

    def test_backend_only_capability_has_no_frontend_support(self):
        """A python-only capability shouldn't drag in frontend config files."""
        sources = QATestHandler()._get_source_artifacts(_inputs("python_cli"))
        assert "backend/main.py" in sources
        assert "frontend/package.json" not in sources


def test_frontend_capabilities_declare_build_support():
    """Every frontend-bearing capability must list the files needed to build,
    else #290/vitest silently skip on "no package.json"."""
    frontend_caps = [
        c
        for c in DEV_CAPABILITIES.values()
        if c.test_framework in (TEST_FRAMEWORK_VITEST, TEST_FRAMEWORK_BOTH)
    ]
    assert frontend_caps, "expected at least one vitest/both capability"
    for cap in frontend_caps:
        assert "package.json" in cap.build_support_files, f"{cap.name} missing package.json"
        assert "index.html" in cap.build_support_files, f"{cap.name} missing index.html"


def test_get_capability_default_build_support_empty():
    """Non-frontend capabilities default to no build-support files."""
    assert get_capability("python_cli").build_support_files == ()

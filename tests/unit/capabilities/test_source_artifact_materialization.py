"""QA source-artifact materialization incl. build-support files (#296).

Bug this guards: package.json / index.html / vite.config.js were excluded from
the QA build/test workspace (``source_filter`` is only .py/.js/.jsx), so the
frontend build check (#290) and vitest skipped on "no package.json" and a
non-runnable frontend shipped undetected (cyc_8617e0975ed5).
"""

from __future__ import annotations

import pytest

from squadops.capabilities.development_profiles import (
    DEVELOPMENT_PROFILES,
    TEST_FRAMEWORK_BOTH,
    TEST_FRAMEWORK_VITEST,
    get_development_profile,
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


def _inputs(development_profile: str) -> dict:
    return {
        "resolved_config": {"development_profile": development_profile},
        "artifact_contents": dict(_CONTENTS),
    }


_NEXTJS_CONTENTS = {
    "app/api/runs/route.ts": "export async function GET() { return Response.json([]) }",
    "app/page.tsx": "export default function Page() { return null }",
    "package.json": "{}",
    "__tests__/runs.test.ts": "it('lists runs', () => {})",
    # Named like source, imported by the suites, matching no *.test.ts pattern — the file
    # #1539 is about.
    "__tests__/helpers.ts": "export const seedRun = () => ({ id: 'r1' })",
}


def _nextjs_inputs() -> dict:
    return {
        "resolved_config": {"development_profile": "nextjs_ts"},
        "artifact_contents": dict(_NEXTJS_CONTENTS),
    }


class TestRootLevelTestsDirectoryIsNotQaSource:
    """#1539, entering at the caller the live cycle uses (``_get_source_artifacts``).

    Bug this guards: the exclusion tested ``"/__tests__/" in path``, which no root-level path
    can satisfy. On the App Router stack every suite lives at the workspace root, so a helper
    module there was materialized into the qa author's source set — the author was shown its
    own harness as the application under test. Every root-level ``__tests__/`` file stored in
    the vault today happens to match the stack's ``*.test.ts`` patterns, so no stored run
    changes; this closes the gap the first non-suite helper would have fallen through.
    """

    def test_the_root_helper_is_excluded_and_the_application_is_not(self):
        sources = QATestHandler()._get_source_artifacts(_nextjs_inputs())
        assert set(sources) == {"app/api/runs/route.ts", "app/page.tsx", "package.json"}

    def test_a_source_file_whose_name_contains_the_token_is_still_source(self):
        inputs = _nextjs_inputs()
        inputs["artifact_contents"]["app/my__tests__util.ts"] = "export const x = 1"
        sources = QATestHandler()._get_source_artifacts(inputs)
        assert "app/my__tests__util.ts" in sources


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
        for c in DEVELOPMENT_PROFILES.values()
        if c.test_framework in (TEST_FRAMEWORK_VITEST, TEST_FRAMEWORK_BOTH)
    ]
    assert frontend_caps, "expected at least one vitest/both capability"
    for cap in frontend_caps:
        assert "package.json" in cap.build_support_files, f"{cap.name} missing package.json"
        # #822: `index.html` was asserted for every frontend capability. That is VITE's entry
        # point, not a property of frontends — Next.js generates its HTML and ships no
        # index.html, so requiring it would force a capability to declare a file its stack
        # does not have. The real invariant, and the one #290 was about, is package.json:
        # without it npm cannot resolve anything and vitest silently skips.
        assert cap.build_support_files, f"{cap.name} declares no build support files"


def test_get_capability_default_build_support_empty():
    """Non-frontend capabilities default to no build-support files."""
    assert get_development_profile("python_cli").build_support_files == ()
